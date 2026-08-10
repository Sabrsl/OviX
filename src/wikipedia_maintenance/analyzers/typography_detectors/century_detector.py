"""Détection et correction des siècles."""

import re
from typing import List
from dataclasses import dataclass

from ..base import Issue

# XXI = 21e siècle, indices 1 à 21 valides (index 0 inutilisé)
ROMAN_NUMERALS = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
                  'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX', 'XXI']


@dataclass
class CenturyDetector:
    """Détecte les siècles en chiffres arabes à convertir en chiffres romains."""

    issues: List[Issue]

    def detect_centuries(self, original: str, masked: str) -> None:
        """Détecte les siècles en chiffres arabes (ex: 20e siècle → XXe siècle).

        Convention Wikipédia (WP:CT) : les siècles s'écrivent en chiffres romains
        suivis d'un "e" minuscule (XXe siècle), jamais en chiffres arabes ni en
        "ème"/"eme".
        """
        century_pattern = re.compile(r'\b(\d{1,2})(?:e|ème|eme)\s+siècles?\b', re.IGNORECASE)

        for match in century_pattern.finditer(masked):
            century_num = int(match.group(1))

            # Bornes strictes : seuls 1 à 21 ont une correspondance romaine valide ici.
            # Un nombre hors de cette plage (0, 22+) est ignoré plutôt que de risquer
            # un IndexError ou une conversion erronée.
            if not (1 <= century_num < len(ROMAN_NUMERALS)):
                continue

            roman = ROMAN_NUMERALS[century_num]
            # Préserve singulier/pluriel du mot "siècle" tel qu'écrit dans le texte
            century_word = match.group(0).split()[-1]

            suggested = f"{roman}e {century_word}"

            self.issues.append(Issue(
                issue_type="century_format",
                description=f"Siècle en chiffres arabes : {match.group(0)} → {suggested}",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=suggested,
                severity="medium"
            ))