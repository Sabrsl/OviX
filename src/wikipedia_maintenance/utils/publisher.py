"""
Correction proposal module with diff generation, position‑aware replacement,
conflict handling, and various diff formats.

This module provides a `Corrector` class that can apply corrections to
wikitext content based on issues detected by analyzers. It supports:
    - Position‑based replacement (using start/end offsets) for precision.
    - Reverse‑order application to avoid offset shifts.
    - Conflict detection when corrections overlap.
    - Preview of corrections before application.
    - Unified and HTML diffs.
    - Summary statistics.

All existing methods (`apply_correction`, `apply_corrections`, etc.) are
preserved and enhanced to use positions when available, falling back to
simple text replacement if necessary.
"""

import difflib
import logging
import random
from .lia_logger import log_published_article
from .published_tracker import PublishedTracker
from .api_throttler import get_global_throttler
import requests
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from ..analyzers.base import Issue
from .edit_summaries import get_random_summary, get_summary
from .api_throttler import get_global_throttler

logger = logging.getLogger(__name__)


@dataclass
class Correction:
    """Represents a proposed correction."""
    issue: Issue
    applied: bool = False
    original_snippet: Optional[str] = None
    corrected_snippet: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'issue': self.issue.to_dict(),
            'applied': self.applied,
            'original_snippet': self.original_snippet,
            'corrected_snippet': self.corrected_snippet,
            'start': self.start,
            'end': self.end,
        }


