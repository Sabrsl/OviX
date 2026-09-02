"""
Link Checker Service for detecting dead links.

Performs HTTP checks with retry logic and distinguishes between
temporary failures and permanently dead links.
"""

import logging
import random
import ssl
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache

from .api_throttler import get_global_throttler, get_link_check_throttler

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_academic_publisher_domains() -> frozenset:
    """
    Load academic publisher domains from configuration file.

    Cached at module level to avoid repeated file I/O - loads once per process.

    Returns:
        Frozen set of academic publisher domain names (immutable for cache safety)
    """
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "academic_domains.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config and 'academic_publisher_domains' in config:
                    domains = frozenset(config['academic_publisher_domains'])
                    logger.info(f"Loaded {len(domains)} academic publisher domains from config file")
                    return domains
    except Exception as e:
        logger.warning(f"Failed to load academic domains from config: {e}")

    return frozenset()


class LinkStatus(Enum):
    """Status of a link check."""
    HEALTHY = "healthy"              # Link is accessible (2xx/3xx)
    DEAD = "dead"                    # Link is permanently dead (404/410/DNS/SSL expired)
    TEMPORARY_ERROR = "temporary_error"  # Temporary failure (5xx, timeout, DNS transient)
    RATE_LIMITED = "rate_limited"    # Rate limited (429)
    REVIEW_REQUIRED = "review_required"  # Ambiguous status (400/401/403/etc)
    UNKNOWN = "unknown"              # Unable to determine


@dataclass
class LinkCheckResult:
    """Result of a link check."""
    url: str
    status: LinkStatus
    http_status_code: Optional[int] = None
    final_url: Optional[str] = None  # After redirects
    error_type: Optional[str] = None
    retry_count: int = 0
    check_duration: float = 0.0
    confidence: float = 1.0  # Confidence in the result (0.0-1.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'url': self.url,
            'status': self.status.value,
            'http_status_code': self.http_status_code,
            'final_url': self.final_url,
            'error_type': self.error_type,
            'retry_count': self.retry_count,
            'check_duration': self.check_duration,
            'confidence': self.confidence
        }


