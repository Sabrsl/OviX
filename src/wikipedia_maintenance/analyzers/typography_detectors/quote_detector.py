"""Détection des guillemets et tirets."""

import re
from typing import List
from dataclasses import dataclass

from ..base import Issue

_TECHNICAL_CONTEXT_CHARS = ('<', '>', '=', 'px', 'style', 'class', 'http')


@dataclass
class QuoteDetector:
    """Détecte les guillemets droits et tirets incorrects."""

    issues: List[Issue]

    def detect_straight_quotes(self, original: str, masked: str) -> None:
        """Remplace les guillemets droits par les guillemets français dans les
        cas évidents uniquement : "texte" → « texte »

        Prudent : ne remplace que quand le contexte est clair (pas de
        guillemets mélangés, pas de contexte technique)."""
        for m in re.finditer(r'"([^"]+)"', masked):
            text = m.group(1)
            if '{{' in text or '}}' in text or '[[' in text or ']]' in text:
                continue
            if len(text) < 3:
                continue

            # Skip technical/markup context (attributs HTML, CSS, URL, code)
            before = original[max(0, m.start()-15):m.start()]
            if any(marker in before.lower() for marker in _TECHNICAL_CONTEXT_CHARS):
                continue
            if any(marker in text.lower() for marker in _TECHNICAL_CONTEXT_CHARS):
                continue

            original_text = original[m.start():m.end()]
            suggested_text = f"« {text} »"
            self.issues.append(Issue(
                issue_type="straight_quotes",
                description="Guillemets droits à remplacer par guillemets français",
                position=m.start(),
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low",
            ))

    def detect_hyphen_to_dash(self, original: str, masked: str) -> None:
        """Remplace un trait d'union utilisé comme ponctuation par un tiret
        demi-cadratin : Paris - Londres → Paris – Londres

        Prudent : ne remplace que quand le trait d'union est clairement utilisé
        comme ponctuation (entre deux mots, pas dans un mot composé, pas une
        plage numérique de type années/pages/heures)."""
        for m in re.finditer(r'\b(\w+)\s+-\s+(\w+)\b', masked):
            before = original[max(0, m.start()-10):m.start()]
            after = original[m.end():m.end()+10]
            if '{{' in before or '}}' in after or '[[' in before or ']]' in after:
                continue

            # Skip si les deux mots encadrants sont numériques (plage: dates,
            # pages, heures) — ce n'est pas de la ponctuation de liaison.
            if m.group(1).isdigit() and m.group(2).isdigit():
                continue

            original_text = original[m.start():m.end()]
            suggested_text = original_text.replace(" - ", " – ")
            self.issues.append(Issue(
                issue_type="hyphen_to_dash",
                description="Trait d'union à remplacer par tiret demi-cadratin",
                position=m.start(),
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low",
            ))