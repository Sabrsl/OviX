"""
HTTP Links Analyzer - Detects and verifies HTTP to HTTPS conversion.

This analyzer:
- Detects HTTP links (http://) in wikitext
- Verifies if HTTPS equivalent is available using HttpsVerificationService
- Creates http_link issues only when HTTPS is confirmed available
- Respects configuration (https_verification.enabled)
- Handles {{Lien web}} templates properly
- Never proposes conversion when HTTPS is unavailable or uncertain
"""

import re
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from .base import BaseAnalyzer, Issue
from wikipedia_maintenance.utils.https_verification_service import HttpsVerificationService, VerificationResult
from wikipedia_maintenance.utils.https_verification_cache import HttpsVerificationCache, VerificationStatus
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper
from wikipedia_maintenance.utils.config import load_config

logger = logging.getLogger(__name__)


class HttpLinksAnalyzer(BaseAnalyzer):
    """
    Analyzer for detecting HTTP links and verifying HTTPS availability.
    
    Only proposes http:// → https:// conversion when HTTPS is confirmed available.
    """

    # Pattern to match HTTP URLs (but not HTTPS)
    HTTP_URL_PATTERN = re.compile(r'http://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=%]+', re.IGNORECASE)

    def __init__(self, name: str = None):
        super().__init__(name)
        
        # Load configuration
        self._load_config()
        
        # Initialize verification service only if enabled
        self.https_verification_service: Optional[HttpsVerificationService] = None
        self.https_cache: Optional[HttpsVerificationCache] = None
        
        if self.enabled:
            self._initialize_verification_service()
        
        # Helper for reference templates
        self.reference_template_helper = ReferenceTemplateHelper()
        
        # Track statistics
        self.stats = {
            'http_links_found': 0,
            'https_verified_available': 0,
            'https_verified_unavailable': 0,
            'https_check_failed': 0,
            'https_cache_hits': 0,
            'corrections_proposed': 0
        }

    def _load_config(self) -> None:
        """Load HTTPS verification configuration."""
        try:
            config = load_config()
            if hasattr(config, 'https_verification'):
                self.enabled = config.https_verification.enabled
                self.timeout = config.https_verification.timeout
                logger.info(f"HttpLinksAnalyzer config: enabled={self.enabled}, timeout={self.timeout}")
            else:
                # Default to disabled if config not found
                self.enabled = False
                self.timeout = 10.0
                logger.warning("https_verification config not found, defaulting to disabled")
        except Exception as e:
            logger.warning(f"Failed to load HTTPS verification config: {e}, defaulting to disabled")
            self.enabled = False
            self.timeout = 10.0

    def _initialize_verification_service(self) -> None:
        """Initialize HTTPS verification service and cache."""
        try:
            from wikipedia_maintenance.utils.database import DatabaseManager
            
            # Get database manager
            db_manager = DatabaseManager()
            
            # Initialize cache with TTL from config
            config = load_config()
            ttl_available = getattr(config.https_verification, 'ttl_available', 30)
            ttl_unavailable = getattr(config.https_verification, 'ttl_unavailable', 7)
            ttl_failed = getattr(config.https_verification, 'ttl_failed', 1)
            
            self.https_cache = HttpsVerificationCache(
                db_manager=db_manager,
                ttl_available=ttl_available,
                ttl_unavailable=ttl_unavailable,
                ttl_failed=ttl_failed
            )
            
            # Initialize verification service
            self.https_verification_service = HttpsVerificationService(
                cache=self.https_cache,
                timeout=int(self.timeout)
            )
            
            logger.info("HttpsVerificationService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize HTTPS verification service: {e}")
            self.enabled = False

    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze content for HTTP links and verify HTTPS availability.
        
        Args:
            content: Wikitext content to analyze
            
        Returns:
            List of Issue objects for HTTP→HTTPS conversions
        """
        self.clear_issues()
        
        if not self.enabled:
            logger.info("HttpLinksAnalyzer is disabled in configuration")
            return self.issues
        
        if not content:
            logger.warning("HttpLinksAnalyzer: empty content provided")
            return self.issues
        
        logger.info(f"HttpLinksAnalyzer started - content_length: {len(content)}")
        
        # Build protected mask to skip nowiki, comments, etc.
        protected_mask = self.build_protected_mask(content)
        
        # Find all HTTP URLs
        all_matches = list(self.HTTP_URL_PATTERN.finditer(content))
        protected_matches = [m for m in all_matches if not self.is_protected(protected_mask, m.start())]
        
        logger.info(f"Found {len(protected_matches)} HTTP URLs to check")
        
        # Process each HTTP URL
        for match in protected_matches:
            http_url = match.group(0)
            position = match.start()
            
            # Skip if this is inside a reference template (will be handled separately)
            template = self.reference_template_helper.find_reference_template(content, http_url, position)
            if template:
                logger.debug(f"HTTP URL inside template, will handle separately: {http_url[:50]}")
                self._process_http_in_template(content, http_url, position, template)
            else:
                # Process bare HTTP URL
                self._process_bare_http_url(content, http_url, position)
        
        # Log statistics
        logger.info(
            f"HttpLinksAnalyzer complete - "
            f"http_links_found={self.stats['http_links_found']}, "
            f"https_available={self.stats['https_verified_available']}, "
            f"https_unavailable={self.stats['https_verified_unavailable']}, "
            f"https_failed={self.stats['https_check_failed']}, "
            f"cache_hits={self.stats['https_cache_hits']}, "
            f"corrections_proposed={self.stats['corrections_proposed']}"
        )
        
        return self.issues

    def _process_bare_http_url(self, content: str, http_url: str, position: int) -> None:
        """
        Process a bare HTTP URL (not inside a template).
        
        Args:
            content: Full wikitext content
            http_url: The HTTP URL found
            position: Position of the URL in content
        """
        self.stats['http_links_found'] += 1
        
        # Verify HTTPS availability
        verification_result = self._verify_https_availability(http_url)
        
        if verification_result.status == VerificationStatus.HTTPS_AVAILABLE:
            # HTTPS is available - propose conversion
            https_url = http_url.replace('http://', 'https://', 1)
            
            self.issues.append(Issue(
                issue_type="http_link",
                description=f"Lien HTTP non sécurisé (HTTPS disponible) : {http_url}",
                position=position,
                original_text=http_url,
                suggested_text=https_url,
                severity="low",  # Low severity as it's an improvement, not a critical issue
                confidence=1.0,
                extra={
                    'http_url': http_url,
                    'https_url': https_url,
                    'verification_status': verification_result.status.value,
                    'http_status_code': verification_result.http_status_code
                }
            ))
            
            self.stats['corrections_proposed'] += 1
            logger.info(f"HTTP→HTTPS conversion proposed: {http_url[:50]} → {https_url[:50]}")
        else:
            # HTTPS not available or check failed - no conversion
            logger.debug(
                f"HTTPS not available for {http_url[:50]}: "
                f"status={verification_result.status.value}, "
                f"error={verification_result.error_type}"
            )

    def _process_http_in_template(self, content: str, http_url: str, position: int, template) -> None:
        """
        Process HTTP URL inside a reference template (e.g., {{Lien web}}).
        
        Args:
            content: Full wikitext content
            http_url: The HTTP URL found
            position: Position of the URL in content
            template: Reference template containing the URL
        """
        self.stats['http_links_found'] += 1
        
        # Verify HTTPS availability
        verification_result = self._verify_https_availability(http_url)
        
        if verification_result.status == VerificationStatus.HTTPS_AVAILABLE:
            # HTTPS is available - propose conversion only for the url parameter
            https_url = http_url.replace('http://', 'https://', 1)
            
            # Find the exact position of the URL within the template
            # We need to replace only the URL parameter value, not break the template
            template_text = template.full_match
            url_position_in_template = template_text.find(http_url)
            
            if url_position_in_template >= 0:
                # Calculate absolute position
                absolute_position = template.start_position + url_position_in_template
                
                self.issues.append(Issue(
                    issue_type="http_link",
                    description=f"Lien HTTP dans template (HTTPS disponible) : {http_url}",
                    position=absolute_position,
                    original_text=http_url,
                    suggested_text=https_url,
                    severity="low",
                    confidence=1.0,
                    extra={
                        'http_url': http_url,
                        'https_url': https_url,
                        'template_name': template.template_name,
                        'verification_status': verification_result.status.value,
                        'http_status_code': verification_result.http_status_code
                    }
                ))
                
                self.stats['corrections_proposed'] += 1
                logger.info(
                    f"HTTP→HTTPS conversion proposed in {template.template_name}: "
                    f"{http_url[:50]} → {https_url[:50]}"
                )
            else:
                logger.warning(f"Could not find URL position within template: {http_url[:50]}")
        else:
            # HTTPS not available - no conversion
            logger.debug(
                f"HTTPS not available for template URL {http_url[:50]}: "
                f"status={verification_result.status.value}"
            )

    def _verify_https_availability(self, http_url: str) -> VerificationResult:
        """
        Verify if HTTPS is available for the given HTTP URL.
        
        Args:
            http_url: HTTP URL to check
            
        Returns:
            VerificationResult with HTTPS availability status
        """
        if not self.https_verification_service:
            logger.warning("HTTPS verification service not initialized")
            return VerificationResult(
                status=VerificationStatus.CHECK_FAILED,
                domain="",
                https_url=None,
                error_type="SERVICE_NOT_INITIALIZED"
            )
        
        try:
            # Extract domain from URL
            parsed = urlparse(http_url)
            domain = parsed.netloc or parsed.hostname
            
            if not domain:
                logger.warning(f"Could not extract domain from URL: {http_url}")
                return VerificationResult(
                    status=VerificationStatus.CHECK_FAILED,
                    domain="",
                    https_url=None,
                    error_type="INVALID_DOMAIN"
                )
            
            # Check if result is cached
            cached = self.https_cache.get(domain)
            if cached:
                self.stats['https_cache_hits'] += 1
                logger.debug(f"Cache hit for domain: {domain}")
                return VerificationResult(
                    status=cached['status_enum'],
                    domain=domain,
                    https_url=cached.get('https_url'),
                    http_status_code=cached.get('http_status_code'),
                    redirect_url=cached.get('redirect_url'),
                    error_type=cached.get('error_type')
                )
            
            # Perform HTTPS verification
            result = self.https_verification_service.verify_domain(domain)
            
            # Update statistics
            if result.status == VerificationStatus.HTTPS_AVAILABLE:
                self.stats['https_verified_available'] += 1
            elif result.status == VerificationStatus.HTTPS_UNAVAILABLE:
                self.stats['https_verified_unavailable'] += 1
            else:
                self.stats['https_check_failed'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Error during HTTPS verification for {http_url}: {e}")
            self.stats['https_check_failed'] += 1
            return VerificationResult(
                status=VerificationStatus.CHECK_FAILED,
                domain="",
                https_url=None,
                error_type="VERIFICATION_ERROR"
            )

    def get_analyzer_name(self) -> str:
        """Return the analyzer name."""
        return "HttpLinksAnalyzer"
