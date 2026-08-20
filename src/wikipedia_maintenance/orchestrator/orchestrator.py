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
from ..analyzers import DeadLinkAnalyzer
from ..utils.publisher import Corrector

logger = logging.getLogger(__name__)


@dataclass
class DeadLinkResult:
    """Result of dead link analysis."""
    original_content: str
    corrected_content: str
    issues: List[Issue]
    dead_links_found: int
    repairs_attempted: int
    repairs_successful: int


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
    ):
        """
        Args:
            language: Language code for analyzers.
            api_session: Optional requests.Session for API calls.
        """
        self.language = language
        self._session = api_session
        
        # OviX Dead Link Analyzer
        self.dead_link_analyzer = DeadLinkAnalyzer()
        
        # Corrector
        self.corrector: Optional[Corrector] = None
    
    def analyze(self, content: str) -> DeadLinkResult:
        """
        Analyze content for dead links and generate corrections.
        
        Args:
            content: Original wikicode.
            
        Returns:
            DeadLinkResult with analysis results.
        """
        logger.info("Starting dead link analysis")
        
        # Run dead link analyzer
        issues = self.dead_link_analyzer.analyze(content)
        
        # Count dead links
        dead_links_found = len([i for i in issues if i.issue_type == 'dead_link'])
        
        # Initialize corrector
        self.corrector = Corrector(content)
        
        # Apply corrections
        corrected = self.corrector.apply_corrections(issues)
        
        # Count repairs
        repairs_attempted = len([i for i in issues if i.suggested_text])
        repairs_successful = 1 if corrected != content else 0
        
        logger.info(f"Dead link analysis complete: {dead_links_found} dead links found, {repairs_successful} repairs applied")
        
        return DeadLinkResult(
            original_content=content,
            corrected_content=corrected,
            issues=issues,
            dead_links_found=dead_links_found,
            repairs_attempted=repairs_attempted,
            repairs_successful=repairs_successful
        )
