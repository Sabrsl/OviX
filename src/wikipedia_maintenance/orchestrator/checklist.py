"""
Checklist verification for Phase 4 of wikification process.

Implements a 47-point checklist organized into categories:
1. Structure (Voir aussi, titles, works lists) - 14 points
2. Links, typography, tables - 8 points
3. Sources and references - 10 points
4. Infobox, categories, banner - 3 points
5. Absolute rule (content) - 12 points
"""

from __future__ import annotations

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    """Status of a checklist item."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"


@dataclass
class CheckResult:
    """Result of a single checklist check."""
    category: str
    item_id: str
    description: str
    status: CheckStatus
    details: Optional[str] = None
    position: Optional[int] = None


class ChecklistChecker:
    """
    Runs the 47-point checklist verification on wikified content.
    
    The checklist is organized into 5 categories:
    1. Structure (14 points)
    2. Links, typography, tables (8 points)
    3. Sources and references (10 points)
    4. Infobox, categories, banner (3 points)
    5. Absolute rule (12 points)
    """
    
    # ---- Checklist definition ----
    CHECKLIST = {
        # Category 1: Structure (14 points)
        "structure": [
            ("1.1", "Section « Voir aussi » présente si nécessaire"),
            ("1.2", "Section « Voir aussi » ne contient pas de sous-sections redondantes"),
            ("1.3", "Niveaux de titres cohérents (pas de sauts de niveau)"),
            ("1.4", "Aucune section dupliquée"),
            ("1.5", "Section « Notes et références » présente si sources"),
            ("1.6", "Section « Bibliographie » distincte de « Œuvres »"),
            ("1.7", "Section « Liens externes » en fin d'article"),
            ("1.8", "Modèles {{Portail}} avant catégories"),
            ("1.9", "Ordre global respecté : corps → notes → portail → catégories"),
            ("1.10", "Aucune section vide"),
            ("1.11", "Filmographie en tableau si 3+ attributs"),
            ("1.12", "Discographie en tableau si 3+ attributs"),
            ("1.13", "Distinctions en prose (pas tableau)"),
            ("1.14", "Titres d'œuvres en italique"),
        ],
        
        # Category 2: Links, typography, tables (8 points)
        "links_typography_tables": [
            ("2.1", "Liens internes vers des pages existantes"),
            ("2.2", "Pas de liens vers pages d'homonymie (sauf intentionnel)"),
            ("2.3", "Guillemets français « » utilisés"),
            ("2.4", "Espaces insécables devant ; : ! ?"),
            ("2.5", "Pas de gras/italique abusif"),
            ("2.6", "Tableaux avec class=\"wikitable\""),
            ("2.7", "Tableaux avec scope=\"col\"/\"row\" pour accessibilité"),
            ("2.8", "Pas de HTML brut (utiliser wikicode)"),
        ],
        
        # Category 3: Sources and references (10 points)
        "sources_references": [
            ("3.1", "Références avec modèle approprié (pas de <ref>URL</ref> brut)"),
            ("3.2", "Références en doublon fusionnées avec <ref name=\"x\">"),
            ("3.3", "Références en casse normale (pas tout en majuscules)"),
            ("3.4", "ISBN avec paramètre isbn="),
            ("3.5", "Modèle bibliographique adapté ({{Lien web}} vs {{Ouvrage}})"),
            ("3.6", "Appels de note bien placés"),
            ("3.7", "Pas de liens morts (ou signalés)"),
            ("3.8", "URL de réseau social déplacée vers Liens externes"),
            ("3.9", "Références avec titre, site et date"),
            ("3.10", "Pas de références vides"),
        ],
        
        # Category 4: Infobox, categories, banner (3 points)
        "infobox_categories_banner": [
            ("4.1", "Infobox avec paramètres renseignés si possible"),
            ("4.2", "Catégories pertinentes et non dupliquées"),
            ("4.3", "Bandeau d'ébauche si nécessaire"),
        ],
        
        # Category 5: Absolute rule (content) (12 points)
        "absolute_rule": [
            ("5.1", "Citations directes non corrigées"),
            ("5.2", "Noms propres non modifiés"),
            ("5.3", "Dates non modifiées sans certitude"),
            ("5.4", "Chiffres et statistiques non modifiés"),
            ("5.5", "Contenu factuel non altéré"),
            ("5.6", "Pas d'ajout d'information non sourcée"),
            ("5.7", "Pas de suppression de contenu sourcé"),
            ("5.8", "Style rédactionnel respecté"),
            ("5.9", "Ton neutre maintenu"),
            ("5.10", "Pas de POV (point de vue) introduit"),
            ("5.11", "Pas de contrevérité introduite"),
            ("5.12", "Pas de contenu hors périmètre modifié"),
        ],
    }
    
    def __init__(self, language: str = 'fr'):
        """
        Args:
            language: Language code for section names and patterns.
        """
        self.language = language.lower()
    
    def run_checks(
        self,
        original_content: str,
        corrected_content: str
    ) -> List[CheckResult]:
        """
        Run all 47 checklist checks.
        
        Args:
            original_content: Original wikicode before wikification.
            corrected_content: Wikicode after wikification.
            
        Returns:
            List of CheckResult objects.
        """
        results = []
        
        # Run category 1: Structure
        results.extend(self._check_structure(corrected_content))
        
        # Run category 2: Links, typography, tables
        results.extend(self._check_links_typography_tables(corrected_content))
        
        # Run category 3: Sources and references
        results.extend(self._check_sources_references(corrected_content))
        
        # Run category 4: Infobox, categories, banner
        results.extend(self._check_infobox_categories_banner(corrected_content))
        
        # Run category 5: Absolute rule (compare original vs corrected)
        results.extend(self._check_absolute_rule(original_content, corrected_content))
        
        return results
    
    def generate_report(self, results: List[CheckResult]) -> str:
        """
        Generate a human-readable report from check results.
        
        Args:
            results: List of CheckResult objects.
            
        Returns:
            Formatted report string.
        """
        # Group by category
        by_category: Dict[str, List[CheckResult]] = {}
        for result in results:
            if result.category not in by_category:
                by_category[result.category] = []
            by_category[result.category].append(result)
        
        lines = []
        lines.append("=" * 60)
        lines.append("RAPPORT DE CHECKLIST - PHASE 4")
        lines.append("=" * 60)
        lines.append("")
        
        # Summary
        total = len(results)
        passed = sum(1 for r in results if r.status == CheckStatus.PASS)
        failed = sum(1 for r in results if r.status == CheckStatus.FAIL)
        warnings = sum(1 for r in results if r.status == CheckStatus.WARNING)
        skipped = sum(1 for r in results if r.status == CheckStatus.SKIP)
        
        lines.append(f"Total : {total} points")
        lines.append(f"✓ Passés : {passed}")
        lines.append(f"✗ Échoués : {failed}")
        lines.append(f"⚠ Avertissements : {warnings}")
        lines.append(f"⊘ Ignorés : {skipped}")
        lines.append("")
        
        # Details by category
        category_names = {
            "structure": "STRUCTURE",
            "links_typography_tables": "LIENS, TYPOGRAPHIE, TABLEAUX",
            "sources_references": "SOURCES ET RÉFÉRENCES",
            "infobox_categories_banner": "INFOBOX, CATÉGORIES, BANDEAU",
            "absolute_rule": "RÈGLE ABSOLUE (CONTENU)",
        }
        
        for category, category_results in by_category.items():
            lines.append("-" * 60)
            lines.append(category_names.get(category, category.upper()))
            lines.append("-" * 60)
            
            for result in category_results:
                status_symbol = {
                    CheckStatus.PASS: "✓",
                    CheckStatus.FAIL: "✗",
                    CheckStatus.WARNING: "⚠",
                    CheckStatus.SKIP: "⊘",
                }[result.status]
                
                lines.append(f"{status_symbol} [{result.item_id}] {result.description}")
                if result.details:
                    lines.append(f"   Détails : {result.details}")
            
            lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    # ------------------------------------------------------------------
    # Category-specific check methods
    # ------------------------------------------------------------------
    
    def _check_structure(self, content: str) -> List[CheckResult]:
        """Run structure checks (14 points)."""
        results = []
        
        # 1.1: Voir aussi section
        voir_aussi_present = bool(re.search(r'==\s*[Vv]oir aussi\s*==', content))
        results.append(CheckResult(
            category="structure",
            item_id="1.1",
            description="Section « Voir aussi » présente si nécessaire",
            status=CheckStatus.PASS if voir_aussi_present else CheckStatus.WARNING,
            details="Section absente" if not voir_aussi_present else None
        ))
        
        # 1.2: No redundant subsections in Voir aussi
        # This is a heuristic - check for multiple small sections
        sections = re.findall(r'==\s*([^=]+)\s*==', content)
        voir_aussi_related = [s for s in sections if any(kw in s.lower() for kw in ['articles connexes', 'liens internes', 'pages liées'])]
        results.append(CheckResult(
            category="structure",
            item_id="1.2",
            description="Section « Voir aussi » ne contient pas de sous-sections redondantes",
            status=CheckStatus.PASS if len(voir_aussi_related) <= 1 else CheckStatus.FAIL,
            details=f"{len(voir_aussi_related)} sous-sections trouvées" if len(voir_aussi_related) > 1 else None
        ))
        
        # 1.3: Consistent heading levels
        heading_pattern = re.compile(r'^(={1,6})\s*[^=]+\s*\1\s*$', re.MULTILINE)
        levels = [len(m.group(1)) for m in heading_pattern.finditer(content)]
        level_jumps = sum(1 for i in range(len(levels)-1) if levels[i+1] > levels[i] + 1)
        results.append(CheckResult(
            category="structure",
            item_id="1.3",
            description="Niveaux de titres cohérents (pas de sauts de niveau)",
            status=CheckStatus.PASS if level_jumps == 0 else CheckStatus.FAIL,
            details=f"{level_jumps} sauts de niveau détectés" if level_jumps > 0 else None
        ))
        
        # 1.4: No duplicate sections
        section_lower = [s.lower() for s in sections]
        duplicates = len(section_lower) - len(set(section_lower))
        results.append(CheckResult(
            category="structure",
            item_id="1.4",
            description="Aucune section dupliquée",
            status=CheckStatus.PASS if duplicates == 0 else CheckStatus.FAIL,
            details=f"{duplicates} sections dupliquées" if duplicates > 0 else None
        ))
        
        # 1.5: Notes et références section
        notes_present = bool(re.search(r'==\s*[Nn]otes et réféférences\s*==', content))
        has_refs = bool(re.search(r'<ref', content))
        if has_refs:
            results.append(CheckResult(
                category="structure",
                item_id="1.5",
                description="Section « Notes et références » présente si sources",
                status=CheckStatus.PASS if notes_present else CheckStatus.FAIL,
                details="Section absente malgré présence de <ref>" if not notes_present else None
            ))
        else:
            results.append(CheckResult(
                category="structure",
                item_id="1.5",
                description="Section « Notes et références » présente si sources",
                status=CheckStatus.SKIP,
                details="Aucune référence détectée"
            ))
        
        # 1.6: Bibliography distinct from Works
        has_biblio = any('bibliographie' in s.lower() for s in sections)
        has_works = any(kw in s.lower() for s in sections for kw in ['filmographie', 'discographie', 'œuvres', 'publications'])
        if has_biblio and has_works:
            results.append(CheckResult(
                category="structure",
                item_id="1.6",
                description="Section « Bibliographie » distincte de « Œuvres »",
                status=CheckStatus.WARNING,
                details="Les deux types de sections sont présentes - vérifier la distinction"
            ))
        else:
            results.append(CheckResult(
                category="structure",
                item_id="1.6",
                description="Section « Bibliographie » distincte de « Œuvres »",
                status=CheckStatus.PASS
            ))
        
        # 1.7: Liens externes at end
        external_links_section = re.search(r'==\s*[Ll]iens externes\s*==', content)
        if external_links_section:
            # Check if there's content after it (except categories)
            after = content[external_links_section.end():]
            after_without_cats = re.sub(r'\[\[(?:Catégorie|Category):[^\]]+\]\]', '', after, flags=re.IGNORECASE)
            has_content_after = bool(after_without_cats.strip())
            results.append(CheckResult(
                category="structure",
                item_id="1.7",
                description="Section « Liens externes » en fin d'article",
                status=CheckStatus.PASS if not has_content_after else CheckStatus.WARNING,
                details="Contenu détecté après Liens externes" if has_content_after else None
            ))
        else:
            results.append(CheckResult(
                category="structure",
                item_id="1.7",
                description="Section « Liens externes » en fin d'article",
                status=CheckStatus.SKIP,
                details="Section absente"
            ))
        
        # 1.8: Portails before categories
        portal_matches = list(re.finditer(r'\{\{[Pp]ortail\|', content))
        category_matches = list(re.finditer(r'\[\[(?:Catégorie|Category):', content, flags=re.IGNORECASE))
        if portal_matches and category_matches:
            first_portal = portal_matches[0].start()
            first_category = category_matches[0].start()
            results.append(CheckResult(
                category="structure",
                item_id="1.8",
                description="Modèles {{Portail}} avant catégories",
                status=CheckStatus.PASS if first_portal < first_category else CheckStatus.FAIL,
                details="Catégories avant portails" if first_portal > first_category else None
            ))
        else:
            results.append(CheckResult(
                category="structure",
                item_id="1.8",
                description="Modèles {{Portail}} avant catégories",
                status=CheckStatus.SKIP,
                details="Pas de portails ou catégories détectés"
            ))
        
        # 1.9: Global order (simplified check)
        # This is complex - we'll do a basic check
        results.append(CheckResult(
            category="structure",
            item_id="1.9",
            description="Ordre global respecté : corps → notes → portail → catégories",
            status=CheckStatus.WARNING,
            details="Vérification manuelle recommandée"
        ))
        
        # 1.10: No empty sections
        empty_sections = []
        for match in re.finditer(r'==\s*([^=]+)\s*==', content):
            section_start = match.end()
            next_heading = re.search(r'\n==', content[section_start:])
            section_end = section_start + next_heading.start() if next_heading else len(content)
            section_content = content[section_start:section_end].strip()
            if not section_content:
                empty_sections.append(match.group(1))
        
        results.append(CheckResult(
            category="structure",
            item_id="1.10",
            description="Aucune section vide",
            status=CheckStatus.PASS if not empty_sections else CheckStatus.FAIL,
            details=f"Sections vides : {', '.join(empty_sections)}" if empty_sections else None
        ))
        
        # 1.11-1.14: Works list checks (simplified)
        results.append(CheckResult(
            category="structure",
            item_id="1.11",
            description="Filmographie en tableau si 3+ attributs",
            status=CheckStatus.WARNING,
            details="Vérification manuelle requise"
        ))
        
        results.append(CheckResult(
            category="structure",
            item_id="1.12",
            description="Discographie en tableau si 3+ attributs",
            status=CheckStatus.WARNING,
            details="Vérification manuelle requise"
        ))
        
        results.append(CheckResult(
            category="structure",
            item_id="1.13",
            description="Distinctions en prose (pas tableau)",
            status=CheckStatus.WARNING,
            details="Vérification manuelle requise"
        ))
        
        results.append(CheckResult(
            category="structure",
            item_id="1.14",
            description="Titres d'œuvres en italique",
            status=CheckStatus.WARNING,
            details="Vérification manuelle requise"
        ))
        
        return results
    
    def _check_links_typography_tables(self, content: str) -> List[CheckResult]:
        """Run links, typography, and table checks (8 points)."""
        results = []
        
        # 2.1: Internal links to existing pages (requires API - skip)
        results.append(CheckResult(
            category="links_typography_tables",
            item_id="2.1",
            description="Liens internes vers des pages existantes",
            status=CheckStatus.SKIP,
            details="Requiert vérification API"
        ))
        
        # 2.2: No disambiguation links (heuristic)
        disambig_keywords = ['homonymie', 'désambiguïsation']
        has_disambig = any(kw in content.lower() for kw in disambig_keywords)
        results.append(CheckResult(
            category="links_typography_tables",
            item_id="2.2",
            description="Pas de liens vers pages d'homonymie (sauf intentionnel)",
            status=CheckStatus.WARNING if has_disambig else CheckStatus.PASS,
            details="Mots-clés d'homonymie détectés" if has_disambig else None
        ))
        
        # 2.3: French quotes
        has_french_quotes = '«' in content and '»' in content
        has_english_quotes = '"' in content
        results.append(CheckResult(
            category="links_typography_tables",
            item_id="2.3",
            description="Guillemets français « » utilisés",
            status=CheckStatus.PASS if has_french_quotes else CheckStatus.WARNING,
            details="Guillemets anglais détectés" if has_english_quotes else None
        ))
        
        # 2.4: Non-breaking spaces before ; : ! ?
        nbsp = '\u00a0'
        punct_before = {';', ':', '!', '?'}
        missing_nbsp = []
        for punct in punct_before:
            # Simple heuristic - check for normal space before punctuation
            if f' {punct}' in content:
                missing_nbsp.append(punct)
        
        results.append(CheckResult(
            category="links_typography_tables",
            item_id="2.4",
            description="Espaces insécables devant ; : ! ?",
            status=CheckStatus.PASS if not missing_nbsp else CheckStatus.WARNING,
            details=f"Espaces normales avant : {', '.join(missing_nbsp)}" if missing_nbsp else None
        ))
        
        # 2.5: No abusive bold/italic
        bold_count = content.count("'''")
        italic_count = content.count("''")
        results.append(CheckResult(
            category="links_typography_tables",
            item_id="2.5",
            description="Pas de gras/italique abusif",
            status=CheckStatus.WARNING,
            details=f"{bold_count // 2} gras, {italic_count // 2} italique - vérification manuelle"
        ))
        
        # 2.6: Tables with wikitable class
        tables = re.findall(r'\{[^}]*class=[\'"]([^\'"]+)[\'"][^}]*\}', content)
        has_wikitable = any('wikitable' in t for t in tables)
        has_tables = '{|' in content
        if has_tables:
            results.append(CheckResult(
                category="links_typography_tables",
                item_id="2.6",
                description="Tableaux avec class=\"wikitable\"",
                status=CheckStatus.PASS if has_wikitable else CheckStatus.FAIL,
                details="Tableau sans class wikitable détecté" if not has_wikitable else None
            ))
        else:
            results.append(CheckResult(
                category="links_typography_tables",
                item_id="2.6",
                description="Tableaux avec class=\"wikitable\"",
                status=CheckStatus.SKIP,
                details="Aucun tableau détecté"
            ))
        
        # 2.7: Tables with scope for accessibility
        has_scope = 'scope=' in content
        if has_tables:
            results.append(CheckResult(
                category="links_typography_tables",
                item_id="2.7",
                description="Tableaux avec scope=\"col\"/\"row\" pour accessibilité",
                status=CheckStatus.PASS if has_scope else CheckStatus.WARNING,
                details="scope manquant - accessibilité réduite" if not has_scope else None
            ))
        else:
            results.append(CheckResult(
                category="links_typography_tables",
                item_id="2.7",
                description="Tableaux avec scope=\"col\"/\"row\" pour accessibilité",
                status=CheckStatus.SKIP,
                details="Aucun tableau détecté"
            ))
        
        # 2.8: No raw HTML
        html_tags = re.findall(r'<(?!ref|nowiki|br|\/ref|\/nowiki)[a-zA-Z][^>]*>', content)
        results.append(CheckResult(
            category="links_typography_tables",
            item_id="2.8",
            description="Pas de HTML brut (utiliser wikicode)",
            status=CheckStatus.PASS if not html_tags else CheckStatus.WARNING,
            details=f"{len(html_tags)} balises HTML détectées" if html_tags else None
        ))
        
        return results
    
    def _check_sources_references(self, content: str) -> List[CheckResult]:
        """Run sources and references checks (10 points)."""
        results = []
        
        # 3.1: No bare URL refs
        bare_refs = re.findall(r'<ref>(https?://[^\s<]+)</ref>', content, re.IGNORECASE)
        results.append(CheckResult(
            category="sources_references",
            item_id="3.1",
            description="Références avec modèle approprié (pas de <ref>URL</ref> brut)",
            status=CheckStatus.PASS if not bare_refs else CheckStatus.FAIL,
            details=f"{len(bare_refs)} références brutes détectées" if bare_refs else None
        ))
        
        # 3.2: Duplicate refs merged
        named_refs = re.findall(r'<ref\s+name=["\'][^"\']+["\']', content)
        total_refs = len(re.findall(r'<ref', content))
        results.append(CheckResult(
            category="sources_references",
            item_id="3.2",
            description="Références en doublon fusionnées avec <ref name=\"x\">",
            status=CheckStatus.PASS if named_refs or total_refs <= 1 else CheckStatus.WARNING,
            details=f"{total_refs} références, {len(named_refs)} nommées" if total_refs > 1 else None
        ))
        
        # 3.3: Normal case in refs
        # Heuristic: check for refs with >50% uppercase
        ref_pattern = re.compile(r'<ref[^>]*>(.*?)</ref>', re.IGNORECASE | re.DOTALL)
        uppercase_refs = 0
        for match in ref_pattern.finditer(content):
            ref_content = match.group(1)
            letters = [c for c in ref_content if c.isalpha()]
            if letters:
                uppercase_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
                if uppercase_ratio > 0.5:
                    uppercase_refs += 1
        
        results.append(CheckResult(
            category="sources_references",
            item_id="3.3",
            description="Références en casse normale (pas tout en majuscules)",
            status=CheckStatus.PASS if uppercase_refs == 0 else CheckStatus.WARNING,
            details=f"{uppercase_refs} références en majuscules" if uppercase_refs > 0 else None
        ))
        
        # 3.4: ISBN with isbn= parameter
        isbn_pattern = re.compile(r'\b(?:ISBN\s*:?\s*)?(\d{9}[\dXx]|\d{13})\b', re.IGNORECASE)
        isbns = isbn_pattern.findall(content)
        isbn_params = content.count('isbn=')
        results.append(CheckResult(
            category="sources_references",
            item_id="3.4",
            description="ISBN avec paramètre isbn=",
            status=CheckStatus.PASS if isbn_params >= len(isbns) or not isbns else CheckStatus.WARNING,
            details=f"{len(isbns)} ISBN, {isbn_params} paramètres isbn=" if isbns else None
        ))
        
        # 3.5-3.10: Simplified checks
        for i, desc in enumerate([
            "Modèle bibliographique adapté ({{Lien web}} vs {{Ouvrage}})",
            "Appels de note bien placés",
            "Pas de liens morts (ou signalés)",
            "URL de réseau social déplacée vers Liens externes",
            "Références avec titre, site et date",
            "Pas de références vides",
        ], start=5):
            results.append(CheckResult(
                category="sources_references",
                item_id=f"3.{i}",
                description=desc,
                status=CheckStatus.WARNING,
                details="Vérification manuelle requise"
            ))
        
        return results
    
    def _check_infobox_categories_banner(self, content: str) -> List[CheckResult]:
        """Run infobox, categories, and banner checks (3 points)."""
        results = []
        
        # 4.1: Infobox with parameters
        infobox_match = re.search(r'\{\{[Ii]nfo(?:box)?[^\|}]*\|', content)
        if infobox_match:
            # Count parameters
            infobox_start = infobox_match.start()
            infobox_end = content.find('}}', infobox_start)
            if infobox_end != -1:
                infobox_content = content[infobox_start:infobox_end]
                param_count = infobox_content.count('|')
                results.append(CheckResult(
                    category="infobox_categories_banner",
                    item_id="4.1",
                    description="Infobox avec paramètres renseignés si possible",
                    status=CheckStatus.PASS if param_count > 2 else CheckStatus.WARNING,
                    details=f"{param_count} paramètres détectés" if param_count <= 2 else None
                ))
        else:
            results.append(CheckResult(
                category="infobox_categories_banner",
                item_id="4.1",
                description="Infobox avec paramètres renseignés si possible",
                status=CheckStatus.SKIP,
                details="Aucune infobox détectée"
            ))
        
        # 4.2: Categories not duplicated
        categories = re.findall(r'\[\[(?:Catégorie|Category):([^\]]+)\]\]', content, re.IGNORECASE)
        cat_lower = [c.lower().strip() for c in categories]
        duplicates = len(cat_lower) - len(set(cat_lower))
        results.append(CheckResult(
            category="infobox_categories_banner",
            item_id="4.2",
            description="Catégories pertinentes et non dupliquées",
            status=CheckStatus.PASS if duplicates == 0 else CheckStatus.WARNING,
            details=f"{duplicates} catégories dupliquées" if duplicates > 0 else None
        ))
        
        # 4.3: Banner if needed
        banners = re.findall(r'\{\{(?:[ÉÉ]bauche|[Ss]tub|[Aa]dQ|[Bb]on article)', content)
        results.append(CheckResult(
            category="infobox_categories_banner",
            item_id="4.3",
            description="Bandeau d'ébauche si nécessaire",
            status=CheckStatus.WARNING,
            details=f"{len(banners)} bandeau(x) détecté(s) - vérification manuelle"
        ))
        
        return results
    
    def _check_absolute_rule(self, original: str, corrected: str) -> List[CheckResult]:
        """Run absolute rule checks (12 points) - compare original vs corrected."""
        results = []
        
        # These are content preservation checks that require human verification
        # We'll flag them for manual review
        
        for i, desc in enumerate([
            "Citations directes non corrigées",
            "Noms propres non modifiés",
            "Dates non modifiées sans certitude",
            "Chiffres et statistiques non modifiés",
            "Contenu factuel non altéré",
            "Pas d'ajout d'information non sourcée",
            "Pas de suppression de contenu sourcé",
            "Style rédactionnel respecté",
            "Ton neutre maintenu",
            "Pas de POV (point de vue) introduit",
            "Pas de contrevérité introduite",
            "Pas de contenu hors périmètre modifié",
        ], start=1):
            results.append(CheckResult(
                category="absolute_rule",
                item_id=f"5.{i}",
                description=desc,
                status=CheckStatus.WARNING,
                details="Vérification manuelle obligatoire (règle absolue)"
            ))
        
        return results
