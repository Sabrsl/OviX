"""
Dead Link Analyzer - Ultra-Simple Version

SINGLE OBJECTIVE:
Replace a dead external link with the new URL of the same source.

ONLY IF:
- Link is truly dead (404/410)
- New URL found for SAME SOURCE
- SAME RESOURCE confirmed with multiple proofs
- Safe URL replacement
- Minimal diff (only URL changes)

Otherwise: NO_REPAIR

Philosophy: FEW REPAIRS + VERY HIGH CERTAINTY + ZERO UNRELATED CHANGES
"""

import re
import logging
import time
import uuid
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import BaseAnalyzer, Issue
from wikipedia_maintenance.utils.api_throttler import get_global_throttler
from wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult, LinkChecker
from wikipedia_maintenance.utils.url_extraction import UrlExtractor
from wikipedia_maintenance.utils.url_metadata import UrlMetadataExtractor
from wikipedia_maintenance.utils.dead_link_analyzer_config import DeadLinkAnalyzerConfig
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplate
from wikipedia_maintenance.utils.bare_url_helper import BareUrlRef
from wikipedia_maintenance.utils.redirect_finder import RedirectFinder, RedirectResult
from wikipedia_maintenance.utils.link_validator import LinkValidator, RepairDecision, RepairResult
from wikipedia_maintenance.utils.content_verifier import ContentVerifier
from wikipedia_maintenance.utils.safe_url_replacer import SafeURLReplacer
from wikipedia_maintenance.utils.archive_provider import ArchiveProvider
from wikipedia_maintenance.utils.archive_content_checker import ArchiveSoftDeadChecker
from wikipedia_maintenance.utils.template_replacement_validator import TemplateReplacementValidator
from wikipedia_maintenance.utils.internal_links_writer import InternalLinksWriter
from wikipedia_maintenance.utils.lien_web_helper import LienWebHelper
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper
from wikipedia_maintenance.utils.bare_url_helper import BareUrlHelper
from wikipedia_maintenance.utils.retry_handler import RetryConfig, RetryHandler, RetryStrategy
# Phase 1: Tracking Service imports
from wikipedia_maintenance.utils.tracking_service import TrackingService, DeadLinkOperation, compute_idempotency_key, normalize_url
from wikipedia_maintenance.utils.database import DatabaseManager
# CandidateFinder currently unused - reserved for future multi-strategy candidate search
# from ..utils.candidate_finder import CandidateFinder

logger = logging.getLogger(__name__)


