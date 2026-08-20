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
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import BaseAnalyzer, Issue
from ..utils.api_throttler import get_global_throttler
from ..utils.link_checker import LinkStatus, LinkCheckResult, LinkChecker
from ..utils.redirect_finder import RedirectFinder, RedirectResult
from ..utils.link_validator import LinkValidator, RepairDecision, RepairResult
from ..utils.content_verifier import ContentVerifier
from ..utils.retry_handler import RetryHandler, RetryConfig, RetryStrategy
from ..utils.safe_url_replacer import SafeURLReplacer
from ..utils.archive_provider import ArchiveProvider
# CandidateFinder currently unused - reserved for future multi-strategy candidate search
# from ..utils.candidate_finder import CandidateFinder

logger = logging.getLogger(__name__)


class DeadLinkAnalyzer(BaseAnalyzer):
    """
    Dead Link Analyzer - Ultra-Simple, Single-Objective Version.

    Replaces dead external links with new URLs of the same source.
    """

    DEFAULT_TIMEOUT = 10
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_MAX_CHECKS_PER_ARTICLE = 50

    # Whitelist of valid URL characters; wikitext delimiters |{}[] are
    # intentionally excluded so a URL match stops before them instead of
    # swallowing trailing template syntax (e.g. "url|consulté le=..." or
    # "[url texte]").
    # FIX: The pattern now requires that if '%' appears, it must be followed
    # by exactly 2 hexadecimal digits (valid percent-encoding). This prevents
    # the regex from swallowing template delimiters like '%/langue=it' that were
    # being incorrectly included in URL matches.
    # FIX: Optimized to avoid catastrophic backtracking by simplifying the pattern
    # and removing nested quantifiers that cause exponential backtracking.
    URL_PATTERN = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=%]+', re.IGNORECASE)

    # Best-effort markers indicating a page body is a "not found" page
    # even though the HTTP status was 200 (soft-404). Not exhaustive by
    # design: this is a defense-in-depth check on top of the HTTP status
    # check, not a replacement for it. FR + EN covers the two languages
    # observed so far in practice.
    NOT_FOUND_MARKERS = [
        'page non-trouvée', 'page non trouvée', "n'est pas disponible à l'adresse",
        'contenu introuvable', 'page introuvable',
        'page not found', '404 not found', 'this page does not exist',
        "the page you requested could not be found",
    ]

    def __init__(self, name: str = None,
                 timeout: int = None,
                 max_retries: int = None,
                 max_checks_per_article: int = None):
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
            else getattr(self, 'timeout', self.DEFAULT_TIMEOUT)
        )
        self.max_retries = (
            max_retries if max_retries is not None
            else getattr(self, 'max_retries', self.DEFAULT_MAX_RETRIES)
        )
        self.max_checks_per_article = (
            max_checks_per_article if max_checks_per_article is not None
            else getattr(self, 'max_checks_per_article', self.DEFAULT_MAX_CHECKS_PER_ARTICLE)
        )

        self.api_throttler = get_global_throttler()
        self.link_checker = LinkChecker(timeout=self.timeout, max_retries=self.max_retries)
        self.redirect_finder = RedirectFinder(timeout=self.timeout)
        # Pass shared LinkChecker to LinkValidator to respect caching and rate limits
        self.link_validator = LinkValidator(link_checker=self.link_checker)
        self.content_verifier = ContentVerifier()
        self.safe_url_replacer = SafeURLReplacer()
        self.archive_provider = ArchiveProvider()
        # CandidateFinder currently unused - reserved for future multi-strategy candidate search
        # self.candidate_finder = CandidateFinder(timeout=self.timeout)

        # enable_auto_repair is loaded from config in _load_config().
        # Default to True if not specified in config.
        self.enable_auto_repair = getattr(self, 'enable_auto_repair', True)

        self._check_cache: Dict[str, LinkCheckResult] = {}
        self._repair_cache: Dict[str, Dict[str, Any]] = {}
        self._checks_count = 0

    def _load_config(self) -> None:
        try:
            from pathlib import Path
            import yaml

            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and 'dead_links_analyzer' in config:
                        analyzer_config = config['dead_links_analyzer']
                        if 'timeout' in analyzer_config:
                            self.timeout = analyzer_config['timeout']
                        if 'max_retries' in analyzer_config:
                            self.max_retries = analyzer_config['max_retries']
                        if 'max_checks_per_article' in analyzer_config:
                            self.max_checks_per_article = analyzer_config['max_checks_per_article']
                        if 'enable_auto_repair' in analyzer_config:
                            self.enable_auto_repair = analyzer_config['enable_auto_repair']
                        logger.info(
                            f"Loaded config: timeout={self.timeout}s, max_retries={self.max_retries}, "
                            f"max_checks={self.max_checks_per_article}, auto_repair={self.enable_auto_repair}"
                        )
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

    def get_analyzer_name(self) -> str:
        return "DeadLinkAnalyzer"

    def _is_url_syntactically_valid(self, url: str) -> bool:
        """
        Check if URL is syntactically valid before attempting network requests.
        """
        if '|' in url or '{' in url or '}' in url or '[' in url or ']' in url:
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=contains_template_delimiters")
            return False

        if url.endswith('|') or url.endswith('='):
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=ends_with_delimiter")
            return False

        # FIX: Reject URLs ending with '%' (incomplete percent-encoding)
        # This catches cases where the regex might have stopped at '%/langue=it%'
        if url.endswith('%'):
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=ends_with_percent")
            return False

        # FIX: Validate that all percent-encoding sequences are valid
        # Each '%' must be followed by exactly 2 hexadecimal digits
        import re
        # Find all % sequences and validate they're followed by 2 hex digits
        invalid_percent = re.search(r'%(?![0-9A-Fa-f]{2})', url)
        if invalid_percent:
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=invalid_percent_encoding")
            return False

        if not url.startswith(('http://', 'https://')):
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=invalid_scheme")
            return False

        return True

    def _is_archive_url(self, url: str) -> bool:
        archive_domains = [
            'web.archive.org',
            'archive.org',
            'webcache.googleusercontent.com',
            'arquivo.pt',
            'archive.today',
            'archive.is'
        ]

        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower() in archive_domains

    # FIX: the previous implementation used urlparse(archive_url).path
    # and split on '/'. Since the embedded original URL's own query
    # string ("?ref=doi") is parsed as the *outer* URL's query by
    # urlparse (there's only one '?' in the whole string and it belongs
    # to the inner URL), everything after '?' was silently dropped.
    # That broke archive/original pairing for any reference using a
    # query string, which is common (DOI links, CMS links, etc.).
    # This version works directly on the raw string and never invokes
    # urlparse on the embedded URL, so query strings and fragments are
    # preserved exactly as written.
    _ARCHIVE_ORIGINAL_RE = re.compile(r'/web/\d+[a-zA-Z]*/(https?://.+)$')

    def _extract_original_url_from_archive(self, archive_url: str) -> Optional[str]:
        """
        Extract the original URL from an archive URL, preserving any
        query string or fragment on the embedded original URL.
        """
        if 'web.archive.org' not in archive_url.lower():
            return None

        match = self._ARCHIVE_ORIGINAL_RE.search(archive_url)
        if match:
            return match.group(1)
        return None

    def _should_skip_archive_url(self, archive_url: str, content: str, archive_position: int) -> bool:
        original_url = self._extract_original_url_from_archive(archive_url)
        if not original_url:
            return False

        if original_url in self._check_cache:
            original_result = self._check_cache[original_url]
            if original_result.status.value == "HEALTHY":
                logger.info(f"ARCHIVE_SKIP | archive_url={archive_url} | original_url={original_url} | reason=ORIGINAL_HEALTHY")
                return True

        return False

    def _archive_content_looks_dead(self, archive_url: str) -> bool:
        """
        Best-effort safety net for archive-fallback repairs.

        A Wayback snapshot can return HTTP 200 (checked via HEAD
        upstream) while the stored body is itself an already-dead
        "page not found" page — a soft-404 that was already broken at
        capture time. A HEAD request has no body, so the HTTP-status
        check alone cannot see this; a small GET + keyword check is
        the only way to catch it without a full content-diff pipeline.

        This is deliberately conservative and imperfect: false
        negatives are expected (some soft-404 pages won't match any
        marker). It exists to catch the demonstrated failure case
        (an archived CAIRN "Page non-trouvée" being auto-applied as a
        confirmed repair), not to be a general soft-404 detector. Any
        failure to fetch/parse is treated as "not obviously dead" so
        this heuristic can only ever block a repair, never force one
        through when the HTTP check itself failed.
        """
        try:
            import urllib.request

            request = urllib.request.Request(
                archive_url,
                headers={'User-Agent': 'WikipediaMaintenanceTool/1.0 (Content Sanity Check)'},
                method='GET'
            )
            context = urllib.request.ssl.create_default_context()
            with urllib.request.urlopen(request, timeout=self.timeout, context=context) as response:
                chunk = response.read(20000).decode('utf-8', errors='ignore').lower()

            return any(marker in chunk for marker in self.NOT_FOUND_MARKERS)

        except Exception as e:
            logger.warning(f"ARCHIVE_CONTENT_CHECK_FAILED | url={archive_url} | error={e}")
            return False

    def analyze(self, content: str) -> List[Issue]:
        self.clear_issues()

        if not content:
            return self.issues

        # Clear both caches to ensure fresh analysis per article
        # This prevents cross-article cache pollution where a link that was dead in one article
        # but healthy in another would get incorrectly replaced with an archive
        self._check_cache.clear()
        self._repair_cache.clear()
        self._checks_count = 0

        logger.info(f"DeadLinkAnalyzer started - max_checks: {self.max_checks_per_article}, auto_repair: {self.enable_auto_repair}")

        protected_mask = self.build_protected_mask(content)
        all_matches = list(self.URL_PATTERN.finditer(content))
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

        # Sort matches by position in descending order to avoid position offset issues
        # when content length changes after successful replacements
        filtered_matches.sort(key=lambda m: m.start(), reverse=True)

        analysis_complete = True

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

            # Get result from cache (computed in Pass 1)
            if url not in self._check_cache:
                logger.warning(f"URL_NOT_IN_CACHE | url={url} | skipping")
                continue

            result = self._check_cache[url]

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
                elif cached_decision.get('decision') == 'REPLACEMENT_CONFIRMED' and self.enable_auto_repair:
                    old_url = url
                    new_url = cached_decision.get('replacement_url')

                    replacement_result = self.safe_url_replacer.replace_exact_occurrence(
                        content, old_url, new_url, url_position
                    )

                    if replacement_result.success:
                        logger.info(f"REPAIR_APPLIED | url={url} | new_url={new_url} | cached=True")
                        content = replacement_result.new_content

                        self.issues.append(Issue(
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
                                'cached': True
                            }
                        ))
                    else:
                        logger.warning(f"REPAIR_FAILED | url={url} | reason={replacement_result.reason}")
                        self.issues.append(Issue(
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
                            }
                        ))
                    continue
                else:
                    logger.info(f"REPAIR_SKIPPED | url={url} | reason=already_unrepairable ({cached_decision.get('decision')})")
                    self.issues.append(Issue(
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
                        }
                    ))
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
                        self.issues.append(Issue(
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
                            }
                        ))

                        archive_repair_result = self._attempt_archive_fallback(url, url_position, result, match)
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
                    repair_result = self._attempt_archive_fallback(url, url_position, result, match)
                    if repair_result:
                        self._repair_cache[url] = {
                            'decision': repair_result.decision.value,
                            'replacement_url': repair_result.replacement_url,
                            'reason': repair_result.reason
                        }
                    
                    # Only add "dead link detected" issue if no successful repair will be made
                    if not (repair_result and repair_result.decision == RepairDecision.REPLACEMENT_CONFIRMED):
                        self.issues.append(Issue(
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
                            }
                        ))

                if repair_result and repair_result.decision == RepairDecision.REPLACEMENT_CONFIRMED:
                    old_url = url
                    new_url = repair_result.replacement_url

                    replacement_result = self.safe_url_replacer.replace_exact_occurrence(
                        content, old_url, new_url, url_position
                    )

                    if replacement_result.success:
                        logger.info(f"REPAIR_DIFF_VALIDATED | url={url} | changed_fields=url | other_changes=0")

                        self.issues.append(Issue(
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
                                'repair_decision': repair_result.decision.value
                            }
                        ))
                        logger.info(f"REPAIR_APPLIED | url={url} | new_url={new_url}")

                        self._repair_cache[url] = {
                            'decision': repair_result.decision.value,
                            'replacement_url': new_url,
                            'reason': repair_result.reason
                        }
                    else:
                        logger.warning(f"REPAIR_DIFF_REJECTED | url={url} | reason={replacement_result.reason}")
                elif repair_result:
                    logger.info(f"REPAIR_REJECTED | url={url} | reason={repair_result.reason}")

            elif result.status == LinkStatus.DEAD and not self.enable_auto_repair:
                logger.info(f"REPAIR_REJECTED | url={url} | reason=AUTO_REPAIR_DISABLED")

                self.issues.append(Issue(
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
                    }
                ))
            elif result.status == LinkStatus.REVIEW_REQUIRED:
                logger.info(f"REVIEW_REQUIRED | url={url} | reason={result.error_type}")
                self.issues.append(Issue(
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
                    }
                ))

        self.issues.sort(key=lambda i: i.position)

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

        return self.issues

    def _attempt_archive_fallback(self, url: str, url_position: int,
                                   result: LinkCheckResult, match) -> Optional[RepairResult]:
        """
        Try to find and validate a Wayback/Archive.org snapshot as a
        fallback repair. Returns a RepairResult with
        decision=REPLACEMENT_CONFIRMED on success, or None if no repair
        could be produced (an Issue has already been appended for every
        rejection path, matching prior behavior).
        """
        if not self._is_url_syntactically_valid(url):
            logger.warning(f"ARCHIVE_FALLBACK_CANCELLED | url={url} | reason=invalid_url_syntax")
            self.issues.append(Issue(
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
                }
            ))
            return None

        archive_result = self.archive_provider.check_archive(url)

        if not (archive_result and archive_result.archive_url):
            logger.info(f"ARCHIVE_FALLBACK_FAILED | url={url} | reason=no_archive_available")
            self.issues.append(Issue(
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
                }
            ))
            return None

        archive_url = archive_result.archive_url
        archive_date = archive_result.archive_date
        provider_name = archive_result.provider
        logger.info(f"ARCHIVE_CANDIDATE | url={url} | archive_url={archive_url} | archive_date={archive_date} | provider={provider_name}")

        logger.info(f"FINAL_VERIFICATION | url={url} | re-checking before archive fallback")

        recheck_retry_config = RetryConfig(
            max_attempts=2,
            base_delay=2.0,
            max_delay=4.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        )
        recheck_retry_handler = RetryHandler(recheck_retry_config)

        final_check = recheck_retry_handler.execute_with_retry_on_result(
            lambda: self.link_checker.check_link(url),
            should_retry_result=lambda r: r.http_status_code in (503, 502, 429)
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
                        self.issues.append(Issue(
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
                            }
                        ))
                        return None
                else:
                    # No alternative providers found - mark as review_required
                    logger.warning(f"ARCHIVE_VERIFICATION_NO_ALTERNATIVE_PROVIDERS | url={url}")
                    self.issues.append(Issue(
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
                        }
                    ))
                    return None
            else:
                logger.warning(f"ARCHIVE_VERIFICATION_FAILED | url={url} | archive_url={archive_url} | provider={provider_name} | status={archive_check.status.value} | http_status={archive_check.http_status_code} | reason=archive_not_healthy")
                # Genuine content failure - classify as ARCHIVE_NOT_ACCESSIBLE
                self.issues.append(Issue(
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
                    }
                ))
                return None

        if self._archive_content_looks_dead(archive_url):
            logger.warning(f"ARCHIVE_CONTENT_REJECTED | url={url} | archive_url={archive_url} | provider={provider_name} | reason=body_matches_not_found_markers")
            self.issues.append(Issue(
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
                }
            ))
            return None

        logger.info(f"ARCHIVE_VERIFIED | url={url} | archive_url={archive_url} | http_status={archive_check.http_status_code}")

        # Archive passed all checks - proceed with replacement
        logger.info(f"ARCHIVE_ACCEPTED | url={url} | archive_url={archive_url} | provider={provider_name} | confidence=high")

        return RepairResult(
            original_url=url,
            decision=RepairDecision.REPLACEMENT_CONFIRMED,
            replacement_url=archive_url,
            reason=f"Archive fallback: using {provider_name} archive from {archive_date} (HTTP {archive_check.http_status_code})"
        )