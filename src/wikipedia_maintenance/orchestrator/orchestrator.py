"""
Dead Link Orchestrator - Specialized for dead link detection and repair.

Implements a simplified workflow focused only on dead link analysis:
- Dead link detection
- Archive search
- Replacement discovery
- Correction generation
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..analyzers.base import Issue
from ..analyzers import DeadLinkAnalyzer, HttpLinksAnalyzer, XMLTypographyAnalyzer
from ..utils.publisher import Corrector
from ..utils.tracking_service import TrackingService
from ..utils.database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class DeadLinkResult:
    """Result of dead link analysis."""
    original_content: str
    corrected_content: str
    issues: List[Issue]
    dead_links_found: int = 0
    http_links_found: int = 0  # Number of HTTP links detected
    typo_corrections_found: int = 0  # Number of typo corrections found
    repairs_attempted: int = 0
    repairs_successful: int = 0


class DeadLinkOrchestrator:
    """
    Orchestrator specialized for dead link detection and repair.
    
    Workflow:
    1. Detect dead links
    2. Search for archives
    3. Find replacement candidates
    4. Generate corrections
    5. Apply corrections
    """
    
    def __init__(
        self,
        language: str = 'fr',
        api_session=None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        """
        Args:
            language: Language code for analyzers.
            api_session: Optional requests.Session for API calls.
            db_manager: Optional DatabaseManager for tracking service.
        """
        self.language = language
        self._session = api_session
        
        # Phase 2: Initialize TrackingService if db_manager provided
        self.tracking_service: Optional[TrackingService] = None
        if db_manager:
            try:
                self.tracking_service = TrackingService(db_manager)
                logger.info("Phase 2: TrackingService initialized in DeadLinkOrchestrator")
            except Exception as e:
                logger.warning(f"Phase 2: Failed to initialize TrackingService: {e}")
        
        # OviX Dead Link Analyzer with tracking service
        self.dead_link_analyzer = DeadLinkAnalyzer(tracking_service=self.tracking_service)
        
        # OviX HTTP Links Analyzer (for HTTP→HTTPS conversion)
        self.http_links_analyzer = HttpLinksAnalyzer()
        
        # OviX XML Typography Analyzer (for typo correction)
        from ..utils.typography_xml_analyzer_config import TypographyXMLAnalyzerConfig
        xml_config = TypographyXMLAnalyzerConfig.load()
        self.xml_typography_analyzer = XMLTypographyAnalyzer.from_config(xml_config)
        
        # Corrector
        self.corrector: Optional[Corrector] = None
    
    def analyze(self, content: str) -> DeadLinkResult:
        """
        Analyze content for dead links, HTTP links, and typography issues, then generate corrections.
        
        Args:
            content: Original wikicode.
            
        Returns:
            DeadLinkResult with analysis results.
        """
        logger.info("Starting dead link, HTTP link, and typography analysis")
        
        # Run dead link analyzer
        dead_link_issues = self.dead_link_analyzer.analyze(content)
        
        # Run HTTP links analyzer (if enabled)
        http_link_issues = self.http_links_analyzer.analyze(content)
        
        # Run XML typography analyzer (if enabled)
        typo_issues = self.xml_typography_analyzer.analyze(content)
        
        # Combine all issues
        issues = dead_link_issues + http_link_issues + typo_issues
        
        # Count issues by type
        dead_links_found = len([i for i in issues if i.issue_type == 'dead_link'])
        http_links_found = len([i for i in issues if i.issue_type == 'http_link'])
        typo_corrections_found = len([i for i in issues if i.issue_type == 'typo'])
        
        # Initialize corrector
        self.corrector = Corrector(content)
        
        # Apply corrections
        corrected = self.corrector.apply_corrections(issues)
        
        # Count repairs
        repairs_attempted = len([i for i in issues if i.suggested_text])
        repairs_successful = len([c for c in self.corrector.corrections if c.applied])
        
        logger.info(
            f"Analysis complete: {dead_links_found} dead links found, "
            f"{http_links_found} HTTP links found, {typo_corrections_found} typo corrections found, "
            f"{repairs_successful} repairs applied"
        )
        
        return DeadLinkResult(
            original_content=content,
            corrected_content=corrected,
            issues=issues,
            dead_links_found=dead_links_found,
            http_links_found=http_links_found,
            typo_corrections_found=typo_corrections_found,
            repairs_attempted=repairs_attempted,
            repairs_successful=repairs_successful
        )
