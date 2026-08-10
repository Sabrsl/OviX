"""Détection des espaces autour des unités."""

import re
from typing import List
from dataclasses import dataclass

from ..base import Issue

_NBSP = "\u00a0"


@dataclass
class SpacingDetector:
    """Détecte les problèmes d'espacement."""

    issues: List[Issue]

    def detect_double_spaces(self, original: str, masked: str) -> None:
        """Signale les suites de deux espaces (ou plus) au sein de la prose.
        Ignore les espaces d'indentation en tout début de ligne (utilisées
        volontairement dans certaines mises en forme wikicode)."""
        for m in re.finditer(r"  +", masked):
            line_start = masked.rfind("\n", 0, m.start())
            if line_start == -1:
                line_start = 0
            line_before = masked[line_start:m.start()]
            if not line_before.strip():
                continue

            original_text = original[m.start():m.end()]
            suggested_text = " "
            self.issues.append(Issue(
                issue_type="double_spaces",
                description="Espace double inutile",
                position=m.start(),
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low",
            ))

    def detect_simple_punctuation_spacing(self, original: str, masked: str) -> None:
        """La virgule et le point ne prennent jamais d'espace avant eux en
        typographie française (contrairement à la ponctuation double
        couverte par _detect_double_punctuation_spacing). Les points de
        suspension sont laissés tels quels (trois points consécutifs)."""
        for m in re.finditer(r" [,.]", masked):
            # Skip if part of ellipsis (...) : on vérifie les 3 caractères
            # à partir du point lui-même (m.start()+1), pas autour de l'espace
            # qui le précède — l'ancien test incluait l'espace et ne pouvait
            # donc jamais correspondre à "...".
            punct = masked[m.start() + 1]
            if punct == "." and masked[m.start() + 1:m.start() + 4] == "...":
                continue

            original_text = original[m.start():m.end()]
            suggested_text = original_text[1:]  # Remove the space
            self.issues.append(Issue(
                issue_type="simple_punctuation_spacing",
                description=f"Espace inutile avant {original_text[1]}",
                position=m.start(),
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low",
            ))

    def detect_parentheses_spacing(self, original: str, masked: str) -> None:
        """Corrige les espaces à l'intérieur des parenthèses :
        - ( mot → (mot    (pas d'espace après '(')
        - mot ) → mot)    (pas d'espace avant ')')

        NE flague PAS l'espace avant '(' ni après ')' : selon WP:CT, une
        espace normale sépare les parenthèses du reste de la phrase, comme
        n'importe quel mot (ex. "Paris (France) depuis" est correct).
        L'ancienne version signalait à tort ces espaces légitimes comme des
        erreurs, ce qui aurait supprimé du texte correct.
        """
        # Space after opening parenthesis
        for m in re.finditer(r"\( ", masked):
            original_text = original[m.start():m.end()]
            suggested_text = "("
            self.issues.append(Issue(
                issue_type="parentheses_spacing",
                description="Espace inutile après (",
                position=m.start(),
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low",
            ))

        # Space before closing parenthesis
        for m in re.finditer(r" \)", masked):
            original_text = original[m.start():m.end()]
            suggested_text = ")"
            self.issues.append(Issue(
                issue_type="parentheses_spacing",
                description="Espace inutile avant )",
                position=m.start(),
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low",
            ))

    def detect_trailing_spaces(self, original: str, masked: str) -> None:
        """Supprime les espaces/tabs en fin de ligne.

        Ne normalise jamais CRLF→LF sur `original` (ça décalerait toutes les
        positions), mais signale les espaces/tabs en fin de ligne comme
        anomalies à corriger."""
        lines = original.split("\n")
        offset = 0
        for line in lines:
            stripped = line.rstrip()
            if len(stripped) < len(line):
                trailing = line[len(stripped):]
                self.issues.append(Issue(
                    issue_type="trailing_spaces",
                    description=f"Espaces en fin de ligne : {repr(trailing)}",
                    position=offset + len(stripped),
                    original_text=trailing,
                    suggested_text="",
                    severity="low",
                ))
            offset += len(line) + 1  # +1 pour le '\n' consommé par split

    def detect_unit_spacing(self, original: str, masked: str) -> None:
        """Ajoute une espace insécable entre nombre et unité :
        20km → 20 km (espace insécable)
        10°C → 10 °C
        13h17 → 13 h 17 (notation horaire compacte)

        Note : la détection du symbole % est volontairement absente d'ici
        et vit uniquement dans NbspDetector.detect_percent_spacing, pour
        éviter des Issues dupliquées quand check_percent_nbsp et check_units
        sont activés simultanément dans le pipeline (typography.py).

        Les `\\b` en fin de pattern empêchent les chevauchements entre unités
        au préfixe commun (ex: "min" ne matche pas le pattern de "m").

        CORRECTIF DE SÉCURITÉ (bug n°4) :
        La notation horaire compacte (13h17, 2h30, 23h59min59s) n'était jamais
        détectée car le pattern (\\d+)(unit)\\b échoue quand l'unité est suivie
        d'un chiffre (\\b ne se déclenche qu'entre \\w et non-\\w). Ajout d'un
        pattern spécifique pour la notation horaire compacte sans \\b final.

        CORRECTIF (bug n°7) :
        Les anciens time_patterns se chevauchaient (23h59min59s matchait 3
        regex différentes en même temps, générant des Issues dupliquées et
        contradictoires, plus un IndexError sur parts[3] qui n'existe jamais).
        Remplacé par une liste ordonnée du plus spécifique au moins spécifique,
        avec arrêt au premier match qui couvre la position (pas de doublon).
        """
        assert len(original) == len(masked), "original et masked doivent avoir la même longueur"

        time_specs = [
            (re.compile(r'(\d+)h(\d+)min(\d+)s', re.IGNORECASE),
             lambda g: f"{g[0]}{_NBSP}h{_NBSP}{g[1]}{_NBSP}min{_NBSP}{g[2]}{_NBSP}s"),
            (re.compile(r'(\d+)h(\d+)min\b', re.IGNORECASE),
             lambda g: f"{g[0]}{_NBSP}h{_NBSP}{g[1]}{_NBSP}min"),
            (re.compile(r'(\d+)min(\d+)s', re.IGNORECASE),
             lambda g: f"{g[0]}{_NBSP}min{_NBSP}{g[1]}{_NBSP}s"),
            (re.compile(r'(\d+)h(\d+)\b', re.IGNORECASE),
             lambda g: f"{g[0]}{_NBSP}h{_NBSP}{g[1]}"),
        ]

        covered_spans = []

        for regex, build in time_specs:
            for m in regex.finditer(masked):
                span = (m.start(), m.end())
                if any(not (span[1] <= s or span[0] >= e) for s, e in covered_spans):
                    continue

                original_text = original[m.start():m.end()]
                suggested_text = build(m.groups())

                self.issues.append(Issue(
                    issue_type="unit_spacing",
                    description="Notation horaire compacte : ajouter des espaces insécables",
                    position=m.start(),
                    original_text=original_text,
                    suggested_text=suggested_text,
                    severity="low",
                ))
                covered_spans.append(span)

        units = ['km', 'm', 'cm', 'mm', 'kg', 'g', 'mg', 'L', 'mL', 'h', 'min', 's']

        for unit in units:
            pattern = rf'(\d+)({unit})\b'
            for m in re.finditer(pattern, masked, re.IGNORECASE):
                span = (m.start(), m.end())
                if any(not (span[1] <= s or span[0] >= e) for s, e in covered_spans):
                    continue
                original_text = original[m.start():m.end()]
                suggested_text = f"{m.group(1)}{_NBSP}{m.group(2)}"
                self.issues.append(Issue(
                    issue_type="unit_spacing",
                    description=f"Espace insécable manquante avant unité {unit}",
                    position=m.start(),
                    original_text=original_text,
                    suggested_text=suggested_text,
                    severity="low",
                ))

        for m in re.finditer(r'(\d+)°C', masked):
            original_text = original[m.start():m.end()]
            suggested_text = f"{m.group(1)}{_NBSP}°C"
            self.issues.append(Issue(
                issue_type="unit_spacing",
                description="Espace insécable manquante avant °C",
                position=m.start(),
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low",
            ))