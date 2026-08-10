"""Détection et correction des ordinaux abrégés."""

import re
from typing import List, Tuple
from dataclasses import dataclass

from ..base import Issue
from ..typography_patterns import ORDINAL_ABBREVIATION_RE

# Noms féminins courants suivant un ordinal en contexte francophone WP.
# Liste volontairement large mais non exhaustive : en cas de doute, le
# détecteur ne corrige rien plutôt que de risquer une forme fausse.
_FEMININE_CONTEXT_WORDS = (
    "fois", "place", "année", "guerre", "édition", "partie", "moitié",
    "classe", "division", "ligne", "colonne", "page", "case", "étape",
    "semaine", "saison", "manche", "journée", "course", "manif",
    "réunion", "rencontre", "tentative", "victoire", "défaite",
    "candidature", "génération", "version", "mi-temps", "période",
    "circonscription", "région", "position", "épreuve", "finale",
    "demi-finale", "phase", "vague", "fournée", "promotion",
)


@dataclass
class OrdinalDetector:
    """Détecte les ordinaux abrégés incorrects."""

    issues: List[Issue]

    def detect_ordinal_abbreviations(self, original: str, masked: str) -> None:
        """« 2e », pas « 2ème » ; « 1re » (fém.), pas « 1ère » (cf. WP:CT et
        Wikipédia:Conventions concernant les nombres).

        Note : Au-delà de 50, les pluriels utilisent "èmes" (51èmes, 52èmes...)
        et non "es" (51es n'existe pas). Les formes avec "èmes" > 50 sont
        déjà correctes et ne doivent pas être modifiées.
        """
        for m in ORDINAL_ABBREVIATION_RE.finditer(masked):
            number, plural = m.group(1), m.group(2)
            n = int(number)

            if plural and n > 50:
                continue

            suffix = "re" if number == "1" else "e"
            suggested = f"{number}{suffix}{plural}"
            original_text = original[m.start():m.end()]
            if suggested == original_text:
                continue
            self.issues.append(Issue(
                issue_type="ordinal_abbreviation",
                description=(
                    "Forme incorrecte de l'ordinal abrégé : « "
                    f"{suggested} » et non « {original_text} » (WP:CT)"
                ),
                position=m.start(),
                original_text=original_text,
                suggested_text=suggested,
                severity="low",
            ))

    def detect_ordinal_with_space(self, original: str, masked: str) -> None:
        """Corrige les ordinaux avec espace incorrecte :
        1 er janvier → 1er janvier
        1 ère fois   → 1re fois     (féminin : "1re", jamais "1er")
        2 ème        → 2e           (jamais "ème" pour les ordinaux)

        Pour "1 X" (nombre 1), l'accord masculin/féminin ne peut pas être
        deviné à l'aveugle. On ne corrige que si le contexte permet de
        trancher avec confiance :
        - l'orthographe d'origine contient déjà "ère"/"ere" → féminin
        - "re" déjà écrit → féminin
        - "er" écrit + mot suivant féminin connu → féminin
        - "er" écrit + mot suivant non reconnu → masculin par défaut
        """
        ordinal_space_re = re.compile(r"\b(\d+)\s+(er|re|ère|ere|ème|eme)s?\b", re.IGNORECASE)

        for m in ordinal_space_re.finditer(masked):
            number = m.group(1)
            ordinal_word = m.group(2).lower()
            original_text = original[m.start():m.end()]

            if number == "1":
                if ordinal_word in ("ère", "ere"):
                    suggested = f"{number}re"
                elif ordinal_word == "re":
                    suggested = f"{number}re"
                elif ordinal_word == "er":
                    after = masked[m.end():m.end() + 20].strip()
                    next_word = after.split(" ", 1)[0].strip(",.;:!?()«»\"'").lower() if after else ""
                    suggested = f"{number}re" if next_word in _FEMININE_CONTEXT_WORDS else f"{number}er"
                else:
                    continue
            else:
                suggested = f"{number}e"

            if suggested == original_text:
                continue

            self.issues.append(Issue(
                issue_type="ordinal_with_space",
                description=f"Ordinal avec espace incorrecte : {original_text} → {suggested}",
                position=m.start(),
                original_text=original_text,
                suggested_text=suggested,
                severity="low",
            ))