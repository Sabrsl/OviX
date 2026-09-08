"""
Domain Enrichment Service for automatically populating domain_to_site_name.

This service orchestrates the process of:
1. Fetching category members from MediaWiki (with pagination)
2. Checking if articles were already analyzed (deduplication)
3. Getting Wikidata QIDs for new pages only
4. Retrieving official websites (P856) from Wikidata
5. Normalizing domains
6. Detecting duplicates and conflicts
7. Previewing and writing to case_normalization_data.yaml

Reuses existing components:
- WikipediaAPIClient for MediaWiki API calls
- WikidataClient for Wikidata API calls
- APIThrottler for rate limiting
- EventManager for progress updates
- Config API for atomic YAML writing
"""

import logging
import yaml
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from urllib.parse import urlparse
import threading
import time

from .wikipedia_api import WikipediaAPIClient
from .wikidata_client import WikidataClient
from .api_throttler import APIThrottler
from .event_manager import get_event_manager, EventType
from .config import load_config

logger = logging.getLogger(__name__)


class EnrichmentState(Enum):
    """States for the enrichment process."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class EntryStatus(Enum):
    """Status of a domain entry."""
    NEW = "new"
    ALREADY_PRESENT = "already_present"
    EQUIVALENT = "equivalent"
    CONFLICT = "conflict"
    REVIEW_REQUIRED = "review_required"
    ERROR = "error"


@dataclass
class CategoryConfig:
    """Configuration for a category to process."""
    wiki: str  # Language code (e.g., 'fr')
    category: str  # Category name
    priority: int  # Priority level (1-6)


@dataclass
class DomainEntry:
    """Represents a domain entry with its status."""
    domain: str
    site_name: str
    status: EntryStatus
    original_url: Optional[str] = None
    page_title: Optional[str] = None
    qid: Optional[str] = None
    conflict_reason: Optional[str] = None


@dataclass
class EnrichmentProgress:
    """Progress information for the enrichment process."""
    state: EnrichmentState = EnrichmentState.IDLE
    current_category: Optional[str] = None
    pages_analyzed: int = 0
    total_pages: int = 0
    skipped: int = 0  # Articles already analyzed and skipped
    p856_found: int = 0
    new_domains: int = 0
    already_present: int = 0
    conflicts: int = 0
    review_required: int = 0
    errors: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    recent_activity: List[str] = field(default_factory=list)

    def add_activity(self, activity: str):
        """Add an activity entry, keeping only the last 20."""
        self.recent_activity.append(activity)
        if len(self.recent_activity) > 20:
            self.recent_activity.pop(0)

    def copy(self) -> "EnrichmentProgress":
        """Return a shallow snapshot safe to hand out to callers."""
        return EnrichmentProgress(
            state=self.state,
            current_category=self.current_category,
            pages_analyzed=self.pages_analyzed,
            total_pages=self.total_pages,
            skipped=self.skipped,
            p856_found=self.p856_found,
            new_domains=self.new_domains,
            already_present=self.already_present,
            conflicts=self.conflicts,
            review_required=self.review_required,
            errors=self.errors,
            started_at=self.started_at,
            completed_at=self.completed_at,
            recent_activity=list(self.recent_activity),
        )


class DomainEnrichmentService:
    """
    Service for enriching domain_to_site_name from Wikidata.

    This service manages the entire enrichment process with:
    - State management (idle, running, paused, cancelled, etc.)
    - Progress tracking and event emission
    - Pause/resume/cancel functionality
    - Domain normalization and deduplication
    - Conflict detection
    - Preview before writing
    - Atomic YAML writing
    - Article analysis tracking to avoid reprocessing
    - Batch processing with pagination
    """

    CASE_NORMALIZATION_FILE = Path(__file__).parent.parent.parent.parent.parent.parent / "config" / "case_normalization_data.yaml"
    ANALYSIS_TRACKER_FILE = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "domain_enrichment_tracker.json"
    RESULTS_FILE = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "domain_enrichment_results.json"

    def __init__(
        self,
        wikipedia_client: Optional[WikipediaAPIClient] = None,
        wikidata_client: Optional[WikidataClient] = None,
        throttler: Optional[APIThrottler] = None,
    ):
        """
        Initialize the enrichment service.

        Args:
            wikipedia_client: Optional WikipediaAPIClient instance
            wikidata_client: Optional WikidataClient instance
            throttler: Optional APIThrottler instance
        """
        # Initialize clients if not provided
        if wikipedia_client is None:
            config = load_config()
            self.wikipedia_client = WikipediaAPIClient(language=config.wikipedia.lang)
        else:
            self.wikipedia_client = wikipedia_client

        if wikidata_client is None:
            self.wikidata_client = WikidataClient()
        else:
            self.wikidata_client = wikidata_client

        # Set throttler on clients
        if throttler:
            self.throttler = throttler
            self.wikipedia_client.set_throttler(throttler)
            self.wikidata_client.throttler = throttler
        else:
            # Create default throttler
            self.throttler = APIThrottler()
            self.wikipedia_client.set_throttler(self.throttler)
            self.wikidata_client.throttler = self.throttler

        self.event_manager = get_event_manager()

        # State management
        self._state = EnrichmentState.IDLE
        self._progress = EnrichmentProgress()
        self._pause_event = threading.Event()
        self._cancel_event = threading.Event()
        # Guards _state, _progress, _entries, _existing_domains and the
        # tracker/pagination dicts against concurrent read (status polling)
        # and write (worker thread) access.
        self._lock = threading.RLock()

        # Results storage
        self._entries: List[DomainEntry] = []
        self._existing_domains: Dict[str, str] = {}

        # Analysis tracking to avoid reprocessing
        self._analyzed_articles: Dict[str, dict] = {}
        self._load_analysis_tracker()

        # Pagination state for pause/resume
        self._pagination_state: Dict[str, Any] = {}
        self._load_pagination_state()

        # Load persisted results if available
        self._load_results()

        # Prevents a write_to_yaml() call from overlapping with another
        # write, or with a start_enrichment() that resets shared state.
        self._write_lock = threading.Lock()

        logger.info("DomainEnrichmentService initialized")

    def get_state(self) -> EnrichmentState:
        """Get current state."""
        with self._lock:
            return self._state

    def get_progress(self) -> EnrichmentProgress:
        """Get a thread-safe snapshot of the current progress."""
        with self._lock:
            return self._progress.copy()

    def _set_state(self, state: EnrichmentState):
        """Set state with thread safety."""
        with self._lock:
            self._state = state
            self._progress.state = state
            logger.info(f"Enrichment state changed to: {state.value}")

    def reset(self) -> None:
        """
        Reset the enrichment service to initial state.
        Clears all progress, results, and tracking data to allow a fresh start.
        """
        with self._lock:
            self._state = EnrichmentState.IDLE
            self._progress = EnrichmentProgress()
            self._entries = []
            self._existing_domains = {}
            self._analyzed_articles = {}
            self._pagination_state = {}
            logger.info("Enrichment service reset to initial state")

        # Clear tracker file
        try:
            if self.ANALYSIS_TRACKER_FILE.exists():
                self.ANALYSIS_TRACKER_FILE.unlink()
                logger.info("Cleared analysis tracker file")
        except Exception as e:
            logger.error(f"Error clearing analysis tracker: {e}")

        # Clear results file
        try:
            if self.RESULTS_FILE.exists():
                self.RESULTS_FILE.unlink()
                logger.info("Cleared results file")
        except Exception as e:
            logger.error(f"Error clearing results file: {e}")

        # Clear pagination state file
        try:
            state_file = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "domain_enrichment_pagination.json"
            if state_file.exists():
                state_file.unlink()
                logger.info("Cleared pagination state file")
        except Exception as e:
            logger.error(f"Error clearing pagination state file: {e}")

    def _load_analysis_tracker(self) -> None:
        """Load the analysis tracker from file."""
        try:
            if self.ANALYSIS_TRACKER_FILE.exists():
                with open(self.ANALYSIS_TRACKER_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._analyzed_articles = data.get('analyzed_articles', {})
                logger.info(f"Loaded {len(self._analyzed_articles)} analyzed articles from tracker")
            else:
                self._analyzed_articles = {}
                # Create parent directory if needed
                self.ANALYSIS_TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
                logger.info("Analysis tracker file not found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading analysis tracker: {e}")
            self._analyzed_articles = {}

    def _save_analysis_tracker(self) -> None:
        """Save the analysis tracker to file."""
        try:
            with self._lock:
                snapshot = dict(self._analyzed_articles)
            with open(self.ANALYSIS_TRACKER_FILE, 'w', encoding='utf-8') as f:
                json.dump({'analyzed_articles': snapshot}, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(snapshot)} analyzed articles to tracker")
        except Exception as e:
            logger.error(f"Error saving analysis tracker: {e}")

    def _is_article_analyzed(self, page_title: str) -> bool:
        """Check if an article has already been analyzed."""
        with self._lock:
            return page_title in self._analyzed_articles

    def _mark_article_analyzed(self, page_title: str, result: str, domain: Optional[str] = None) -> None:
        """Mark an article as analyzed with its result."""
        with self._lock:
            self._analyzed_articles[page_title] = {
                'analyzed_at': datetime.now().isoformat(),
                'result': result,  # 'new', 'already_present', 'conflict', 'error'
                'domain': domain
            }

    def _load_pagination_state(self) -> None:
        """Load pagination state from file for pause/resume."""
        try:
            state_file = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "domain_enrichment_pagination.json"
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    self._pagination_state = json.load(f)
                logger.info(f"Loaded pagination state: {self._pagination_state}")
            else:
                self._pagination_state = {}
                state_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Error loading pagination state: {e}")
            self._pagination_state = {}

    def _save_pagination_state(self) -> None:
        """Save pagination state to file for pause/resume."""
        try:
            state_file = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "domain_enrichment_pagination.json"
            with self._lock:
                snapshot = dict(self._pagination_state)
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved pagination state: {snapshot}")
        except Exception as e:
            logger.error(f"Error saving pagination state: {e}")

    def _clear_pagination_state(self) -> None:
        """Clear pagination state when starting fresh."""
        with self._lock:
            self._pagination_state = {}
        try:
            state_file = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "domain_enrichment_pagination.json"
            if state_file.exists():
                state_file.unlink()
                logger.info("Cleared pagination state file")
        except Exception as e:
            logger.error(f"Error clearing pagination state: {e}")

    def _save_results(self) -> None:
        """Save enrichment results to file for persistence."""
        try:
            with self._lock:
                entries_snapshot = [
                    {
                        'domain': entry.domain,
                        'site_name': entry.site_name,
                        'original_url': entry.original_url,
                        'page_title': entry.page_title,
                        'qid': entry.qid,
                        'status': entry.status.value,
                        'conflict_reason': entry.conflict_reason,
                    }
                    for entry in self._entries
                ]
                progress_snapshot = {
                    'state': self._progress.state.value,
                    'current_category': self._progress.current_category,
                    'pages_analyzed': self._progress.pages_analyzed,
                    'total_pages': self._progress.total_pages,
                    'skipped': self._progress.skipped,
                    'p856_found': self._progress.p856_found,
                    'new_domains': self._progress.new_domains,
                    'already_present': self._progress.already_present,
                    'conflicts': self._progress.conflicts,
                    'review_required': self._progress.review_required,
                    'errors': self._progress.errors,
                    'started_at': self._progress.started_at.isoformat() if self._progress.started_at else None,
                    'completed_at': self._progress.completed_at.isoformat() if self._progress.completed_at else None,
                    'recent_activity': self._progress.recent_activity,
                }
            
            results = {
                'entries': entries_snapshot,
                'progress': progress_snapshot,
            }
            
            with open(self.RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(entries_snapshot)} enrichment results to {self.RESULTS_FILE}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")

    def _load_results(self) -> None:
        """Load enrichment results from file if available."""
        try:
            if self.RESULTS_FILE.exists():
                with open(self.RESULTS_FILE, 'r', encoding='utf-8') as f:
                    results = json.load(f)
                
                with self._lock:
                    # Load entries
                    self._entries = [
                        DomainEntry(
                            domain=entry['domain'],
                            site_name=entry['site_name'],
                            original_url=entry.get('original_url'),
                            page_title=entry.get('page_title'),
                            qid=entry.get('qid'),
                            status=EntryStatus(entry.get('status', 'new')),
                            conflict_reason=entry.get('conflict_reason'),
                        )
                        for entry in results.get('entries', [])
                    ]
                    
                    # Load progress
                    progress_data = results.get('progress', {})
                    self._progress = EnrichmentProgress(
                        state=EnrichmentState(progress_data.get('state', 'idle')),
                        current_category=progress_data.get('current_category'),
                        pages_analyzed=progress_data.get('pages_analyzed', 0),
                        total_pages=progress_data.get('total_pages', 0),
                        skipped=progress_data.get('skipped', 0),
                        p856_found=progress_data.get('p856_found', 0),
                        new_domains=progress_data.get('new_domains', 0),
                        already_present=progress_data.get('already_present', 0),
                        conflicts=progress_data.get('conflicts', 0),
                        review_required=progress_data.get('review_required', 0),
                        errors=progress_data.get('errors', 0),
                        started_at=datetime.fromisoformat(progress_data['started_at']) if progress_data.get('started_at') else None,
                        completed_at=datetime.fromisoformat(progress_data['completed_at']) if progress_data.get('completed_at') else None,
                        recent_activity=progress_data.get('recent_activity', []),
                    )
                    
                    # Set state to completed if results were loaded
                    if self._progress.state == EnrichmentState.RUNNING:
                        self._progress.state = EnrichmentState.COMPLETED
                        self._state = EnrichmentState.COMPLETED
                
                logger.info(f"Loaded {len(self._entries)} enrichment results from {self.RESULTS_FILE}")
            else:
                self.RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Error loading results: {e}")
            self._entries = []
            self._progress = EnrichmentProgress()

    def _normalize_domain(self, url: str, keep_www: bool = False) -> Optional[str]:
        """
        Normalize a URL to extract and clean the domain.

        Args:
            url: URL to normalize
            keep_www: If True, preserve www prefix. If False, remove it.

        Returns:
            Normalized domain or None if invalid
        """
        try:
            parsed = urlparse(url)

            # Validate URL
            if not parsed.scheme or not parsed.netloc:
                return None

            # Extract domain (remove port, path, etc.)
            domain = parsed.netloc.lower()

            # Remove userinfo if present (user:pass@host)
            if '@' in domain:
                domain = domain.rsplit('@', 1)[-1]

            # Remove port if present
            if ':' in domain:
                domain = domain.split(':')[0]

            # Remove 'www.' prefix only if keep_www is False
            if not keep_www and domain.startswith('www.'):
                domain = domain[4:]

            # Basic validation
            if not domain or len(domain) < 3:
                return None

            # Check for invalid characters (allow IDN/punycode 'xn--' forms,
            # still restricted to ASCII host characters)
            if not re.match(r'^[a-z0-9.-]+$', domain):
                return None

            # Reject domains with no dot at all (not a real hostname)
            if '.' not in domain:
                return None

            return domain

        except Exception as e:
            logger.debug(f"Error normalizing domain from {url}: {e}")
            return None

    def _load_existing_domains(self) -> Dict[str, str]:
        """
        Load existing domain_to_site_name mappings.

        Returns:
            Dictionary mapping normalized domains to site names
        """
        try:
            if not self.CASE_NORMALIZATION_FILE.exists():
                logger.warning(f"Case normalization file not found: {self.CASE_NORMALIZATION_FILE}")
                return {}

            with open(self.CASE_NORMALIZATION_FILE, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            domain_to_site_name = data.get('domain_to_site_name') or {}

            # Normalize all existing domains for comparison
            existing = {}
            for domain, site_name in domain_to_site_name.items():
                normalized = self._normalize_domain(f"https://{domain}")
                if not normalized:
                    continue

                # Handle both string format and list format [[site_name]]
                resolved_name = site_name
                while isinstance(resolved_name, list) and len(resolved_name) > 0:
                    resolved_name = resolved_name[0]

                existing[normalized] = resolved_name

            logger.info(f"Loaded {len(existing)} existing domain mappings")
            return existing

        except Exception as e:
            logger.error(f"Error loading existing domains: {e}")
            return {}

    def _check_conflict(self, domain: str, site_name: str) -> Optional[str]:
        """
        Check if a domain conflicts with existing mappings.

        Args:
            domain: Normalized domain
            site_name: Proposed site name

        Returns:
            Conflict reason or None if no conflict
        """
        # Check exact match
        if domain in self._existing_domains:
            existing_site = self._existing_domains[domain]
            if existing_site != site_name:
                return f"Domain already mapped to '{existing_site}'"
            # Same mapping, no conflict - will be marked as already_present

        # Check www/non-www variant
        if domain.startswith('www.'):
            non_www_variant = domain[4:]
            if non_www_variant in self._existing_domains:
                existing_site = self._existing_domains[non_www_variant]
                if existing_site != site_name:
                    return f"Domain variant '{non_www_variant}' already mapped to '{existing_site}'"
        else:
            www_variant = f"www.{domain}"
            if www_variant in self._existing_domains:
                existing_site = self._existing_domains[www_variant]
                if existing_site != site_name:
                    return f"Domain variant '{www_variant}' already mapped to '{existing_site}'"

        return None

    def _process_page(self, page_title: str, wiki_lang: str, keep_www: bool = False) -> Optional[DomainEntry]:
        """
        Process a single Wikipedia page to extract domain mappings.

        Args:
            page_title: Wikipedia page title
            wiki_lang: Wikipedia language code
            keep_www: If True, preserve www prefix in domain normalization

        Returns:
            DomainEntry or None if no valid data found
        """
        # Check if already analyzed FIRST (early exit)
        if self._is_article_analyzed(page_title):
            logger.debug(f"SKIP: Article '{page_title}' already analyzed")
            with self._lock:
                self._progress.skipped += 1
            return None

        try:
            # Get QID from page title
            qid = self.wikidata_client.get_qid_from_page_title(page_title, wiki_lang)
            if not qid:
                logger.debug(f"No QID found for page: {page_title}")
                self._mark_article_analyzed(page_title, 'no_qid')
                return None

            # Get entity data from Wikidata
            entity = self.wikidata_client.get_entity(qid)
            if not entity or not entity.official_websites:
                logger.debug(f"No official websites found for {qid} ({page_title})")
                self._mark_article_analyzed(page_title, 'no_p856')
                return None

            # Use the first official website (could be enhanced to handle multiple)
            url = entity.official_websites[0]
            domain = self._normalize_domain(url, keep_www=keep_www)
            if not domain:
                logger.debug(f"Could not normalize domain from {url}")
                self._mark_article_analyzed(page_title, 'invalid_domain')
                return None

            # Determine site name (prefer label, fallback to page title)
            site_name = entity.label if entity.label else page_title

            # Check for conflicts
            conflict = self._check_conflict(domain, site_name)

            # Determine status (progress counters updated under lock to stay
            # consistent with concurrent get_progress() snapshots)
            with self._lock:
                if conflict:
                    status = EntryStatus.CONFLICT
                    self._progress.conflicts += 1
                elif domain in self._existing_domains:
                    status = EntryStatus.ALREADY_PRESENT
                    self._progress.already_present += 1
                else:
                    status = EntryStatus.NEW
                    self._progress.new_domains += 1

            result_label = {
                EntryStatus.CONFLICT: 'conflict',
                EntryStatus.ALREADY_PRESENT: 'already_present',
                EntryStatus.NEW: 'new',
            }[status]
            self._mark_article_analyzed(page_title, result_label, domain)

            return DomainEntry(
                domain=domain,
                site_name=site_name,
                status=status,
                original_url=url,
                page_title=page_title,
                qid=qid,
                conflict_reason=conflict
            )

        except Exception as e:
            logger.error(f"Error processing page {page_title}: {e}")
            with self._lock:
                self._progress.errors += 1
            self._mark_article_analyzed(page_title, 'error')
            return None

    def _process_category(self, category: str, wiki_lang: str, batch_size: int = 500, max_pages: Optional[int] = None, keep_www: bool = False) -> List[DomainEntry]:
        """
        Process all pages in a category with batch processing and pagination.

        Args:
            category: Category name
            wiki_lang: Wikipedia language code
            batch_size: Number of pages to fetch per batch
            max_pages: Maximum pages to process (across the whole enrichment run)
            keep_www: If True, preserve www prefix in domain normalization

        Returns:
            List of DomainEntry objects
        """
        entries = []
        offset = 0
        total_fetched = 0
        has_more = True
        max_iterations = 1000  # Safety limit to prevent infinite loops
        iteration_count = 0

        # Check if we have saved pagination state for this category
        category_key = f"{wiki_lang}:{category}"
        with self._lock:
            saved_state = self._pagination_state.get(category_key)
        if saved_state:
            offset = saved_state.get('offset', 0)
            total_fetched = saved_state.get('total_fetched', 0)
            logger.info(f"Resuming category '{category}' from offset {offset}")

        try:
            while has_more:
                iteration_count += 1
                if iteration_count >= max_iterations:
                    logger.error(f"Max iterations ({max_iterations}) reached for category '{category}', stopping to prevent infinite loop")
                    has_more = False
                    break
                # Check for cancellation
                if self._cancel_event.is_set():
                    logger.info("Cancellation requested, stopping category processing")
                    with self._lock:
                        self._pagination_state[category_key] = {
                            'offset': offset,
                            'total_fetched': total_fetched,
                            'category': category,
                            'wiki_lang': wiki_lang
                        }
                    self._save_pagination_state()
                    break

                # Check for pause
                while self._pause_event.is_set() and not self._cancel_event.is_set():
                    time.sleep(0.1)

                if self._cancel_event.is_set():
                    break

                # Check max_pages limit (global across the whole run)
                with self._lock:
                    pages_so_far = self._progress.pages_analyzed
                if max_pages is not None and pages_so_far >= max_pages:
                    logger.info(f"Max pages limit reached ({max_pages}), stopping")
                    break

                # Shrink the batch so we don't fetch far more members than we
                # are allowed to actually process this run.
                effective_batch_size = batch_size
                if max_pages is not None:
                    remaining = max(0, max_pages - pages_so_far)
                    if remaining == 0:
                        break
                    effective_batch_size = min(batch_size, remaining)

                # Fetch batch
                members = self.wikipedia_client.get_category_members(
                    category_name=category,
                    max_results=effective_batch_size,
                    recursive=False
                )

                if not members:
                    logger.info(f"No more members in category '{category}'")
                    has_more = False
                    # Clear pagination state for completed category
                    with self._lock:
                        self._pagination_state.pop(category_key, None)
                    self._save_pagination_state()
                    break

                total_fetched += len(members)
                with self._lock:
                    self._progress.total_pages = total_fetched

                logger.info(f"Processing batch {offset}-{offset + len(members)} in category '{category}'")

                # Process batch
                for member in members:
                    # Check for cancellation
                    if self._cancel_event.is_set():
                        logger.info("Cancellation requested during batch processing")
                        break

                    # Check for pause
                    while self._pause_event.is_set() and not self._cancel_event.is_set():
                        time.sleep(0.1)

                    if self._cancel_event.is_set():
                        break

                    # Re-check max_pages inside the batch too, in case it was
                    # reached mid-batch.
                    with self._lock:
                        pages_so_far = self._progress.pages_analyzed
                    if max_pages is not None and pages_so_far >= max_pages:
                        logger.info(f"Max pages limit reached ({max_pages}) mid-batch, stopping")
                        break

                    page_title = member.get('title')
                    if not page_title:
                        continue

                    # Process the page
                    entry = self._process_page(page_title, wiki_lang, keep_www=keep_www)
                    if entry:
                        entries.append(entry)
                        with self._lock:
                            self._progress.pages_analyzed += 1
                            self._progress.p856_found += 1
                            self._progress.add_activity(
                                f"✓ {page_title} → {entry.domain} → {entry.status.value}"
                            )
                            should_save_tracker = self._progress.pages_analyzed % 10 == 0

                        # Save tracker periodically (every 10 pages)
                        if should_save_tracker:
                            self._save_analysis_tracker()

                # Move to next batch
                offset += len(members)

                # Save pagination state after each batch
                with self._lock:
                    self._pagination_state[category_key] = {
                        'offset': offset,
                        'total_fetched': total_fetched,
                        'category': category,
                        'wiki_lang': wiki_lang
                    }
                self._save_pagination_state()

                # If we got fewer results than requested, we're done with this category
                if len(members) < effective_batch_size:
                    has_more = False
                    logger.info(f"Category '{category}' completed: {total_fetched} total pages")
                    with self._lock:
                        self._pagination_state.pop(category_key, None)
                    self._save_pagination_state()

            # Final save of tracker
            self._save_analysis_tracker()

        except Exception as e:
            logger.error(f"Error processing category {category}: {e}")
            with self._lock:
                self._progress.errors += 1

        return entries

    def start_enrichment(
        self,
        categories: List[CategoryConfig],
        dry_run: bool = True,
        max_pages: Optional[int] = None,
        keep_www: bool = False
    ) -> EnrichmentProgress:
        """
        Start the enrichment process.

        Args:
            categories: List of categories to process
            dry_run: If True, only analyze without writing
            max_pages: Maximum number of pages to process (None = unlimited)
            keep_www: If True, preserve www prefix in domain normalization to allow variants

        Returns:
            Final progress information
        """
        with self._lock:
            if self._state != EnrichmentState.IDLE:
                raise RuntimeError(f"Cannot start enrichment: current state is {self._state.value}")

        if not categories:
            raise ValueError("start_enrichment requires at least one category")
        if max_pages is not None and max_pages <= 0:
            raise ValueError("max_pages must be a positive integer when provided")

        logger.info(f"Starting enrichment with {len(categories)} categories (dry_run={dry_run}, max_pages={max_pages})")

        # Initialize state
        self._set_state(EnrichmentState.RUNNING)
        with self._lock:
            self._progress = EnrichmentProgress(state=EnrichmentState.RUNNING)
            self._progress.started_at = datetime.now()
            self._entries = []
        self._pause_event.clear()
        self._cancel_event.clear()

        # Clear pagination state for fresh start
        self._clear_pagination_state()

        # Load existing domains
        existing_domains = self._load_existing_domains()
        with self._lock:
            self._existing_domains = existing_domains

        try:
            # Sort categories by priority
            sorted_categories = sorted(categories, key=lambda c: c.priority)

            for category_config in sorted_categories:
                # Check if max_pages limit reached
                with self._lock:
                    pages_so_far = self._progress.pages_analyzed
                if max_pages is not None and pages_so_far >= max_pages:
                    logger.info(f"Max pages limit reached ({max_pages}), stopping enrichment")
                    self._set_state(EnrichmentState.COMPLETED)
                    with self._lock:
                        self._progress.completed_at = datetime.now()
                    break

                # Check for cancellation
                if self._cancel_event.is_set():
                    logger.info("Cancellation requested, stopping enrichment")
                    self._set_state(EnrichmentState.CANCELLED)
                    break

                # Check for pause
                while self._pause_event.is_set() and not self._cancel_event.is_set():
                    time.sleep(0.1)

                if self._cancel_event.is_set():
                    break

                # Process category
                with self._lock:
                    self._progress.current_category = category_config.category

                logger.info(f"Processing category: {category_config.category} (wiki: {category_config.wiki})")

                entries = self._process_category(category_config.category, category_config.wiki, max_pages=max_pages, keep_www=keep_www)
                with self._lock:
                    self._entries.extend(entries)

            # Update final state
            with self._lock:
                new_domains_found = self._progress.new_domains

            if self._cancel_event.is_set():
                logger.info(f"Enrichment cancelled but {new_domains_found} new domains collected")
            # When cancelled, still mark as completed to allow preview of collected data
            self._set_state(EnrichmentState.COMPLETED)
            with self._lock:
                self._progress.completed_at = datetime.now()

            logger.info(f"Enrichment completed: {new_domains_found} new domains found")
            
            # Save results for persistence
            self._save_results()

        except Exception as e:
            logger.error(f"Enrichment failed: {e}", exc_info=True)
            self._set_state(EnrichmentState.FAILED)
            with self._lock:
                self._progress.completed_at = datetime.now()

        return self.get_progress()

    def pause(self):
        """Pause the enrichment process."""
        with self._lock:
            if self._state != EnrichmentState.RUNNING:
                logger.warning(f"Cannot pause: current state is {self._state.value}")
                return

        logger.info("Pausing enrichment...")
        self._pause_event.set()
        self._set_state(EnrichmentState.PAUSED)
        logger.info("Enrichment paused")

    def resume(self):
        """Resume a paused enrichment process."""
        with self._lock:
            if self._state != EnrichmentState.PAUSED:
                logger.warning(f"Cannot resume: current state is {self._state.value}")
                return

        logger.info("Resuming enrichment...")
        self._pause_event.clear()
        self._set_state(EnrichmentState.RUNNING)
        logger.info("Enrichment resumed")

    def cancel(self):
        """Cancel the enrichment process."""
        with self._lock:
            if self._state not in (EnrichmentState.RUNNING, EnrichmentState.PAUSED):
                logger.warning(f"Cannot cancel: current state is {self._state.value}")
                return

        logger.info("Cancelling enrichment...")
        self._set_state(EnrichmentState.CANCELLING)
        self._cancel_event.set()

        # Clear pause event to allow cancellation to proceed
        self._pause_event.clear()

    def get_new_entries(self) -> List[DomainEntry]:
        """Get all new entries that can be added."""
        with self._lock:
            return [e for e in self._entries if e.status == EntryStatus.NEW]

    def get_preview(self) -> Dict[str, Any]:
        """
        Get a preview of changes that would be made.

        Returns:
            Dictionary with preview information
        """
        new_entries = self.get_new_entries()
        progress = self.get_progress()
        
        # Estimate how many entries will be written (including www variants)
        # Each domain will get both www and non-www variants if not already present
        estimated_entries = len(new_entries) * 2

        return {
            'new_entries': [
                {
                    'domain': entry.domain,
                    'site_name': entry.site_name,
                    'original_url': entry.original_url,
                    'page_title': entry.page_title,
                    'qid': entry.qid,
                }
                for entry in new_entries
            ],
            'summary': {
                'estimated_total': estimated_entries,
                'domains': len(new_entries),
                'already_present': progress.already_present,
                'conflicts': progress.conflicts,
                'review_required': progress.review_required,
                'errors': progress.errors,
            }
        }

    def _write_yaml_atomic(self, path: Path, data: Dict[str, Any]) -> None:
        """
        Write YAML data to `path` atomically.

        This is a local copy of the atomic write function from config.py
        to avoid circular imports.
        """
        import os
        import tempfile

        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=None, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)  # atomic on POSIX and Windows
        except Exception:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise

    def write_to_yaml(self, entries: List[DomainEntry]) -> Tuple[bool, int]:
        """
        Write new entries to case_normalization_data.yaml atomically.

        Args:
            entries: List of new entries to write

        Returns:
            Tuple of (success: bool, entries_added: int)
        """
        if not entries:
            logger.info("write_to_yaml called with no entries, nothing to do")
            return True, 0

        # Serializes concurrent write attempts (e.g. a double-click on
        # "confirm write") so we never read-modify-write the YAML file
        # from two threads at once.
        with self._write_lock:
            try:
                # Read existing file
                if not self.CASE_NORMALIZATION_FILE.exists():
                    logger.error(f"Case normalization file not found: {self.CASE_NORMALIZATION_FILE}")
                    return False, 0

                with open(self.CASE_NORMALIZATION_FILE, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}

                # Ensure domain_to_site_name section exists
                if 'domain_to_site_name' not in data or data['domain_to_site_name'] is None:
                    data['domain_to_site_name'] = {}

                # Add new entries - keep both www and non-www variants if they come from Wikidata
                entries_added = 0
                for entry in entries:
                    # Keep the domain exactly as retrieved from Wikidata (with or without www)
                    domain = entry.domain
                    
                    # Format: domain: [[site_name]]
                    # Only add if not already present (avoid duplicates)
                    if domain not in data['domain_to_site_name']:
                        data['domain_to_site_name'][domain] = [[entry.site_name]]
                        entries_added += 1
                    else:
                        # Domain exists, check if site name matches
                        existing = data['domain_to_site_name'][domain]
                        if existing and existing[0] != entry.site_name:
                            logger.warning(f"Domain {domain} exists with different site name: {existing[0]} vs {entry.site_name}")

                # Write atomically
                self._write_yaml_atomic(self.CASE_NORMALIZATION_FILE, data)

                logger.info(f"Successfully wrote {entries_added} entries ({len(entries)} domains with variants) to {self.CASE_NORMALIZATION_FILE}")
                
                # Update persisted results after successful write
                self._save_results()
                
                return True, entries_added

            except Exception as e:
                logger.error(f"Error writing to YAML: {e}", exc_info=True)
                return (False, 0)