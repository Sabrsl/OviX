"""
Analyseur des problèmes de typographie dans les articles Wikipédia.

Ce module effectue UNIQUEMENT des corrections mécaniques, déterministes
et basées sur des règles (regex). Aucune IA n'est utilisée dans cet analyseur.

Corrections autorisées :
- Suppression des espaces doubles
- Suppression des espaces en fin de ligne
- Suppression des lignes vides multiples
- Normalisation des espaces avant : ; ? ! selon les conventions typographiques françaises/Wikipédia
- Normalisation des guillemets français (« ... ») et des espaces associées
- Correction des intervalles numériques (1914 - 1918 → 1914–1918) uniquement lorsque les deux côtés sont des nombres
- Ajout de l'espace avant % (10% → 10 %)
- Ajout des espaces entre les nombres et les unités (10km → 10 km, 25kg → 25 kg, 50°C → 50 °C, etc.)
- Nettoyage mécanique du wikicode (espaces inutiles autour de certains éléments lorsque cela est sans risque)
- Simplification des liens internes identiques ([[Paris|Paris]] → [[Paris]])
- Suppression des catégories dupliquées

NE JAMAIS EFFECTUER :
- de reformulation
- de correction grammaticale
- de correction orthographique
- de wikification
- d'ajout ou suppression de contenu
- de modification des références
- de modification des modèles
- de modification des dates, chiffres ou informations factuelles

Toutes les règles sont déterministes, testables et sans ambiguïté.
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .base import BaseAnalyzer, Issue
from .typography_utils import MASK_CHAR, mask_content
from .typography_patterns import (
    DOUBLE_SPACE_PATTERN,
    TRAILING_SPACE_PATTERN,
    MULTIPLE_BLANK_LINES_PATTERN,
    PUNCTUATION_SPACING_PATTERN,
    FRENCH_QUOTES_PATTERN,
    NUMERIC_INTERVAL_PATTERN,
    PERCENT_SPACING_PATTERN,
    CATEGORY_PATTERN,
    DEGREE_ALONE_PATTERN,
)

logger = logging.getLogger(__name__)

_NBSP = "\u00a0"


class TypographyAnalyzer(BaseAnalyzer):
    """Analyseur de typographie effectuant uniquement des corrections mécaniques déterministes.

    Cet analyseur n'utilise aucune IA et n'effectue que des corrections basées sur
    des règles regex clairement définies et testables.
    """

    def __init__(
        self,
        check_double_spaces: bool = True,
        check_trailing_spaces: bool = True,
        check_multiple_blank_lines: bool = True,
        check_punctuation_spacing: bool = True,
        check_french_quotes: bool = True,
        check_numeric_intervals: bool = True,
        check_percent_spacing: bool = True,
        check_unit_spacing: bool = True,
        check_duplicate_categories: bool = True,
        check_degree_spacing: bool = True,
        max_issues: Optional[int] = None,
    ) -> None:
        """
        Args:
            check_double_spaces: Suppression des espaces doubles
            check_trailing_spaces: Suppression des espaces en fin de ligne
            check_multiple_blank_lines: Suppression des lignes vides multiples
            check_punctuation_spacing: Normalisation des espaces avant : ; ? !
            check_french_quotes: Normalisation des guillemets français
            check_numeric_intervals: Correction des intervalles numériques
            check_percent_spacing: Ajout de l'espace avant %
            check_unit_spacing: Ajout des espaces entre nombres et unités
            check_duplicate_categories: Suppression des catégories dupliquées
            check_degree_spacing: Ajout d'espace avant ° seul
            max_issues: nombre maximal d'anomalies rapportées
        """
        super().__init__()
        self.check_double_spaces = check_double_spaces
        self.check_trailing_spaces = check_trailing_spaces
        self.check_multiple_blank_lines = check_multiple_blank_lines
        self.check_punctuation_spacing = check_punctuation_spacing
        self.check_french_quotes = check_french_quotes
        self.check_numeric_intervals = check_numeric_intervals
        self.check_percent_spacing = check_percent_spacing
        self.check_unit_spacing = check_unit_spacing
        self.check_duplicate_categories = check_duplicate_categories
        self.check_degree_spacing = check_degree_spacing
        self.max_issues = max_issues

    def get_analyzer_name(self) -> str:
        """Return a human‑readable name for this analyzer."""
        return "TypographyAnalyzer"

    def analyze(self, content: str) -> List[Issue]:
        """Analyse le contenu pour des problèmes de typographie mécaniques.

        Args:
            content: contenu wikicode de l'article.

        Returns:
            Liste des anomalies détectées, triées par position croissante.
        """
        if not isinstance(content, str):
            raise TypeError(f"content doit être une chaîne, reçu {type(content).__name__}")

        self.clear_issues()
        if not content:
            return self.issues

        masked = mask_content(content)

        # Corrections mécaniques déterministes
        if self.check_double_spaces:
            self._detect_double_spaces(content, masked)

        if self.check_trailing_spaces:
            self._detect_trailing_spaces(content, masked)

        if self.check_multiple_blank_lines:
            self._detect_multiple_blank_lines(content, masked)

        if self.check_punctuation_spacing:
            self._detect_punctuation_spacing(content, masked)

        if self.check_french_quotes:
            self._detect_french_quotes(content, masked)

        if self.check_numeric_intervals:
            self._detect_numeric_intervals(content, masked)

        if self.check_percent_spacing:
            self._detect_percent_spacing(content, masked)

        if self.check_unit_spacing:
            self._detect_unit_spacing(content, masked)

        if self.check_duplicate_categories:
            self._detect_duplicate_categories(content)

        if self.check_degree_spacing:
            self._detect_degree_spacing(content, masked)

        # Simplification des liens internes identiques (désactivé pour éviter les modifications indésirables)
        # self._detect_duplicate_links(content, masked)

        self.issues.sort(key=lambda issue: issue.position)
        if self.max_issues is not None:
            self.issues = self.issues[: self.max_issues]
        return self.issues

    def _is_protected_zone(self, original: str, start: int, end: int, masked: str) -> bool:
        """Vérifie si la zone est protégée et ne doit pas être modifiée.
        
        Retourne True si la zone est protégée (ne pas modifier), False sinon.
        Factorise tous les checks de protection pour éviter les incohérences.
        """
        # Vérification de base : zone masquée
        if masked[start:end] == MASK_CHAR * (end - start):
            return True
        if MASK_CHAR in masked[start:end]:
            return True
        if masked[start:end] != original[start:end]:
            return True

        # Vérification des blocs à syntaxe interne stricte (<timeline>, <math>, <gallery>, <graph>, <score>, <chem>, <syntaxhighlight>, <source>, <code>)
        strict_syntax_blocks = ['timeline', 'math', 'gallery', 'graph', 'score', 'chem', 'syntaxhighlight', 'source', 'code']
        for block_name in strict_syntax_blocks:
            # Chercher la balise ouvrante avant la position
            open_tag = f'<{block_name}'
            close_tag = f'</{block_name}>'
            
            open_pos = original.rfind(open_tag, 0, start)
            if open_pos != -1:
                # Vérifier s'il y a une fermeture entre open_pos et start
                # Si non, on est à l'intérieur du bloc
                if close_tag not in original[open_pos:start]:
                    # Vérifier s'il y a une fermeture après la position
                    close_pos = original.find(close_tag, end)
                    if close_pos != -1:
                        return True

        # Protéger le gras/italique wikicode ('' ou ''')
        context_window = 20
        context_start = max(0, start - context_window)
        context_end = min(len(original), end + context_window)
        context = original[context_start:context_end]
        if "''" in context:
            return True

        # Protection des entités HTML (&...;) - ne jamais insérer d'espace à l'intérieur
        html_entity_pattern = r'&[a-zA-Z#0-9]+;'
        for entity_match in re.finditer(html_entity_pattern, context):
            entity_start = context_start + entity_match.start()
            entity_end = context_start + entity_match.end()
            # Si notre zone est à l'intérieur de l'entité HTML
            if entity_start <= start and end <= entity_end:
                return True

        # Vérification des templates avec deux-points syntaxiques ({{DEFAULTSORT:, {{Infobox:, etc.)
        # Ne pas ajouter d'espace avant : dans {{TEMPLATE:...}}
        template_colon_pattern = r'\{\{[A-Za-z0-9_]+\s*:'
        for template_match in re.finditer(template_colon_pattern, context):
            # Si le : est dans notre zone de détection
            colon_pos_in_context = template_match.end() - 1
            colon_global_pos = context_start + colon_pos_in_context
            if start <= colon_global_pos < end:
                return True

        # Vérification des attributs HTML (name="...", style="...", etc.)
        # Si on est à l'intérieur d'un attribut HTML avec guillemets droits
        extended_context_start = max(0, start - 50)
        extended_context_end = min(len(original), end + 50)
        extended_context = original[extended_context_start:extended_context_end]
        if '=' in extended_context:
            # Chercher des patterns d'attributs HTML
            attr_pattern = r'\b[a-zA-Z_-]+\s*=\s*"[^"]*"'
            for attr_match in re.finditer(attr_pattern, extended_context):
                attr_start = extended_context_start + attr_match.start()
                attr_end = extended_context_start + attr_match.end()
                # Si notre zone est à l'intérieur de l'attribut
                if attr_start <= start and end <= attr_end:
                    return True

        # Vérification des paramètres de template (|param=valeur)
        if '|' in extended_context and '=' in extended_context:
            # Chercher des patterns de paramètres de template
            param_pattern = r'\|\s*[a-zA-Z_-]+\s*='
            for param_match in re.finditer(param_pattern, extended_context):
                param_start = extended_context_start + param_match.start()
                param_end = extended_context_start + param_match.end()
                # Si notre zone est juste après un paramètre de template
                if abs(start - param_end) < 20:
                    return True

        return False

    def _detect_double_spaces(self, original: str, masked: str) -> None:
        """Détecte les espaces doubles dans le texte."""
        for match in DOUBLE_SPACE_PATTERN.finditer(original):
            # Éviter les zones masquées
            start, end = match.start(), match.end()
            if masked[start:end] == MASK_CHAR * (end - start):
                continue

            original_text = match.group()
            suggested_text = ' '
            self.issues.append(Issue(
                issue_type="double_space",
                description="Espace double détecté",
                position=start,
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low"
            ))

    def _detect_trailing_spaces(self, original: str, masked: str) -> None:
        """Détecte les espaces en fin de ligne (hors blocs protégés : pre, source, syntaxhighlight...)."""
        for match in TRAILING_SPACE_PATTERN.finditer(original, re.MULTILINE):
            start, end = match.start(), match.end()
            if masked[start:end] == MASK_CHAR * (end - start):
                continue
            original_text = match.group()
            self.issues.append(Issue(
                issue_type="trailing_space",
                description="Espace en fin de ligne",
                position=start,
                original_text=original_text,
                suggested_text='',
                severity="low"
            ))

    def _detect_multiple_blank_lines(self, original: str, masked: str) -> None:
        """Détecte les lignes vides multiples (hors blocs protégés)."""
        for match in MULTIPLE_BLANK_LINES_PATTERN.finditer(original):
            start, end = match.start(), match.end()
            if masked[start:end] == MASK_CHAR * (end - start):
                continue
            original_text = match.group()
            self.issues.append(Issue(
                issue_type="multiple_blank_lines",
                description="Lignes vides multiples",
                position=start,
                original_text=original_text,
                suggested_text='\n\n',
                severity="low"
            ))

    def _detect_punctuation_spacing(self, original: str, masked: str) -> None:
        """Normalise les espaces avant : ; ? ! selon les conventions françaises."""
        for match in PUNCTUATION_SPACING_PATTERN.finditer(original):
            start, end = match.start(), match.end()
            
            # Vérification de protection unifiée
            if self._is_protected_zone(original, start, end, masked):
                continue

            # Éviter les deux-points horaires (12:30)
            if match.group(2) == ':' and match.group(1).isdigit():
                # Vérifier si c'est une heure
                after_punct = original[end:end+1] if end < len(original) else ''
                if after_punct.isdigit():
                    continue

            # Vérification : éviter les corrections après des & (entités HTML)
            if match.group(1) == '&':
                continue  # Ne pas ajouter d'espace après & (évite de briser &nbsp; etc.)

            # Vérification : éviter les corrections dans les liens wikicode (Fichier:, Image:, Catégorie:, etc.)
            # Chercher le début du lien wikicode à proximité
            context_start = max(0, start - 30)
            context = original[context_start:end]
            if '[[Fichier:' in context or '[[Image:' in context or '[[File:' in context or '[[Catégorie:' in context or '[[Category:' in context:
                continue  # Dans un lien wikicode, ne pas modifier les :

            # Vérification : éviter les corrections dans les structures spéciales (tableaux, templates)
            # Si le caractère avant est `:` ou `|`, ignorer (tableaux wikicode)
            if start > 0:
                char_before = original[start - 1]
                if char_before in [':', '|', '{', '}']:
                    continue

            # Vérification : éviter les corrections après des accolades ou crochets fermants
            if match.group(1) in ['}', ']', ')']:
                continue

            # Vérification plus robuste : éviter les corrections dans les commentaires HTML
            # Chercher les délimiteurs de commentaires autour de la position
            before_text = original[:start]
            after_text = original[end:]
            
            # Vérifier si on est à l'intérieur d'un commentaire HTML
            # Chercher le dernier <!-- avant start et le premier --> après end
            last_comment_start = before_text.rfind('<!--')
            first_comment_end = after_text.find('-->')
            
            # Si on est entre <!-- et -->, ignorer
            if last_comment_start != -1 and first_comment_end != -1:
                continue  # On est dans un commentaire HTML

            original_text = match.group()
            suggested_text = match.group(1) + _NBSP + match.group(2)
            self.issues.append(Issue(
                issue_type="punctuation_spacing",
                description=f"Espace insécable manquant avant {match.group(2)}",
                position=start,
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low"
            ))

    def _detect_french_quotes(self, original: str, masked: str) -> None:
        """Normalise les guillemets français et leurs espaces."""
        # Supprimer le lookbehind problématique qui créait des guillemets orphelins
        # et revenir à une approche plus simple mais robuste
        pattern = r'"([^"=<>{}\|\n]{1,500})"'
        
        for match in re.finditer(pattern, original):
            start, end = match.start(), match.end()

            # Vérification de protection unifiée (inclut les attributs HTML et wikicode)
            if self._is_protected_zone(original, start, end, masked):
                continue

            if start > 0 and original[start - 1] == '=':
                continue

            inner_text = match.group(1)
            if inner_text.count('"') > 1:
                continue

            # Vérification spécifique : éviter de convertir si le guillemet est collé à une apostrophe
            # (cas d'embarras "gastriques" - le " est collé à s' précédent)
            if start > 0 and original[start - 1] in "'’":
                continue

            # Guillemets déséquilibrés : vérifier dans une fenêtre resserrée
            context_start = max(0, start - 40)
            context_end = min(len(original), end + 40)
            context = original[context_start:context_end]
            if context.count('"') % 2 != 0:
                continue

            # Ne bloquer que si un guillemet français apparaît collé à CETTE paire
            immediate_before = original[max(0, start - 3):start]
            immediate_after = original[end:end + 3]
            if '«' in immediate_before or '»' in immediate_after:
                continue

            # Vérification supplémentaire : éviter de modifier dans les contextes
            # où le guillemet droit est probablement voulu
            extended_context = original[max(0, start - 100):end + 100]
            if '«' in extended_context or '»' in extended_context:
                french_quote_count = extended_context.count('«') + extended_context.count('»')
                if french_quote_count >= 2:
                    continue

            original_text = match.group()
            suggested_text = f'«{_NBSP}{inner_text}{_NBSP}»'
            self.issues.append(Issue(
                issue_type="french_quotes",
                description="Guillemets droits à remplacer par guillemets français",
                position=start,
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low"
            ))

    def _detect_numeric_intervals(self, original: str, masked: str) -> None:
        """Corrige les intervalles numériques (1914 - 1918 → 1914–1918)."""
        for match in NUMERIC_INTERVAL_PATTERN.finditer(original):
            start, end = match.start(), match.end()
            
            # Vérification de protection unifiée
            if self._is_protected_zone(original, start, end, masked):
                continue

            original_text = match.group()
            suggested_text = f"{match.group(1)}–{match.group(2)}"
            self.issues.append(Issue(
                issue_type="numeric_interval",
                description="Intervalle numérique à corriger",
                position=start,
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low"
            ))

    def _detect_percent_spacing(self, original: str, masked: str) -> None:
        """Ajoute l'espace avant % (10% → 10 %)."""
        for match in PERCENT_SPACING_PATTERN.finditer(original):
            start, end = match.start(), match.end()
            
            # Vérification de protection unifiée
            if self._is_protected_zone(original, start, end, masked):
                continue

            original_text = match.group()
            suggested_text = f"{match.group(1)}{_NBSP}%"
            self.issues.append(Issue(
                issue_type="percent_spacing",
                description="Espace manquant avant %",
                position=start,
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low"
            ))

    def _detect_unit_spacing(self, original: str, masked: str) -> None:
        """Ajoute les espaces entre nombres et unités."""
        # Liste des unités courantes (ordonnée par longueur décroissante pour éviter les conflits)
        # Note: ° n'est pas inclus ici car °C et °F couvrent déjà les cas principaux
        units = ['°C', '°F', 'km', 'kg', 'g', 'm', 'cm', 'mm', 'l', 'ml', 'h', 'min', 's']
        
        for unit in units:
            pattern = rf'(\d)({re.escape(unit)})'
            for match in re.finditer(pattern, original):
                start, end = match.start(), match.end()
                
                # Vérification de protection unifiée
                if self._is_protected_zone(original, start, end, masked):
                    continue

                # Vérification supplémentaire : éviter d'ajouter des espaces dans les
                # constructions avec exposants (ex: 10<sup>26</sup>grilles)
                # Vérifier si le nombre est suivi d'une balise <sup>
                if end < len(original) and original[end:end+5].startswith('<sup'):
                    continue
                
                # Vérifier si le nombre est précédé d'une balise </sup>
                if start > 6 and original[start-6:start] == '</sup>':
                    continue

                original_text = match.group()
                suggested_text = f"{match.group(1)}{_NBSP}{match.group(2)}"
                self.issues.append(Issue(
                    issue_type="unit_spacing",
                    description=f"Espace manquant avant {unit}",
                    position=start,
                    original_text=original_text,
                    suggested_text=suggested_text,
                    severity="low"
                ))

    def _detect_duplicate_categories(self, original: str) -> None:
        """Détecte les catégories dupliquées (Catégorie: FR et Category: EN/redirect)."""
        matches = list(CATEGORY_PATTERN.finditer(original))

        seen = {}
        for m in matches:
            # Normalisation : casse + espaces multiples réduits, pour comparer le nom réel de la catégorie
            cat_name = re.sub(r'\s+', ' ', m.group(1).strip()).lower()
            if cat_name in seen:
                original_text = m.group()
                self.issues.append(Issue(
                    issue_type="duplicate_category",
                    description=f"Catégorie dupliquée : {original_text}",
                    position=m.start(),
                    original_text=original_text,
                    suggested_text='',
                    severity="medium"
                ))
            else:
                seen[cat_name] = m.start()

    def _detect_degree_spacing(self, original: str, masked: str) -> None:
        """Ajoute un espace avant ° seul (20° → 20 °)."""
        for match in DEGREE_ALONE_PATTERN.finditer(original):
            start, end = match.start(), match.end()
            
            # Vérification de protection
            if self._is_protected_zone(original, start, end, masked):
                continue
            
            # Vérifier que ce n'est pas déjà °C ou °F
            if end < len(original) and original[end:end+1] in ['C', 'F', 'c', 'f']:
                continue
            
            original_text = match.group()
            suggested_text = f"{match.group(1)}{_NBSP}°"
            self.issues.append(Issue(
                issue_type="degree_spacing",
                description="Espace manquant avant °",
                position=start,
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low"
            ))

    def _detect_duplicate_links(self, original: str, masked: str) -> None:
        """Simplifie les liens internes identiques ([[Paris|Paris]] → [[Paris]])."""
        pattern = r'\[\[([^\]|]+)\|\1\]\]'
        for match in re.finditer(pattern, original):
            start, end = match.start(), match.end()
            
            # Éviter les zones masquées
            if masked[start:end] == MASK_CHAR * (end - start):
                continue

            original_text = match.group()
            link_target = match.group(1)
            suggested_text = f"[[{link_target}]]"
            self.issues.append(Issue(
                issue_type="duplicate_link",
                description="Lien interne avec alias identique à la cible",
                position=start,
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low"
            ))
