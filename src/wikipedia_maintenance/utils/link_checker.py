"""
Link Checker Service for detecting dead links.

Performs HTTP checks with retry logic and distinguishes between
temporary failures and permanently dead links.
"""

import logging
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

from .api_throttler import get_global_throttler, get_link_check_throttler

logger = logging.getLogger(__name__)


def _load_academic_publisher_domains() -> set:
    """
    Load academic publisher domains from configuration file.
    
    Returns:
        Set of academic publisher domain names
    """
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "academic_domains.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config and 'academic_publisher_domains' in config:
                    domains = set(config['academic_publisher_domains'])
                    logger.info(f"Loaded {len(domains)} academic publisher domains from config file")
                    return domains
    except Exception as e:
        logger.warning(f"Failed to load academic domains from config: {e}")
    
    # Fallback to empty set if config fails
    return set()


class LinkStatus(Enum):
    """Status of a link check."""
    HEALTHY = "healthy"  # Link is accessible (2xx/3xx)
    DEAD = "dead"  # Link is permanently dead (404/410)
    TEMPORARY_ERROR = "temporary_error"  # Temporary failure (5xx, timeout, DNS)
    RATE_LIMITED = "rate_limited"  # Rate limited (429)
    REVIEW_REQUIRED = "review_required"  # Ambiguous status (400/401/403/etc)
    UNKNOWN = "unknown"  # Unable to determine


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
    # resource, so it belongs in REVIEW_REQUIRED, not PERMANENTLY_DEAD.
    PERMANENTLY_DEAD_CODES = {404, 410}
    REVIEW_REQUIRED_CODES = {400, 401, 403, 498}
    TEMPORARY_ERROR_CODES = {500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529, 408}
    # Realistic browser User-Agent to reduce anti-bot detection for academic publishers
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

    def __init__(self, timeout: int = None, max_retries: int = 3):
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.max_retries = max_retries
        # Use dedicated throttler for link checks (more aggressive limits for parallelism)
        self.api_throttler = get_link_check_throttler()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        # Load academic publisher domains from config file
        self.academic_publisher_domains = _load_academic_publisher_domains()

    def _is_academic_publisher(self, url: str) -> bool:
        """
        Check if URL belongs to an academic publisher known to block automated requests.
        
        Academic publishers systematically block bots with 403 regardless of User-Agent
        due to advanced fingerprinting. These 403s are false positives - the content
        likely exists but is behind anti-bot protection.
        
        Args:
            url: URL to check
            
        Returns:
            True if domain is in academic publisher whitelist
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Check exact domain match
        if domain in self.academic_publisher_domains:
            return True
        
        # Check subdomain match (e.g., www.sciencedirect.com)
        for publisher_domain in self.academic_publisher_domains:
            if domain == f"www.{publisher_domain}" or domain.endswith(f".{publisher_domain}"):
                return True
        
        return False

    def check_link(self, url: str) -> LinkCheckResult:
        """Check if a link is accessible with retry logic."""
        start_time = time.time()
        retry_count = 0

        self.api_throttler.wait_if_needed()

        try:
            for attempt in range(self.max_retries):
                result = self._attempt_check(url, attempt)

                if result.status in [LinkStatus.HEALTHY, LinkStatus.DEAD, LinkStatus.RATE_LIMITED]:
                    result.check_duration = time.time() - start_time
                    result.retry_count = attempt + 1
                    return result

                if result.status == LinkStatus.TEMPORARY_ERROR and attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    retry_count = attempt + 1
                    continue

                result.check_duration = time.time() - start_time
                result.retry_count = attempt + 1
                return result

            return LinkCheckResult(
                url=url,
                status=LinkStatus.UNKNOWN,
                retry_count=retry_count,
                check_duration=time.time() - start_time,
                confidence=0.0
            )

        except Exception:
            return LinkCheckResult(
                url=url,
                status=LinkStatus.UNKNOWN,
                error_type="UNEXPECTED_ERROR",
                retry_count=retry_count,
                check_duration=time.time() - start_time,
                confidence=0.0
            )

    # ------------------------------------------------------------------
    # FIX: the previous version had a single try/except wrapping only the
    # first HEAD request (with an inline GET fallback for 403/405 nested
    # inside that except), followed - OUTSIDE any try block - by the
    # status-code classification, followed by three more `except`
    # clauses that didn't belong to any open `try`. That is a Python
    # SyntaxError: the module cannot be imported as-is.
    #
    # This version keeps the same intent (HEAD first, fall back to GET
    # once on 403/405, classify by status code, handle URLError/timeouts
    # as TEMPORARY_ERROR) but as a single coherent try/except with the
    # status-code classification factored into a shared helper so the
    # success path and the HTTPError-without-fallback path don't
    # duplicate the same elif chain.
    # ------------------------------------------------------------------

    def _attempt_check(self, url: str, attempt: int) -> LinkCheckResult:
        """Attempt a single check of the URL."""
        context = urllib.request.ssl.create_default_context()
        used_get_fallback = False

        def _request(method: str):
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
            return urllib.request.urlopen(req, timeout=self.timeout, context=context)

        try:
            response = _request('HEAD')

        except urllib.error.HTTPError as e:
            status_code = e.code if hasattr(e, 'code') else None

            # Some servers reject/misbehave on HEAD even for a valid URL
            # (405 Method Not Allowed) or gate it behind anti-bot rules
            # that a GET clears (403). Try once with GET before giving up.
            if status_code in (403, 405):
                try:
                    response = _request('GET')
                    used_get_fallback = True
                except urllib.error.HTTPError as get_error:
                    return self._classify_http_error(url, get_error, attempt)
                except urllib.error.URLError as get_error:
                    return self._classify_url_error(url, get_error, attempt)
                except Exception as get_error:
                    return LinkCheckResult(
                        url=url,
                        status=LinkStatus.UNKNOWN,
                        error_type=f"UNEXPECTED_{type(get_error).__name__}",
                        retry_count=attempt,
                        check_duration=0.0,
                        confidence=0.0
                    )
            else:
                return self._classify_http_error(url, e, attempt)

        except urllib.error.URLError as e:
            return self._classify_url_error(url, e, attempt)

        except Exception as e:
            return LinkCheckResult(
                url=url,
                status=LinkStatus.UNKNOWN,
                error_type=f"UNEXPECTED_{type(e).__name__}",
                retry_count=attempt,
                check_duration=0.0,
                confidence=0.0
            )

        # We reach here only with a live response object (HEAD, or the
        # GET fallback, succeeded).
        status_code = response.getcode()
        final_url = response.url

        self.api_throttler.report_success()

        if used_get_fallback:
            self._logger.info(f"GET_FALLBACK_USED | url={url} | reason=HEAD_failed")

        return self._classify_status_code(url, status_code, final_url, attempt)

    def _classify_status_code(self, url: str, status_code: int,
                               final_url: Optional[str], attempt: int) -> LinkCheckResult:
        """Classify a successfully-obtained HTTP status code."""
        if 200 <= status_code < 400:
            return LinkCheckResult(
                url=url, status=LinkStatus.HEALTHY, http_status_code=status_code,
                final_url=final_url, retry_count=attempt, check_duration=0.0, confidence=1.0
            )
        elif status_code in self.PERMANENTLY_DEAD_CODES:
            return LinkCheckResult(
                url=url, status=LinkStatus.DEAD, http_status_code=status_code,
                final_url=final_url, error_type=f"HTTP_{status_code}",
                retry_count=attempt, check_duration=0.0, confidence=1.0
            )
        elif status_code in self.REVIEW_REQUIRED_CODES:
            # Special handling for 403 from academic publishers
            if status_code == 403 and self._is_academic_publisher(url):
                self._logger.info(f"ACADEMIC_PUBLISHER_403 | url={url} | classified_as=TEMPORARY_ERROR")
                return LinkCheckResult(
                    url=url, status=LinkStatus.TEMPORARY_ERROR, http_status_code=status_code,
                    final_url=final_url, error_type="HTTP_403_ACADEMIC_PUBLISHER",
                    retry_count=attempt, check_duration=0.0, confidence=0.6
                )
            return LinkCheckResult(
                url=url, status=LinkStatus.REVIEW_REQUIRED, http_status_code=status_code,
                final_url=final_url, error_type=f"HTTP_{status_code}",
                retry_count=attempt, check_duration=0.0, confidence=0.0
            )
        elif status_code in self.TEMPORARY_ERROR_CODES:
            return LinkCheckResult(
                url=url, status=LinkStatus.TEMPORARY_ERROR, http_status_code=status_code,
                final_url=final_url, error_type=f"HTTP_{status_code}",
                retry_count=attempt, check_duration=0.0, confidence=0.8
            )
        elif status_code == 429:
            self.api_throttler.report_429()
            return LinkCheckResult(
                url=url, status=LinkStatus.RATE_LIMITED, http_status_code=status_code,
                final_url=final_url, error_type="RATE_LIMITED",
                retry_count=attempt, check_duration=0.0, confidence=1.0
            )
        else:
            return LinkCheckResult(
                url=url, status=LinkStatus.UNKNOWN, http_status_code=status_code,
                final_url=final_url, error_type=f"HTTP_{status_code}",
                retry_count=attempt, check_duration=0.0, confidence=0.5
            )

    def _classify_http_error(self, url: str, e: urllib.error.HTTPError, attempt: int) -> LinkCheckResult:
        """Classify an HTTPError raised by urlopen (no final_url available)."""
        status_code = e.code if hasattr(e, 'code') else None

        if status_code == 429:
            self.api_throttler.report_429()
            return LinkCheckResult(
                url=url, status=LinkStatus.RATE_LIMITED, http_status_code=status_code,
                error_type="RATE_LIMITED", retry_count=attempt, check_duration=0.0, confidence=1.0
            )
        elif status_code in self.PERMANENTLY_DEAD_CODES:
            return LinkCheckResult(
                url=url, status=LinkStatus.DEAD, http_status_code=status_code,
                error_type=f"HTTP_{status_code}", retry_count=attempt, check_duration=0.0, confidence=1.0
            )
        elif status_code in self.REVIEW_REQUIRED_CODES:
            # Special handling for 403 from academic publishers
            if status_code == 403 and self._is_academic_publisher(url):
                self._logger.info(f"ACADEMIC_PUBLISHER_403 | url={url} | classified_as=TEMPORARY_ERROR")
                return LinkCheckResult(
                    url=url, status=LinkStatus.TEMPORARY_ERROR, http_status_code=status_code,
                    error_type="HTTP_403_ACADEMIC_PUBLISHER", retry_count=attempt, check_duration=0.0, confidence=0.6
                )
            return LinkCheckResult(
                url=url, status=LinkStatus.REVIEW_REQUIRED, http_status_code=status_code,
                error_type=f"HTTP_{status_code}", retry_count=attempt, check_duration=0.0, confidence=0.0
            )
        elif status_code in self.TEMPORARY_ERROR_CODES:
            return LinkCheckResult(
                url=url, status=LinkStatus.TEMPORARY_ERROR, http_status_code=status_code,
                error_type=f"HTTP_{status_code}", retry_count=attempt, check_duration=0.0, confidence=0.8
            )
        else:
            return LinkCheckResult(
                url=url, status=LinkStatus.UNKNOWN, http_status_code=status_code,
                error_type=f"HTTP_{status_code}", retry_count=attempt, check_duration=0.0, confidence=0.5
            )

    def _classify_url_error(self, url: str, e: urllib.error.URLError, attempt: int) -> LinkCheckResult:
        """Classify a URLError (DNS failure, connection refused, timeout, ...)."""
        reason = e.reason
        reason_text = str(reason)

        # A timeout/connection-refused OSError is often carried as
        # e.reason (an exception instance) rather than a plain string.
        is_timeout_like = isinstance(reason, TimeoutError) or 'timed out' in reason_text.lower()
        is_connection_issue = isinstance(reason, (ConnectionRefusedError, ConnectionResetError))
        
        # DNS failure (domain doesn't exist) or SSL certificate expired = DEAD (permanent)
        is_dns_failure = 'getaddrinfo failed' in reason_text or 'nodename nor servname provided' in reason_text.lower()
        is_ssl_expired = 'certificate has expired' in reason_text.lower() or 'certificate verify failed' in reason_text.lower()

        if is_dns_failure or is_ssl_expired:
            return LinkCheckResult(
                url=url, status=LinkStatus.DEAD,
                error_type=f"URL_ERROR_{reason_text}", retry_count=attempt,
                check_duration=0.0, confidence=0.9
            )
        elif is_timeout_like:
            return LinkCheckResult(
                url=url, status=LinkStatus.TEMPORARY_ERROR, error_type="TIMEOUT",
                retry_count=attempt, check_duration=0.0, confidence=0.8
            )
        elif is_connection_issue:
            return LinkCheckResult(
                url=url, status=LinkStatus.TEMPORARY_ERROR,
                error_type=type(reason).__name__, retry_count=attempt,
                check_duration=0.0, confidence=0.8
            )
        else:
            return LinkCheckResult(
                url=url, status=LinkStatus.TEMPORARY_ERROR,
                error_type=f"URL_ERROR_{reason_text}", retry_count=attempt,
                check_duration=0.0, confidence=0.6
            )