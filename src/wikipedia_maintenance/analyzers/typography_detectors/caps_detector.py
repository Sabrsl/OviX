"""Détection des problèmes de casse et de formatage."""

import re
from typing import List
from dataclasses import dataclass

from ..base import Issue
from ..typography_data import ACRONYM_WHITELIST
from ..typography_patterns import BOLD_PATTERN, ITALIC_PATTERN, SECTION_PATTERN

# Chiffres romains valides (ex: XVIII, MCMXC, IV) - à ne jamais traiter comme "tout en capitales"
ROMAN_NUMERAL_PATTERN = re.compile(r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$')

# Indices qu'un gras en dehors de la 1re phrase est un synonyme/alias légitime du sujet
ALIAS_INTRO_MARKERS = (
    'dit ', 'dite ', 'dits ', 'dites ', 'surnommé', 'surnommée',
    'alias', 'né ', 'née ', 'de son vrai nom', 'également appelé', 'également appelée',
)


@dataclass
class CapsDetector:
    """Détecte les problèmes de casse et de formatage."""

    issues: List[Issue]

    def detect_all_caps(self, original: str, masked: str) -> None:
        """Détecte le texte en capitales qui devrait être en casse normale."""
        # Look for sequences of 5+ uppercase letters (not acronyms)
        caps_pattern = re.compile(r'\b[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ]{5,}\b')

        for match in caps_pattern.finditer(masked):
            text = match.group(0)

            # Sigle connu : pas une anomalie, on ignore silencieusement.
            if text.upper() in ACRONYM_WHITELIST:
                continue

            # Chiffre romain (siècle, souverain, tome...) : jamais une anomalie de casse.
            if ROMAN_NUMERAL_PATTERN.match(text):
                continue

            # Skip if it's inside a template or link
            before = original[max(0, match.start()-10):match.start()]
            after = original[match.end():match.end()+10]
            if '{{' in before or '}}' in after or '[[' in before or ']]' in after:
                continue

            # Skip if inside work title markers ('' or ''')
            # Work titles are often intentionally uppercase (e.g., album titles, brand names)
            before_context = original[max(0, match.start()-5):match.start()]
            after_context = original[match.end():match.end()+5]
            if "''" in before_context or "''" in after_context:
                continue

            suggested = text.capitalize()
            self.issues.append(Issue(
                issue_type="all_caps",
                description=f"Texte en capitales : {text} → {suggested}",
                position=match.start(),
                original_text=text,
                suggested_text=suggested,
                severity="low"
            ))

    def detect_inappropriate_bold(self, original: str, masked: str) -> None:
        """Détecte le gras inapproprié (sauf titres d'article et sections).

        Préserve le gras dans:
        - Première phrase / paragraphe d'intro (nom de l'entité et ses alias)
        - Titres de section
        - Titres d'œuvres (livres, films, albums)
        """
        # Fin du paragraphe d'intro : plus fiable qu'un simple find('.'),
        # qui casse dès la première abréviation pointée ("né le 3 mars...", "St.").
        intro_end = original.find('\n\n')
        if intro_end == -1:
            intro_end = len(original)

        for match in BOLD_PATTERN.finditer(original):
            text = match.group(0)
            position = match.start()

            # Skip if it's a section title
            section_match = SECTION_PATTERN.search(original[max(0, position-50):position+50])
            if section_match:
                continue

            # Skip if it's inside a template or link (infobox, légendes...)
            before = original[max(0, position-10):position]
            after_ctx = original[match.end():match.end()+10]
            if '{{' in before or '}}' in after_ctx or '[[' in before or ']]' in after_ctx:
                continue

            # Skip if it's within the intro paragraph (article name + alias éventuels)
            if position < intro_end:
                continue

            # Skip if immediately preceded by an alias marker ("dit", "surnommé"...)
            # même hors du tout premier paragraphe (cas d'intro longue).
            before_wide = original[max(0, position-40):position].lower()
            if any(marker in before_wide for marker in ALIAS_INTRO_MARKERS):
                continue

            # Skip if it's a work title (followed by work indicators)
            after = original[match.end():match.end()+30]
            work_indicators = ['film', 'album', 'livre', 'roman', 'chanson', 'série', 'œuvre']
            if any(indicator in after.lower() for indicator in work_indicators):
                continue

            self.issues.append(Issue(
                issue_type="inappropriate_bold",
                description=f"Gras inapproprié : {text}",
                position=position,
                original_text=text,
                suggested_text=text.strip("'"),
                severity="low"
            ))

    def detect_abusive_bold_italic(self, original: str, masked: str) -> None:
        """Détecte l'utilisation abusive de gras (''') et italique ('')."""
        # BOLD_PATTERN correspond exactement à l'original (minimum 3 caractères).
        # ITALIC_PATTERN correspond exactement à l'original (minimum 2 caractères).
        bold_count = len(list(BOLD_PATTERN.finditer(original)))
        if bold_count > 3:
            self.issues.append(Issue(
                issue_type="abusive_bold",
                description=f"Utilisation abusive du gras ({bold_count} occurrences)",
                position=0,
                original_text="",
                suggested_text="",
                severity="low"
            ))

        italic_count = len(list(ITALIC_PATTERN.finditer(original)))
        if italic_count > 5:
            self.issues.append(Issue(
                issue_type="abusive_italic",
                description=f"Utilisation abusive de l'italique ({italic_count} occurrences)",
                position=0,
                original_text="",
                suggested_text="",
                severity="low"
            ))