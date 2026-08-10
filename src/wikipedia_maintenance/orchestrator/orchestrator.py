"""
Wikification orchestrator for Phase 1-4 processing.

Implements the 4-phase wikification process:
- Phase 1: Audit (sections, works lists, infobox)
- Phase 2: "Voir aussi" algorithm
- Phase 2bis: Section structure (duplicates, heading levels)
- Phase 3: Full wikification (all analyzers)
- Phase 4: Checklist verification
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..analyzers.base import Issue
from ..analyzers import (
    LinkAnalyzer, TypographyAnalyzer, WhitespaceAnalyzer,
    TemplateAnalyzer, HTMLAnalyzer, CategoryAnalyzer,
    ReferenceAnalyzer, StructureAnalyzer, WorksListAnalyzer,
    HttpLinksAnalyzer, DeadLinkAnalyzer
)
from ..utils.corrector import Corrector
from ..utils.ui_settings import get_settings_manager
from ..utils.database import DatabaseManager
from ..utils.https_verification_cache import HttpsVerificationCache
from ..utils.https_verification_service import HttpsVerificationService
from .checklist import ChecklistChecker, CheckResult

logger = logging.getLogger(__name__)


@dataclass
class AuditReport:
    """Report from Phase 1 audit."""
    sections: List[Dict[str, Any]]
    works_lists: List[Dict[str, Any]]
    infobox_status: Dict[str, Any]


@dataclass
class StructurePlan:
    """Plan from Phase 2 structure analysis."""
    voir_aussi_restructure: bool
    duplicate_sections: List[str]
    heading_level_fixes: List[Dict[str, Any]]


@dataclass
class WikificationResult:
    """Final result of wikification process."""
    original_content: str
    corrected_content: str
    phase1_audit: AuditReport
    phase2_plan: StructurePlan
    phase3_issues: List[Issue]
    phase4_checklist: List[CheckResult]
    checklist_report: str


class WikificationOrchestrator:
    """
    Orchestrates the 4-phase wikification process.
    
    Phase 1: Audit sections, works lists, infobox
    Phase 2: Apply "Voir aussi" algorithm
    Phase 2bis: Fix section structure (duplicates, heading levels)
    Phase 3: Run all analyzers for full wikification
    Phase 4: Run checklist verification
    """
    
    def __init__(
        self,
        language: str = 'fr',
        api_session=None,
        enable_reference_analyzer: bool = True,
        enable_structure_analyzer: bool = True,
        enable_works_analyzer: bool = True,
    ):
        """
        Args:
            language: Language code for analyzers.
            api_session: Optional requests.Session for API calls.
            enable_reference_analyzer: Enable ReferenceAnalyzer.
            enable_structure_analyzer: Enable StructureAnalyzer.
            enable_works_analyzer: Enable WorksListAnalyzer.
        """
        self.language = language
        self._session = api_session
        
        # Analyzers are now initialized dynamically based on settings
        self.link_analyzer = None
        self.typography_analyzer = None
        self.whitespace_analyzer = None
        self.template_analyzer = None
        self.html_analyzer = None
        self.category_analyzer = None
        self.reference_analyzer = None
        self.structure_analyzer = None
        self.works_analyzer = None
        
        # Checklist checker
        self.checklist_checker = ChecklistChecker(language=language)
        
        # Corrector
        self.corrector: Optional[Corrector] = None
    
    def run_phase1_audit(self, content: str) -> AuditReport:
        """
        Phase 1: Audit sections, works lists, and infobox.
        
        Args:
            content: Original wikicode.
            
        Returns:
            AuditReport with findings.
        """
        logger.info("Starting Phase 1: Audit")
        
        sections = []
        works_lists = []
        infobox_status = {}
        
        # Audit sections
        if self.structure_analyzer:
            structure_issues = self.structure_analyzer.analyze(content)
            # Extract section info from structure analyzer
            # This is a simplified version - in practice, we'd add methods to StructureAnalyzer
            sections = [
                {
                    'title': 'Section audit',
                    'issue_count': len(structure_issues),
                    'issues': [i.description for i in structure_issues[:5]]
                }
            ]
        
        # Audit works lists
        if self.works_analyzer:
            works_issues = self.works_analyzer.analyze(content)
            works_lists = [
                {
                    'type': 'Filmographie/Discographie/Bibliographie',
                    'issue_count': len(works_issues),
                    'issues': [i.description for i in works_issues[:5]]
                }
            ]
        
        # Audit infobox (via template analyzer)
        template_issues = self.template_analyzer.analyze(content)
        infobox_issues = [i for i in template_issues if 'infobox' in i.description.lower()]
        infobox_status = {
            'has_infobox': '{{Infobox' in content or '{{infobox' in content,
            'issue_count': len(infobox_issues),
            'issues': [i.description for i in infobox_issues[:5]]
        }
        
        logger.info(f"Phase 1 complete: {len(sections)} sections, {len(works_lists)} works lists, infobox: {infobox_status['has_infobox']}")
        
        return AuditReport(
            sections=sections,
            works_lists=works_lists,
            infobox_status=infobox_status
        )
    
    def run_phase2_algo(self, content: str, audit: AuditReport) -> StructurePlan:
        """
        Phase 2: Apply "Voir aussi" algorithm.
        
        Args:
            content: Original wikicode.
            audit: Audit report from Phase 1.
            
        Returns:
            StructurePlan with restructuring recommendations.
        """
        logger.info("Starting Phase 2: Voir aussi algorithm")
        
        voir_aussi_restructure = False
        duplicate_sections = []
        heading_level_fixes = []
        
        if self.structure_analyzer:
            # Run structure analyzer to get "Voir aussi" recommendations
            structure_issues = self.structure_analyzer.analyze(content)
            
            # Check for "Voir aussi" restructure issues
            voir_aussi_issues = [i for i in structure_issues if i.issue_type == 'voir_aussi_restructure']
            voir_aussi_restructure = len(voir_aussi_issues) > 0
            
            # Check for duplicate sections
            duplicate_section_issues = [i for i in structure_issues if i.issue_type == 'duplicate_section']
            duplicate_sections = [i.description for i in duplicate_section_issues]
            
            # Check for heading level issues
            heading_issues = [i for i in structure_issues if i.issue_type == 'heading_level_jump']
            heading_level_fixes = [
                {'position': i.position, 'description': i.description}
                for i in heading_issues
            ]
        
        logger.info(f"Phase 2 complete: voir_aussi={voir_aussi_restructure}, duplicates={len(duplicate_sections)}, heading_fixes={len(heading_level_fixes)}")
        
        return StructurePlan(
            voir_aussi_restructure=voir_aussi_restructure,
            duplicate_sections=duplicate_sections,
            heading_level_fixes=heading_level_fixes
        )
    
    def run_phase2bis_sections(self, content: str, plan: StructurePlan) -> str:
        """
        Phase 2bis: Apply section structure corrections.
        
        Note: This is a placeholder. Actual corrections would require
        sophisticated content manipulation and should be done manually
        or with user approval.
        
        Args:
            content: Wikicode to correct.
            plan: Structure plan from Phase 2.
            
        Returns:
            Corrected wikicode (placeholder - returns original).
        """
        logger.info("Starting Phase 2bis: Section structure corrections")
        
        # In a real implementation, this would:
        # - Merge duplicate sections
        # - Fix heading level jumps
        # - Restructure "Voir aussi"
        
        # For now, return original content (manual correction required)
        logger.info("Phase 2bis complete: manual correction required")
        return content
    
    def run_phase3_wikify(self, content: str, plan: StructurePlan) -> str:
        """
        Phase 3: Run all analyzers for full wikification.
        
        Args:
            content: Wikicode to wikify.
            plan: Structure plan (may influence corrections).
            
        Returns:
            Wikified content.
        """
        logger.info("Starting Phase 3: Full wikification")
        
        # Get enabled analyzers from settings
        settings_manager = get_settings_manager()
        settings = settings_manager.get_settings()
        enabled_analyzer_names = settings.get_enabled_analyzers()
        
        # Map analyzer names to their classes
        analyzer_classes = {
            "LinkAnalyzer": LinkAnalyzer,
            "WhitespaceAnalyzer": WhitespaceAnalyzer,
            "TypographyAnalyzer": TypographyAnalyzer,
            "TemplateAnalyzer": TemplateAnalyzer,
            "CategoryAnalyzer": CategoryAnalyzer,
            "HTMLAnalyzer": HTMLAnalyzer,
            "ReferenceAnalyzer": ReferenceAnalyzer,
            "StructureAnalyzer": StructureAnalyzer,
            "WorksListAnalyzer": WorksListAnalyzer,
            "HttpLinksAnalyzer": HttpLinksAnalyzer,
            "DeadLinkAnalyzer": DeadLinkAnalyzer
        }
        
        # Initialize only enabled analyzers
        analyzers = []
        
        # Get UI settings for HTTPS verification
        settings_manager = get_settings_manager()
        settings = settings_manager.settings
        
        # Initialize HTTPS verification service if HttpLinksAnalyzer is enabled
        https_service = None
        if "HttpLinksAnalyzer" in enabled_analyzer_names:
            # Always enable HTTPS verification when HttpLinksAnalyzer is active
            # This is the safe default to avoid converting HTTP links without verification
            db_manager = DatabaseManager()
            cache = HttpsVerificationCache(db_manager)
            https_service = HttpsVerificationService(
                cache,
                timeout=settings.https_check_timeout
            )
        
        for analyzer_name in enabled_analyzer_names:
            if analyzer_name in analyzer_classes:
                if analyzer_name == "HttpLinksAnalyzer":
                    # Always enable HTTPS verification when HttpLinksAnalyzer is active
                    analyzers.append(analyzer_classes[analyzer_name](
                        enable_https_verification=True,  # Force enable
                        https_verification_service=https_service,
                        max_https_checks=settings.max_https_checks,
                        https_check_timeout=settings.https_check_timeout
                    ))
                elif analyzer_name in ["LinkAnalyzer", "WhitespaceAnalyzer", "ReferenceAnalyzer", "StructureAnalyzer", "WorksListAnalyzer"]:
                    analyzers.append(analyzer_classes[analyzer_name](language=self.language))
                else:
                    analyzers.append(analyzer_classes[analyzer_name]())
        
        if not analyzers:
            logger.warning("No analyzers enabled, skipping Phase 3")
            return content
        
        # Initialize corrector
        self.corrector = Corrector(content)
        
        # Collect all issues from all analyzers
        all_issues = []
        
        # Run enabled analyzers
        for analyzer in analyzers:
            try:
                issues = analyzer.analyze(content)
                all_issues.extend(issues)
            except Exception as e:
                logger.warning(f"{analyzer.__class__.__name__} failed: {e}")
        
        # Sort issues by position (reverse order for application)
        all_issues.sort(key=lambda i: i.position if i.position is not None else 0, reverse=True)
        
        logger.info(f"Phase 3: {len(all_issues)} issues detected")
        
        # Apply corrections (only those with suggested_text)
        # In a real implementation, this would be more sophisticated
        # and would require user approval for each correction
        corrected = content  # Placeholder - return original for safety
        
        return corrected
    
    def run_phase4_checklist(self, original_content: str, corrected_content: str) -> List[CheckResult]:
        """
        Phase 4: Run checklist verification.
        
        Args:
            original_content: Original wikicode.
            corrected_content: Corrected wikicode.
            
        Returns:
            List of CheckResult objects.
        """
        logger.info("Starting Phase 4: Checklist verification")
        
        results = self.checklist_checker.run_checks(original_content, corrected_content)
        
        passed = sum(1 for r in results if r.status.value == 'pass')
        failed = sum(1 for r in results if r.status.value == 'fail')
        warnings = sum(1 for r in results if r.status.value == 'warning')
        
        logger.info(f"Phase 4 complete: {passed} passed, {failed} failed, {warnings} warnings")
        
        return results
    
    def wikify(self, content: str) -> WikificationResult:
        """
        Run the complete 4-phase wikification process.
        
        Args:
            content: Original wikicode.
            
        Returns:
            WikificationResult with all phase outputs.
        """
        logger.info("Starting complete wikification process")
        
        # Phase 1: Audit
        phase1_audit = self.run_phase1_audit(content)
        
        # Phase 2: Voir aussi algorithm
        phase2_plan = self.run_phase2_algo(content, phase1_audit)
        
        # Phase 2bis: Section structure corrections
        content_after_2bis = self.run_phase2bis_sections(content, phase2_plan)
        
        # Phase 3: Full wikification
        corrected_content = self.run_phase3_wikify(content_after_2bis, phase2_plan)
        
        # Collect issues from Phase 3
        phase3_issues = []
        if self.corrector:
            phase3_issues = self.corrector.corrections
        
        # Phase 4: Checklist
        phase4_checklist = self.run_phase4_checklist(content, corrected_content)
        checklist_report = self.checklist_checker.generate_report(phase4_checklist)
        
        logger.info("Wikification process complete")
        
        return WikificationResult(
            original_content=content,
            corrected_content=corrected_content,
            phase1_audit=phase1_audit,
            phase2_plan=phase2_plan,
            phase3_issues=phase3_issues,
            phase4_checklist=phase4_checklist,
            checklist_report=checklist_report
        )
