"""
Reference Analyzer - Detects bare URLs and duplicate references.

This analyzer:
- Detects bare URLs (URLs without {{Lien web}} template)
- Detects duplicate references
- Respects configuration (references.check_bare_refs, references.check_duplicate_refs)
"""

import re
import logging
from typing import List, Optional, Dict, Any

from .base import BaseAnalyzer, Issue
from wikipedia_maintenance.utils.config import load_config
from wikipedia_maintenance.utils.reference_utils import find_duplicate_refs

logger = logging.getLogger(__name__)


class ReferenceAnalyzer(BaseAnalyzer):
    """
    Analyzer for detecting reference issues.
    
    Detects:
    - Bare URLs (URLs in <ref> without proper template)
    - Duplicate references
    """

    # Pattern to match bare URLs in <ref> tags
    BARE_URL_PATTERN = re.compile(r'<ref[^>]*>(https?://[^\s<]+)</ref>', re.IGNORECASE)

    def __init__(self, name: str = None):
        super().__init__(name)
        
        # Load configuration
        self._load_config()
        
        # Track statistics
        self.stats = {
            'bare_urls_found': 0,
            'duplicate_refs_found': 0,
            'total_issues': 0
        }

    def _load_config(self) -> None:
        """Load reference analyzer configuration."""
        try:
            config = load_config()
            if hasattr(config, 'references'):
                self.check_bare_refs = config.references.check_bare_refs
                self.check_duplicate_refs = config.references.check_duplicate_refs
                logger.info(f"ReferenceAnalyzer config: check_bare_refs={self.check_bare_refs}, check_duplicate_refs={self.check_duplicate_refs}")
            else:
                # Default to enabled if config not found
                self.check_bare_refs = True
                self.check_duplicate_refs = True
                logger.warning("references config not found, defaulting to enabled")
        except Exception as e:
            logger.warning(f"Failed to load reference analyzer config: {e}, defaulting to enabled")
            self.check_bare_refs = True
            self.check_duplicate_refs = True

    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze content for reference issues.
        
        Args:
            content: Wikicode content to analyze
            
        Returns:
            List of Issue objects
        """
        issues = []
        
        # Check for bare URLs if enabled
        if self.check_bare_refs:
            bare_issues = self._find_bare_urls(content)
            issues.extend(bare_issues)
            self.stats['bare_urls_found'] = len(bare_issues)
        
        # Check for duplicate references if enabled
        if self.check_duplicate_refs:
            duplicate_issues = self._find_duplicate_references(content)
            issues.extend(duplicate_issues)
            self.stats['duplicate_refs_found'] = len(duplicate_issues)
        
        self.stats['total_issues'] = len(issues)
        logger.info(f"ReferenceAnalyzer: {len(issues)} issues found (bare={self.stats['bare_urls_found']}, duplicates={self.stats['duplicate_refs_found']})")
        
        return issues

    def _find_bare_urls(self, content: str) -> List[Issue]:
        """
        Find bare URLs in <ref> tags.
        
        Args:
            content: Wikicode content
            
        Returns:
            List of Issue objects for bare URLs
        """
        issues = []
        
        for match in self.BARE_URL_PATTERN.finditer(content):
            url = match.group(1)
            position = match.start()
            
            issue = Issue(
                issue_type='bare_url',
                description=f"Bare URL detected in reference: {url}",
                position=position,
                original_text=match.group(),
                suggested_text=f"{{{{Lien web|url={url}}}}}",
                severity='medium'
            )
            issues.append(issue)
        
        return issues

    def _find_duplicate_references(self, content: str) -> List[Issue]:
        """
        Find duplicate references.
        
        Args:
            content: Wikicode content
            
        Returns:
            List of Issue objects for duplicate references
        """
        issues = []
        
        duplicates = find_duplicate_refs(content)
        
        for normalized_ref, positions in duplicates:
            # Create an issue for each duplicate occurrence (skip the first one)
            for position in positions[1:]:
                issue = Issue(
                    issue_type='duplicate_reference',
                    description=f"Duplicate reference detected",
                    position=position,
                    original_text=normalized_ref[:100],  # Truncate for display
                    suggested_text=None,  # No automatic suggestion for duplicates
                    severity='low'
                )
                issues.append(issue)
        
        return issues

    def get_analyzer_name(self) -> str:
        """Return the analyzer name."""
        return "ReferenceAnalyzer"