class Corrector:
    """
    Applies corrections to article content and generates diffs.

    Uses position‑based replacement when possible (if the issue provides
    position and original_text), with a fallback to simple text replacement.
    Corrections are applied in reverse order of position to avoid shifting
    offsets. Overlapping corrections are detected and may be skipped
    depending on the conflict resolution strategy.
    """

    # Conflict resolution strategies
    CONFLICT_SKIP = "skip"          # Skip the later correction
    CONFLICT_OVERWRITE = "overwrite" # Apply later, overwriting earlier (use with caution)
    CONFLICT_MERGE = "merge"        # Not implemented; fallback to skip

    def __init__(
        self,
        original_content: str,
        conflict_strategy: str = CONFLICT_SKIP,
        strict_position_check: bool = True,
    ):
        """
        Initialize corrector with original content.

        Args:
            original_content: Original article wikicode.
            conflict_strategy: How to handle overlapping corrections.
            strict_position_check: If True, verify that the original_text
                at the given position matches the expected original_text
                before applying.
        """
        self.original_content = original_content
        self.current_content = original_content
        self.corrections: List[Correction] = []
        self.conflict_strategy = conflict_strategy
        self.strict_position_check = strict_position_check
        self._applied_ranges: List[Tuple[int, int]] = []  # (start, end) of applied corrections

    # ------------------------------------------------------------------
    # Core correction methods
    # ------------------------------------------------------------------

    def apply_correction(self, issue: Issue) -> bool:
        """
        Apply a single correction.

        Uses position if available, otherwise falls back to simple replacement.

        Args:
            issue: Issue to correct.

        Returns:
            True if correction was applied, False otherwise.
        """
        if not issue.suggested_text or not issue.original_text:
            logger.debug("Cannot apply correction: missing suggested_text or original_text")
            return False

        # Try position‑based replacement first
        if issue.position is not None:
            return self._apply_correction_at_position(issue)

        # Fallback: simple text replacement (first occurrence only)
        # This is less reliable and deprecated for positional issues.
        logger.warning("Applying correction without position (fallback)")
        return self._apply_correction_by_text(issue)

    def apply_corrections(
        self,
        issues: List[Issue],
        selected_indices: Optional[List[int]] = None,
    ) -> str:
        """
        Apply multiple corrections.

        Args:
            issues: List of issues to correct.
            selected_indices: Indices of issues to apply (None = all).

        Returns:
            Corrected content.
        """
        self.reset()

        if selected_indices is None:
            selected_indices = list(range(len(issues)))

        # Get the selected issues
        selected_issues = [issues[i] for i in selected_indices if i < len(issues)]

        # Sort by position descending (to avoid offset shifts)
        # Issues without position are applied last (simple replacement)
        with_position = [i for i in selected_issues if i.position is not None]
        without_position = [i for i in selected_issues if i.position is None]

        sorted_issues = sorted(with_position, key=lambda x: x.position, reverse=True)
        sorted_issues.extend(without_position)  # apply text‑based ones last

        for issue in sorted_issues:
            self.apply_correction(issue)

        return self.current_content

    def _apply_correction_at_position(self, issue: Issue) -> bool:
        """
        Apply correction using the position and original_text from the issue.

        Verifies that the original_text matches the content at that position.
        Handles overlapping corrections based on conflict_strategy.
        """
        if issue.position is None or issue.original_text is None:
            return False

        start = issue.position
        end = start + len(issue.original_text)

        # Ensure we have enough content
        if end > len(self.current_content):
            logger.warning("Issue position out of bounds")
            return False

        # Verify that the text at the position matches the expected original
        if self.strict_position_check:
            actual_text = self.current_content[start:end]
            if actual_text != issue.original_text:
                logger.warning(
                    f"Text mismatch at position {start}: expected {issue.original_text!r}, got {actual_text!r}"
                )
                # Attempt to find the text elsewhere? Not safe; we skip.
                self.corrections.append(
                    Correction(
                        issue=issue,
                        applied=False,
                        original_snippet=actual_text,
                        start=start,
                        end=end,
                    )
                )
                return False

        # Check for overlap with previously applied corrections
        if self._overlaps_with_applied(start, end):
            if self.conflict_strategy == self.CONFLICT_SKIP:
                logger.debug(f"Skipping overlapping correction at {start}-{end}")
                self.corrections.append(
                    Correction(
                        issue=issue,
                        applied=False,
                        original_snippet=self.current_content[start:end],
                        start=start,
                        end=end,
                    )
                )
                return False
            elif self.conflict_strategy == self.CONFLICT_OVERWRITE:
                # Remove previous corrections that overlap? Complex; we'll just apply and hope.
                logger.warning("Overwriting previous correction (may cause issues)")
                # We could remove the old ones from applied_ranges, but we'll just apply and update ranges later.
                # For simplicity, we'll just proceed and adjust ranges.
            else:
                logger.warning(f"Unknown conflict strategy: {self.conflict_strategy}")
                return False

        # Apply the correction
        new_content = (
            self.current_content[:start]
            + issue.suggested_text
            + self.current_content[end:]
        )
        self.current_content = new_content

        # Record the correction
        correction = Correction(
            issue=issue,
            applied=True,
            original_snippet=issue.original_text,
            corrected_snippet=issue.suggested_text,
            start=start,
            end=end,
        )
        self.corrections.append(correction)

        # Update applied ranges (shifting subsequent ranges? We apply in reverse order, so no shifting needed)
        # However, if we ever apply in forward order, we'd need to adjust; we always apply reverse.
        self._applied_ranges.append((start, start + len(issue.suggested_text)))

        return True

    def _apply_correction_by_text(self, issue: Issue) -> bool:
        """
        Fallback: apply using simple text replacement (first occurrence only).
        """
        if not issue.original_text or not issue.suggested_text:
            return False

        if issue.original_text in self.current_content:
            self.current_content = self.current_content.replace(
                issue.original_text,
                issue.suggested_text,
                1  # only first occurrence
            )
            correction = Correction(issue=issue, applied=True)
            self.corrections.append(correction)
            return True
        else:
            correction = Correction(issue=issue, applied=False)
            self.corrections.append(correction)
            return False

    def _overlaps_with_applied(self, start: int, end: int) -> bool:
        """Check if the range [start, end) overlaps with any applied correction."""
        for s, e in self._applied_ranges:
            if not (end <= s or start >= e):
                return True
        return False

    # ------------------------------------------------------------------
    # Diff generation
    # ------------------------------------------------------------------

    def get_diff(self) -> str:
        """Generate unified diff between original and corrected content."""
        original_lines = self.original_content.splitlines(keepends=True)
        corrected_lines = self.current_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            corrected_lines,
            fromfile='original',
            tofile='corrected',
            lineterm=''
        )
        return ''.join(diff)

    def get_html_diff(self, wrapcolumn: int = 80) -> str:
        """Generate HTML diff with color coding."""
        original_lines = self.original_content.splitlines()
        corrected_lines = self.current_content.splitlines()

        differ = difflib.HtmlDiff(wrapcolumn=wrapcolumn)
        html_diff = differ.make_table(
            original_lines,
            corrected_lines,
            fromdesc='Original',
            todesc='Corrigé',
            context=True,
            numlines=3
        )
        return html_diff

    def get_side_by_side_diff(self) -> List[Tuple[str, str]]:
        """Return a side‑by‑side diff as a list of (original, corrected) lines."""
        original_lines = self.original_content.splitlines()
        corrected_lines = self.current_content.splitlines()

        differ = difflib.SequenceMatcher(None, original_lines, corrected_lines)
        result = []
        for op, i1, i2, j1, j2 in differ.get_opcodes():
            if op == 'equal':
                for i in range(i1, i2):
                    result.append((original_lines[i], corrected_lines[j1 + (i - i1)]))
            elif op == 'replace':
                # Show replacements
                for i in range(i1, i2):
                    result.append((original_lines[i], None))
                for j in range(j1, j2):
                    result.append((None, corrected_lines[j]))
                # Or show pairs? Let's just show both sides with None for missing.
            elif op == 'delete':
                for i in range(i1, i2):
                    result.append((original_lines[i], None))
            elif op == 'insert':
                for j in range(j1, j2):
                    result.append((None, corrected_lines[j]))
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of corrections applied."""
        total = len(self.corrections)
        applied = sum(1 for c in self.corrections if c.applied)
        failed = total - applied

        by_type: Dict[str, Dict[str, int]] = defaultdict(lambda: {'applied': 0, 'failed': 0})
        for correction in self.corrections:
            issue_type = correction.issue.issue_type
            if correction.applied:
                by_type[issue_type]['applied'] += 1
            else:
                by_type[issue_type]['failed'] += 1

        return {
            'total_corrections': total,
            'applied': applied,
            'failed': failed,
            'by_type': dict(by_type),
        }

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset to original content."""
        self.current_content = self.original_content
        self.corrections = []
        self._applied_ranges = []

    def get_corrected_content(self) -> str:
        """Get current corrected content."""
        return self.current_content

    def preview_correction(self, issue: Issue) -> Optional[str]:
        """
        Preview what the corrected content would look like for a single issue
        without actually applying it.
        """
        if issue.position is None or issue.original_text is None or issue.suggested_text is None:
            return None

        start = issue.position
        end = start + len(issue.original_text)

        if end > len(self.current_content):
            return None

        preview = (
            self.current_content[:start]
            + "**"
            + issue.suggested_text
            + "**"
            + self.current_content[end:]
        )
        return preview

    def get_issue_correction_status(self, issue_id: Optional[int] = None) -> Dict[str, bool]:
        """
        Return a mapping of issue identifiers (or indices) to their application status.
        Only works if issues are provided with an ID or we track by position.
        For simplicity, this returns a dict of applied statuses for all corrections.
        """
        result = {}
        for i, corr in enumerate(self.corrections):
            key = f"issue_{i}"
            # If issue has a unique ID, use it
            if hasattr(corr.issue, 'id'):
                key = corr.issue.id
            result[key] = corr.applied
        return result


