"""
Analyzer for article structure and section-related issues in Wikipedia articles.

Detects:
    - Section audit (list and count sections)
    - "Voir aussi" algorithm (≥2 sections to restructure)
    - Heading level jumps (inconsistent section levels)
    - Duplicate sections that should be merged
    - Portal template placement ({{Portail|...}} before categories)
    - Section order (body → notes → portal → categories)
    - Works/Publications vs Bibliography distinction
    - Empty sections

All checks are non-destructive and preserve existing functionality.
"""

from __future__ import annotations

import re
import logging
from typing import List, Optional, Dict, Set, Tuple
from dataclasses import dataclass

from .base import BaseAnalyzer, Issue

logger = logging.getLogger(__name__)


@dataclass
class SectionInfo:
    """Information about a section."""
    level: int  # Heading level (1-6)
    title: str  # Section title
    position: int  # Position in content
    line_number: int  # Line number (1-based)
    content: str  # Full heading line


class StructureAnalyzer(BaseAnalyzer):
    """Analyzes articles for structure and section-related issues."""

    # ---- Precompiled patterns ----
    
    # Section headings: == Title ==, === Title ===, etc.
    _HEADING_RE = re.compile(r'^(={1,6})\s*([^=]+?)\s*\1\s*$', re.MULTILINE)
    
    # Portal template: {{Portail|...}}
    _PORTAL_RE = re.compile(r'\{\{[Pp]ortail\|[^}]+\}\}')
    
    # Category link: [[Catégorie:...]] or [[Category:...]]
    _CATEGORY_RE = re.compile(r'\[\[(?:Catégorie|Category):[^\]]+\]\]', re.IGNORECASE)
    
    # Common section names (French)
    _COMMON_SECTIONS = {
        'voir aussi', 'notes et références', 'notes', 'références',
        'bibliographie', 'sources', 'liens externes', 'annexes',
        'articles connexes', 'filmographie', 'discographie', 'œuvres',
        'publications', 'distinctions', 'prix', 'homonymie'
    }
    
    # Works-related sections
    _WORKS_SECTIONS = {'filmographie', 'discographie', 'œuvres', 'publications'}
    
    def __init__(
        self,
        language: str = 'fr',
        check_heading_levels: bool = True,
        check_duplicate_sections: bool = True,
        check_voir_aussi_algorithm: bool = True,
        check_portal_placement: bool = True,
        check_section_order: bool = True,
        check_empty_sections: bool = True,
    ):
        """
        Args:
            language: Language code for section names.
            check_heading_levels: Detect heading level jumps.
            check_duplicate_sections: Detect duplicate sections.
            check_voir_aussi_algorithm: Apply "Voir aussi" restructuring algorithm.
            check_portal_placement: Check portal template placement.
            check_section_order: Check overall section order.
            check_empty_sections: Detect empty sections.
        """
        super().__init__()
        self.language = language.lower()
        self.check_heading_levels = check_heading_levels
        self.check_duplicate_sections = check_duplicate_sections
        self.check_voir_aussi_algorithm = check_voir_aussi_algorithm
        self.check_portal_placement = check_portal_placement
        self.check_section_order = check_section_order
        self.check_empty_sections = check_empty_sections

    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze content for structure issues.

        Args:
            content: Article wikicode content

        Returns:
            List of detected issues (sorted by position)
        """
        self.clear_issues()
        if not content:
            return self.issues

        # Phase 1: Audit sections
        sections = self._audit_sections(content)
        
        # Phase 2: Apply "Voir aussi" algorithm
        if self.check_voir_aussi_algorithm:
            self._calculate_voir_aussi_algorithm(content, sections)
        
        # Phase 2bis: Other structure checks
        if self.check_heading_levels:
            self._detect_heading_level_jumps(sections)
        
        if self.check_duplicate_sections:
            self._detect_duplicate_sections(sections)
        
        if self.check_portal_placement:
            self._detect_portal_placement(content)
        
        if self.check_section_order:
            self._detect_section_order(content, sections)
        
        if self.check_empty_sections:
            self._detect_empty_sections(content, sections)
        
        if self.check_duplicate_sections:
            self._detect_works_vs_bibliography(sections)

        # Sort issues by position
        self.issues.sort(key=lambda i: i.position)
        return self.issues

    def get_analyzer_name(self) -> str:
        return "StructureAnalyzer"

    # ------------------------------------------------------------------
    # Phase 1: Section audit
    # ------------------------------------------------------------------

    def _audit_sections(self, content: str) -> List[SectionInfo]:
        """
        Audit all sections in the article.
        
        Returns:
            List of SectionInfo objects
        """
        sections = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, start=1):
            match = self._HEADING_RE.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                position = content.find(line)
                
                sections.append(SectionInfo(
                    level=level,
                    title=title,
                    position=position,
                    line_number=i,
                    content=line
                ))
        
        return sections

    # ------------------------------------------------------------------
    # Phase 2: "Voir aussi" algorithm
    # ------------------------------------------------------------------

    def _calculate_voir_aussi_algorithm(self, content: str, sections: List[SectionInfo]) -> None:
        """
        Apply the "Voir aussi" restructuring algorithm.
        
        If there are ≥2 sections that could be merged into "Voir aussi",
        suggest restructuring.
        """
        # Look for sections that could be in "Voir aussi"
        voir_aussi_candidates = []
        
        for section in sections:
            title_lower = section.title.lower()
            # Common "Voir aussi" subsections
            if any(candidate in title_lower for candidate in [
                'articles connexes', 'liens internes', 'pages liées',
                'sur le même sujet', 'thèmes connexes'
            ]):
                voir_aussi_candidates.append(section)
        
        # If we have ≥2 candidates, suggest merging
        if len(voir_aussi_candidates) >= 2:
            for section in voir_aussi_candidates:
                self.issues.append(Issue(
                    issue_type="voir_aussi_restructure",
                    description=f"Section « {section.title} » : fusionner dans « Voir aussi » (algorithme Phase 2)",
                    position=section.position,
                    original_text=section.content,
                    suggested_text=None,  # Manual restructuring
                    severity="high"
                ))

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _detect_heading_level_jumps(self, sections: List[SectionInfo]) -> None:
        """
        Detect inconsistent heading level jumps.
        For example: == Section === followed by ==== Subsection ====
        (skipping level 3).
        """
        if len(sections) < 2:
            return
        
        for i in range(len(sections) - 1):
            current = sections[i]
            next_section = sections[i + 1]
            
            # Level should increase by 1 or decrease (but not skip levels)
            if next_section.level > current.level + 1:
                self.issues.append(Issue(
                    issue_type="heading_level_jump",
                    description=(
                        f"Saut de niveau de titre : niveau {current.level} → {next_section.level} "
                        f"(devrait être {current.level + 1})"
                    ),
                    position=next_section.position,
                    original_text=next_section.content,
                    suggested_text='=' * (current.level + 1) + ' ' + next_section.title + ' ' + '=' * (current.level + 1),
                    severity="medium"
                ))

    def _detect_duplicate_sections(self, sections: List[SectionInfo]) -> None:
        """
        Detect duplicate sections (same title) that should be merged.
        """
        seen_titles: Dict[str, List[SectionInfo]] = {}
        
        for section in sections:
            title_lower = section.title.lower()
            if title_lower not in seen_titles:
                seen_titles[title_lower] = []
            seen_titles[title_lower].append(section)
        
        for title, section_list in seen_titles.items():
            if len(section_list) > 1:
                # Skip first occurrence, flag duplicates
                for section in section_list[1:]:
                    self.issues.append(Issue(
                        issue_type="duplicate_section",
                        description=f"Section dupliquée : « {section.title} » (fusionner avec la première occurrence)",
                        position=section.position,
                        original_text=section.content,
                        suggested_text=None,
                        severity="medium"
                    ))

    def _detect_portal_placement(self, content: str) -> None:
        """
        Detect portal templates that are not autonomous before categories.
        Portals should be in their own section or at the end before categories.
        """
        # Find all portal templates
        portal_matches = list(self._PORTAL_RE.finditer(content))
        
        for match in portal_matches:
            # Check if there's text after the portal that's not a category
            after = content[match.end():]
            
            # Remove categories from consideration
            after_without_cats = self._CATEGORY_RE.sub('', after)
            
            # If there's non-whitespace content after portal (excluding categories)
            if after_without_cats.strip():
                # Check if it's just a newline or template
                # If there's actual prose, flag it
                lines_after = after_without_cats.split('\n')[:5]  # Check first 5 lines
                prose_lines = [l for l in lines_after if l.strip() and not l.strip().startswith('{{')]
                
                if prose_lines:
                    self.issues.append(Issue(
                        issue_type="portal_placement",
                        description="Modèle {{Portail}} non autonome (déplacer avant catégories ou dans section dédiée)",
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="low"
                    ))

    def _detect_section_order(self, content: str, sections: List[SectionInfo]) -> None:
        """
        Detect incorrect section order.
        Expected order: body → notes → portal → categories
        """
        if not sections:
            return
        
        # Find positions of key sections
        section_positions = {}
        for section in sections:
            title_lower = section.title.lower()
            if 'note' in title_lower or 'référence' in title_lower:
                section_positions['notes'] = section.position
            elif 'bibliographie' in title_lower or 'source' in title_lower:
                section_positions['bibliography'] = section.position
            elif 'lien externe' in title_lower:
                section_positions['external_links'] = section.position
            elif 'voir aussi' in title_lower:
                section_positions['voir_aussi'] = section.position
        
        # Check order: notes should come before external links
        if 'notes' in section_positions and 'external_links' in section_positions:
            if section_positions['notes'] > section_positions['external_links']:
                self.issues.append(Issue(
                    issue_type="section_order",
                    description="Ordre incorrect : Notes et références après Liens externes",
                    position=section_positions['external_links'],
                    original_text="Liens externes",
                    suggested_text=None,
                    severity="low"
                ))
        
        # Check: Voir aussi should come before external links
        if 'voir_aussi' in section_positions and 'external_links' in section_positions:
            if section_positions['voir_aussi'] > section_positions['external_links']:
                self.issues.append(Issue(
                    issue_type="section_order",
                    description="Ordre incorrect : Voir aussi après Liens externes",
                    position=section_positions['voir_aussi'],
                    original_text="Voir aussi",
                    suggested_text=None,
                    severity="low"
                ))

    def _detect_empty_sections(self, content: str, sections: List[SectionInfo]) -> None:
        """
        Detect sections with no content (empty or only whitespace).
        """
        for i, section in enumerate(sections):
            # Get content between this section and the next
            start = section.position + len(section.content)
            end = sections[i + 1].position if i + 1 < len(sections) else len(content)
            
            section_content = content[start:end].strip()
            
            # Remove templates and refs to check for actual content
            cleaned = re.sub(r'\{\{[^}]+\}\}', '', section_content)
            cleaned = re.sub(r'<ref[^>]*>.*?</ref>', '', cleaned, flags=re.DOTALL)
            cleaned = cleaned.strip()
            
            if not cleaned:
                self.issues.append(Issue(
                    issue_type="empty_section",
                    description=f"Section vide : « {section.title} »",
                    position=section.position,
                    original_text=section.content,
                    suggested_text=None,
                    severity="low"
                ))

    def _detect_works_vs_bibliography(self, sections: List[SectionInfo]) -> None:
        """
        Detect when "Œuvres" or "Publications" exists alongside "Bibliographie".
        These should be distinct or properly organized.
        """
        has_works = any(
            any(ws in s.title.lower() for ws in self._WORKS_SECTIONS)
            for s in sections
        )
        has_bibliography = any(
            'bibliographie' in s.title.lower()
            for s in sections
        )
        
        if has_works and has_bibliography:
            # Find the works section
            for section in sections:
                if any(ws in section.title.lower() for ws in self._WORKS_SECTIONS):
                    self.issues.append(Issue(
                        issue_type="works_vs_bibliography",
                        description=(
                            f"Section « {section.title} » présente avec « Bibliographie » : "
                            "vérifier la distinction (œuvres créées vs sources consultées)"
                        ),
                        position=section.position,
                        original_text=section.content,
                        suggested_text=None,
                        severity="medium"
                    ))
