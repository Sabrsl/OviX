"""
Broken Link Analyzer - Checks for broken links in references.

This analyzer:
- Checks if links in references are broken (404, etc.)
- Respects configuration (references.check_broken_links, references.link_check_timeout)
- Uses LinkChecker for status verification
"""

import re
import logging
from typing import List, Optional, Dict, Any

from .base import BaseAnalyzer, Issue
from wikipedia_maintenance.utils.config import load_config
from wikipedia_maintenance.utils.link_checker import LinkChecker, LinkStatus

logger = logging.getLogger(__name__)


class BrokenLinkAnalyzer(BaseAnalyzer):
    """
    Analyzer for detecting broken links in references.
    
    Detects:
    - HTTP 404 errors
    - Connection failures
    - DNS resolution failures
    """

    # Pattern to match URLs in references
    URL_PATTERN = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%\u0080-\uFFFF]+', re.IGNORECASE)

    def __init__(self, name: str = None):
        super().__init__(name)
        
        # Load configuration
        self._load_config()
        
        # Initialize link checker if enabled
        self.link_checker: Optional[LinkChecker] = None
        if self.check_broken_links:
            self._initialize_link_checker()
        
        # Track statistics
        self.stats = {
            'links_checked': 0,
            'broken_links_found': 0,
            'total_issues': 0
        }

    def _load_config(self) -> None:
        """Load broken link analyzer configuration."""
        try:
            config = load_config()
            if hasattr(config, 'references'):
                self.check_broken_links = config.references.check_broken_links
                self.link_check_timeout = config.references.link_check_timeout
                logger.info(f"BrokenLinkAnalyzer config: check_broken_links={self.check_broken_links}, timeout={self.link_check_timeout}")
            else:
                # Default to disabled if config not found
                self.check_broken_links = False
                self.link_check_timeout = 5.0
                logger.warning("references config not found, defaulting to disabled")
        except Exception as e:
            logger.warning(f"Failed to load broken link analyzer config: {e}, defaulting to disabled")
            self.check_broken_links = False
            self.link_check_timeout = 5.0

    def _initialize_link_checker(self) -> None:
        """Initialize the link checker."""
        try:
            self.link_checker = LinkChecker(timeout=self.link_check_timeout)
            logger.info("BrokenLinkAnalyzer: LinkChecker initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize LinkChecker: {e}")
            self.link_checker = None

    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze content for broken links.
        
        Args:
            content: Wikicode content to analyze
            
        Returns:
            List of Issue objects
        """
        if not self.check_broken_links or not self.link_checker:
            logger.info("BrokenLinkAnalyzer disabled or LinkChecker not available")
            return []
        
        issues = []
        urls = self._extract_urls(content)
        
        for url, position in urls:
            self.stats['links_checked'] += 1
            
            try:
                result = self.link_checker.check_link(url)
                
                if result.status == LinkStatus.DEAD:
                    issue = Issue(
                        issue_type='broken_link',
                        description=f"Broken link detected: {url} ({result.http_status_code})",
                        position=position,
                        original_text=url,
                        suggested_text=None,  # No automatic suggestion for broken links
                        severity='high'
                    )
                    issues.append(issue)
                    self.stats['broken_links_found'] += 1
                elif result.status == LinkStatus.REVIEW_REQUIRED:
                    issue = Issue(
                        issue_type='broken_link',
                        description=f"Link requires review: {url} ({result.http_status_code})",
                        position=position,
                        original_text=url,
                        suggested_text=None,
                        severity='medium'
                    )
                    issues.append(issue)
                    self.stats['broken_links_found'] += 1
                    
            except Exception as e:
                logger.warning(f"Error checking link {url}: {e}")
        
        self.stats['total_issues'] = len(issues)
        logger.info(f"BrokenLinkAnalyzer: {len(issues)} broken links found (checked {self.stats['links_checked']} links)")
        
        return issues

    def _extract_urls(self, content: str) -> List[tuple]:
        """
        Extract URLs from content with their positions.
        
        Args:
            content: Wikicode content
            
        Returns:
            List of (url, position) tuples
        """
        urls = []
        
        for match in self.URL_PATTERN.finditer(content):
            url = match.group()
            position = match.start()
            urls.append((url, position))
        
        return urls

    def get_analyzer_name(self) -> str:
        """Return the analyzer name."""
        return "BrokenLinkAnalyzer"
