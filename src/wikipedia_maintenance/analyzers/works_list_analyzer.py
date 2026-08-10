"""
Analyzer for works lists (filmography, discography, bibliography) in Wikipedia articles.

Detects:
    - Filmography with 3+ attributes that should be converted to a table
    - Discography with 3+ attributes that should be converted to a table
    - Bibliography of author that should use {{Ouvrage}}
    - Awards that should be written as prose (not table)
    - Missing italics for work titles
    - Missing {{lang}} template for translated works
    - Wrong sort order (chronological vs alphabetical)

All checks are non-destructive (report-only, suggested_text is always None)
and preserve existing functionality.

---
CORRECTIFS :

1. _detect_bibliography : la position utilisait `section_content.find(line)`,
   qui retrouve toujours la PREMIÈRE occurrence d'une ligne identique dans la
   section. En cas d'entrées bibliographiques dupliquées (même texte), tous
   les signalements pointaient vers la même position, rendant le rapport
   trompeur pour un humain cliquant sur le lien de l'issue. Corrigé en
   parcourant les lignes avec un offset cumulatif réel plutôt qu'une
   recherche de sous-chaîne.

2. _MULTI_ATTR_LIST_RE : `[^-]+` s'arrêtait au premier tiret rencontré dans
   un champ, tronquant/décalant les groupes captés pour des titres ou rôles
   contenant un tiret (ex. "Spider-Man", "Jean-Claude"). Remplacé par un
   séparateur explicite (tiret entouré d'espaces) pour ne
   matcher que les VRAIS séparateurs de colonnes, pas un tiret interne à un
   mot ou nom composé.
---
"""

from __future__ import annotations

import re
import logging
from typing import List, Optional, Dict, Set, Tuple
from dataclasses import dataclass

from .base import BaseAnalyzer, Issue

logger = logging.getLogger(__name__)