class DeadLinkAnalyzer(BaseAnalyzer):
    """
    Dead Link Analyzer - Ultra-Simple, Single-Objective Version.

    Replaces dead external links with new URLs of the same source.
    """

    # Backward compatibility constants - actual values managed by DeadLinkAnalyzerConfig
    DEFAULT_TIMEOUT = 10
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_MAX_CHECKS_PER_ARTICLE = 20


    def __init__(self, name: str = None,
                 timeout: int = None,
                 max_retries: int = None,
                 max_checks_per_article: int = None,
                 tracking_service: Optional[TrackingService] = None):
        super().__init__(name)

        # _load_config() may set self.timeout / self.max_retries /
        # self.max_checks_per_article / self.enable_auto_repair from
        # config.yaml. It must run before the getattr(...) fallbacks
        # below so a loaded config value is visible to them.
        self._load_config()

        # FIX: previously this was `timeout or self.DEFAULT_TIMEOUT`,
        # which used the *constructor argument* (None in normal usage)
        # and silently clobbered whatever _load_config() had just set
        # on self.timeout from config.yaml. Same bug existed for
        # max_retries and max_checks_per_article (confirmed in
        # production logs: "Loaded config: ... max_checks=20" followed
        # immediately by "started - max_checks: 20").
        #
        # Priority is now, correctly: explicit constructor arg >
        # value loaded from config.yaml > hardcoded default.
        self.timeout = (
            timeout if timeout is not None
            else getattr(self, 'timeout', DeadLinkAnalyzerConfig.DEFAULT_TIMEOUT)
        )
        self.max_retries = (
            max_retries if max_retries is not None
            else getattr(self, 'max_retries', DeadLinkAnalyzerConfig.DEFAULT_MAX_RETRIES)
        )
        self.max_checks_per_article = (
            max_checks_per_article if max_checks_per_article is not None
            else getattr(self, 'max_checks_per_article', DeadLinkAnalyzerConfig.DEFAULT_MAX_CHECKS_PER_ARTICLE)
        )

        self.api_throttler = get_global_throttler()
        self.link_checker = LinkChecker(timeout=self.timeout, max_retries=self.max_retries)
        self.redirect_finder = RedirectFinder(timeout=self.timeout)
        # Pass shared LinkChecker to LinkValidator to respect caching and rate limits
        self.link_validator = LinkValidator(link_checker=self.link_checker)
        self.content_verifier = ContentVerifier()
        self.safe_url_replacer = SafeURLReplacer()
        self.archive_provider = ArchiveProvider()
        self.archive_content_checker = ArchiveSoftDeadChecker(timeout=self.timeout)
        self.template_validator = TemplateReplacementValidator()
        self.internal_links_writer = InternalLinksWriter()
        self.lien_web_helper = LienWebHelper()
        self.reference_template_helper = ReferenceTemplateHelper()
        self.bare_url_helper = BareUrlHelper()
        # CandidateFinder currently unused - reserved for future multi-strategy candidate search
        # self.candidate_finder = CandidateFinder(timeout=self.timeout)

        # enable_auto_repair is loaded from config in _load_config().
        # Default to True if not specified in config.
        self.enable_auto_repair = getattr(self, 'enable_auto_repair', True)

        # assume_wikipedia_patch_deployed controls whether we assume the Wikipedia Lua patch
        # that makes archive the main link when "brisé le" + "archive-url" are present.
        # Default to False for safety (works on both patched and unpatched wikis).
        self.assume_wikipedia_patch_deployed = getattr(self, 'assume_wikipedia_patch_deployed', False)

        self._check_cache: Dict[str, LinkCheckResult] = {}
        self._repair_cache: Dict[str, Dict[str, Any]] = {}
        self._template_cache: Dict[str, Any] = {}  # Cache reference template lookups to avoid redundant calls
        self._checks_count = 0
        self._consecutive_dns_failures = 0  # Track consecutive DNS transient failures for health check
        self.repaired_content: Optional[str] = None  # Store final repaired content

        # Phase 1: Tracking Service - Optional for parallel write
        self.tracking_service = tracking_service
        self._article_title: Optional[str] = None  # Track current article for tracking
        self._revision_id: Optional[int] = None  # Track current revision for tracking

    def _load_config(self) -> None:
        try:
            config = DeadLinkAnalyzerConfig.load()
            
            if config.validate():
                self.timeout = config.timeout
                self.max_retries = config.max_retries
                self.max_checks_per_article = config.max_checks_per_article
                self.enable_auto_repair = config.enable_auto_repair
                self.assume_wikipedia_patch_deployed = config.assume_wikipedia_patch_deployed
            else:
                logger.warning("Invalid configuration loaded, using defaults")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using defaults.")

    def get_analyzer_name(self) -> str:
        return "DeadLinkAnalyzer"

    # Phase 1: Tracking Service integration methods
    def _set_tracking_context(self, article_title: str, revision_id: Optional[int] = None) -> None:
        """
        Set the tracking context for the current analysis.
        
        Args:
            article_title: Article title
            revision_id: Wikipedia revision ID
        """
        self._article_title = article_title
        self._revision_id = revision_id

    def _create_deadlink_operation(
        self,
        url: str,
        context_type: str,
        reference_type: Optional[str] = None,
        template_name: Optional[str] = None,
        field_name: Optional[str] = None
    ) -> Optional[DeadLinkOperation]:
        """
        Create a DeadLinkOperation for tracking.
        
        Args:
            url: Original URL
            context_type: Context type (ref, template, bare_url)
            reference_type: Reference type (lien_web, ouvrage, etc.)
            template_name: Template name if applicable
            field_name: Field name if applicable
            
        Returns:
            DeadLinkOperation or None if tracking service not available
        """
        if not self.tracking_service:
            return None
        
        operation_id = str(uuid.uuid4())
        url_normalized = normalize_url(url)
        
        # Compute idempotency key if we have all required information
        idempotency_key = None
        if self._article_title and self._revision_id:
            idempotency_key = compute_idempotency_key(
                self._article_title,
                self._revision_id,
                url,
                context_type,
                reference_type or 'unknown'
            )
        
        operation = DeadLinkOperation(
            id=str(uuid.uuid4()),
            article_title=self._article_title or 'unknown',
            revision_id=self._revision_id,
            operation_id=operation_id,
            url_original=url,
            url_normalized=url_normalized,
            context_type=context_type,
            reference_type=reference_type,
            template_name=template_name,
            field_name=field_name,
            idempotency_key=idempotency_key,
            final_status='DETECTED',
            created_at=None,  # Will be set by database
            detected_at=None  # Will be set by database
        )
        
        return operation

    def _record_operation_to_tracking(self, operation: DeadLinkOperation) -> bool:
        """
        Record operation to tracking service (parallel write).
        
        Args:
            operation: DeadLinkOperation to record
            
        Returns:
            True if successful, False otherwise
        """
        if not self.tracking_service:
            return False
        
        try:
            success = self.tracking_service.record_operation(operation)
            if success:
                self._logger.info(f"PHASE1_TRACKING | operation_id={operation.operation_id} | url={operation.url_original}")
            return success
        except Exception as e:
            self._logger.warning(f"PHASE1_TRACKING_FAILED | operation_id={operation.operation_id} | error={e}")
            return False

    def _add_issue_with_tracking(
        self,
        issue_type: str,
        description: str,
        position: Optional[int],
        original_text: Optional[str],
        suggested_text: Optional[str],
        severity: str = "medium",
        confidence: float = 1.0,
        extra: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        context_type: Optional[str] = None,
        reference_type: Optional[str] = None,
        template_name: Optional[str] = None,
        field_name: Optional[str] = None
    ) -> None:
        """
        Add issue with parallel tracking (Phase 1).
        
        This method:
        1. Creates a DeadLinkOperation if tracking service is available
        2. Records the operation to tracking service (parallel write)
        3. Creates Issue with operation_id for correlation
        4. Adds Issue to self.issues (old system, continues to work)
        
        Args:
            issue_type: Type of issue
            description: Issue description
            position: Position in content
            original_text: Original text
            suggested_text: Suggested correction
            severity: Severity level
            confidence: Confidence score
            extra: Additional metadata
            url: URL for tracking (required for operation creation)
            context_type: Context type for tracking (ref, template, bare_url)
            reference_type: Reference type for tracking (lien_web, ouvrage, etc.)
            template_name: Template name for tracking
            field_name: Field name for tracking
        """
        operation_id = None
        
        # Phase 1: Create and record operation if tracking service available and URL provided
        if self.tracking_service and url:
            try:
                operation = self._create_deadlink_operation(
                    url=url,
                    context_type=context_type or 'unknown',
                    reference_type=reference_type,
                    template_name=template_name,
                    field_name=field_name
                )
                
                if operation:
                    self._record_operation_to_tracking(operation)
                    operation_id = operation.operation_id
            except Exception as e:
                self._logger.warning(f"PHASE1_TRACKING_BYPASS | url={url} | error={e}")
        
        # Create Issue with operation_id (correlation field)
        issue = Issue(
            issue_type=issue_type,
            description=description,
            position=position,
            original_text=original_text,
            suggested_text=suggested_text,
            severity=severity,
            confidence=confidence,
            extra=extra,
            operation_id=operation_id  # Phase 1: Correlation field
        )
        
        # Add to self.issues (old system, continues to work)
        self.issues.append(issue)

    def _is_url_syntactically_valid(self, url: str) -> bool:
        """
        Check if URL is syntactically valid before attempting network requests.
        """
        # Load excluded domains from academic_domains.yaml
        from wikipedia_maintenance.utils.link_checker import _load_academic_publisher_domains
        excluded_domains = _load_academic_publisher_domains()
        return UrlExtractor.is_syntactically_valid(url, excluded_domains)

    def _is_archive_url(self, url: str) -> bool:
        return UrlExtractor.is_archive_url(url)

    def _extract_original_url_from_archive(self, archive_url: str) -> Optional[str]:
        return UrlExtractor.extract_original_from_archive(archive_url)

    def _get_param_any(self, parameters: Dict[str, str], variants: tuple) -> Optional[str]:
        """Return the first non-None value found among the given parameter
        name variants, or None if none of them are present."""
        for name in variants:
            value = parameters.get(name)
            if value is not None:
                return value
        return None

    def _get_archive_url_param_any(self, parameters: Dict[str, str]) -> Optional[str]:
        """Return the first non-None archive URL parameter value found among
        all recognized variants (archive-url, archiveurl, archive_url, etc.)."""
        archive_url_variants = ('archive-url', 'archiveurl', 'archive_url')
        return self._get_param_any(parameters, archive_url_variants)

    def _get_archive_date_param_any(self, parameters: Dict[str, str]) -> Optional[str]:
        """Return the first non-None archive date parameter value found among
        all recognized variants (archive-date, archivedate, archive_date, etc.)."""
        archive_date_variants = ('archive-date', 'archivedate', 'archive_date')
        return self._get_param_any(parameters, archive_date_variants)

    def _get_original_title(self, template: Optional[ReferenceTemplate]) -> Optional[str]:
        """Extract the original title from a template, checking all variants."""
        if not template or not template.parameters:
            return None
        title_variants = ('titre', 'title', 'Titre', 'Title')
        return self._get_param_any(template.parameters, title_variants)

    def _extract_site_name_from_url(self, url: str) -> Optional[str]:
        """
        Extract site name from URL using the site name mapping for human-readable names.
        
        If the URL is an archive URL, first extract the original URL before
        determining the site name, so we get the original site instead of the archive site.
        
        Args:
            url: URL to extract site name from
            
        Returns:
            Human-readable site name from mapping, or raw domain if not in mapping
        """
        # If this is an archive URL, extract the original URL first
        if self._is_archive_url(url):
            original_url = self._extract_original_url_from_archive(url)
            if original_url:
                url = original_url
                logger.info(f"Extracted original URL from archive: {original_url}")
        
        domain = UrlMetadataExtractor.extract_site_name(url)
        if not domain:
            return None
        
        # Use the site name mapping from ReferenceTemplateHelper for human-readable names
        return self.reference_template_helper._resolve_site_display_name(domain)

    def _extract_title_from_url(self, url: str) -> Optional[str]:
        return UrlMetadataExtractor.extract_title(url)

    def _get_site_parameter_if_missing(self, template, url: str) -> Optional[Dict[str, str]]:
        """
        If a reference template's |site= parameter is missing or empty,
        return an extra_params dict with site filled from the domain of the main link.
        If site is already present, return None (no extra params needed).

        This is safer than mutating template.parameters in place.

        Args:
            template: Reference template
            url: Main link URL

        Returns:
            Dict with site parameter if missing, None otherwise
        """
        # Skip for templates that should NOT have |site= (e.g., ouvrage)
        if template.template_name in self.reference_template_helper.TEMPLATES_WITHOUT_SITE_PARAM:
            return None

        # If site is already present and non-empty, no extra params needed
        # Check all variants (site, Site, etc.) for consistency
        site_variants = ('site', 'Site', 'SITE')
        if self._get_param_any(template.parameters, site_variants):
            return None

        # If site is missing, fill it from URL using the site name mapping
        site_value = self._extract_site_name_from_url(url)
        if not site_value:
            return None

        # Check if série or collection has the same name as the potential site
        # If so, skip adding site to avoid duplication
        série = template.parameters.get('série')
        collection = template.parameters.get('collection')
        
        if série or collection:
            # Normalize for comparison (case-insensitive, remove brackets)
            # Handle site_value being a list (defensive programming)
            if isinstance(site_value, list):
                site_value = str(site_value[0]) if site_value else None
            if not site_value:
                return None
            site_clean = site_value.strip().lower().replace('[[', '').replace(']]', '')
            
            if série:
                série_clean = série.strip().lower().replace('[[', '').replace(']]', '')
                if site_clean == série_clean or site_clean in série_clean or série_clean in site_clean:
                    logger.info(f"SITE_PARAMETER_SKIP_AUTO_FILL | url={url} | série={série} | reason=série_same_as_site")
                    return None
            
            if collection:
                collection_clean = collection.strip().lower().replace('[[', '').replace(']]', '')
                if site_clean == collection_clean or site_clean in collection_clean or collection_clean in site_clean:
                    logger.info(f"SITE_PARAMETER_SKIP_AUTO_FILL | url={url} | collection={collection} | reason=collection_same_as_site")
                    return None

        logger.info(f"SITE_PARAMETER_AUTO_FILLED | url={url} | site={site_value}")
        return {'site': site_value}

    def _archive_content_looks_dead(self, archive_url: str) -> bool:
        """
        Best-effort safety net for archive-fallback repairs.

        Delegates to ArchiveSoftDeadChecker for soft-404 detection.
        """
        return self.archive_content_checker.looks_dead(archive_url)

    def _add_repair_issue(self, old_url: str, new_url: str, repair_type: str,
                          url_position: int, result: LinkCheckResult,
                          repair_result: RepairResult, archive_repairs: list,
                          archive_url: str = None, archive_date: str = None,
                          provider: str = None, original_text: str = None,
                          suggested_text: str = None, position: int = None,
                          context_type: str = None, reference_type: str = None,
                          template_name: str = None) -> None:
        """
        Helper method to add a repair issue and track archive repairs.
        Factorizes duplicated logic from multiple fallback paths.
        
        Phase 1: Now uses _add_issue_with_tracking for parallel write.
        """
        if archive_url and archive_date:
            archive_repairs.append({
                'original_url': old_url,
                'archive_url': archive_url,
                'archive_date': archive_date,
                'provider': provider or 'WaybackMachine'
            })

        # Phase 1: Use _add_issue_with_tracking for parallel write
        self._add_issue_with_tracking(
            issue_type="dead_link",
            description=f"Lien mort réparé : {old_url}",
            position=position or url_position,
            original_text=original_text or old_url,
            suggested_text=suggested_text or new_url,
            severity="high",
            confidence=1.0,
            extra={
                'url': old_url,
                'old_url': old_url,
                'new_url': new_url,
                'http_status_code': result.http_status_code,
                'repair_decision': repair_result.decision.value if repair_result else 'unknown',
                'repair_type': repair_type,
                'archive_url': archive_url,
                'archive_date': archive_date,
                'provider': provider,
                'repair_status': 'REPAIR_APPLIED'
            },
            url=old_url,  # Phase 1: Required for tracking
            context_type=context_type,  # Phase 1: Context for tracking
            reference_type=reference_type,  # Phase 1: Reference type for tracking
            template_name=template_name  # Phase 1: Template name for tracking
        )

    def _classify_reference_context(self, content: str, url: str, url_position: int) -> Dict[str, Any]:
        """
        Classify the reference context in a single pass.
        Returns a structured object with:
        - template_type: 'lien_web' | 'article' | 'ouvrage' | 'lien_brise' | None
        - is_bare_url: bool
        - is_in_ref_tag: bool
        - is_academic_formatted: bool
        - template: ReferenceTemplate or None
        - confidence: float
        """
        context = {
            'template_type': None,
            'is_bare_url': False,
            'is_in_ref_tag': False,
            'is_academic_formatted': False,
            'template': None,
            'confidence': 0.0
        }

        # Check if in <ref> tag
        ref_start = content.rfind('<ref', 0, url_position)
        ref_end = content.find('>', url_position)
        context['is_in_ref_tag'] = (ref_start != -1 and ref_end != -1 and ref_start < url_position < ref_end)

        # Try to find reference template
        template = self._get_cached_reference_template(content, url, url_position)
        if template:
            context['template'] = template
            context['template_type'] = template.template_name.lower()
            context['confidence'] = 1.0
            return context

        # Check if bare URL
        bare_refs = self.bare_url_helper.find_bare_urls(content)
        for ref in bare_refs:
            if ref.dead_url == url and ref.dead_url_start == url_position:
                context['is_bare_url'] = True
                context['confidence'] = 0.9
                break

        # Check for academic formatting patterns
        context_start = max(0, url_position - 200)
        context_end = min(len(content), url_position + 200)
        context_text = content[context_start:context_end]

        academic_patterns = [
            r'\{\{(en|es|de|fr|it|pt|gl|ca|ru|zh|ja)\}\}',
            r'\{\{vol\.\|',
            r'\{\{n[°o]\|',
            r'\{\{p\.\|',
            r'\{\{ISBN\|',
            r'\{\{OCLC\|',
            r'\{\{ISSN\|',
            r'\{\{DOI\|',
            r'\[\[.*?\]\]',
        ]

        for pattern in academic_patterns:
            if re.search(pattern, context_text, re.IGNORECASE):
                context['is_academic_formatted'] = True
                context['confidence'] = max(context['confidence'], 0.7)
                break

        return context

    def analyze(self, content: str) -> List[Issue]:
        self.clear_issues()

        if not content:
            logger.warning("DeadLinkAnalyzer: empty content provided")
            return self.issues

        # Clear both caches to ensure fresh analysis per article
        # This prevents cross-article cache pollution where a link that was dead in one article
        # but healthy in another would get incorrectly replaced with an archive
        self._check_cache.clear()
        self._repair_cache.clear()
        self._template_cache.clear()
        self._checks_count = 0
        self._consecutive_dns_failures = 0

        logger.info(f"DeadLinkAnalyzer started - content_length: {len(content)}, max_checks: {self.max_checks_per_article}, auto_repair: {self.enable_auto_repair}")

        protected_mask = self.build_protected_mask(content)
        all_matches = list(UrlExtractor.URL_PATTERN.finditer(content))
        protected_matches = [m for m in all_matches if not self.is_protected(protected_mask, m.start())]

        archive_urls_to_skip = set()
        url_to_original_map = {}

        for match in protected_matches:
            url = match.group(0)
            if self._is_archive_url(url):
                original_url = self._extract_original_url_from_archive(url)
                if original_url:
                    for orig_match in protected_matches:
                        if orig_match.group(0) == original_url:
                            archive_urls_to_skip.add(url)
                            url_to_original_map[url] = original_url
                            logger.info(f"ARCHIVE_PAIR_DETECTED | archive_url={url} | original_url={original_url}")
                            break

        filtered_matches = [m for m in protected_matches if m.group(0) not in archive_urls_to_skip]

        seen_urls = set()
        deduplicated_matches = []
        duplicate_count = 0
        for match in filtered_matches:
            url = match.group(0)
            if url not in seen_urls:
                seen_urls.add(url)
                deduplicated_matches.append(match)
            else:
                duplicate_count += 1
                logger.info(f"URL_DUPLICATE_SKIPPED | url={url}")

        filtered_matches = deduplicated_matches
        total_urls = len(filtered_matches)
        logger.info(f"Found {total_urls} URLs to check (skipped {len(archive_urls_to_skip)} archive URLs with paired originals, {duplicate_count} duplicates)")

        scoped_matches = [
            m for m in filtered_matches
            if self._is_url_in_reference_scope(content, m.group(0), m.start())
        ]
        out_of_scope_count = len(filtered_matches) - len(scoped_matches)
        if out_of_scope_count:
            logger.info(f"URLS_OUT_OF_SCOPE_SKIPPED | count={out_of_scope_count} | reason=not_in_reference_or_citation_template")
        filtered_matches = scoped_matches
        total_urls = len(filtered_matches)

        # Sort matches by position in descending order to avoid position offset issues
        # when content length changes after successful replacements
        filtered_matches.sort(key=lambda m: m.start(), reverse=True)

        analysis_complete = True
        # Track archive repairs for internal links
        archive_repairs = []

        # ---- PASSE 1 : vérification parallèle des liens ----
        matches_to_check = filtered_matches[:self.max_checks_per_article]
        if len(filtered_matches) > self.max_checks_per_article:
            analysis_complete = False
            logger.info(f"Reached max checks limit ({self.max_checks_per_article}), stopping")

        valid_matches = []
        for match in matches_to_check:
            url = match.group(0)
            if not self._is_url_syntactically_valid(url):
                logger.warning(f"URL_REJECTED | url={url} | reason=SYNTAX_INVALID")
                continue
            valid_matches.append(match)

        # Parallel link checking with ThreadPoolExecutor
        if valid_matches:
            logger.info(f"Starting parallel link check for {len(valid_matches)} URLs with max_workers=5")
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_match = {
                    executor.submit(self.link_checker.check_link, m.group(0)): m
                    for m in valid_matches
                }
                for future in as_completed(future_to_match):
                    match = future_to_match[future]
                    url = match.group(0)
                    try:
                        result = future.result()
                        self._check_cache[url] = result
                        self._checks_count += 1

                        # Track consecutive DNS transient failures for network health check
                        if result.error_type and result.error_type.startswith("DNS_TRANSIENT"):
                            self._consecutive_dns_failures += 1
                        else:
                            self._consecutive_dns_failures = 0  # Reset on non-DNS failure

                        # Network health check: abort if first 3 checks all fail with DNS transient errors
                        if self._checks_count >= 3 and self._consecutive_dns_failures == self._checks_count:
                            logger.error(f"NETWORK_HEALTH_CHECK_FAILED | consecutive_dns_failures={self._consecutive_dns_failures} | aborting_analysis | reason=local_dns_network_appears_down")
                            return self.issues

                        logger.info(f"URL_CHECK | url={url} | http_status={result.http_status_code} | classification={result.status.value} | error={result.error_type} | attempts={result.retry_count}")
                    except Exception as e:
                        logger.error(f"URL_CHECK_FAILED | url={url} | error={e}")
                        # Create a failure result to avoid crashes in repair phase
                        # LinkStatus is already imported at module level
                        self._check_cache[url] = LinkCheckResult(
                            url=url,
                            status=LinkStatus.UNKNOWN,
                            error_type="CHECK_EXCEPTION",
                            retry_count=0,
                            check_duration=0.0,
                            confidence=0.0
                        )
                        self._checks_count += 1

        logger.info(f"Parallel link check completed - checked {self._checks_count}/{len(valid_matches)} URLs")

        # ---- PASSE 2 : réparation séquentielle (en utilisant le cache) ----
        for match in valid_matches:
            url = match.group(0)
            url_position = match.start()

            # CRITICAL FIX: Reset repair_result to prevent contamination between iterations
            # This prevents archive_url from a previous URL being used for the current URL
            repair_result = None

            # Get result from cache (computed in Pass 1)
            if url not in self._check_cache:
                logger.warning(f"URL_NOT_IN_CACHE | url={url} | skipping")
                continue

            result = self._check_cache[url]

            # Skip repair for DNS transient errors - these are local network issues, not dead links
            if result.error_type and result.error_type.startswith("DNS_TRANSIENT"):
                logger.warning(f"SKIP_REPAIR_DNS_TRANSIENT | url={url} | error_type={result.error_type} | reason=local_network_issue_not_dead_link")
                continue

            # CRITICAL FIX: Validate cache BEFORE checking status to prevent applying stale repairs
            # This prevents applying archived replacements to links that are now healthy
            if url in self._repair_cache:
                cached_decision = self._repair_cache[url]
                logger.info(f"REPAIR_CACHED | url={url} | decision={cached_decision.get('decision')} | replacement_url={cached_decision.get('replacement_url')}")

                # Always re-validate current status before applying cached repair
                if result.status != LinkStatus.DEAD:
                    logger.warning(f"REPAIR_CACHE_INVALIDATED | url={url} | current_status={result.status.value} | cached_decision={cached_decision.get('decision')} | reason=link_no_longer_dead")
                    # Remove from cache since it's no longer valid
                    del self._repair_cache[url]
                    continue  # Skip this URL since it's no longer dead
                elif cached_decision.get('decision') == 'REPLACEMENT_CONFIRMED' and self.enable_auto_repair:
                    old_url = url
                    new_url = cached_decision.get('replacement_url')

                    replacement_result = self.safe_url_replacer.replace_exact_occurrence(
                        content, old_url, new_url, url_position
                    )

                    if replacement_result.success:
                        logger.info(f"REPAIR_APPLIED | url={url} | new_url={new_url} | cached=True")
                        # Don't modify content directly - create Issue for Corrector
                        # content = replacement_result.new_content

                        # Phase 1: Use _add_issue_with_tracking for parallel write
                        self._add_issue_with_tracking(
                            issue_type="dead_link",
                            description=f"Lien mort remplacé : {old_url} → {new_url}",
                            position=url_position,
                            original_text=old_url,
                            suggested_text=new_url,
                            severity="high",
                            confidence=1.0,
                            extra={
                                'url': url,
                                'old_url': old_url,
                                'new_url': new_url,
                                'http_status_code': result.http_status_code,
                                'repair_decision': cached_decision.get('decision'),
                                'cached': True,
                                'repair_status': 'REPAIR_APPLIED'
                            },
                            url=old_url,  # Phase 1: Required for tracking
                            context_type='template',  # Phase 1: Context for tracking
                            reference_type='lien_web'  # Phase 1: Reference type for tracking
                        )
                    else:
                        logger.warning(f"REPAIR_FAILED | url={url} | reason={replacement_result.reason}")
                        # Phase 1: Use _add_issue_with_tracking for parallel write
                        self._add_issue_with_tracking(
                            issue_type="dead_link",
                            description=f"Lien mort détecté, réparation échouée : {url}",
                            position=url_position,
                            original_text=match.group(0),
                            suggested_text=None,
                            severity="high",
                            confidence=1.0,
                            extra={
                                'url': url,
                                'http_status_code': result.http_status_code,
                                'error_type': result.error_type,
                                'repair_status': 'REPAIR_FAILED',
                                'repair_reason': replacement_result.reason
                            },
                            url=url,  # Phase 1: Required for tracking
                            context_type='template',  # Phase 1: Context for tracking
                            reference_type='lien_web'  # Phase 1: Reference type for tracking
                        )
                    continue
                else:
                    logger.info(f"REPAIR_SKIPPED | url={url} | reason=already_unrepairable ({cached_decision.get('decision')})")
                    # Phase 1: Use _add_issue_with_tracking for parallel write
                    self._add_issue_with_tracking(
                        issue_type="dead_link",
                        description=f"Lien mort détecté, réparation impossible (déjà évalué) : {url}",
                        position=url_position,
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="high",
                        confidence=1.0,
                        extra={
                            'url': url,
                            'http_status_code': result.http_status_code,
                            'error_type': result.error_type,
                            'repair_status': 'REPAIR_SKIPPED',
                            'cached_decision': cached_decision.get('decision')
                        },
                        url=url,  # Phase 1: Required for tracking
                        context_type='template',  # Phase 1: Context for tracking
                        reference_type='lien_web'  # Phase 1: Reference type for tracking
                    )
                    continue

            # CRITICAL FIX: Only check for existing archives if the link is DEAD
            # This prevents adding archive parameters to healthy links
            if result.status != LinkStatus.DEAD:
                logger.info(f"LINK_NOT_DEAD_SKIP_REPAIR | url={url} | status={result.status.value}")

                # Add low-severity issue for REVIEW_REQUIRED and TEMPORARY_ERROR to ensure visibility
                if result.status in (LinkStatus.REVIEW_REQUIRED, LinkStatus.TEMPORARY_ERROR):
                    # Phase 1: Use _add_issue_with_tracking for parallel write
                    self._add_issue_with_tracking(
                        issue_type="dead_link",
                        description=f"Lien à surveiller ({result.status.value}) : {url}",
                        position=url_position,
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="low",
                        confidence=0.5,
                        extra={
                            'url': url,
                            'http_status_code': result.http_status_code,
                            'error_type': result.error_type,
                            'link_status': result.status.value,
                            'repair_status': result.status.value.upper()
                        },
                        url=url,  # Phase 1: Required for tracking
                        context_type='template',  # Phase 1: Context for tracking
                        reference_type='lien_web'  # Phase 1: Reference type for tracking
                    )

                # Link is healthy or non-dead - skip all repair logic including archive checks
                continue

            # Check for URL truncation before attempting repair
            # If this "dead" URL is a prefix of a healthy URL already seen, it's likely an extraction artifact
            healthy_prefix_match = self._check_url_truncation(url)
            if healthy_prefix_match:
                logger.warning(f"SKIP_REPAIR_URL_TRUNCATION | url={url} | healthy_prefix={healthy_prefix_match} | reason=extraction_artifact")
                # Phase 1: Use _add_issue_with_tracking for parallel write
                self._add_issue_with_tracking(
                    issue_type="dead_link",
                    description=f"URL tronquée détectée (artefact d'extraction) : {url} → {healthy_prefix_match}",
                    position=url_position,
                    original_text=match.group(0),
                    suggested_text=healthy_prefix_match,
                    severity="medium",
                    confidence=0.8,
                    extra={
                        'url': url,
                        'http_status_code': result.http_status_code,
                        'error_type': result.error_type,
                        'repair_status': 'URL_TRUNCATION_DETECTED',
                        'healthy_prefix': healthy_prefix_match
                    },
                    url=url,  # Phase 1: Required for tracking
                    context_type='template',  # Phase 1: Context for tracking
                    reference_type='lien_web'  # Phase 1: Reference type for tracking
                )
                continue

            # Check if this URL has an existing archive in the same template
            has_existing_archive = False
            existing_archive_url = None
            existing_archive_status = None

            template = self._get_cached_reference_template(content, url, url_position)
            if template and template.parameters:
                existing_archive_url = self._get_archive_url_param_any(template.parameters)
                existing_archive_date = self._get_archive_date_param_any(template.parameters)
                if existing_archive_url:
                    has_existing_archive = True
                    logger.info(f"EXISTING_ARCHIVE_DETECTED | url={url} | archive_url={existing_archive_url} | archive_date={existing_archive_date}")

                    # Check if the existing archive is valid
                    archive_check_result = self.link_checker.check_link(existing_archive_url)
                    existing_archive_status = archive_check_result.status

                    if existing_archive_status == LinkStatus.HEALTHY:
                        logger.info(f"EXISTING_ARCHIVE_VALID | url={url} | archive_url={existing_archive_url} | action=add_brise_le_parameter")
                        # Archive is valid - add brisé le= parameter to mark main link as dead
                        if template:
                            # Check if brisé le is already present
                            brise_le_variants = ('brisé le', 'brisé le', 'brise le', 'dead-url')
                            has_brise_le = False
                            for variant in brise_le_variants:
                                if variant in template.parameters:
                                    has_brise_le = True
                                    logger.info(f"BRISE_LE_ALREADY_PRESENT | url={url} | variant={variant}")
                                    break
                            
                            if not has_brise_le:
                                # Add brisé le= parameter with current date
                                from datetime import datetime
                                current_date = datetime.now().strftime('%Y-%m-%d')
                                
                                # Create a new template with brisé le parameter added
                                new_template = self.reference_template_helper.add_brise_le_parameter(
                                    template,
                                    current_date
                                )
                                
                                if new_template:
                                    # Create Issue for Corrector to apply the change
                                    if self._validate_template_replacement(content, content[:template.start_position] + new_template + content[template.end_position:], template, new_template):
                                        logger.info(f"BRISE_LE_ADDED | url={url} | brise_le={current_date}")
                                        
                                        # Phase 1: Use _add_issue_with_tracking for parallel write
                                        self._add_issue_with_tracking(
                                            issue_type="dead_link",
                                            description=f"Lien mort marqué comme brisé : {url} (archive: {existing_archive_url})",
                                            position=template.start_position,
                                            original_text=template.full_match,
                                            suggested_text=new_template,
                                            severity="high",
                                            confidence=1.0,
                                            extra={
                                                'url': url,
                                                'http_status_code': result.http_status_code,
                                                'error_type': result.error_type,
                                                'repair_status': 'BRISE_LE_ADDED',
                                                'existing_archive_url': existing_archive_url,
                                                'existing_archive_status': existing_archive_status.value,
                                                'brise_le_date': current_date
                                            },
                                            url=url,  # Phase 1: Required for tracking
                                            context_type='template',  # Phase 1: Context for tracking
                                            reference_type='lien_web',  # Phase 1: Reference type for tracking
                                            template_name=template.template_name  # Phase 1: Template name for tracking
                                        )
                                        continue
                            else:
                                # brisé le already present, just log the issue
                                logger.info(f"BRISE_LE_ALREADY_EXISTS | url={url} | action=skip")
                                # Phase 1: Use _add_issue_with_tracking for parallel write
                                self._add_issue_with_tracking(
                                    issue_type="dead_link",
                                    description=f"Lien mort avec archive valide (déjà marqué brisé) : {url} (archive: {existing_archive_url})",
                                    position=url_position,
                                    original_text=match.group(0),
                                    suggested_text=None,
                                    severity="medium",
                                    confidence=1.0,
                                    extra={
                                        'url': url,
                                        'http_status_code': result.http_status_code,
                                        'error_type': result.error_type,
                                        'repair_status': 'ARCHIVE_VALID_BRISE_LE_EXISTS',
                                        'existing_archive_url': existing_archive_url,
                                        'existing_archive_status': existing_archive_status.value
                                    },
                                    url=url,  # Phase 1: Required for tracking
                                    context_type='template',  # Phase 1: Context for tracking
                                    reference_type='lien_web',  # Phase 1: Reference type for tracking
                                    template_name=template.template_name if template else None  # Phase 1: Template name for tracking
                                )
                                continue
                        else:
                            # No template found, just log the issue
                            logger.warning(f"NO_TEMPLATE_FOR_ARCHIVE_VALID | url={url} | action=log_only")
                            # Phase 1: Use _add_issue_with_tracking for parallel write
                            self._add_issue_with_tracking(
                                issue_type="dead_link",
                                description=f"Lien mort avec archive valide (pas de template) : {url} (archive: {existing_archive_url})",
                                position=url_position,
                                original_text=match.group(0),
                                suggested_text=None,
                                severity="medium",
                                confidence=1.0,
                                extra={
                                    'url': url,
                                    'http_status_code': result.http_status_code,
                                    'error_type': result.error_type,
                                    'repair_status': 'ARCHIVE_VALID_NO_TEMPLATE',
                                    'existing_archive_url': existing_archive_url,
                                    'existing_archive_status': existing_archive_status.value
                                },
                                url=url,  # Phase 1: Required for tracking
                                context_type='template',  # Phase 1: Context for tracking
                                reference_type='lien_web'  # Phase 1: Reference type for tracking
                            )
                            continue
                    else:
                        logger.info(f"EXISTING_ARCHIVE_DEAD | url={url} | archive_url={existing_archive_url} | action=repair_archive_only")
                        # Archive is dead - try to find a new archive for the archive URL only
                        archive_repair_result = self._attempt_archive_fallback(existing_archive_url, url_position, archive_check_result, match, content)
                        if archive_repair_result and archive_repair_result.decision == RepairDecision.REPLACEMENT_CONFIRMED:
                            # Update only the archive URL in the template
                            new_archive_url = archive_repair_result.replacement_url
                            new_archive_date = archive_repair_result.details.get('archive_date')
                            provider = archive_repair_result.details.get('provider')

                            # Generate updated template with new archive URL
                            if template:
                                # Auto-fill |site= from the main link's domain if it was left empty
                                extra_site_params = self._get_site_parameter_if_missing(template, url)
                                if extra_site_params:
                                    # Create a new template with merged parameters (ReferenceTemplate is frozen)
                                    template = ReferenceTemplate(
                                        template_name=template.template_name,
                                        parameters={**template.parameters, **extra_site_params},
                                        full_match=template.full_match,
                                        start_position=template.start_position,
                                        end_position=template.end_position,
                                        is_supported=template.is_supported
                                    )

                                new_template = self.reference_template_helper.generate_archive_repair_template(
                                    template,
                                    new_archive_url,
                                    new_archive_date,
                                    url,
                                    assume_patch_deployed=self.assume_wikipedia_patch_deployed,
                                    provider=provider
                                )

                                # Create Issue for Corrector to apply instead of modifying content directly
                                if self._validate_template_replacement(content, content[:template.start_position] + new_template + content[template.end_position:], template, new_template):
                                    logger.info(f"ARCHIVE_ONLY_REPAIR_APPLIED | url={url} | old_archive={existing_archive_url} | new_archive={new_archive_url}")

                                    # Phase 1: Use _add_issue_with_tracking for parallel write
                                    self._add_issue_with_tracking(
                                        issue_type="dead_link",
                                        description=f"Archive morte remplacée : {existing_archive_url} → {new_archive_url}",
                                        position=template.start_position,
                                        original_text=template.full_match,
                                        suggested_text=new_template,
                                        severity="high",
                                        confidence=1.0,
                                        extra={
                                            'url': url,
                                            'old_archive_url': existing_archive_url,
                                            'new_archive_url': new_archive_url,
                                            'archive_date': new_archive_date,
                                            'provider': provider,
                                            'repair_status': 'ARCHIVE_ONLY_REPAIR'
                                        },
                                        url=url,  # Phase 1: Required for tracking
                                        context_type='template',  # Phase 1: Context for tracking
                                        reference_type='lien_web',  # Phase 1: Reference type for tracking
                                        template_name=template.template_name  # Phase 1: Template name for tracking
                                    )
                                    continue
                        # If archive repair failed, fall through to normal repair logic
                        # (handled below via the has_existing_archive guard)

            if has_existing_archive:
                # An archive parameter is present on this reference but neither the
                # "valid" nor the "repaired" branch above completed successfully
                # (e.g. archive was dead and no replacement archive could be found
                # or validated). Per policy: if a reference already carries an
                # archive-url, DeadLinkAnalyzer must never touch the main/original
                # URL — only the archive slot is ever a repair target for such
                # references. Log and move on instead of falling through into the
                # main-link repair logic below.
                logger.info(f"EXISTING_ARCHIVE_UNREPAIRABLE | url={url} | archive_url={existing_archive_url} | action=skip_main_link_repair_no_archive_fix")
                # Phase 1: Use _add_issue_with_tracking for parallel write
                self._add_issue_with_tracking(
                    issue_type="dead_link",
                    description=f"Lien mort avec archive morte, archive non réparable : {url} (archive: {existing_archive_url})",
                    position=url_position,
                    original_text=match.group(0),
                    suggested_text=None,
                    severity="high",
                    confidence=1.0,
                    extra={
                        'url': url,
                        'http_status_code': result.http_status_code,
                        'error_type': result.error_type,
                        'repair_status': 'ARCHIVE_UNREPAIRABLE',
                        'existing_archive_url': existing_archive_url,
                        'existing_archive_status': existing_archive_status.value if existing_archive_status else None
                    },
                    url=url,  # Phase 1: Required for tracking
                    context_type='template',  # Phase 1: Context for tracking
                    reference_type='lien_web',  # Phase 1: Reference type for tracking
                    template_name=template.template_name if template else None  # Phase 1: Template name for tracking
                )
                continue

            if result.status == LinkStatus.DEAD and self.enable_auto_repair:
                logger.info(f"REPLACEMENT_SEARCH | url={url}")

                redirect_start = time.time()
                redirect_result = self.redirect_finder.find_redirect(url)
                redirect_duration = time.time() - redirect_start

                if redirect_result:
                    logger.info(f"REPLACEMENT_CANDIDATE | url={url} | redirect_decision={redirect_result.decision.value} | redirect_url={redirect_result.redirected_url if redirect_result.redirected_url else 'N/A'} | duration={redirect_duration:.2f}s")
                else:
                    logger.info(f"REPLACEMENT_CANDIDATE | url={url} | redirect_decision=None | redirect_url=N/A | duration={redirect_duration:.2f}s")

                repair_result = None

                if redirect_result and redirect_result.decision.value == "valid_redirect":
                    logger.info(f"REPLACEMENT_VALIDATION | url={url} | candidate={redirect_result.redirected_url}")

                    content_result = self.content_verifier.verify_same_resource(url, redirect_result.redirected_url)

                    logger.info(f"REPLACEMENT_VALIDATION | url={url} | content_decision={content_result.decision.value} | domain_match={content_result.domain_match} | path_similarity={content_result.path_similarity:.2f} | title_match={content_result.title_match}")

                    logger.info(f"ARCHIVE_VERIFICATION | url={url} | candidate={redirect_result.redirected_url}")
                    archive_evidence = self.archive_provider.verify_content_match(url, redirect_result.redirected_url)

                    logger.info(f"ARCHIVE_VERIFICATION | url={url} | original_archive={archive_evidence['original_archive_available']} | candidate_archive={archive_evidence['candidate_archive_available']} | original_title={archive_evidence['original_title']} | candidate_title={archive_evidence['candidate_title']}")

                    repair_result = self.link_validator.validate_repair(
                        check_result=result,
                        redirect_result=redirect_result,
                        reference_title=archive_evidence.get('original_title'),
                        archive_evidence=archive_evidence
                    )

                    logger.info(f"REPAIR_DECISION | url={url} | decision={repair_result.decision.value} | reason={repair_result.reason}")

                    self._repair_cache[url] = {
                        'decision': repair_result.decision.value,
                        'replacement_url': repair_result.replacement_url,
                        'reason': repair_result.reason
                    }

                    # FIX (Bug 1): si le redirect a été REJETÉ (pas confirmé), on ne s'arrête
                    # plus ici — on retente une réparation via archive avant d'abandonner.
                    if repair_result.decision != RepairDecision.REPLACEMENT_CONFIRMED:
                        logger.info(f"REPAIR_REJECTED | url={url} | reason={repair_result.reason}")
                        # Phase 1: Use _add_issue_with_tracking for parallel write
                        self._add_issue_with_tracking(
                            issue_type="dead_link",
                            description=f"Lien mort détecté, redirect trouvé mais rejeté (preuves insuffisantes) : {url}",
                            position=url_position,
                            original_text=match.group(0),
                            suggested_text=None,
                            severity="high",
                            confidence=1.0,
                            extra={
                                'url': url,
                                'http_status_code': result.http_status_code,
                                'error_type': result.error_type,
                                'repair_status': 'REDIRECT_REJECTED',
                                'redirect_reason': repair_result.reason
                            },
                            url=url,  # Phase 1: Required for tracking
                            context_type='template',  # Phase 1: Context for tracking
                            reference_type='lien_web'  # Phase 1: Reference type for tracking
                        )

                        archive_repair_result = self._attempt_archive_fallback(url, url_position, result, match, content)
                        if archive_repair_result:
                            repair_result = archive_repair_result
                            self._repair_cache[url] = {
                                'decision': repair_result.decision.value,
                                'replacement_url': repair_result.replacement_url,
                                'reason': repair_result.reason
                            }
                        else:
                            repair_result = None  # rien à appliquer plus bas, déjà loggé
                else:
                    logger.info(f"ARCHIVE_FALLBACK | url={url} | reason=no_valid_redirect")

                    self._repair_cache[url] = {
                        'decision': 'REDIRECT_NOT_FOUND',
                        'replacement_url': None,
                        'reason': 'no_valid_redirect'
                    }

                    # Try archive fallback before adding the issue
                    repair_result = self._attempt_archive_fallback(url, url_position, result, match, content)
                    if repair_result:
                        self._repair_cache[url] = {
                            'decision': repair_result.decision.value,
                            'replacement_url': repair_result.replacement_url,
                            'reason': repair_result.reason
                        }

                    # Only add "dead link detected" issue if no successful repair will be made
                    if not (repair_result and repair_result.decision == RepairDecision.REPLACEMENT_CONFIRMED):
                        # Phase 1: Use _add_issue_with_tracking for parallel write
                        self._add_issue_with_tracking(
                            issue_type="dead_link",
                            description=f"Lien mort détecté, aucun redirect valide trouvé : {url}",
                            position=url_position,
                            original_text=match.group(0),
                            suggested_text=None,
                            severity="high",
                            confidence=1.0,
                            extra={
                                'url': url,
                                'http_status_code': result.http_status_code,
                                'error_type': result.error_type,
                                'repair_status': 'REDIRECT_NOT_FOUND'
                            },
                            url=url,  # Phase 1: Required for tracking
                            context_type='template',  # Phase 1: Context for tracking
                            reference_type='lien_web'  # Phase 1: Reference type for tracking
                        )

                if repair_result and repair_result.decision == RepairDecision.REPLACEMENT_CONFIRMED:
                    old_url = url
                    new_url = repair_result.replacement_url

                    # Check if this is a reference template repair (Lien web, article, ouvrage, etc.)
                    is_reference_template_repair = False
                    template_name = None
                    if repair_result.details and repair_result.details.get('is_reference_template'):
                        is_reference_template_repair = True
                        template_name = repair_result.details.get('template_name')
                        logger.info(f"REFERENCE_TEMPLATE_REPAIR | url={url} | template={template_name} | using_archive_template_format")

                    if is_reference_template_repair:
                        # Use reference template format with archive parameters
                        template = self._get_cached_reference_template(content, old_url, url_position)
                        if template:
                            # Check if template is supported
                            if not template.is_supported:
                                # Attempt partial safe repair: only modify URL and add archive parameters
                                # This preserves manual metadata (titre, auteur, éditeur, série, collection)
                                if repair_result and repair_result.decision == RepairDecision.REPLACEMENT_CONFIRMED:
                                    archive_url = repair_result.details.get('archive_url')
                                    archive_date = repair_result.details.get('archive_date')
                                    provider = repair_result.details.get('provider')

                                    if archive_url and archive_date:
                                        logger.info(f"PARTIAL_REPAIR_UNSUPPORTED_TEMPLATE | url={old_url} | template_name={template.template_name} | archive_url={archive_url}")
                                        # Use existing generate_archive_repair_template method
                                        # It will preserve all existing parameters and only add archive ones
                                        new_template = self.reference_template_helper.generate_archive_repair_template(
                                            template,
                                            archive_url,
                                            archive_date,
                                            old_url,
                                            assume_patch_deployed=False,  # Keep original URL as main link
                                            provider=provider
                                        )

                                        if new_template:
                                            # Phase 1: Use _add_issue_with_tracking for parallel write
                                            self._add_issue_with_tracking(
                                                issue_type="dead_link",
                                                description=f"Lien mort réparé partiellement (archive ajoutée) : {old_url} (template: {template.template_name})",
                                                position=template.start_position,
                                                original_text=template.full_match,
                                                suggested_text=new_template,
                                                severity="medium",
                                                confidence=0.8,
                                                extra={
                                                    'url': old_url,
                                                    'http_status_code': result.http_status_code,
                                                    'repair_status': 'PARTIAL_REPAIR_APPLIED',
                                                    'template_name': template.template_name,
                                                    'archive_url': archive_url,
                                                    'archive_date': archive_date,
                                                    'repair_type': 'partial_archive_only'
                                                },
                                                url=old_url,  # Phase 1: Required for tracking
                                                context_type='template',  # Phase 1: Context for tracking
                                                reference_type=template.template_name.lower(),  # Phase 1: Reference type for tracking
                                                template_name=template.template_name  # Phase 1: Template name for tracking
                                            )
                                            continue

                                # If no partial repair possible, mark for review
                                logger.warning(f"TEMPLATE_UNSUPPORTED_REPAIR | url={old_url} | template_name={template.template_name} | action=review_required")
                                # Phase 1: Use _add_issue_with_tracking for parallel write
                                self._add_issue_with_tracking(
                                    issue_type="dead_link",
                                    description=f"Lien mort détecté, template non supporté pour réparation automatique : {old_url} (template: {template.template_name})",
                                    position=url_position,
                                    original_text=match.group(0),
                                    suggested_text=None,
                                    severity="medium",
                                    confidence=0.7,
                                    extra={
                                        'url': old_url,
                                        'http_status_code': result.http_status_code,
                                        'error_type': result.error_type,
                                        'repair_status': 'REVIEW_REQUIRED',
                                        'template_name': template.template_name,
                                        'template_unsupported': True,
                                        'review_reason': 'unsupported_template_type',
                                        'supported_templates': list(self.reference_template_helper.KNOWN_TEMPLATE_NAMES.values())
                                    },
                                    url=old_url,  # Phase 1: Required for tracking
                                    context_type='template',  # Phase 1: Context for tracking
                                    reference_type=template.template_name.lower(),  # Phase 1: Reference type for tracking
                                    template_name=template.template_name  # Phase 1: Template name for tracking
                                )
                                continue

                            # Auto-fill |site= from the main link's domain if it was left empty
                            extra_site_params = self._get_site_parameter_if_missing(template, old_url)
                            if extra_site_params:
                                # Create a new template with merged parameters (ReferenceTemplate is frozen)
                                template = ReferenceTemplate(
                                    template_name=template.template_name,
                                    parameters={**template.parameters, **extra_site_params},
                                    full_match=template.full_match,
                                    start_position=template.start_position,
                                    end_position=template.end_position,
                                    is_supported=template.is_supported
                                )

                            new_template = self.reference_template_helper.generate_archive_repair_template(
                                template,
                                repair_result.details.get('archive_url'),
                                repair_result.details.get('archive_date'),
                                repair_result.details.get('original_url'),
                                assume_patch_deployed=self.assume_wikipedia_patch_deployed,
                                provider=repair_result.details.get('provider')
                            )

                            # Create Issue for Corrector to apply instead of modifying content directly
                            new_content = content[:template.start_position] + new_template + content[template.end_position:]

                            # Validate the replacement
                            if self._validate_template_replacement(content, new_content, template, new_template):
                                logger.info(f"REFERENCE_TEMPLATE_REPAIR_APPLIED | url={old_url} | template={template_name} | archive_url={new_url}")

                                # Track archive repair for internal links
                                archive_repairs.append({
                                    'original_url': old_url,
                                    'archive_url': repair_result.details.get('archive_url'),
                                    'archive_date': repair_result.details.get('archive_date'),
                                    'provider': repair_result.details.get('provider', 'WaybackMachine')
                                })

                                # Phase 1: Use _add_issue_with_tracking for parallel write
                                self._add_issue_with_tracking(
                                    issue_type="dead_link",
                                    description=f"Lien mort réparé avec format {{{{template_name}}}} : {old_url} → {new_url}",
                                    position=template.start_position,
                                    original_text=template.full_match,
                                    suggested_text=new_template,
                                    severity="high",
                                    confidence=1.0,
                                    extra={
                                        'url': url,
                                        'old_url': old_url,
                                        'new_url': new_url,
                                        'http_status_code': result.http_status_code,
                                        'repair_decision': repair_result.decision.value,
                                        'repair_type': f"{(template_name or 'unknown').lower()}_template",
                                        'template_name': template_name,
                                        'archive_url': repair_result.details.get('archive_url'),
                                        'archive_date': repair_result.details.get('archive_date'),
                                        'repair_status': 'REPAIR_APPLIED'
                                    },
                                    url=old_url,  # Phase 1: Required for tracking
                                    context_type='template',  # Phase 1: Context for tracking
                                    reference_type=template_name.lower() if template_name else 'lien_web',  # Phase 1: Reference type for tracking
                                    template_name=template_name  # Phase 1: Template name for tracking
                                )

                                # Don't update content - let Corrector apply the changes
                                # content = new_content

                                self._repair_cache[url] = {
                                    'decision': repair_result.decision.value,
                                    'replacement_url': new_url,
                                    'reason': repair_result.reason,
                                    'repair_type': f"{(template_name or 'unknown').lower()}_template"
                                }
                            else:
                                logger.warning(f"REFERENCE_TEMPLATE_REPAIR_REJECTED | url={url} | template={template_name} | reason=template_validation_failed")
                                # Fall back to simple URL replacement but with enhanced logging
                                self._apply_simple_url_replacement(content, old_url, new_url, url_position, result, repair_result, archive_repairs)
                        else:
                            # Check if there's actually a template around the URL but we couldn't parse it
                            # This prevents destructive bare-URL fallback for templates that exist but aren't recognized
                            template_bounds = self.reference_template_helper._find_enclosing_template_bounds(content, url_position)
                            if template_bounds:
                                logger.warning(f"TEMPLATE_FOUND_BUT_UNPARSABLE | url={url} | bounds={template_bounds} | action=review_required")
                                # Phase 1: Use _add_issue_with_tracking for parallel write
                                self._add_issue_with_tracking(
                                    issue_type="dead_link",
                                    description=f"Lien mort détecté, template présent mais non analysable : {url}",
                                    position=url_position,
                                    original_text=match.group(0),
                                    suggested_text=None,
                                    severity="medium",
                                    confidence=0.7,
                                    extra={
                                        'url': old_url,
                                        'http_status_code': result.http_status_code,
                                        'error_type': result.error_type,
                                        'repair_status': 'REVIEW_REQUIRED',
                                        'template_bounds': template_bounds,
                                        'review_reason': 'template_present_but_unparsable',
                                        'supported_templates': list(self.reference_template_helper.KNOWN_TEMPLATE_NAMES.values())
                                    },
                                    url=old_url,  # Phase 1: Required for tracking
                                    context_type='template',  # Phase 1: Context for tracking
                                    reference_type='unknown'  # Phase 1: Reference type for tracking
                                )
                            else:
                                logger.warning(f"REFERENCE_TEMPLATE_NOT_FOUND | url={url} | falling_back_to_simple_replacement")
                                # Fall back to simple URL replacement
                                self._apply_simple_url_replacement(content, old_url, new_url, url_position, result, repair_result, archive_repairs)
                    else:
                        # Simple URL replacement (not a {{Lien web}} template)
                        self._apply_simple_url_replacement(content, old_url, new_url, url_position, result, repair_result, archive_repairs)
                elif repair_result:
                    logger.info(f"REPAIR_REJECTED | url={url} | reason={repair_result.reason}")

            elif result.status == LinkStatus.DEAD and not self.enable_auto_repair:
                logger.info(f"REPAIR_REJECTED | url={url} | reason=AUTO_REPAIR_DISABLED")

                # Phase 1: Use _add_issue_with_tracking for parallel write
                self._add_issue_with_tracking(
                    issue_type="dead_link",
                    description=f"Lien mort détecté : {url} ({result.error_type})",
                    position=url_position,
                    original_text=match.group(0),
                    suggested_text=None,
                    severity="high",
                    confidence=1.0,
                    extra={
                        'url': url,
                        'http_status_code': result.http_status_code,
                        'error_type': result.error_type,
                        'link_status': result.status.value,
                        'repair_status': 'AUTO_REPAIR_DISABLED'
                    },
                    url=url,  # Phase 1: Required for tracking
                    context_type='template',  # Phase 1: Context for tracking
                    reference_type='lien_web'  # Phase 1: Reference type for tracking
                )
            elif result.status == LinkStatus.REVIEW_REQUIRED:
                logger.info(f"REVIEW_REQUIRED | url={url} | reason={result.error_type}")
                # Phase 1: Use _add_issue_with_tracking for parallel write
                self._add_issue_with_tracking(
                    issue_type="dead_link",
                    description=f"Lien nécessitant révision manuelle : {url} ({result.error_type})",
                    position=url_position,
                    original_text=match.group(0),
                    suggested_text=None,
                    severity="medium",
                    confidence=0.7,
                    extra={
                        'url': url,
                        'http_status_code': result.http_status_code,
                        'error_type': result.error_type,
                        'link_status': result.status.value,
                        'repair_status': 'REVIEW_REQUIRED'
                    },
                    url=url,  # Phase 1: Required for tracking
                    context_type='template',  # Phase 1: Context for tracking
                    reference_type='lien_web'  # Phase 1: Reference type for tracking
                )

        self.issues.sort(key=lambda i: i.position)

        # Don't store modified content - let Corrector apply changes
        # self.repaired_content = content

        # Count issue types for accurate summary - separate technical findings from actionable repairs
        issue_type_counts = {}
        actionable_repairs = 0
        manual_review = 0
        unresolved = 0

        for issue in self.issues:
            repair_status = issue.extra.get('repair_status', 'unknown')

            # Replace 'unknown' with diagnostic information
            if repair_status == 'unknown':
                # Try to infer from other fields
                if issue.suggested_text:
                    repair_status = 'REPAIR_AVAILABLE_BUT_UNKNOWN_REASON'
                elif issue.extra.get('link_status'):
                    repair_status = f"LINK_STATUS_{issue.extra.get('link_status').upper()}"
                else:
                    repair_status = 'DIAGNOSTIC_REQUIRED'
                # Update the issue extra for consistency
                issue.extra['repair_status'] = repair_status

            issue_type_counts[repair_status] = issue_type_counts.get(repair_status, 0) + 1

            # Categorize for clearer reporting
            if repair_status in ['REPAIR_APPLIED', 'SAFE_REPLACEMENT']:
                actionable_repairs += 1
            elif repair_status in ['REVIEW_REQUIRED', 'REDIRECT_REJECTED', 'AUTO_REPAIR_DISABLED']:
                manual_review += 1
            elif repair_status in ['unknown', 'DIAGNOSTIC_REQUIRED', 'REPAIR_AVAILABLE_BUT_UNKNOWN_REASON']:
                unresolved += 1

        # Log detailed summary with clear separation
        logger.info(f"DeadLinkAnalyzer completed - Technical findings: {len(self.issues)} issues")
        logger.info(f"DeadLinkAnalyzer completed - Actionable repairs: {actionable_repairs}, Manual review: {manual_review}, Unresolved: {unresolved}")
        logger.info(f"DeadLinkAnalyzer completed - Issues breakdown: {dict(issue_type_counts)} (checked {self._checks_count}/{total_urls} URLs)")

        skipped_urls = total_urls - self._checks_count
        if analysis_complete:
            logger.info(f"DeadLinkAnalyzer completed - found {len(self.issues)} issues (checked {self._checks_count}/{total_urls} URLs)")
        else:
            logger.warning(f"DeadLinkAnalyzer incomplete - found {len(self.issues)} issues (checked {self._checks_count}/{total_urls} URLs, {skipped_urls} skipped)")

        # Don't add internal links directly - let Corrector handle content
        # if archive_repairs:
        #     content = self._add_archive_internal_links(content, archive_repairs)

        # Don't store modified content - let Corrector apply changes
        # self.repaired_content = content

        return self.issues

    def _generate_archive_internal_link(self, original_url: str, archive_url: str, archive_date: str, provider: str) -> str:
        """
        Generate an internal link to the archive service for the corrected link.

        Delegates to InternalLinksWriter for link generation.
        """
        return self.internal_links_writer.generate_archive_internal_link(
            original_url, archive_url, archive_date, provider
        )

    def _add_archive_internal_links(self, content: str, archive_repairs: list) -> str:
        """
        Add internal links to archive services in the "Voir aussi" section.

        Delegates to InternalLinksWriter for link injection.
        """
        return self.internal_links_writer.add_archive_links(content, archive_repairs)

    def _get_cached_reference_template(self, content: str, url: str, url_position: int):
        """
        Get reference template with caching to avoid redundant lookups.

        Uses a cache key based on URL and position to avoid calling
        find_reference_template multiple times for the same URL.
        """
        cache_key = f"{url}:{url_position}"
        if cache_key not in self._template_cache:
            self._template_cache[cache_key] = self.reference_template_helper.find_reference_template(content, url, url_position)
        return self._template_cache[cache_key]

    def _check_url_truncation(self, dead_url: str) -> Optional[str]:
        """
        Check if a dead URL is a truncated version of a healthy URL already seen.

        If dead_url is a strict prefix of a URL already classified as HEALTHY
        in this run, it's likely an extraction artifact (premature truncation)
        rather than a genuinely dead link.

        Args:
            dead_url: The URL classified as dead.

        Returns:
            The healthy URL that is a prefix match, or None if no match found.
        """
        for checked_url, result in self._check_cache.items():
            if (checked_url != dead_url
                and checked_url.startswith(dead_url)
                and result.status == LinkStatus.HEALTHY):
                logger.warning(f"LIKELY_URL_TRUNCATION | dead_url={dead_url} | matches_healthy_prefix_of={checked_url}")
                return checked_url
        return None

    def _is_url_in_reference_scope(self, content: str, url: str, url_position: int) -> bool:
        """
        Vérifie si l'URL est dans le périmètre d'une référence (balise <ref> ou template de citation).

        True seulement si l'URL est dans le périmètre autorisé : à l'intérieur
        d'un <ref>...</ref>, ou dans un template de citation reconnu qui sert
        de source (Lien web, article, ouvrage, etc.). Toute URL hors de ce
        périmètre (Liens externes, Voir aussi, texte libre) est exclue.
        """
        import re
        for ref_match in re.finditer(r'<ref[^>]*>(.*?)</ref>', content, re.DOTALL):
            if ref_match.start() <= url_position < ref_match.end():
                return True

        template = self._get_cached_reference_template(content, url, url_position)
        return template is not None

    def _attempt_archive_fallback(self, url: str, url_position: int, result: LinkCheckResult, match, content: str) -> Optional[RepairResult]:
        """
        Try to find and validate a Wayback/Archive.org snapshot as a
        fallback repair. Returns a RepairResult with
        decision=REPLACEMENT_CONFIRMED on success, or None if no repair
        could be produced (an Issue has already been appended for every
        rejection path, matching prior behavior).
        """
        if not self._is_url_syntactically_valid(url):
            logger.warning(f"ARCHIVE_FALLBACK_CANCELLED | url={url} | reason=invalid_url_syntax")
            # Phase 1: Use _add_issue_with_tracking for parallel write
            self._add_issue_with_tracking(
                issue_type="dead_link",
                description=f"Lien mort détecté, syntaxe invalide (paramètres de template) : {url}",
                position=url_position,
                original_text=match.group(0),
                suggested_text=None,
                severity="high",
                confidence=1.0,
                extra={
                    'url': url,
                    'http_status_code': result.http_status_code,
                    'error_type': result.error_type,
                    'repair_status': 'INVALID_URL_SYNTAX'
                },
                url=url,  # Phase 1: Required for tracking
                context_type='template',  # Phase 1: Context for tracking
                reference_type='lien_web'  # Phase 1: Reference type for tracking
            )
            return None

        archive_result = self.archive_provider.check_archive(url)

        if not (archive_result and archive_result.archive_url):
            logger.info(f"ARCHIVE_FALLBACK_FAILED | url={url} | reason=no_archive_available")
            # Phase 1: Use _add_issue_with_tracking for parallel write
            self._add_issue_with_tracking(
                issue_type="dead_link",
                description=f"Lien mort détecté, aucune archive disponible : {url}",
                position=url_position,
                original_text=match.group(0),
                suggested_text=None,
                severity="high",
                confidence=1.0,
                extra={
                    'url': url,
                    'http_status_code': result.http_status_code,
                    'error_type': result.error_type,
                    'repair_status': 'ARCHIVE_NOT_FOUND'
                },
                url=url,  # Phase 1: Required for tracking
                context_type='template',  # Phase 1: Context for tracking
                reference_type='lien_web'  # Phase 1: Reference type for tracking
            )
            return None

        archive_url = archive_result.archive_url
        archive_date = archive_result.archive_date
        provider_name = archive_result.provider

        # Extract metadata from archive result if available (title, author, etc.)
        archive_metadata = archive_result.metadata if archive_result else {}
        archive_title = archive_metadata.get('title') if archive_metadata else None
        archive_author = archive_metadata.get('author') if archive_metadata else None

        logger.info(f"ARCHIVE_CANDIDATE | url={url} | archive_url={archive_url} | archive_date={archive_date} | provider={provider_name} | has_title={archive_title is not None} | has_author={archive_author is not None}")

        logger.info(f"FINAL_VERIFICATION | url={url} | re-checking before archive fallback")

        recheck_retry_config = RetryConfig(
            max_attempts=2,
            base_delay=2.0,
            max_delay=4.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        )
        recheck_retry_handler = RetryHandler(recheck_retry_config)

        try:
            final_check = recheck_retry_handler.execute_with_retry_on_result(
                lambda: self.link_checker.check_link(url),
                should_retry_result=lambda r: r.http_status_code in (503, 502, 429)
            )
        except Exception as e:
            logger.warning(f"FINAL_VERIFICATION_EXCEPTION | url={url} | error={e}")
            # If final check fails, assume link is still dead and proceed with archive fallback
            final_check = LinkCheckResult(
                url=url,
                status=LinkStatus.DEAD,
                error_type="VERIFICATION_EXCEPTION",
                retry_count=0,
                check_duration=0.0,
                confidence=0.0
            )

        if final_check.status != LinkStatus.DEAD:
            logger.warning(f"ARCHIVE_FALLBACK_CANCELLED | url={url} | original_status={final_check.status.value} | reason=original_url_not_actually_dead")
            return None

        logger.info(f"ARCHIVE_VERIFICATION | url={url} | archive_url={archive_url} | verifying_http_access")

        # Retry logic for archive verification with exponential backoff
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            max_delay=8.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retry_on_exceptions=(Exception,)
        )
        retry_handler = RetryHandler(retry_config)

        def verify_archive_access():
            return self.link_checker.check_link(archive_url)

        try:
            archive_check = retry_handler.execute_with_retry(verify_archive_access)
        except Exception as e:
            logger.warning(f"ARCHIVE_VERIFICATION_EXCEPTION | url={url} | archive_url={archive_url} | error={e}")
            archive_check = LinkCheckResult(
                url=archive_url,
                status=LinkStatus.UNKNOWN,
                error_type="VERIFICATION_EXCEPTION",
                retry_count=0,
                check_duration=0.0,
                confidence=0.0
            )

        # CRITICAL FIX: Only accept HEALTHY status for archives
        # Previously accepted HTTP 498 from web.archive.org, but this is too risky
        # 498 can indicate proxy issues, timeouts, or other problems that don't guarantee the archive is actually accessible
        # Also distinguish between service unavailability (503/502) and genuine content failure (404)
        if archive_check.status != LinkStatus.HEALTHY:
            # Distinguish between service errors and content failures
            if archive_check.http_status_code in (503, 502, 429):
                logger.warning(f"ARCHIVE_VERIFICATION_RETRY_EXHAUSTED | url={url} | archive_url={archive_url} | provider={provider_name} | status={archive_check.status.value} | http_status={archive_check.http_status_code} | reason=service_unavailable_after_retries")

                # Fallback: Try to verify via other providers that also found an archive
                logger.info(f"ARCHIVE_VERIFICATION_FALLBACK | url={url} | checking_other_providers")
                all_available_results = self.archive_provider.check_all_providers(url)

                # Filter out the current provider (already failed)
                other_providers = [r for r in all_available_results if r.provider != provider_name]

                if other_providers:
                    logger.info(f"ARCHIVE_VERIFICATION_FALLBACK | url={url} | found={len(other_providers)} alternative providers")

                    for alt_result in other_providers:
                        alt_provider = alt_result.provider
                        alt_archive_url = alt_result.archive_url
                        logger.info(f"ARCHIVE_VERIFICATION_FALLBACK | url={url} | attempting_verification_via={alt_provider} | archive_url={alt_archive_url}")

                        # Retry verification for alternative provider with backoff
                        retry_config = RetryConfig(
                            max_attempts=3,
                            base_delay=2.0,
                            max_delay=8.0,
                            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                            retry_on_exceptions=(Exception,)
                        )
                        retry_handler = RetryHandler(retry_config)

                        def verify_alt_access():
                            return self.link_checker.check_link(alt_archive_url)

                        try:
                            alt_check = retry_handler.execute_with_retry(verify_alt_access)
                        except Exception as e:
                            logger.warning(f"ARCHIVE_VERIFICATION_FALLBACK_EXCEPTION | url={url} | provider={alt_provider} | error={e}")
                            alt_check = LinkCheckResult(
                                url=alt_archive_url,
                                status=LinkStatus.UNKNOWN,
                                error_type="VERIFICATION_EXCEPTION",
                                retry_count=0,
                                check_duration=0.0,
                                confidence=0.0
                            )

                        if alt_check.status == LinkStatus.HEALTHY:
                            logger.info(f"ARCHIVE_VERIFICATION_FALLBACK_SUCCESS | url={url} | provider={alt_provider} | archive_url={alt_archive_url}")
                            # Use alternative provider's archive instead
                            archive_url = alt_archive_url
                            provider_name = alt_provider
                            archive_date = alt_result.archive_date
                            archive_check = alt_check  # Update archive_check to reflect successful verification
                            break  # Exit loop, use this successful provider
                        else:
                            logger.warning(f"ARCHIVE_VERIFICATION_FALLBACK_FAILED | url={url} | provider={alt_provider} | status={alt_check.status.value} | http_status={alt_check.http_status_code}")

                    # If we successfully switched to another provider, continue with normal flow
                    if archive_check.status != LinkStatus.HEALTHY:
                        # All providers failed - mark as review_required
                        logger.warning(f"ARCHIVE_VERIFICATION_ALL_PROVIDERS_FAILED | url={url} | providers_tried={len(all_available_results)}")
                        # Phase 1: Use _add_issue_with_tracking for parallel write
                        self._add_issue_with_tracking(
                            issue_type="dead_link",
                            description=f"Lien mort détecté, archive disponible mais tous les services de vérification indisponibles : {url}",
                            position=url_position,
                            original_text=match.group(0),
                            suggested_text=None,
                            severity="medium",
                            confidence=0.7,
                            extra={
                                'url': url,
                                'http_status_code': result.http_status_code,
                                'error_type': result.error_type,
                                'repair_status': 'REVIEW_REQUIRED',
                                'archive_url': archive_url,
                                'archive_http_status': archive_check.http_status_code,
                                'archive_status': archive_check.status.value,
                                'archive_provider': provider_name,
                                'review_reason': 'all_verification_providers_unavailable_after_retries'
                            },
                            url=url,  # Phase 1: Required for tracking
                            context_type='template',  # Phase 1: Context for tracking
                            reference_type='lien_web'  # Phase 1: Reference type for tracking
                        )
                        return None
                else:
                    # No alternative providers found - mark as review_required
                    logger.warning(f"ARCHIVE_VERIFICATION_NO_ALTERNATIVE_PROVIDERS | url={url}")
                    # Phase 1: Use _add_issue_with_tracking for parallel write
                    self._add_issue_with_tracking(
                        issue_type="dead_link",
                        description=f"Lien mort détecté, archive disponible mais service temporairement indisponible (pas d'alternative) : {url}",
                        position=url_position,
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="medium",
                        confidence=0.7,
                        extra={
                            'url': url,
                            'http_status_code': result.http_status_code,
                            'error_type': result.error_type,
                            'repair_status': 'REVIEW_REQUIRED',
                            'archive_url': archive_url,
                            'archive_http_status': archive_check.http_status_code,
                            'archive_status': archive_check.status.value,
                            'archive_provider': provider_name,
                            'review_reason': 'no_alternative_providers_available'
                        },
                        url=url,  # Phase 1: Required for tracking
                        context_type='template',  # Phase 1: Context for tracking
                        reference_type='lien_web'  # Phase 1: Reference type for tracking
                    )
                    return None
            else:
                logger.warning(f"ARCHIVE_VERIFICATION_FAILED | url={url} | archive_url={archive_url} | provider={provider_name} | status={archive_check.status.value} | http_status={archive_check.http_status_code} | reason=archive_not_healthy")
                # Genuine content failure - classify as ARCHIVE_NOT_ACCESSIBLE
                # Phase 1: Use _add_issue_with_tracking for parallel write
                self._add_issue_with_tracking(
                    issue_type="dead_link",
                    description=f"Lien mort détecté, archive non accessible : {url}",
                    position=url_position,
                    original_text=match.group(0),
                    suggested_text=None,
                    severity="high",
                    confidence=1.0,
                    extra={
                        'url': url,
                        'http_status_code': result.http_status_code,
                        'error_type': result.error_type,
                        'repair_status': 'ARCHIVE_NOT_ACCESSIBLE',
                        'archive_url': archive_url,
                        'archive_http_status': archive_check.http_status_code,
                        'archive_status': archive_check.status.value,
                        'archive_provider': provider_name
                    },
                    url=url,  # Phase 1: Required for tracking
                    context_type='template',  # Phase 1: Context for tracking
                    reference_type='lien_web'  # Phase 1: Reference type for tracking
                )
                return None

        if self._archive_content_looks_dead(archive_url):
            logger.warning(f"ARCHIVE_CONTENT_REJECTED | url={url} | archive_url={archive_url} | provider={provider_name} | reason=body_matches_not_found_markers")
            # Phase 1: Use _add_issue_with_tracking for parallel write
            self._add_issue_with_tracking(
                issue_type="dead_link",
                description=f"Lien mort détecté, archive trouvée mais suspecte (contenu type page introuvable) : {url}",
                position=url_position,
                original_text=match.group(0),
                suggested_text=None,
                severity="high",
                confidence=0.6,
                extra={
                    'url': url,
                    'http_status_code': result.http_status_code,
                    'error_type': result.error_type,
                    'repair_status': 'ARCHIVE_CONTENT_SUSPICIOUS',
                    'archive_url': archive_url,
                    'archive_provider': provider_name
                },
                url=url,  # Phase 1: Required for tracking
                context_type='template',  # Phase 1: Context for tracking
                reference_type='lien_web'  # Phase 1: Reference type for tracking
            )
            return None

        logger.info(f"ARCHIVE_VERIFIED | url={url} | archive_url={archive_url} | http_status={archive_check.http_status_code}")

        # Archive passed all checks - proceed with replacement
        logger.info(f"ARCHIVE_ACCEPTED | url={url} | archive_url={archive_url} | provider={provider_name} | confidence=high")

        # Check if this is a reference template repair (Lien web, article, ouvrage, etc.)
        # Use full content to find the template, not just the match
        template = self._get_cached_reference_template(content, url, url_position)
        is_reference_template = template is not None
        template_name = template.template_name if template else None

        repair_details = {
            'archive_url': archive_url,
            'archive_date': archive_date,
            'provider': provider_name,
            'is_reference_template': is_reference_template,
            'template_name': template_name,
            'is_lien_web_template': is_reference_template and template_name == 'Lien web',  # Backward compatibility
            'archive_title': archive_title,  # Title from archive metadata if available
            'archive_author': archive_author,  # Author from archive metadata if available
            'original_url': url
        }

        return RepairResult(
            original_url=url,
            decision=RepairDecision.REPLACEMENT_CONFIRMED,
            replacement_url=archive_url,
            reason=f"Archive fallback: using {provider_name} archive from {archive_date} (HTTP {archive_check.http_status_code})",
            details=repair_details
        )

    def _build_lien_web_template(self, mode: str, original_url: str, archive_url: str,
                                  archive_date: str, provider: Optional[str] = None,
                                  archive_title: Optional[str] = None,
                                  archive_author: Optional[str] = None,
                                  ref: Optional[BareUrlRef] = None,
                                  original_title: Optional[str] = None) -> Optional[str]:
        """
        Build a {{Lien web}} template with mode-specific behavior.

        Modes:
        - 'dead_link': For dead links in references (uses brisé le=)
        - 'external_links': For external links section (uses consulté le=, preserves original text)

        Args:
            mode: 'dead_link' or 'external_links'
            original_url: The original dead URL
            archive_url: The archive URL to use for repair
            archive_date: Archive date from provider (YYYYMMDDHHMMSS or YYYY-MM-DD)
            provider: Archive provider name (e.g., WaybackMachine, Arquivo.pt)
            archive_title: Title from archive metadata if available
            archive_author: Author from archive metadata if available
            ref: BareUrlRef for external_links mode (for text extraction)
            original_title: Original title from existing template (preserved over archive_title)

        Returns:
            A properly formatted template string, or None if essential data is missing
        """
        if not archive_url or not archive_date:
            logger.warning(f"TEMPLATE_BUILD_FAILED | url={original_url[:80]} | mode={mode} | reason=missing_essential_data")
            return None

        # Normalize archive date to YYYY-MM-DD format using datetime.strptime with multiple formats
        from datetime import datetime
        normalized_date = archive_date
        date_formats = [
            '%Y%m%d%H%M%S',  # Wayback Machine full timestamp
            '%Y%m%d',         # YYYYMMDD
            '%Y-%m-%d',       # YYYY-MM-DD
            '%Y%m%dT%H%M%S',  # ISO format with T
            '%Y%m%dT%H%M%SZ', # ISO format with Z
        ]

        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(archive_date, fmt)
                normalized_date = parsed_date.strftime('%Y-%m-%d')
                break
            except (ValueError, TypeError):
                continue

        # Extract site name from URL for |site= parameter
        site_value = self._extract_site_name_from_url(original_url)

        # Build template parts
        template_parts = ["Lien web"]

        if mode == 'external_links' and ref:
            # External links mode: preserve original text and parenthetical notes
            original_text = None
            parenthetical_notes = []

            if ref.context_text:
                import re
                # Improved regex to handle nested brackets
                bracket_match = re.search(r'\[([^\[\]]+(?:\[[^\[\]]*\][^\[\]]*)*)\]', ref.context_text)
                if bracket_match:
                    bracket_content = bracket_match.group(1)
                    parts = bracket_content.split()
                    if len(parts) >= 2:
                        for part in parts:
                            if part.startswith('http'):
                                text_parts = [p for p in parts if p != part]
                                original_text = ' '.join(text_parts)
                                break

                # If no bracketed text, try line context
                if not original_text:
                    url_pos = ref.context_text.find(original_url)
                    if url_pos > 0:
                        before_text = ref.context_text[:url_pos].strip()
                        before_text = before_text.replace('*', '').replace('#', '').strip()
                        if before_text and len(before_text) > 2:
                            original_text = before_text

                # Extract parenthetical notes
                url_pos = ref.context_text.find(original_url)
                if url_pos >= 0:
                    after_text = ref.context_text[url_pos + len(original_url):].strip()
                    paren_matches = re.findall(r'\(([^)]+)\)', after_text)
                    if paren_matches:
                        # Filter out duplicate parenthetical notes that might already be in original_text
                        for note in paren_matches:
                            note_pattern = f'({note})'
                            if note_pattern not in original_text:
                                parenthetical_notes.append(note)

            # Use original text as titre, with unique parenthetical notes
            if original_text:
                if parenthetical_notes:
                    original_text = original_text + ' ' + ' '.join(f'({note})' for note in parenthetical_notes)
                template_parts.append(f"titre={original_text}")
            else:
                # Fallback to title extraction
                title_value = archive_title if archive_title else self._extract_title_from_url(original_url)
                if not title_value:
                    title_value = site_value or "Page web"
                if parenthetical_notes:
                    title_value = title_value + ' ' + ' '.join(f'({note})' for note in parenthetical_notes)
                template_parts.append(f"titre={title_value}")

            # Use consulté le instead of brisé le for external links
            current_date = datetime.now().strftime('%Y-%m-%d')
            template_parts.append(f"consulté le={current_date}")

        else:
            # Dead link mode: prioritize original title over archive title
            title_value = original_title if original_title else archive_title
            if not title_value:
                title_value = self._extract_title_from_url(original_url)
            if not title_value:
                title_value = site_value or "Page web"

            # Avoid duplication: if archive_title is similar to original_title, use original only
            if original_title and archive_title:
                # Check if archive_title is a substring of original_title or vice versa
                original_lower = original_title.lower().strip()
                archive_lower = archive_title.lower().strip()
                if (archive_lower in original_lower or original_lower in archive_lower) and len(original_lower) > 5:
                    # Use the longer, more complete title
                    title_value = original_title if len(original_title) >= len(archive_title) else archive_title
                    logger.info(f"TITLE_DUPLICATION_AVOIDED | original={original_title[:50]} | archive={archive_title[:50]} | selected={title_value[:50]}")

            # Add author if available
            if archive_author:
                template_parts.append(f"auteur={archive_author}")

            # Use brisé le for dead links
            current_date = datetime.now().strftime('%Y-%m-%d')
            template_parts.append(f"brisé le={current_date}")

        # Common parameters for both modes
        template_parts.append(f"url={original_url}")
        template_parts.append(f"archive-url={archive_url}")
        template_parts.append(f"archive-date={normalized_date}")

        if site_value:
            template_parts.append(f"site={site_value}")

        # Construct template string
        template_str = "{{" + " | ".join(template_parts) + "}}"

        logger.info(f"TEMPLATE_BUILT | url={original_url[:80]} | mode={mode} | template={template_str[:120]}")
        return template_str

    def _apply_simple_url_replacement(self, content: str, old_url: str, new_url: str,
                                      url_position: int, result: LinkCheckResult,
                                      repair_result: RepairResult, archive_repairs: list) -> str:
        """
        Apply simple URL replacement or convert bare URL to {{Lien web}} template.
        Args:
            content: Wikitext content
            old_url: Original URL to replace
            new_url: New URL to replace with
            url_position: Position of URL in content
            result: Link check result
            repair_result: Repair result with decision
            archive_repairs: List to track archive repairs for internal links
        Returns:
            Updated content after replacement
        """
        # Try to convert bare URL to proper {{Lien web}} template
        try:
            # Check if this URL is in the "Liens externes" section - apply dedicated logic
            import re
            external_links_match = re.search(r'==\s*[Ll]iens externes\s*==', content)
            is_external_links_section = external_links_match and url_position > external_links_match.start()

            # Check if this URL is already in a reference template (Lien web, article, ouvrage, etc.)
            # If it is, we should NOT convert it to a bare URL template - it already has a template
            template = self._get_cached_reference_template(content, old_url, url_position)
            if template:
                logger.info(f"URL already in reference template {template.template_name}, skipping bare URL conversion: {old_url[:80]}")
                return content

            # Check if this URL is part of a formatted academic reference (with language templates, volume/issue templates, etc.)
            # These should NOT be converted to {{Lien web}} templates as they already have proper formatting
            # Look for common academic reference patterns around the URL
            context_start = max(0, url_position - 200)
            context_end = min(len(content), url_position + 200)
            context = content[context_start:context_end]
            
            # Check for academic reference indicators
            academic_patterns = [
                r'\{\{(en|es|de|fr|it|pt|gl|ca|ru|zh|ja)\}\}',  # Language templates
                r'\{\{vol\.\|',  # Volume template
                r'\{\{n[°o]\|',  # Number template (n° or no)
                r'\{\{p\.\|',  # Page template
                r'\{\{ISBN\|',  # ISBN
                r'\{\{OCLC\|',  # OCLC
                r'\{\{ISSN\|',  # ISSN
                r'\{\{DOI\|',  # DOI
                r'\[\[.*?\]\]',  # Wikilinks (publishers, journals)
            ]
            
            for pattern in academic_patterns:
                if re.search(pattern, context, re.IGNORECASE):
                    logger.info(f"URL appears to be in a formatted academic reference (matched {pattern}), skipping bare URL conversion: {old_url[:80]}")
                    return content

            # Find bare URLs in content
            bare_refs = self.bare_url_helper.find_bare_urls(content)

            # Find if this URL is a bare URL
            matching_ref = None
            for ref in bare_refs:
                if ref.dead_url == old_url and ref.dead_url_start == url_position:
                    matching_ref = ref
                    break

            if matching_ref:
                # Convert to proper Wikipedia template
                archive_url = repair_result.details.get('archive_url', new_url)
                archive_date = repair_result.details.get('archive_date')
                provider = repair_result.details.get('provider')
                archive_title = repair_result.details.get('archive_title')  # Title from archive metadata
                archive_author = repair_result.details.get('archive_author')  # Author from archive metadata

                if is_external_links_section:
                    # Dedicated logic for Liens externes section:
                    # - No brisé le=
                    # - Keep consulté le=
                    # - Preserve original link text/titre over archive title
                    # - Preserve parenthetical notes
                    template_str = self._build_lien_web_template(
                        mode='external_links',
                        original_url=old_url,
                        archive_url=archive_url,
                        archive_date=archive_date,
                        provider=provider,
                        archive_title=archive_title,
                        archive_author=archive_author,
                        ref=matching_ref
                    )
                else:
                    # Standard logic for references section
                    # Auto-fill |site= from the main link's domain when building a
                    # brand-new {{Lien web}} template, since a bare URL has no
                    # existing |site= to preserve. Left as None (unchanged) if the
                    # domain can't be derived, so callers relying on extra_params
                    # being None for "no extra info" keep working as before.
                    site_value = self._extract_site_name_from_url(old_url)
                    extra_params = {'site': site_value} if site_value else None

                    # Add author if available from archive metadata
                    if archive_author:
                        if extra_params is None:
                            extra_params = {}
                        extra_params['auteur'] = archive_author

                    # Try to convert to template with validation
                    template_str = self.bare_url_helper.build_repaired_reference_template(
                        matching_ref,
                        archive_url=archive_url,
                        archive_date=archive_date,
                        title_hint=archive_title,  # Use archive title if available
                        provider=provider,
                        template_name='Lien web',  # Default, can be enhanced with context detection
                        extra_params=extra_params,  # Can be enhanced with author detection
                        template_helper=self.reference_template_helper
                    )

                if template_str:
                    logger.info(f"BARE_URL_CONVERTED_TO_TEMPLATE | url={old_url[:80]} | template={template_str[:120]}")
                    # Extract the actual text to replace (URL + trailing context)
                    original_text = content[matching_ref.dead_url_start:matching_ref.replacement_end]
                    self._add_repair_issue(
                        old_url=old_url,
                        new_url=archive_url,
                        repair_type='bare_url_to_template',
                        url_position=matching_ref.dead_url_start,
                        result=result,
                        repair_result=repair_result,
                        archive_repairs=archive_repairs,
                        archive_url=archive_url,
                        archive_date=archive_date,
                        provider=provider,
                        original_text=original_text,
                        suggested_text=template_str,
                        position=matching_ref.dead_url_start,
                        context_type='bare_url',  # Phase 1: Context for tracking
                        reference_type='lien_web',  # Phase 1: Reference type for tracking
                        template_name='Lien web'  # Phase 1: Template name for tracking
                    )
                    return content
                else:
                    # Template conversion failed validation - build minimal template as fallback
                    # FIX: Instead of falling back to raw URL replacement, build a minimal {{Lien web}} template
                    logger.info(f"BARE_URL_CONVERSION_FAILED | url={old_url[:80]} | building_minimal_template_fallback")
                    
                    # Build minimal {{Lien web}} template with essential parameters
                    # Try to extract original title from template if available
                    original_title = self._get_original_title(template)
                    
                    minimal_template = self._build_lien_web_template(
                        mode='dead_link',
                        original_url=old_url,
                        archive_url=archive_url,
                        archive_date=archive_date,
                        provider=provider,
                        archive_title=repair_result.details.get('archive_title'),
                        archive_author=repair_result.details.get('archive_author'),
                        original_title=original_title
                    )
                    
                    if minimal_template:
                        logger.info(f"MINIMAL_TEMPLATE_APPLIED | url={old_url[:80]} | template={minimal_template[:120]}")
                        # Extract the actual text to replace (URL + trailing context)
                        original_text = content[matching_ref.dead_url_start:matching_ref.replacement_end]
                        self._add_repair_issue(
                            old_url=old_url,
                            new_url=archive_url,
                            repair_type='minimal_lien_web_template',
                            url_position=matching_ref.dead_url_start,
                            result=result,
                            repair_result=repair_result,
                            archive_repairs=archive_repairs,
                            archive_url=archive_url,
                            archive_date=archive_date,
                            provider=provider,
                            original_text=original_text,
                            suggested_text=minimal_template,
                            position=matching_ref.dead_url_start,
                            context_type='bare_url',  # Phase 1: Context for tracking
                            reference_type='lien_web',  # Phase 1: Reference type for tracking
                            template_name='Lien web'  # Phase 1: Template name for tracking
                        )
                        return content
                    else:
                        # Even minimal template construction failed - skip this URL
                        logger.warning(f"MINIMAL_TEMPLATE_CONSTRUCTION_FAILED | url={old_url[:80]} | falling_back_to_raw_url")
                        return content
        except Exception as e:
            logger.warning(f"BARE_URL_CONVERSION_FAILED | url={old_url} | error={e}")

        # If we have archive information but bare URL conversion failed, try minimal template construction
        # This handles cases where the URL wasn't detected as a bare URL but we still have archive data
        if repair_result and repair_result.details:
            archive_url = repair_result.details.get('archive_url', new_url)
            archive_date = repair_result.details.get('archive_date')
            provider = repair_result.details.get('provider')
            
            if archive_url and archive_date:
                logger.info(f"ATTEMPTING_MINIMAL_TEMPLATE_FOR_NON_BARE_URL | url={old_url[:80]}")
                # Try to extract original title from template if available
                template = self._get_cached_reference_template(content, old_url, url_position)
                original_title = self._get_original_title(template)
                
                minimal_template = self._build_lien_web_template(
                    mode='dead_link',
                    original_url=old_url,
                    archive_url=archive_url,
                    archive_date=archive_date,
                    provider=provider,
                    archive_title=repair_result.details.get('archive_title'),
                    archive_author=repair_result.details.get('archive_author'),
                    original_title=original_title
                )
                
                if minimal_template:
                    logger.info(f"MINIMAL_TEMPLATE_APPLIED_FOR_NON_BARE_URL | url={old_url[:80]} | template={minimal_template[:120]}")
                    self._add_repair_issue(
                        old_url=old_url,
                        new_url=archive_url,
                        repair_type='minimal_lien_web_template',
                        url_position=url_position,
                        result=result,
                        repair_result=repair_result,
                        archive_repairs=archive_repairs,
                        archive_url=archive_url,
                        archive_date=archive_date,
                        provider=provider,
                        original_text=old_url,
                        suggested_text=minimal_template,
                        context_type='template',  # Phase 1: Context for tracking
                        reference_type='lien_web',  # Phase 1: Reference type for tracking
                        template_name='Lien web'  # Phase 1: Template name for tracking
                    )
                    return content

        # Fallback: build a minimal {{Lien web}} template even if we have minimal data
        # This ensures we always produce a proper template instead of raw URLs
        logger.info(f"BUILDING_FALLBACK_TEMPLATE | url={old_url[:80]}")
        
        # Try to get archive info from repair_result if available
        archive_url = None
        archive_date = None
        provider = None
        
        if repair_result and repair_result.details:
            archive_url = repair_result.details.get('archive_url', new_url)
            archive_date = repair_result.details.get('archive_date')
            provider = repair_result.details.get('provider')
        
        # If no archive info, use new_url as archive_url and generate a date
        if not archive_url:
            archive_url = new_url
        if not archive_date:
            # Use current date as fallback
            from datetime import datetime
            archive_date = datetime.now().strftime('%Y-%m-%d')
        
        # Build minimal template
        # Try to extract original title from template if available
        template = self._get_cached_reference_template(content, old_url, url_position)
        original_title = self._get_original_title(template)
        
        minimal_template = self._build_lien_web_template(
            mode='dead_link',
            original_url=old_url,
            archive_url=archive_url,
            archive_date=archive_date,
            provider=provider,
            archive_title=repair_result.details.get('archive_title') if repair_result and repair_result.details else None,
            archive_author=repair_result.details.get('archive_author') if repair_result and repair_result.details else None,
            original_title=original_title
        )
        
        if minimal_template:
            logger.info(f"FALLBACK_TEMPLATE_APPLIED | url={old_url[:80]} | template={minimal_template[:120]}")
            self._add_repair_issue(
                old_url=old_url,
                new_url=archive_url,
                repair_type='minimal_lien_web_template',
                url_position=url_position,
                result=result,
                repair_result=repair_result,
                archive_repairs=archive_repairs,
                archive_url=archive_url,
                archive_date=archive_date,
                provider=provider,
                original_text=old_url,
                suggested_text=minimal_template,
                context_type='bare_url',  # Phase 1: Context for tracking
                reference_type='lien_web',  # Phase 1: Reference type for tracking
                template_name='Lien web'  # Phase 1: Template name for tracking
            )
            logger.info(f"REPAIR_APPLIED | url={old_url} | new_url={new_url}")

            if repair_result:
                self._repair_cache[old_url] = {
                    'decision': repair_result.decision.value,
                    'replacement_url': new_url,
                    'reason': repair_result.reason,
                    'repair_type': 'simple_url'
                }

            return content

        # Ultimate fallback: simple URL replacement (should rarely reach here)
        logger.warning(f"ULTIMATE_FALLBACK_TO_RAW_URL | url={old_url[:80]}")
        replacement_result = self.safe_url_replacer.replace_exact_occurrence(
            content, old_url, new_url, url_position
        )

        if replacement_result.success:
            logger.info(f"REPAIR_DIFF_VALIDATED | url={old_url} | changed_fields=url | other_changes=0")
            self._add_repair_issue(
                old_url=old_url,
                new_url=new_url,
                repair_type='simple_url',
                url_position=url_position,
                result=result,
                repair_result=repair_result,
                archive_repairs=archive_repairs,
                context_type='template',  # Phase 1: Context for tracking
                reference_type='lien_web',  # Phase 1: Reference type for tracking
                template_name='Lien web'  # Phase 1: Template name for tracking
            )
            logger.info(f"REPAIR_APPLIED | url={old_url} | new_url={new_url}")

            if repair_result:
                self._repair_cache[old_url] = {
                    'decision': repair_result.decision.value,
                    'replacement_url': new_url,
                    'reason': repair_result.reason,
                    'repair_type': 'simple_url'
                }

            return content
        else:
            logger.warning(f"REPAIR_DIFF_REJECTED | url={old_url} | reason={replacement_result.reason}")
            return content

    def _validate_template_replacement(self, old_content: str, new_content: str,
                                       old_template, new_template: str) -> bool:
        """
        Validate that template replacement is safe and minimal.

        Delegates to TemplateReplacementValidator for validation logic.
        """
        is_valid, error_msg = self.template_validator.validate(
            old_content, new_content, 
            old_template.start_position, old_template.end_position, 
            new_template
        )
        return is_valid