class LinkChecker:
    """
    Link checker with retry logic and temporary failure detection.

    This is integrated into DeadLinkAnalyzer for direct use.
    """

    DEFAULT_TIMEOUT = 10

    # Only codes that definitively indicate the resource no longer exists.
    # 403 is intentionally NOT here: it usually means access restrictions
    # (geo-blocking, auth wall, anti-bot) rather than a genuinely dead
    # resource, so it belongs in REVIEW_REQUIRED, not here.
    PERMANENTLY_DEAD_CODES = frozenset({404, 410})

    # 498 = "Invalid Token" (non-standard, used by some CDNs/APIs e.g. Esri)
    # kept here rather than in TEMPORARY_ERROR because it signals an
    # auth/config problem, not server unavailability.
    REVIEW_REQUIRED_CODES = frozenset({400, 401, 403, 498})

    TEMPORARY_ERROR_CODES = frozenset(
        {408, 500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529}
    )

    # Windows WSA DNS error codes that indicate transient DNS failures
    # These should NOT be treated as permanently dead links
    DNS_TRANSIENT_ERRORS = frozenset({
        11001,  # HOST_NOT_FOUND (can be transient)
        11002,  # TRY_AGAIN (definitely transient - DNS server busy)
        11003,  # NO_RECOVERY (can be transient DNS server issue)
        11004,  # NO_DATA (can be transient)
    })

    # Realistic browser User-Agent to reduce anti-bot detection for academic publishers
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    # Statuses that already carry a final, trustworthy verdict and should
    # stop the retry loop immediately.
    _TERMINAL_STATUSES = frozenset(
        {LinkStatus.HEALTHY, LinkStatus.DEAD, LinkStatus.RATE_LIMITED,
         LinkStatus.REVIEW_REQUIRED, LinkStatus.UNKNOWN}
    )

    def __init__(self, timeout: int = None, max_retries: int = 3):
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.max_retries = max_retries
        # Use dedicated throttler for link checks (more aggressive limits for parallelism)
        self.api_throttler = get_link_check_throttler()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        # Load academic publisher domains from config file
        self.academic_publisher_domains = _load_academic_publisher_domains()
        # Explicit SSL context, built once per checker instance.
        self._ssl_context = ssl.create_default_context()

    def _is_academic_publisher(self, domain: str) -> bool:
        """
        Check if a (lowercased) domain belongs to an academic publisher known
        to block automated requests.

        Academic publishers systematically block bots with 403 regardless of
        User-Agent due to advanced fingerprinting. These 403s are false
        positives - the content likely exists but is behind anti-bot
        protection.

        Args:
            domain: lowercased netloc, e.g. "www.sciencedirect.com"

        Returns:
            True if domain (or its parent domain) is in the whitelist.
        """
        if domain in self.academic_publisher_domains:
            return True
        for publisher_domain in self.academic_publisher_domains:
            if domain == f"www.{publisher_domain}" or domain.endswith(f".{publisher_domain}"):
                return True
        return False

    def check_link(self, url: str) -> LinkCheckResult:
        """Check if a link is accessible, retrying on temporary failures."""
        start_time = time.time()
        last_result: Optional[LinkCheckResult] = None

        self.api_throttler.wait_if_needed()

        try:
            for attempt in range(self.max_retries):
                result = self._attempt_check(url, attempt)
                last_result = result

                if result.status in self._TERMINAL_STATUSES:
                    result.retry_count = attempt + 1
                    result.check_duration = time.time() - start_time
                    return result

                # Only TEMPORARY_ERROR falls through to here.
                if attempt < self.max_retries - 1:
                    # Exponential backoff with jitter to avoid thundering
                    # herd when many URLs hit transient errors together.
                    wait_time = (2 ** attempt) + random.uniform(0, 0.5)
                    time.sleep(wait_time)
                    continue

                result.retry_count = attempt + 1
                result.check_duration = time.time() - start_time
                return result

            # Exhausted retries without a terminal result (defensive fallback;
            # should not normally be reached given the loop above).
            return LinkCheckResult(
                url=url,
                status=LinkStatus.UNKNOWN,
                error_type=last_result.error_type if last_result else None,
                retry_count=self.max_retries,
                check_duration=time.time() - start_time,
                confidence=0.0
            )

        except Exception as e:
            self._logger.exception(f"UNEXPECTED_CHECK_FAILURE | url={url}")
            return LinkCheckResult(
                url=url,
                status=LinkStatus.UNKNOWN,
                error_type=f"UNEXPECTED_{type(e).__name__}",
                retry_count=0,
                check_duration=time.time() - start_time,
                confidence=0.0
            )

    def _request(self, url: str, method: str):
        """Build and send a single HTTP request, returning the open response."""
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': self.USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            method=method
        )
        return urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_context)

    def _attempt_check(self, url: str, attempt: int) -> LinkCheckResult:
        """Attempt a single check of the URL: HEAD first, GET fallback on 403/405."""
        domain = urlparse(url).netloc.lower()
        used_get_fallback = False
        response = None

        try:
            try:
                response = self._request(url, 'HEAD')
            except urllib.error.HTTPError as e:
                status_code = e.code if hasattr(e, 'code') else None

                # Some servers reject/misbehave on HEAD even for a valid URL
                # (405 Method Not Allowed) or gate it behind anti-bot rules
                # that a GET clears (403). Try once with GET before giving up.
                if status_code in (403, 405):
                    try:
                        response = self._request(url, 'GET')
                        used_get_fallback = True
                    except urllib.error.HTTPError as get_error:
                        return self._classify_error(url, get_error, attempt, domain)
                    except urllib.error.URLError as get_error:
                        return self._classify_error(url, get_error, attempt, domain)
                else:
                    return self._classify_error(url, e, attempt, domain)
            except urllib.error.URLError as e:
                return self._classify_error(url, e, attempt, domain)

            # We reach here only with a live response object (HEAD, or the
            # GET fallback, succeeded).
            status_code = response.getcode()
            final_url = response.url

            self.api_throttler.report_success()
            if used_get_fallback:
                self._logger.info(f"GET_FALLBACK_USED | url={url} | reason=HEAD_failed")

            return self._classify_status_code(url, status_code, final_url, attempt, domain)

        except Exception as e:
            return LinkCheckResult(
                url=url,
                status=LinkStatus.UNKNOWN,
                error_type=f"UNEXPECTED_{type(e).__name__}",
                retry_count=attempt,
                confidence=0.0
            )
        finally:
            if response is not None:
                response.close()

    def _classify_error(
        self, url: str, e: Exception, attempt: int, domain: str
    ) -> LinkCheckResult:
        """
        Dispatch any raised exception (HTTPError or URLError) to the
        appropriate classifier. Single entry point so HEAD and GET failure
        paths share identical logic.
        """
        if isinstance(e, urllib.error.HTTPError):
            return self._classify_http_status(
                url,
                status_code=e.code if hasattr(e, 'code') else None,
                final_url=None,
                attempt=attempt,
                domain=domain,
            )
        return self._classify_url_error(url, e, attempt)

    def _classify_status_code(
        self, url: str, status_code: int, final_url: Optional[str], attempt: int, domain: str
    ) -> LinkCheckResult:
        """Classify a successfully-obtained HTTP status code (2xx-3xx path)."""
        return self._classify_http_status(url, status_code, final_url, attempt, domain)

    def _classify_http_status(
        self, url: str, status_code: Optional[int], final_url: Optional[str],
        attempt: int, domain: str
    ) -> LinkCheckResult:
        """
        Single source of truth for turning an HTTP status code into a
        LinkCheckResult. Used for both the success path (HEAD/GET returned
        normally) and the HTTPError path (status_code came from the raised
        exception).
        """
        common = dict(url=url, http_status_code=status_code, final_url=final_url, retry_count=attempt)

        if status_code is None:
            return LinkCheckResult(status=LinkStatus.UNKNOWN, error_type="NO_STATUS_CODE",
                                    confidence=0.0, **common)

        if 200 <= status_code < 400:
            return LinkCheckResult(status=LinkStatus.HEALTHY, confidence=1.0, **common)

        if status_code == 429:
            self.api_throttler.report_429()
            return LinkCheckResult(status=LinkStatus.RATE_LIMITED, error_type="RATE_LIMITED",
                                    confidence=1.0, **common)

        if status_code in self.PERMANENTLY_DEAD_CODES:
            return LinkCheckResult(status=LinkStatus.DEAD, error_type=f"HTTP_{status_code}",
                                    confidence=1.0, **common)

        if status_code in self.REVIEW_REQUIRED_CODES:
            if status_code == 403 and self._is_academic_publisher(domain):
                self._logger.info(f"ACADEMIC_PUBLISHER_403 | url={url} | classified_as=TEMPORARY_ERROR")
                return LinkCheckResult(status=LinkStatus.TEMPORARY_ERROR,
                                        error_type="HTTP_403_ACADEMIC_PUBLISHER",
                                        confidence=0.6, **common)
            return LinkCheckResult(status=LinkStatus.REVIEW_REQUIRED, error_type=f"HTTP_{status_code}",
                                    confidence=0.0, **common)

        if status_code in self.TEMPORARY_ERROR_CODES:
            return LinkCheckResult(status=LinkStatus.TEMPORARY_ERROR, error_type=f"HTTP_{status_code}",
                                    confidence=0.8, **common)

        return LinkCheckResult(status=LinkStatus.UNKNOWN, error_type=f"HTTP_{status_code}",
                                confidence=0.5, **common)

    def _classify_url_error(self, url: str, e: urllib.error.URLError, attempt: int) -> LinkCheckResult:
        """Classify a URLError (DNS failure, connection refused, timeout, ...)."""
        reason = e.reason
        reason_text = str(reason)
        reason_lower = reason_text.lower()

        is_timeout_like = isinstance(reason, TimeoutError) or 'timed out' in reason_lower
        is_connection_issue = isinstance(reason, (ConnectionRefusedError, ConnectionResetError))
        is_dns_failure = 'getaddrinfo failed' in reason_text or 'nodename nor servname provided' in reason_lower
        is_ssl_expired = 'certificate has expired' in reason_lower
        is_ssl_verify_failed = 'certificate verify failed' in reason_lower

        common = dict(url=url, retry_count=attempt)

        if is_dns_failure:
            # Check if this is a transient DNS error (Windows WSA error codes)
            errno = getattr(reason, 'errno', None)
            if errno in self.DNS_TRANSIENT_ERRORS:
                self._logger.warning(f"DNS_TRANSIENT_ERROR | url={url} | errno={errno} | reason={reason_text}")
                return LinkCheckResult(status=LinkStatus.TEMPORARY_ERROR,
                                        error_type=f"DNS_TRANSIENT_{errno}",
                                        confidence=0.0, **common)
            # Non-transient DNS failure: treat as permanently dead
            return LinkCheckResult(status=LinkStatus.DEAD, error_type=f"URL_ERROR_{reason_text}",
                                    confidence=0.9, **common)
        if is_ssl_expired:
            # SSL certificate expired: permanently dead
            return LinkCheckResult(status=LinkStatus.DEAD, error_type=f"URL_ERROR_{reason_text}",
                                    confidence=0.9, **common)
        if is_ssl_verify_failed:
            # SSL certificate verification failed (chain/authority issue, not expired)
            # This is often a misconfiguration, the site may still be accessible
            # Treat as REVIEW_REQUIRED rather than DEAD to avoid false positives
            self._logger.warning(f"SSL_VERIFY_FAILED | url={url} | reason={reason_text} | classified_as=REVIEW_REQUIRED")
            return LinkCheckResult(status=LinkStatus.REVIEW_REQUIRED, error_type="SSL_VERIFY_FAILED",
                                    confidence=0.7, **common)
        if is_timeout_like:
            return LinkCheckResult(status=LinkStatus.TEMPORARY_ERROR, error_type="TIMEOUT",
                                    confidence=0.8, **common)
        if is_connection_issue:
            return LinkCheckResult(status=LinkStatus.TEMPORARY_ERROR, error_type=type(reason).__name__,
                                    confidence=0.8, **common)
        return LinkCheckResult(status=LinkStatus.TEMPORARY_ERROR, error_type=f"URL_ERROR_{reason_text}",
                                confidence=0.6, **common)