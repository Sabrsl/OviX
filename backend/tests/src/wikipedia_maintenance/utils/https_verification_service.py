"""
HTTPS Verification Service.

Checks if a domain is accessible via HTTPS with proper error handling,
timeout management, and redirect following.
"""

import logging
import socket
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from enum import Enum

from .https_verification_cache import HttpsVerificationCache, VerificationStatus
from .api_throttler import get_link_check_throttler
from .retry_handler import RateLimitError
from .retry_handler import RateLimitError


logger = logging.getLogger(__name__)


class VerificationResult:
    """Result of HTTPS verification."""
    
    def __init__(self, status: VerificationStatus, domain: str, 
                 https_url: Optional[str] = None, http_status_code: Optional[int] = None,
                 redirect_url: Optional[str] = None, error_type: Optional[str] = None):
        self.status = status
        self.domain = domain
        self.https_url = https_url
        self.http_status_code = http_status_code
        self.redirect_url = redirect_url
        self.error_type = error_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'status': self.status.value,
            'domain': self.domain,
            'https_url': self.https_url,
            'http_status_code': self.http_status_code,
            'redirect_url': self.redirect_url,
            'error_type': self.error_type
        }


class HttpsVerificationService:
    """
    Service for verifying HTTPS availability of domains.
    
    This service checks if a domain that uses HTTP is also accessible via HTTPS,
    with proper error handling, timeout management, and redirect following.
    """
    
    # Default timeout in seconds
    DEFAULT_TIMEOUT = 10
    
    # User agent for HTTP requests
    USER_AGENT = "WikipediaMaintenanceTool/1.0 (HTTPS verification)"
    
    def __init__(self, cache: HttpsVerificationCache, timeout: int = None):
        """
        Initialize the HTTPS verification service.
        
        Args:
            cache: HttpsVerificationCache instance
            timeout: Request timeout in seconds
        """
        self.cache = cache
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.api_throttler = get_link_check_throttler()
    
    def verify_domain(self, domain: str) -> VerificationResult:
        """
        Verify if a domain is accessible via HTTPS.
        
        Args:
            domain: Domain to verify (e.g., "example.com", "www.example.com")
            
        Returns:
            VerificationResult with status and details
        """
        # Normalize domain
        normalized_domain = self._normalize_domain(domain)
        
        # Check cache first
        cached = self.cache.get(normalized_domain)
        if cached and cached.get('status_enum'):
            self._logger.debug(f"Cache hit for domain: {normalized_domain}")
            return VerificationResult(
                status=cached['status_enum'],
                domain=normalized_domain,
                https_url=cached.get('https_url'),
                http_status_code=cached.get('http_status_code'),
                redirect_url=cached.get('redirect_url'),
                error_type=cached.get('error_type')
            )
        
        # Prevent concurrent checks for same domain
        if self.cache.is_check_pending(normalized_domain):
            self._logger.debug(f"Check already pending for domain: {normalized_domain}")
            # Wait a bit and try cache again
            import time
            time.sleep(0.5)
            cached = self.cache.get(normalized_domain)
            if cached and cached.get('status_enum'):
                return VerificationResult(
                    status=cached['status_enum'],
                    domain=normalized_domain,
                    https_url=cached.get('https_url'),
                    http_status_code=cached.get('http_status_code'),
                    redirect_url=cached.get('redirect_url'),
                    error_type=cached.get('error_type')
                )
        
        # Mark as pending
        self.cache.mark_check_pending(normalized_domain)
        
        try:
            # Perform HTTPS check
            result = self._check_https(normalized_domain)
            
            # Store in cache
            self.cache.set(
                domain=normalized_domain,
                status=result.status,
                https_url=result.https_url,
                http_status_code=result.http_status_code,
                redirect_url=result.redirect_url,
                error_type=result.error_type
            )
            
            return result
        finally:
            # Mark as complete
            self.cache.mark_check_complete(normalized_domain)
    
    def _normalize_domain(self, domain: str) -> str:
        """
        Normalize domain name for consistent caching.
        
        Args:
            domain: Domain to normalize
            
        Returns:
            Normalized domain (lowercase, no trailing slash)
        """
        # Remove protocol if present
        if domain.startswith('http://') or domain.startswith('https://'):
            parsed = urlparse(domain)
            domain = parsed.netloc
        
        # Remove www prefix for consistency (some sites have different content on www vs non-www)
        # But be careful - this could break if they are different hosts
        # For now, just normalize case and trailing slash
        normalized = domain.lower().rstrip('/')
        
        return normalized
    
    def _check_https(self, domain: str) -> VerificationResult:
        """
        Perform actual HTTPS check for a domain.
        
        Args:
            domain: Domain to check
            
        Returns:
            VerificationResult with check details
        """
        https_url = f"https://{domain}"
        
        # Use centralized API throttler to prevent rate limiting
        self.api_throttler.wait_if_needed()
        
        try:
            # Create request with timeout
            request = urllib.request.Request(
                https_url,
                headers={'User-Agent': self.USER_AGENT},
                method='HEAD'  # Use HEAD to avoid downloading full page
            )
            
            # Set timeout
            context = urllib.request.ssl.create_default_context()
            response = urllib.request.urlopen(request, timeout=self.timeout, context=context)
            
            # Check HTTP status code
            status_code = response.getcode()
            
            # Report success to throttler to reset backoff
            self.api_throttler.report_success()
            
            # Consider 2xx and 3xx as success
            if 200 <= status_code < 400:
                # Success - HTTPS is available
                return VerificationResult(
                    status=VerificationStatus.HTTPS_AVAILABLE,
                    domain=domain,
                    https_url=https_url,
                    http_status_code=status_code
                )
            elif 400 <= status_code < 500:
                # Client error - likely domain doesn't exist or requires specific headers
                return VerificationResult(
                    status=VerificationStatus.HTTPS_UNAVAILABLE,
                    domain=domain,
                    https_url=https_url,
                    http_status_code=status_code,
                    error_type=f"HTTP_{status_code}"
                )
            elif 500 <= status_code < 600:
                # Server error - can't determine, treat as check failed
                return VerificationResult(
                    status=VerificationStatus.CHECK_FAILED,
                    domain=domain,
                    https_url=https_url,
                    http_status_code=status_code,
                    error_type=f"HTTP_{status_code}"
                )
            else:
                # Other status codes
                return VerificationResult(
                    status=VerificationStatus.CHECK_FAILED,
                    domain=domain,
                    https_url=https_url,
                    http_status_code=status_code,
                    error_type=f"HTTP_{status_code}"
                )
                
        except urllib.error.HTTPError as e:
            # HTTP error
            status_code = e.code if hasattr(e, 'code') else None
            
            # Check for rate limiting (HTTP 429)
            if status_code == 429:
                self.api_throttler.report_429()
                self._logger.warning(f"Rate limited (429) when checking HTTPS for {domain}")
                return VerificationResult(
                    status=VerificationStatus.CHECK_FAILED,
                    domain=domain,
                    https_url=https_url,
                    http_status_code=status_code,
                    error_type="RATE_LIMITED"
                )
            
            return VerificationResult(
                status=VerificationStatus.CHECK_FAILED,
                domain=domain,
                https_url=https_url,
                http_status_code=status_code,
                error_type="HTTP_ERROR"
            )
        except urllib.error.URLError as e:
            # URL error - could be DNS, connection refused, timeout, etc.
            error_type = "URL_ERROR"
            
            # Distinguish between specific error types
            if isinstance(e.reason, TimeoutError):
                error_type = "TIMEOUT"
            elif isinstance(e.reason, ConnectionRefusedError):
                error_type = "CONNECTION_REFUSED"
            elif isinstance(e.reason, socket.gaierror):
                error_type = "DNS_ERROR"
            elif "timed out" in str(e.reason).lower():
                error_type = "TIMEOUT"
            
            return VerificationResult(
                status=VerificationStatus.CHECK_FAILED,
                domain=domain,
                https_url=https_url,
                error_type=error_type
            )
        except Exception as e:
            # Other errors (SSL/TLS, etc.)
            error_type = type(e).__name__
            self._logger.warning(f"Unexpected error checking HTTPS for {domain}: {e}")
            
            return VerificationResult(
                status=VerificationStatus.CHECK_FAILED,
                domain=domain,
                https_url=https_url,
                error_type=error_type
            )
    
    def verify_domain_from_url(self, http_url: str) -> VerificationResult:
        """
        Extract domain from HTTP URL and verify HTTPS availability.
        
        Args:
            http_url: HTTP URL to check
            
        Returns:
            VerificationResult
        """
        try:
            parsed = urlparse(http_url)
            domain = parsed.netloc or parsed.hostname
            
            if not domain:
                # Invalid URL, treat as check failed
                return VerificationResult(
                    status=VerificationStatus.CHECK_FAILED,
                    domain="",
                    https_url=None,
                    error_type="INVALID_URL"
                )
            
            return self.verify_domain(domain)
        except Exception as e:
            self._logger.error(f"Error parsing URL {http_url}: {e}")
            return VerificationResult(
                status=VerificationStatus.CHECK_FAILED,
                domain="",
                https_url=None,
                error_type="PARSE_ERROR"
            )