class Publisher:
    """
    Publisher class for publishing corrections to Wikipedia via MediaWiki API.

    This class handles the actual publishing of corrections to Wikipedia
    using the MediaWiki API directly. It supports manual publication with
    human-readable edit summaries.
    """

    def __init__(self, username: str = "LearnLynx", password: str = None, dry_run: bool = True, lang: str = "fr"):
        """
        Args:
            username: Wikipedia username (default: LearnLynx).
            password: Wikipedia password (if None, will load from passwords.py).
            dry_run: If True, don't actually publish (default for safety).
            lang: Wikipedia language code (default: fr).
        """
        self.username = username
        self.password = password
        self.dry_run = dry_run
        
        # Use provided lang or fallback to config
        if lang is None or lang == '':
            try:
                from .config import load_config
                config = load_config()
                self.lang = config.wikipedia.lang
            except Exception:
                self.lang = 'fr'  # Ultimate fallback
        else:
            self.lang = lang
        self.session = requests.Session()
        
        # Use global API throttler
        self.api_throttler = get_global_throttler()
        
        # P0 CRITICAL FIX: Add maximum diff size validation
        self.max_diff_size = 2000  # Maximum characters in diff for safety
        
        # P0 CRITICAL FIX: Add conflict detection by revision ID
        self.require_revision_check = True  # Check revision ID before publish
        
        # Note: Wikipedia API client integration temporarily disabled due to circular import
        # Will be re-enabled after refactoring
        self.wikipedia_client = None
        
        # Load configuration
        import yaml
        from pathlib import Path
        
        # P2 FIX: Use bot identity system for User-Agent
        try:
            from .bot_identity import get_user_agent
            user_agent = get_user_agent(purpose="Wikipedia Maintenance")
        except ImportError:
            # Fallback to default if bot_identity not available
            user_agent = "WikipediaMaintenanceTool/1.0"
            logger.warning("Bot identity system not available, using default User-Agent")
        
        api_url_template = "https://{lang}.wikipedia.org/w/api.php"
        self.api_timeout = 30
        
        try:
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config:
                        if 'api_urls' in config and 'wikipedia' in config['api_urls']:
                            api_url_template = config['api_urls']['wikipedia']
                        # P2 FIX: Bot identity takes precedence over config user_agent
                        # if 'other' in config and 'user_agent' in config['other']:
                        #     user_agent = config['other']['user_agent']
                        if 'timeouts' in config and 'wikipedia_api' in config['timeouts']:
                            self.api_timeout = config['timeouts']['wikipedia_api']
        except Exception:
            pass
        
        self.session.headers.update({
            'User-Agent': user_agent
        })
        self._authenticated = False
        self.api_url = api_url_template.format(lang=lang)
        self.tracker = PublishedTracker()
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load credentials from secure credential manager (environment variables only)."""
        if self.password is not None:
            return
        
        # Use secure credential manager
        try:
            from .secure_credentials import get_credential_manager
            cred_manager = get_credential_manager(allow_env_only=True)
            
            username, password = cred_manager.get_wikipedia_credentials()
            if username and password:
                self.username = username
                self.password = password
                # Log masked username for debugging (never log password)
                masked_username = cred_manager.mask_sensitive_value(username, visible_chars=3)
                logger.info(f"Loaded credentials securely for user: {masked_username}")
                return
            else:
                logger.warning("Wikipedia credentials not found in environment variables")
                logger.warning("Please set WIKIPEDIA_USERNAME and WIKIPEDIA_PASSWORD environment variables")
                
        except ImportError:
            logger.warning("Secure credential manager not available, falling back to environment variables")
            # Fallback to direct environment variable access
            import os
            env_username = os.environ.get('WIKIPEDIA_USERNAME')
            env_password = os.environ.get('WIKIPEDIA_PASSWORD')
            
            if env_username and env_password:
                self.username = env_username
                self.password = env_password
                masked_username = "*" * (len(env_username) - 3) + env_username[-3:] if len(env_username) > 3 else "***"
                logger.info(f"Loaded credentials from environment variables for user: {masked_username}")
            else:
                logger.warning("Wikipedia credentials not found in environment variables")
    
    def _validate_diff_size(self, original_content: str, new_content: str) -> tuple[bool, str]:
        """
        P0 CRITICAL FIX: Validate that the diff size is within safe limits.
        
        Args:
            original_content: Original page content
            new_content: New page content
            
        Returns:
            (is_valid, error_message) - True if diff size is acceptable
        """
        # Calculate diff size
        diff_size = len(new_content) - len(original_content)
        absolute_diff = abs(diff_size)
        
        # Check if diff exceeds maximum allowed size
        if absolute_diff > self.max_diff_size:
            error_msg = f"Diff size ({absolute_diff} chars) exceeds maximum allowed ({self.max_diff_size} chars). This suggests an unintended large-scale modification."
            logger.error(error_msg)
            return False, error_msg
        
        # Additional safety check: if content more than doubled or halved
        if len(new_content) > len(original_content) * 2 or len(new_content) < len(original_content) / 2:
            error_msg = f"Content size changed dramatically (from {len(original_content)} to {len(new_content)} chars). This suggests an unintended modification."
            logger.error(error_msg)
            return False, error_msg
        
        return True, ""
    
    def _check_revision_conflict(self, title: str, expected_revision_id: int) -> tuple[bool, str]:
        """
        P0 CRITICAL FIX: Check if the page has been modified since analysis.
        
        Args:
            title: Page title
            expected_revision_id: Revision ID from analysis time
            
        Returns:
            (is_safe, error_message) - True if no conflict detected
        """
        if not self.require_revision_check or expected_revision_id is None:
            return True, ""
        
        try:
            params = {
                'action': 'query',
                'titles': title,
                'prop': 'info',
                'format': 'json'
            }
            
            response = self._throttled_get(self.api_url, params=params)
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            page = next(iter(pages.values())) if pages else None
            
            if page and 'lastrevid' in page:
                current_revision_id = page['lastrevid']
                if current_revision_id != expected_revision_id:
                    error_msg = f"Revision conflict: expected {expected_revision_id}, found {current_revision_id}. Page has been modified since analysis."
                    logger.error(error_msg)
                    return False, error_msg
        
        except Exception as e:
            logger.warning(f"Could not check revision conflict for {title}: {e}")
            # Fail-safe: allow publication if check fails (conservative approach)
            return True, ""
        
        return True, ""
    
    def _throttled_get(self, url: str, params: Dict[str, Any], **kwargs) -> requests.Response:
        """
        Make a throttled GET request to the API.
        
        Args:
            url: The URL to request
            params: Query parameters
            **kwargs: Additional arguments to pass to requests.get
            
        Returns:
            Response object
        """
        # Apply throttling before the request
        self.api_throttler.wait_if_needed()
        
        # Add maxlag parameter to respect server lag
        params = params.copy()
        if 'maxlag' not in params:
            params['maxlag'] = 5  # Wait if server lag exceeds 5 seconds
        
        # Make the request
        response = self.session.get(url, params=params, **kwargs)
        
        # Handle 429 errors with exponential backoff
        if response.status_code == 429:
            self.api_throttler.report_429()
            logger.warning(f"Received 429 error, backing off...")
            # Wait and retry once with increased delay
            self.api_throttler.wait_if_needed()
            response = self.session.get(url, params=params, **kwargs)
            if response.status_code == 429:
                logger.error("Still getting 429 after backoff, giving up")
            else:
                self.api_throttler.report_success()
        else:
            self.api_throttler.report_success()
        
        # Log request count
        request_count = self.api_throttler.get_request_count()
        logger.debug(f"API request made (total this minute: {request_count})")
        
        return response
    
    def check_page_protection_batch(self, page_titles: List[str]) -> Dict[str, bool]:
        """
        Check protection status for multiple pages using the centralized Wikipedia API client.
        
        Args:
            page_titles: List of page titles to check
            
        Returns:
            Dictionary mapping page titles to protection status (True if protected)
        """
        if not page_titles:
            return {}
        
        # Try to use centralized Wikipedia API client if available
        if self.wikipedia_client:
            try:
                results = self.wikipedia_client.check_page_protection(page_titles)
                
                for title, is_protected in results.items():
                    if is_protected:
                        logger.info(f"Page '{title}' is protected")
                
                return results
                
            except Exception as e:
                logger.error(f"Error checking page protection batch with centralized client: {e}")
                # Fall back to direct requests
                logger.info("Falling back to direct API requests")
        
        # Fallback to direct API requests (original implementation)
        try:
            # MediaWiki API accepts up to 50 titles per request
            batch_size = 50
            results = {}
            
            for i in range(0, len(page_titles), batch_size):
                batch = page_titles[i:i + batch_size]
                titles_param = '|'.join(batch)
                
                logger.info(f"Checking protection for {len(batch)} pages (batch {i//batch_size + 1})")
                
                response = self._throttled_get(
                    self.api_url,
                    params={
                        'action': 'query',
                        'prop': 'info',
                        'titles': titles_param,
                        'inprop': 'protection',
                        'format': 'json'
                    }
                )
                
                data = response.json()
                
                # Process results
                for page_id, page_info in data['query']['pages'].items():
                    if page_id == '-1':  # Invalid page
                        continue
                    title = page_info.get('title', '')
                    is_protected = bool(page_info.get('protection'))
                    results[title] = is_protected
                    
                    if is_protected:
                        logger.info(f"Page '{title}' is protected")
            
            return results
            
        except Exception as e:
            logger.error(f"Error checking page protection batch: {e}")
            # Fallback: return all as unprotected to not block operations
            return {title: False for title in page_titles}

    def authenticate(self) -> bool:
        """
        Authenticate with Wikipedia using MediaWiki API.

        Returns:
            True if authentication successful, False otherwise
        """
        logger.info("=== AUTHENTICATION START ===")
        # Mask username for security
        masked_username = "*" * (len(self.username) - 3) + self.username[-3:] if len(self.username) > 3 else "***"
        logger.info(f"Username: {masked_username}")
        logger.info(f"API URL: {self.api_url}")
        
        # Apply throttling before login
        self.api_throttler.wait_if_needed()
        
        try:
            # Get login token
            logger.info("Getting login token...")
            token_response = self._throttled_get(
                self.api_url,
                params={
                    'action': 'query',
                    'meta': 'tokens',
                    'type': 'login',
                    'format': 'json'
                },
                timeout=self.api_timeout
            )

            logger.info(f"Token response status: {token_response.status_code}")

            if not token_response.text or token_response.status_code != 200:
                logger.error(f"Invalid response from API: status={token_response.status_code}")
                return False

            token_data = token_response.json()
            login_token = token_data['query']['tokens']['logintoken']
            logger.info("Got login token")

            # Login
            logger.info("Attempting login...")
            login_response = self.session.post(
                self.api_url,
                data={
                    'action': 'login',
                    'lgname': self.username,
                    'lgpassword': self.password,
                    'lgtoken': login_token,
                    'format': 'json'
                },
                timeout=self.api_timeout
            )

            logger.info(f"Login response status: {login_response.status_code}")

            if not login_response.text:
                logger.error("Empty response from API during login")
                return False

            login_data = login_response.json()
            logger.info(f"Login response: {login_data}")

            if login_data.get('login', {}).get('result') == 'Success':
                self._authenticated = True
                logger.info(f"=== AUTHENTICATION SUCCESS ===")
                return True
            else:
                logger.error(f"=== AUTHENTICATION FAILED ===")
                logger.error(f"Login result: {login_data.get('login', {}).get('result')}")
                logger.error(f"Login data: {login_data}")
                return False

        except Exception as e:
            logger.error(f"=== AUTHENTICATION ERROR ===")
            logger.error(f"Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def set_dry_run(self, dry_run: bool) -> None:
        """Set the dry_run mode."""
        self.dry_run = dry_run

    def generate_edit_summary(self, num_corrections: int, correction_types: List[str]) -> str:
        """
        Generate an edit summary using the edit_summaries module.
        
        Args:
            num_corrections: Number of corrections made (not used, kept for compatibility).
            correction_types: List of correction type identifiers.
            
        Returns:
            Edit summary adapted to the dominant correction type.
        """
        # Convert correction_types list to issue_types dict
        from collections import Counter
        if correction_types:
            issue_types = dict(Counter(correction_types))
        else:
            issue_types = {}
        
        # Use get_summary with issue_types for adaptive summary
        return get_summary(corrections_count=num_corrections, correction_types=correction_types, issue_types=issue_types)

    def publish(self, page_title: str, content: str, summary: str, minor: bool = True, original_content: str = None, expected_revision_id: int = None) -> Tuple[bool, str]:
        """
        Publish content to a Wikipedia page with P0 CRITICAL VALIDATIONS.

        Args:
            page_title: Title of the page to edit.
            content: New content to publish.
            summary: Edit summary.
            minor: Mark as minor edit (default: True for maintenance edits).
            original_content: Original page content for diff validation (P0 CRITICAL).
            expected_revision_id: Expected revision ID for conflict detection (P0 CRITICAL).

        Returns:
            Tuple of (success, message) where message contains details.
        """
        logger.info(f"=== PUBLISH START ===")
        logger.info(f"Page: {page_title}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info(f"Authenticated: {self._authenticated}")

        # P0 CRITICAL FIX: FINAL Kill Switch verification BEFORE ANY edit
        # This is the authoritative check - overrides scheduler, workers, queue, everything
        try:
            from .kill_switch_manager import get_kill_switch_manager
            kill_switch = get_kill_switch_manager()
            kill_switch.check_and_raise()  # Raises exception if enabled
            logger.info("Kill switch check passed - publication allowed")
        except RuntimeError as e:
            logger.error(f"Publication blocked by kill switch: {e}")
            return False, f"Publication blocked: {str(e)}"
        except ImportError:
            logger.warning("Kill switch manager not available - proceeding without kill switch check")

        if self.dry_run:
            logger.info(f"DRY RUN: Would publish to '{page_title}' with summary: {summary}")
            return True, f"DRY RUN: Would publish to '{page_title}'"

        # P0 CRITICAL FIX: Validate diff size if original content provided
        if original_content is not None:
            is_valid, error_msg = self._validate_diff_size(original_content, content)
            if not is_valid:
                logger.error(f"DIFF VALIDATION FAILED: {error_msg}")
                return False, f"Publication blocked: {error_msg}"
            logger.info("Diff size validation passed")

        # P0 CRITICAL FIX: Check revision conflict if expected revision ID provided
        if expected_revision_id is not None:
            is_safe, conflict_msg = self._check_revision_conflict(page_title, expected_revision_id)
            if not is_safe:
                logger.error(f"REVISION CONFLICT DETECTED: {conflict_msg}")
                return False, f"Publication blocked: {conflict_msg}"
            logger.info("Revision conflict check passed")

        if not self._authenticated:
            logger.warning("Not authenticated, attempting authentication")
            if not self.authenticate():
                logger.error("Authentication failed")
                return False, "Authentication failed"
        
        # Continue with actual publication logic
        try:
            logger.info("Getting CSRF token...")
            # Use global throttler before any API call
            self.api_throttler.wait_if_needed()
            
            # Get edit token
            token_response = self._throttled_get(
                self.api_url,
                params={
                    'action': 'query',
                    'meta': 'tokens',
                    'type': 'csrf',
                    'format': 'json'
                }
            )
            logger.info(f"Token response status: {token_response.status_code}")
            token_data = token_response.json()
            csrf_token = token_data['query']['tokens']['csrftoken']
            logger.info("Got CSRF token")
            
            # Use global throttler before posting
            self.api_throttler.wait_if_needed()
            
            # Make the edit
            edit_params = {
                'action': 'edit',
                'title': page_title,
                'text': content,
                'summary': summary,
                'minor': '1' if minor else '0',
                'token': csrf_token,
                'format': 'json'
            }
            
            logger.info(f"Publishing to '{page_title}' with summary: {summary}")
            edit_response = self.session.post(
                self.api_url,
                data=edit_params
            )
            
            logger.info(f"Edit response status: {edit_response.status_code}")
            edit_data = edit_response.json()
            
            if edit_response.status_code == 200 and 'edit' in edit_data:
                new_rev_id = edit_data['edit'].get('newrevid')
                logger.info(f"Successfully published to '{page_title}' with revision ID: {new_rev_id}")
                return True, str(new_rev_id) if new_rev_id else f"Successfully published to '{page_title}'"
            else:
                error_msg = edit_data.get('error', {}).get('info', 'Unknown error')
                logger.error(f"Publication failed: {error_msg}")
                return False, f"Publication failed: {error_msg}"
                
        except Exception as e:
            logger.error(f"Publication error: {e}")
            return False, f"Publication error: {str(e)}"
    
    def publish_unsafe(self, page_title: str, content: str, summary: str, minor: bool = True) -> Tuple[bool, str]:
        """
        Legacy publish method without P0 validations for backward compatibility.
        
        WARNING: This method bypasses critical safety validations. Use publish() instead.
        
        Args:
            page_title: Title of the page to edit.
            content: New content to publish.
            summary: Edit summary.
            minor: Mark as minor edit (default: True for maintenance edits).

        Returns:
            Tuple of (success, message) where message contains details.
        """
        logger.warning("=== USING UNSAFE PUBLISH METHOD - CRITICAL VALIDATIONS DISABLED ===")
        return self.publish(page_title, content, summary, minor, original_content=None, expected_revision_id=None)

    def preview_changes(self, page_title: str, new_content: str) -> Tuple[bool, str, str]:
        """
        Preview changes without publishing.

        Args:
            page_title: Title of the page.
            new_content: New content to preview.

        Returns:
            Tuple of (success, message, diff) where diff is the unified diff.
        """
        try:
            # Get current page content
            page_response = self._throttled_get(
                self.api_url,
                params={
                    'action': 'query',
                    'prop': 'revisions',
                    'rvprop': 'content',
                    'titles': page_title,
                    'format': 'json'
                }
            )
            page_data = page_response.json()

            # Check if page exists
            pages = page_data['query']['pages']
            page_id = list(pages.keys())[0]
            if page_id == '-1':
                return False, f"Page '{page_title}' does not exist", ""

            current_content = pages[page_id]['revisions'][0]['*']

            # Generate diff
            diff = difflib.unified_diff(
                current_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile='current',
                tofile='proposed',
                lineterm=''
            )
            diff_text = ''.join(diff)

            return True, f"Preview for '{page_title}'", diff_text

        except Exception as e:
            logger.error(f"Preview error: {e}")
            return False, f"Preview error: {str(e)}", ""

    def validate_before_publish(self, page_title: str, new_content: str, issues: List[Issue]) -> Tuple[bool, str]:
        """
        Validate changes before publishing.

        Args:
            page_title: Title of the page.
            new_content: New content to publish.
            issues: List of issues that were applied.

        Returns:
            Tuple of (valid, message) where valid indicates if publishing is safe.
        """
        logger.info(f"=== VALIDATION START ===")
        logger.info(f"Page: {page_title}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info(f"Authenticated: {self._authenticated}")
        logger.info(f"Number of issues: {len(issues)}")

        # Skip authentication check for dry-run mode
        if not self.dry_run and not self._authenticated:
            logger.error("Validation failed: Not authenticated")
            return False, "Non authentifié"

        try:
            # Get current page content
            logger.info("Getting current page content...")
            page_response = self._throttled_get(
                self.api_url,
                params={
                    'action': 'query',
                    'prop': 'revisions',
                    'rvprop': 'content',
                    'titles': page_title,
                    'format': 'json'
                }
            )
            logger.info(f"Page response status: {page_response.status_code}")
            page_data = page_response.json()

            # Check if page exists
            pages = page_data['query']['pages']
            page_id = list(pages.keys())[0]
            if page_id == '-1':
                logger.error(f"Validation failed: Page '{page_title}' does not exist")
                return False, f"Page '{page_title}' does not exist"

            current_content = pages[page_id]['revisions'][0]['*']
            logger.info(f"Got current content (length: {len(current_content)})")

            # Check if content has changed
            if current_content == new_content:
                logger.error("Validation failed: No changes detected")
                return False, "Aucun changement détecté"

            # Check for issues without suggested_text (should not be applied)
            # Only check if they were actually selected for correction
            issues_without_text = [i for i in issues if i.suggested_text is None]
            if issues_without_text:
                logger.warning(f"Found {len(issues_without_text)} issues without suggested_text (manual corrections only)")
                # Don't fail validation for manual-only issues - they just won't be applied
                # return False, f"{len(issues_without_text)} issues sans suggested_text détectées"

            # Check for high severity issues
            high_severity = [i for i in issues if i.severity == "high"]
            if high_severity:
                logger.error(f"Validation failed: {len(high_severity)} high severity issues")
                return False, f"{len(high_severity)} issues de haute sévérité détectées"

            # Check diff size (prevent massive changes)
            diff_lines = len(list(difflib.unified_diff(
                current_content.splitlines(),
                new_content.splitlines(),
                lineterm=''
            )))
            logger.info(f"Diff size: {diff_lines} lines")
            if diff_lines > 1000:  # Arbitrary threshold
                logger.error(f"Validation failed: Diff too large ({diff_lines} lines)")
                return False, f"Diff trop important ({diff_lines} lignes)"

            # Check if page is protected
            logger.info("Checking page protection...")
            info_response = self._throttled_get(
                self.api_url,
                params={
                    'action': 'query',
                    'prop': 'info',
                    'titles': page_title,
                    'inprop': 'protection',
                    'format': 'json'
                }
            )
            info_data = info_response.json()
            page_info = list(info_data['query']['pages'].values())[0]
            if page_info.get('protection'):
                logger.error(f"Validation failed: Page is protected")
                return False, "Page protégée"

            logger.info("=== VALIDATION SUCCESS ===")
            return True, "Validation réussie"

        except Exception as e:
            logger.error(f"=== VALIDATION ERROR ===")
            logger.error(f"Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, f"Erreur de validation: {str(e)}"