class WorksListAnalyzer(BaseAnalyzer):
    """Analyzes articles for works list-related issues."""

    # ---- Precompiled patterns ----
    
    # Filmography section
    _FILMOGRAPHY_SECTION_RE = re.compile(r'==\s*[Ff]ilmographie\s*==', re.IGNORECASE)
    
    # Discography section
    _DISCOGRAPHY_SECTION_RE = re.compile(r'==\s*[Dd]iscographie\s*==', re.IGNORECASE)
    
    # Bibliography section
    _BIBLIOGRAPHY_SECTION_RE = re.compile(r'==\s*[Bb]ibliographie\s*==', re.IGNORECASE)
    
    # Awards/Distinctions section
    _AWARDS_SECTION_RE = re.compile(r'==\s*(?:[Dd]istinctions|[Pp]rix|[Rré]compenses)\s*==', re.IGNORECASE)
    
    # List item with multiple attributes (filmography/discography)
    # Pattern: * Year - Title - Role - Director (or similar)
    # CORRIGÉ : le séparateur doit être un tiret ENTOURÉ D'ESPACES pour ne
    # pas couper un titre ou un nom composé contenant un tiret interne
    # (ex. "Spider-Man", "Jean-Claude Dupont"). [^-]+ trop permissif avant.
    _MULTI_ATTR_LIST_RE = re.compile(
        r'^\*\s*(\d{4})\s+[-–]\s+([^\n]+?)\s+[-–]\s+([^\n]+?)(?:\s+[-–]\s+([^\n]+?))?\s*$',
        re.MULTILINE
    )
    
    # Work title in quotes or italics
    _WORK_TITLE_RE = re.compile(r'["\']([^\ "\']+)["\']|\'\'([^\ \']+)[^\']*\'\'')
    
    # Lang template detection
    _LANG_TEMPLATE_RE = re.compile(r'\{\{[Ll]ang\|[^}]+\}\}')
    
    # Ouvrage template
    _OUVRAGE_TEMPLATE_RE = re.compile(r'\{\{[Oo]uvrage\|[^}]+\}\}')
    
    def __init__(
        self,
        language: str = 'fr',
        filmography_threshold: int = 3,
        discography_threshold: int = 3,
        check_awards: bool = True,
        check_italics: bool = True,
        check_lang_template: bool = True,
        check_sort_order: bool = True,
    ):
        """
        Args:
            language: Language code for section names.
            filmography_threshold: Number of attributes to trigger table conversion.
            discography_threshold: Number of attributes to trigger table conversion.
            check_awards: Check awards sections.
            check_italics: Check for missing italics on work titles.
            check_lang_template: Check for missing {{lang}} on translated works.
            check_sort_order: Check sort order (chronological vs alphabetical).
        """
        super().__init__()
        self.language = language.lower()
        self.filmography_threshold = filmography_threshold
        self.discography_threshold = discography_threshold
        self.check_awards = check_awards
        self.check_italics = check_italics
        self.check_lang_template = check_lang_template
        self.check_sort_order = check_sort_order

    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze content for works list issues.

        Args:
            content: Article wikicode content

        Returns:
            List of detected issues (sorted by position)
        """
        self.clear_issues()
        if not content:
            return self.issues

        # ---- Detect and analyze each type of works list ----
        self._detect_filmography(content)
        self._detect_discography(content)
        self._detect_bibliography(content)
        
        if self.check_awards:
            self._detect_awards(content)
        
        if self.check_italics:
            self._detect_missing_italics(content)
        
        if self.check_lang_template:
            self._detect_missing_lang_template(content)
        
        if self.check_sort_order:
            self._detect_wrong_sort_order(content)

        # Sort issues by position
        self.issues.sort(key=lambda i: i.position)
        return self.issues

    def get_analyzer_name(self) -> str:
        return "WorksListAnalyzer"

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _detect_filmography(self, content: str) -> None:
        """
        Detect filmography sections with 3+ attributes that should be converted to a table.
        """
        for match in self._FILMOGRAPHY_SECTION_RE.finditer(content):
            section_start = match.end()
            
            # Find the end of the section (next == or end of content)
            next_heading = re.search(r'\n==', content[section_start:])
            if next_heading:
                section_end = section_start + next_heading.start()
            else:
                section_end = len(content)
            
            section_content = content[section_start:section_end]
            
            # Count list items with multiple attributes
            multi_attr_count = 0
            total_items = 0
            
            for list_match in self._MULTI_ATTR_LIST_RE.finditer(section_content):
                total_items += 1
                attrs = [g for g in list_match.groups() if g]
                if len(attrs) >= self.filmography_threshold:
                    multi_attr_count += 1
            
            # If we have items with 3+ attributes, suggest table conversion
            if multi_attr_count > 0:
                self.issues.append(Issue(
                    issue_type="filmography_to_table",
                    description=(
                        f"Filmographie avec {multi_attr_count} entrées à {self.filmography_threshold}+ attributs : "
                        "convertir en tableau wikitable"
                    ),
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=None,  # Manual conversion
                    severity="high"
                ))

    def _detect_discography(self, content: str) -> None:
        """
        Detect discography sections with 3+ attributes that should be converted to a table.
        """
        for match in self._DISCOGRAPHY_SECTION_RE.finditer(content):
            section_start = match.end()
            
            # Find the end of the section
            next_heading = re.search(r'\n==', content[section_start:])
            if next_heading:
                section_end = section_start + next_heading.start()
            else:
                section_end = len(content)
            
            section_content = content[section_start:section_end]
            
            # Count list items with multiple attributes
            multi_attr_count = 0
            total_items = 0
            
            for list_match in self._MULTI_ATTR_LIST_RE.finditer(section_content):
                total_items += 1
                attrs = [g for g in list_match.groups() if g]
                if len(attrs) >= self.discography_threshold:
                    multi_attr_count += 1
            
            # If we have items with 3+ attributes, suggest table conversion
            if multi_attr_count > 0:
                self.issues.append(Issue(
                    issue_type="discography_to_table",
                    description=(
                        f"Discographie avec {multi_attr_count} entrées à {self.discography_threshold}+ attributs : "
                        "convertir en tableau wikitable"
                    ),
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=None,
                    severity="high"
                ))

    def _detect_bibliography(self, content: str) -> None:
        """
        Detect bibliography sections that should use {{Ouvrage}} template.

        CORRIGÉ : la position de chaque ligne est désormais calculée via un
        offset cumulatif réel pendant l'itération, au lieu de
        `section_content.find(line)` qui retrouvait toujours la première
        occurrence d'une ligne — faussant la position de toute ligne
        dupliquée dans la section.
        """
        for match in self._BIBLIOGRAPHY_SECTION_RE.finditer(content):
            section_start = match.end()
            
            # Find the end of the section
            next_heading = re.search(r'\n==', content[section_start:])
            if next_heading:
                section_end = section_start + next_heading.start()
            else:
                section_end = len(content)
            
            section_content = content[section_start:section_end]
            
            # Check if there are list items without {{Ouvrage}}
            # Offset cumulatif réel : position absolue de chaque ligne dans
            # `content`, correcte même en cas de lignes dupliquées.
            cursor = 0
            for line in section_content.split('\n'):
                line_abs_pos = section_start + cursor
                cursor += len(line) + 1  # +1 pour le '\n' consommé par split

                if line.strip().startswith('*'):
                    # Check if it contains {{Ouvrage}}
                    if not self._OUVRAGE_TEMPLATE_RE.search(line):
                        # Check if it looks like a book entry (has author, title, etc.)
                        if re.search(r'[A-Z][a-z]+,?\s+[A-Z]', line):  # Author pattern
                            # Position réelle du premier caractère non-blanc de la ligne
                            leading_ws = len(line) - len(line.lstrip())
                            self.issues.append(Issue(
                                issue_type="bibliography_to_ouvrage",
                                description="Entrée de bibliographie sans modèle {{Ouvrage}}",
                                position=line_abs_pos + leading_ws,
                                original_text=line.strip(),
                                suggested_text=None,
                                severity="medium"
                            ))

    def _detect_awards(self, content: str) -> None:
        """
        Detect awards sections that use tables when prose would be better.
        """
        for match in self._AWARDS_SECTION_RE.finditer(content):
            section_start = match.end()
            
            # Find the end of the section
            next_heading = re.search(r'\n==', content[section_start:])
            if next_heading:
                section_end = section_start + next_heading.start()
            else:
                section_end = len(content)
            
            section_content = content[section_start:section_end]
            
            # Check for table syntax
            if '{|' in section_content and '|}' in section_content:
                # If it's a simple awards table, suggest prose
                # Heuristic: if table has few columns and simple structure
                table_start = section_content.find('{|')
                table_end = section_content.find('|}', table_start) + 2
                table_content = section_content[table_start:table_end]
                
                # Count rows
                row_count = table_content.count('|-')
                
                # If it's a small table, suggest prose
                if row_count <= 10:
                    self.issues.append(Issue(
                        issue_type="awards_to_prose",
                        description=(
                            f"Section distinctions en tableau ({row_count} lignes) : "
                            "préférer une rédaction en prose"
                        ),
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="low"
                    ))

    def _detect_missing_italics(self, content: str) -> None:
        """
        Detect work titles that should be in italics but aren't.
        This includes film titles, book titles, album titles, etc.
        
        NOTE: Disabled automatic conversion of quotes to italics to preserve
        episode titles, chapter titles, and song titles which should remain
        in quotes « » according to French typographic conventions.
        """
        # Look for work titles in quotes that should be italics
        # Pattern: "Title" where Title looks like a work title
        quote_pattern = re.compile(r'"([A-Z][^"]{3,50})"')
        
        for match in quote_pattern.finditer(content):
            title = match.group(1)
            
            # Skip if already in italics (''Title'')
            if "''" in content[max(0, match.start()-2):match.end()+2]:
                continue
            
            # Skip if inside a template or ref
            before = content[max(0, match.start()-20):match.start()]
            after = content[match.end():match.end()+20]
            if '{{' in before or '}}' in after:
                continue
            
            # Check if it looks like a work title (capitalized, reasonable length)
            if title[0].isupper() and 3 < len(title) < 50:
                # DISABLED: Do not auto-convert quotes to italics
                # Episode titles, chapter titles, and song titles should remain in quotes
                self.issues.append(Issue(
                    issue_type="missing_italics",
                    description=f"Titre d'œuvre sans italique : « {title} »",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=None,  # Manual review required
                    severity="low"
                ))

    def _detect_missing_lang_template(self, content: str) -> None:
        """
        Detect foreign language work titles that should use {{lang}} template.
        """
        # Look for non-French characters in titles
        # This is a heuristic - we look for titles with diacritics or non-Latin scripts
        # that aren't French
        
        # Pattern: ''Title'' where Title has non-French characters
        italics_pattern = re.compile(r"''([^']+)''")
        
        for match in italics_pattern.finditer(content):
            title = match.group(1)
            
            # Skip if already has {{lang}}
            if self._LANG_TEMPLATE_RE.search(content[max(0, match.start()-20):match.end()+20]):
                continue
            
            # Check for non-French characters (simplified heuristic)
            # French uses: é è à ù ç â ê î ô û æ œ ë ï ü ÿ
            french_chars = set('éèàùçâêîôûæœëïüÿÉÈÀÙÇÂÊÎÔÛÆŒËÏÜŸ')
            has_french = any(c in french_chars for c in title)
            
            # Check for non-Latin scripts (Cyrillic, Greek, CJK, Arabic, etc.)
            has_non_latin = any(ord(c) > 127 and c not in french_chars for c in title)
            
            if has_non_latin or (not has_french and any(ord(c) > 127 for c in title)):
                self.issues.append(Issue(
                    issue_type="missing_lang_template",
                    description=f"Titre en langue étrangère sans modèle {{lang}} : « {title} »",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=None,  # Manual correction required - heuristic is too imprecise
                    severity="low"
                ))

    def _detect_wrong_sort_order(self, content: str) -> None:
        """
        Detect wrong sort order in works lists (should be chronological).
        """
        # Look for filmography/discography sections
        sections_to_check = [
            (self._FILMOGRAPHY_SECTION_RE, "filmographie"),
            (self._DISCOGRAPHY_SECTION_RE, "discographie"),
        ]
        
        for pattern, section_name in sections_to_check:
            for match in pattern.finditer(content):
                section_start = match.end()
                
                # Find the end of the section
                next_heading = re.search(r'\n==', content[section_start:])
                if next_heading:
                    section_end = section_start + next_heading.start()
                else:
                    section_end = len(content)
                
                section_content = content[section_start:section_end]
                
                # Extract years from list items
                years = []
                for list_match in self._MULTI_ATTR_LIST_RE.finditer(section_content):
                    year = list_match.group(1)
                    if year and year.isdigit():
                        years.append(int(year))
                
                # Check if years are in chronological order
                if len(years) > 1:
                    is_chronological = all(years[i] <= years[i+1] for i in range(len(years)-1))
                    
                    if not is_chronological:
                        self.issues.append(Issue(
                            issue_type="wrong_sort_order",
                            description=f"Section {section_name} non triée chronologiquement",
                            position=match.start(),
                            original_text=match.group(0),
                            suggested_text=None,
                            severity="low"
                        ))