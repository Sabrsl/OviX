"""
Analyzer for detecting insecure HTTP links in Wikipedia articles.

This analyzer is a single-responsibility module that detects external links
using http:// (insecure) and suggests converting them to https:// (secure).

It detects HTTP URLs in:
- Plain text
- References <ref>...</ref>
- Templates like {{Lien web}}
- Template parameters
- Any other wikitext context

It does NOT:
- Perform network requests (unless HTTPS verification is enabled)
- Check if HTTPS is actually available (unless HTTPS verification is enabled)
- Analyze internal Wikipedia links
- Check for broken links
- Handle other link-related issues

The detection is purely regex-based and deterministic.

HTTPS verification can be optionally enabled to avoid converting HTTP links to HTTPS
when the domain doesn't support HTTPS.
"""

import re
import logging
import time
from typing import List, Optional, Dict
from urllib.parse import urlparse
from .base import BaseAnalyzer, Issue

logger = logging.getLogger(__name__)


class HttpLinksAnalyzer(BaseAnalyzer):
    """
    Analyzer for detecting insecure HTTP links and suggesting HTTPS conversion.
    
    This analyzer has a single responsibility: find URLs starting with http://
    and suggest replacing them with https://. It operates entirely on regex
    pattern matching with no network calls, unless HTTPS verification is enabled.
    
    HTTPS verification can be optionally enabled to check if a domain actually
    supports HTTPS before suggesting the conversion.
    """

    # Regex pattern to match HTTP URLs
    # Matches http:// followed by valid URL characters (not whitespace, brackets, etc.)
    # This pattern detects HTTP URLs in various contexts (text, refs, templates)
    # Fixed to properly exclude template delimiters
    _HTTP_URL_RE = re.compile(
        r'http://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+',
        re.IGNORECASE
    )

    def __init__(self, max_issues: Optional[int] = None, 
                 enable_https_verification: bool = False,
                 https_verification_service = None,
                 max_https_checks: int = 30,
                 https_check_timeout: float = 60.0):
        """
        Initialize the HTTP links analyzer.
        
        Args:
            max_issues: Maximum number of HTTP links to report (None = no limit)
            enable_https_verification: Whether to verify HTTPS availability before suggesting conversion
            https_verification_service: HttpsVerificationService instance for HTTPS checks
            max_https_checks: Maximum number of HTTPS verifications per article (prevents blocking)
            https_check_timeout: Global timeout for all HTTPS checks in seconds (prevents long blocking)
        """
        super().__init__()
        self.max_issues = max_issues
        self.enable_https_verification = enable_https_verification
        self.https_verification_service = https_verification_service
        self.max_https_checks = max_https_checks
        self.https_check_timeout = https_check_timeout
        self._https_checks_count = 0
        self._https_check_start_time = None

    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze wikitext content for insecure HTTP links.
        
        Args:
            content: The article's wikitext
            
        Returns:
            List of Issue objects for each HTTP link found
        """
        self.clear_issues()
        
        if not content:
            return self.issues

        # Reset HTTPS check counters
        self._https_checks_count = 0
        self._https_check_start_time = time.time()
        self._https_verification_cache: Dict[str, str] = {}  # Cache for current analysis session
        
        logger.info(f"HttpLinksAnalyzer started - HTTPS verification: {self.enable_https_verification}, Service: {self.https_verification_service is not None}, max_checks: {self.max_https_checks}, timeout: {self.https_check_timeout}")

        # Use a mask to skip protected areas (nowiki, comments, etc.)
        protected_mask = self.build_protected_mask(content)

        # Find all HTTP URLs
        for match in self._HTTP_URL_RE.finditer(content):
            # Skip if this match is in a protected area
            if self.is_protected(protected_mask, match.start()):
                continue

            original_url = match.group(0)
            
            # Generate HTTPS version
            https_url = original_url.replace('http://', 'https://', 1)
            
            # Check HTTPS availability if verification is enabled
            should_suggest = True
            if self.enable_https_verification and self.https_verification_service:
                # Check limits to prevent blocking
                if self._should_skip_https_verification():
                    logger.warning(
                        f"HTTPS verification skipped: limits reached "
                        f"(checks: {self._https_checks_count}/{self.max_https_checks}, "
                        f"timeout: {self.https_check_timeout}s)"
                    )
                    # Skip verification but still suggest correction (conservative approach)
                    # Or set to False to not suggest correction without verification
                    should_suggest = False
                else:
                    try:
                        # Check cache first to avoid duplicate verifications
                        if original_url in self._https_verification_cache:
                            verification_result = self._https_verification_cache[original_url]
                            logger.info(f"Using cached HTTPS result for {original_url}: {verification_result.status.value}")
                        else:
                            logger.info(f"Vérification HTTPS pour : {original_url}")
                            verification_result = self.https_verification_service.verify_domain_from_url(original_url)
                            self._https_checks_count += 1
                            # Cache the result for this analysis session
                            self._https_verification_cache[original_url] = verification_result
                        
                        logger.info(f"Résultat HTTPS pour {original_url}: {verification_result.status.value}")
                        
                        # Only suggest correction if HTTPS is available
                        if verification_result.status.value != "HTTPS_AVAILABLE":
                            should_suggest = False
                            logger.debug(f"HTTPS not available for {original_url}: {verification_result.status.value}")
                    except Exception as e:
                        logger.warning(f"HTTPS verification failed for {original_url}: {e}")
                        # If verification fails, be conservative and don't suggest correction
                        should_suggest = False
            
            suggested_text = https_url if should_suggest else None
            
            self.issues.append(Issue(
                issue_type="http_link",
                description=f"Lien HTTP non sécurisé détecté : {original_url}",
                position=match.start(),
                original_text=original_url,
                suggested_text=suggested_text,
                severity="medium" if should_suggest else "low"
            ))

            # Apply max_issues limit if set
            if self.max_issues is not None and len(self.issues) >= self.max_issues:
                break

        # Sort issues by position
        self.issues.sort(key=lambda i: i.position)
        
        return self.issues
    
    def _should_skip_https_verification(self) -> bool:
        """
        Check if HTTPS verification should be skipped due to limits.
        
        Returns:
            True if limits are reached and verification should be skipped
        """
        # Check if we've exceeded max checks
        if self.max_https_checks is not None and self._https_checks_count >= self.max_https_checks:
            return True
        
        # Check if we've exceeded global timeout
        if self.https_check_timeout is not None:
            elapsed = time.time() - self._https_check_start_time
            if elapsed >= self.https_check_timeout:
                return True
        
        return False

    def get_analyzer_name(self) -> str:
        """Return the analyzer name."""
        return "HttpLinksAnalyzer"
    
    def extract_domain_from_url(self, url: str) -> Optional[str]:
        """
        Extract domain from URL for HTTPS verification.
        
        Args:
            url: HTTP URL
            
        Returns:
            Domain or None if invalid
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc or parsed.hostname
        except Exception:
            return None
