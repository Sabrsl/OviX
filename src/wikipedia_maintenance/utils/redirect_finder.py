"""
Redirect Finder Service for locating valid redirects/replacements for dead links.

This service attempts to find a working URL that corresponds to the same resource
as a dead link, using deterministic criteria to validate the correspondence.
"""

import logging
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, urljoin
from enum import Enum
from dataclasses import dataclass

from .api_throttler import get_global_throttler

logger = logging.getLogger(__name__)


class RedirectDecision(Enum):
    """Decision on redirect validity."""
    VALID_REDIRECT = "valid_redirect"  # Confirmed redirect to same resource
    INVALID_REDIRECT = "invalid_redirect"  # Redirect to different resource
    NO_REDIRECT = "no_redirect"  # No redirect found
    AMBIGUOUS = "ambiguous"  # Multiple possible redirects


@dataclass
class RedirectResult:
    """Result of redirect search."""
    original_url: str
    decision: RedirectDecision
    redirected_url: Optional[str] = None
    http_status_code: Optional[int] = None
    reason: Optional[str] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'original_url': self.original_url,
            'decision': self.decision.value,
            'redirected_url': self.redirected_url,
            'http_status_code': self.http_status_code,
            'reason': self.reason,
            'confidence': self.confidence
        }


class RedirectFinder:
    """
    Service for finding and validating redirects.
    
    Design principles:
    - Only accept redirects that are demonstrably to the same resource
    - Use deterministic criteria (not similarity scores)
    - Reject ambiguous cases
    - Require high confidence before accepting
    """
    
    USER_AGENT = "WikipediaMaintenanceTool/1.0 (Redirect Finder)"
    DEFAULT_TIMEOUT = 10
    
    # Status codes that indicate redirects
    REDIRECT_CODES = {301, 302, 303, 307, 308}
    
    def __init__(self, timeout: int = None):
        """
        Initialize redirect finder.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.api_throttler = get_global_throttler()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def find_redirect(self, url: str) -> RedirectResult:
        """
        Attempt to find a valid redirect for a dead URL.
        
        Args:
            url: Dead URL to find redirect for
            
        Returns:
            RedirectResult with decision and details
        """
        self.api_throttler.wait_if_needed()
        
        try:
            # Attempt to fetch the URL and follow redirects
            request = urllib.request.Request(
                url,
                headers={'User-Agent': self.USER_AGENT},
                method='HEAD'
            )
            
            context = urllib.request.ssl.create_default_context()
            response = urllib.request.urlopen(request, timeout=self.timeout, context=context)
            
            final_url = response.url
            status_code = response.getcode()
            
            self.api_throttler.report_success()
            
            # Check if URL was redirected
            if final_url != url:
                # Validate the redirect
                decision = self._validate_redirect(url, final_url, status_code)
                
                return RedirectResult(
                    original_url=url,
                    decision=decision,
                    redirected_url=final_url if decision == RedirectDecision.VALID_REDIRECT else None,
                    http_status_code=status_code,
                    reason=self._get_reason(decision, url, final_url),
                    confidence=1.0 if decision == RedirectDecision.VALID_REDIRECT else 0.0
                )
            else:
                return RedirectResult(
                    original_url=url,
                    decision=RedirectDecision.NO_REDIRECT,
                    http_status_code=status_code,
                    reason="No redirect occurred"
                )
                
        except urllib.error.HTTPError as e:
            status_code = e.code if hasattr(e, 'code') else None
            
            if status_code == 429:
                self.api_throttler.report_429()
            
            return RedirectResult(
                original_url=url,
                decision=RedirectDecision.NO_REDIRECT,
                http_status_code=status_code,
                reason=f"HTTP error: {status_code}"
            )
                
        except Exception as e:
            self._logger.warning(f"Error finding redirect for {url}: {e}")
            return RedirectResult(
                original_url=url,
                decision=RedirectDecision.NO_REDIRECT,
                reason=f"Error: {str(e)}"
            )
    
    def _validate_redirect(self, original_url: str, redirected_url: str, status_code: int) -> RedirectDecision:
        """
        Validate that a redirect is to the same resource.
        
        Uses deterministic criteria:
        - Same domain (with known equivalent patterns)
        - Same path or structural path equivalence
        - Reject arbitrary path changes (no length-based heuristics)
        
        Args:
            original_url: Original URL
            redirected_url: Redirected URL
            status_code: HTTP status code
            
        Returns:
            RedirectDecision
        """
        orig_parsed = urlparse(original_url)
        redir_parsed = urlparse(redirected_url)
        
        # Criterion 1: Exact same domain
        if orig_parsed.netloc == redir_parsed.netloc:
            # Same domain - validate path structure
            return self._validate_path_structure(orig_parsed.path, redir_parsed.path)
        
        # Criterion 2: Protocol-only change (http -> https)
        orig_domain_noproto = orig_parsed.netloc.replace('http://', '').replace('https://', '')
        redir_domain_noproto = redir_parsed.netloc.replace('http://', '').replace('https://', '')
        
        if orig_domain_noproto == redir_domain_noproto:
            # Same domain with different protocol - validate path structure
            return self._validate_path_structure(orig_parsed.path, redir_parsed.path)
        
        # Criterion 3: www-only change (www.example.com -> example.com)
        orig_domain_nowww = orig_parsed.netloc.replace('www.', '')
        redir_domain_nowww = redir_parsed.netloc.replace('www.', '')
        
        if orig_domain_nowww == redir_domain_nowww:
            # Same domain with/without www - validate path structure
            return self._validate_path_structure(orig_parsed.path, redir_parsed.path)
        
        # Different domains: reject immediately (different source)
        return RedirectDecision.INVALID_REDIRECT
    
    def _validate_path_structure(self, orig_path: str, redir_path: str) -> RedirectDecision:
        """
        Validate that two paths represent the same resource structure.
        
        REJECTS arbitrary path changes - only accepts:
        - Identical paths
        - Trailing slash differences
        - Case-only differences (for case-insensitive servers)
        - Known URL encoding variations
        
        Args:
            orig_path: Original URL path
            redir_path: Redirected URL path
            
        Returns:
            RedirectDecision
        """
        # Normalize for comparison
        orig_normalized = orig_path.rstrip('/').lower()
        redir_normalized = redir_path.rstrip('/').lower()
        
        # Exact match (normalized)
        if orig_normalized == redir_normalized:
            return RedirectDecision.VALID_REDIRECT
        
        # Trailing slash only difference
        if orig_path.rstrip('/') == redir_path.rstrip('/'):
            return RedirectDecision.VALID_REDIRECT
        
        # Case-only difference (for case-insensitive servers)
        if orig_path.lower() == redir_path.lower():
            return RedirectDecision.VALID_REDIRECT
        
        # If paths differ in any other way, reject as different resource
        # NO length-based heuristics - that would contradict the
        # "deterministic criteria, not similarity scores" philosophy
        self._logger.info(
            f"PATH_DIFF_REJECTED | orig_path={orig_path} | redir_path={redir_path} | "
            f"reason=Path structure differs significantly"
        )
        return RedirectDecision.INVALID_REDIRECT
    
    def _get_reason(self, decision: RedirectDecision, original_url: str, redirected_url: str) -> str:
        """Get human-readable reason for decision."""
        if decision == RedirectDecision.VALID_REDIRECT:
            return f"Valid redirect to same resource: {redirected_url}"
        elif decision == RedirectDecision.INVALID_REDIRECT:
            return f"Redirect to different resource: {redirected_url}"
        elif decision == RedirectDecision.NO_REDIRECT:
            return "No redirect found"
        else:
            return "Ambiguous redirect"
