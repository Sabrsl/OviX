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

from .base import BaseAnalyzer, Issue
from ..utils.api_throttler import get_global_throttler
from ..utils.link_checker import LinkStatus, LinkCheckResult, LinkChecker
from ..utils.redirect_finder import RedirectFinder, RedirectResult
from ..utils.link_validator import LinkValidator, RepairDecision, RepairResult
from ..utils.content_verifier import ContentVerifier
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
    DEFAULT_MAX_CHECKS_PER_ARTICLE = 20

    # Whitelist of valid URL characters; wikitext delimiters |{}[] are
    # intentionally excluded so a URL match stops before them instead of
    # swallowing trailing template syntax (e.g. "url|consulté le=..." or
    # "[url texte]").
    # FIX: The pattern now requires that if '%' appears, it must be followed
    # by exactly 2 hexadecimal digits (valid percent-encoding). This prevents
    # the regex from swallowing template delimiters like '%/langue=it' that were
    # being incorrectly included in URL matches.
    URL_PATTERN = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=]+(?:%[0-9A-Fa-f]{2}[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=]*)*', re.IGNORECASE)

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

        for match in filtered_matches:
            if self._checks_count >= self.max_checks_per_article:
                logger.info(f"Reached max checks limit ({self.max_checks_per_article}), stopping")
                analysis_complete = False
                break

            url = match.group(0)
            url_position = match.start()

            if not self._is_url_syntactically_valid(url):
                logger.warning(f"URL_REJECTED | url={url} | reason=SYNTAX_INVALID")
                continue

            logger.info(f"URL_CHECK | url={url}")
            http_start = time.time()

            if url in self._check_cache:
                result = self._check_cache[url]
                logger.info(f"URL_CHECK | url={url} | status=CACHED | http_status={result.http_status_code} | classification={result.status.value}")
            else:
                result = self.link_checker.check_link(url)
                self._check_cache[url] = result
                self._checks_count += 1

            http_duration = time.time() - http_start
            logger.info(f"URL_CHECK | url={url} | http_status={result.http_status_code} | classification={result.status.value} | error={result.error_type} | attempts={result.retry_count} | duration={http_duration:.2f}s")

            if result.status == LinkStatus.DEAD and self.enable_auto_repair:
                if not analysis_complete:
                    logger.info(f"REPAIR_REJECTED | url={url} | reason=ANALYSIS_INCOMPLETE")
                    continue

                if url in self._repair_cache:
                    cached_decision = self._repair_cache[url]
                    logger.info(f"REPAIR_CACHED | url={url} | decision={cached_decision.get('decision')} | replacement_url={cached_decision.get('replacement_url')}")

                    if cached_decision.get('decision') == 'REPLACEMENT_CONFIRMED':
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
                            continue
                        else:
                            logger.warning(f"REPAIR_FAILED | url={url} | reason={replacement_result.reason}")
                            continue
                    else:
                        logger.info(f"REPAIR_SKIPPED | url={url} | reason=already_unrepairable ({cached_decision.get('decision')})")
                        continue

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
                else:
                    logger.info(f"ARCHIVE_FALLBACK | url={url} | reason=no_valid_redirect")

                    self._repair_cache[url] = {
                        'decision': 'REDIRECT_NOT_FOUND',
                        'replacement_url': None,
                        'reason': 'no_valid_redirect'
                    }

                    # FIX: Validate URL before archive lookup to catch corrupted URLs
                    # This prevents corrupted URLs (with template parameters) from being
                    # sent to the archive provider, which would construct invalid archive URLs
                    if not self._is_url_syntactically_valid(url):
                        logger.warning(f"ARCHIVE_FALLBACK_CANCELLED | url={url} | reason=invalid_url_syntax")
                        self._repair_cache[url] = {
                            'decision': 'INVALID_URL_SYNTAX',
                            'replacement_url': None,
                            'reason': 'URL contains invalid syntax (likely template parameters), archive fallback cancelled'
                        }
                        continue

                    archive_result = self.archive_provider.check_archive(url)

                    if archive_result and archive_result.archive_url:
                        archive_url = archive_result.archive_url
                        archive_date = archive_result.archive_date
                        provider_name = archive_result.provider
                        logger.info(f"ARCHIVE_FOUND | url={url} | archive_url={archive_url} | archive_date={archive_date} | provider={provider_name}")

                        # CRITICAL: Re-verify original URL is actually dead before using archive fallback
                        # This prevents replacing healthy URLs with archives due to false positives
                        logger.info(f"FINAL_VERIFICATION | url={url} | re-checking before archive fallback")
                        final_check = self.link_checker.check_link(url)
                        
                        if final_check.status != LinkStatus.DEAD:
                            logger.warning(f"ARCHIVE_FALLBACK_CANCELLED | url={url} | original_status={final_check.status.value} | reason=original_url_not_actually_dead")
                            self._repair_cache[url] = {
                                'decision': 'ORIGINAL_URL_HEALTHY',
                                'replacement_url': None,
                                'reason': f'Original URL is not dead (status: {final_check.status.value}), archive fallback cancelled'
                            }
                            continue

                        logger.info(f"ARCHIVE_VERIFICATION | url={url} | archive_url={archive_url} | verifying_http_access")
                        archive_check = self.link_checker.check_link(archive_url)

                        if archive_check.status == LinkStatus.HEALTHY:
                            # FIX: an HTTP 200 from HEAD only proves the
                            # snapshot exists and answers requests - it
                            # does NOT prove the archived page has real
                            # content. A GET-based keyword check catches
                            # the case where Wayback faithfully archived
                            # an already-dead "page not found" response
                            # (observed in production: a confirmed
                            # repair pointed to an archived CAIRN
                            # "Page non-trouvée").
                            if self._archive_content_looks_dead(archive_url):
                                logger.warning(f"ARCHIVE_CONTENT_SUSPICIOUS | url={url} | archive_url={archive_url} | reason=body_matches_not_found_markers")
                                self._repair_cache[url] = {
                                    'decision': 'ARCHIVE_CONTENT_SUSPICIOUS',
                                    'replacement_url': None,
                                    'reason': 'Archive snapshot returns HTTP 200 but content looks like a not-found page'
                                }
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
                                        'archive_url': archive_url,
                                        'repair_status': 'ARCHIVE_CONTENT_SUSPICIOUS'
                                    }
                                ))
                                continue

                            logger.info(f"ARCHIVE_VERIFIED | url={url} | archive_url={archive_url} | http_status={archive_check.http_status_code}")

                            repair_result = RepairResult(
                                original_url=url,
                                decision=RepairDecision.REPLACEMENT_CONFIRMED,
                                replacement_url=archive_url,
                                reason=f"Archive fallback: No redirect found, using {provider_name} archive from {archive_date} (HTTP {archive_check.http_status_code})"
                            )

                            self._repair_cache[url] = {
                                'decision': repair_result.decision.value,
                                'replacement_url': repair_result.replacement_url,
                                'reason': repair_result.reason
                            }

                            logger.info(f"REPAIR_DECISION | url={url} | decision={repair_result.decision.value} | reason={repair_result.reason} | using_archive={archive_url}")
                        else:
                            logger.warning(f"ARCHIVE_NOT_ACCESSIBLE | url={url} | archive_url={archive_url} | status={archive_check.status.value} | http_status={archive_check.http_status_code}")
                            self._repair_cache[url] = {
                                'decision': 'ARCHIVE_NOT_ACCESSIBLE',
                                'replacement_url': None,
                                'reason': f'Archive found but not accessible (HTTP {archive_check.http_status_code})'
                            }
                            continue
                    else:
                        logger.info(f"ARCHIVE_NOT_FOUND | url={url} | reason=no_archive_available")
                        continue

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

        self.issues.sort(key=lambda i: i.position)

        skipped_urls = total_urls - self._checks_count
        if analysis_complete:
            logger.info(f"DeadLinkAnalyzer completed - found {len(self.issues)} dead links (checked {self._checks_count}/{total_urls} URLs)")
        else:
            logger.warning(f"DeadLinkAnalyzer incomplete - found {len(self.issues)} dead links (checked {self._checks_count}/{total_urls} URLs, {skipped_urls} skipped)")

        return self.issues