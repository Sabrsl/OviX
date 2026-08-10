"""Détection des espaces insécables manquantes."""

import re
from typing import List
from dataclasses import dataclass

from ..base import Issue

_NBSP = "\u00a0"
_SKIP_NEIGHBOURS = (" ", _NBSP, "\n", "\t")

# Une entité HTML se termine par ';' précédé de '&nom' ou '&#123'
_HTML_ENTITY = re.compile(r"&#?\w+;")


@dataclass
class NbspDetector:
    """Détecte les espaces insécables manquantes."""

    issues: List[Issue]

    def _is_html_entity_semicolon(self, masked: str, idx: int) -> bool:
        """True si le ';' à idx termine une entité HTML (&nbsp; &eacute; etc.)."""
        for m in _HTML_ENTITY.finditer(masked):
            if m.end() - 1 == idx:
                return True
        return False

    def detect_double_punctuation_spacing(self, masked: str) -> None:
        """« ; », « : », « ? », « ! » doivent être précédés d'une espace
        insécable sur Wikipédia en français (WP:CT), sauf le deux-points
        horaire (14:30), l'indentation wikicode (":texte" en début de ligne),
        les entités HTML (&nbsp; &eacute; etc.) et la syntaxe wikicode
        ([[Catégorie:, {{Portail:, etc.)."""
        for m in re.finditer(r"[;:?!]", masked):
            idx = m.start()
            if idx == 0:
                continue
            prev_char = masked[idx - 1]
            if prev_char in _SKIP_NEIGHBOURS:
                continue

            # Skip horary time (14:30)
            if prev_char.isdigit() and m.group() == ":":
                if idx + 1 < len(masked) and masked[idx + 1].isdigit():
                    continue

            # Skip wikicode indentation (":texte" en début de ligne)
            if m.group() == ":" and (idx == 0 or masked[idx - 1] == "\n"):
                continue

            # Skip séquences de deux-points d'indentation (::, :::, etc.) en début de ligne
            if m.group() == ":" and idx >= 1:
                # Vérifier si on est en début de ligne et si c'est une séquence de :
                line_start = masked.rfind("\n", 0, idx)
                if line_start == -1:
                    line_start = 0
                line_before = masked[line_start:idx]
                # Si la ligne ne contient que des : (ignorant les autres caractères comme '''), c'est de l'indentation wikicode
                # On vérifie uniquement les caractères qui ne sont pas des espaces ou MASK_CHAR
                non_space_chars = [c for c in line_before if c not in (" ", "\t", "\n", "\u2063")]
                if not non_space_chars or all(c == ":" for c in non_space_chars):
                    continue

            # Skip ';' faisant partie d'une entité HTML
            if m.group() == ";" and self._is_html_entity_semicolon(masked, idx):
                continue

            # Skip ':' faisant partie de la syntaxe wikicode ([[Catégorie:, {{Portail:, etc.)
            if m.group() == ":" and idx >= 2:
                # Vérifier si précédé par {{ ou [[
                if masked[idx - 2:idx] in ("{{", "[["):
                    continue
                # Vérifier si précédé par MASK_CHAR (modèle déjà masqué)
                if masked[idx - 1] == "\u2063":
                    continue
                # Vérifier si précédé par un nom de modèle (lettres majuscules)
                # Pattern: {{NOM: ou [[NOM: ou {{NOM :
                if idx >= 3:
                    # Chercher le début du modèle en remontant
                    template_start = masked.rfind("{{", 0, idx)
                    link_start = masked.rfind("[[", 0, idx)
                    start = max(template_start, link_start)
                    if start != -1 and idx - start < 50:  # Limite raisonnable pour un nom de modèle
                        # Vérifier si entre {{ ou [[ et : il n'y a que des lettres, chiffres ou espaces
                        between = masked[start + 2:idx]
                        if between.strip() and all(c.isalnum() or c in (" ", "_", "-") for c in between):
                            continue

            original_text = masked[idx:idx + 1]
            suggested_text = f"{_NBSP}{original_text}"
            self.issues.append(Issue(
                issue_type="double_punctuation_spacing",
                description=f"Espace insécable manquante avant « {original_text} »",
                position=idx,
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low",
            ))

    def detect_guillemets_spacing(self, masked: str) -> None:
        """« doit être suivi et » précédé d'une espace insécable (WP:CT)."""
        for m in re.finditer(r"[«»]", masked):
            idx = m.start()
            char = m.group()
            original_text = char

            if char == "«":
                if idx + 1 < len(masked) and masked[idx + 1] not in _SKIP_NEIGHBOURS:
                    suggested_text = f"{char}{_NBSP}"
                    self.issues.append(Issue(
                        issue_type="guillemets_spacing",
                        description="Espace insécable manquante après «",
                        position=idx,
                        original_text=original_text,
                        suggested_text=suggested_text,
                        severity="low",
                    ))
            else:  # »
                if idx > 0 and masked[idx - 1] not in _SKIP_NEIGHBOURS:
                    suggested_text = f"{_NBSP}{char}"
                    self.issues.append(Issue(
                        issue_type="guillemets_spacing",
                        description="Espace insécable manquante avant »",
                        position=idx,
                        original_text=original_text,
                        suggested_text=suggested_text,
                        severity="low",
                    ))

    def detect_percent_spacing(self, masked: str) -> None:
        """« % » doit être précédé d'une espace insécable (Wiktionnaire,
        Convention:Typographie). Volontairement conservateur : ne signale
        le cas "collé" (ex. "100%") que lorsque le caractère précédent est
        un chiffre (cas d'usage le plus courant en prose)."""
        for m in re.finditer(r"(\d)%", masked):
            idx = m.start()
            original_text = f"{m.group(1)}%"
            suggested_text = f"{m.group(1)}{_NBSP}%"
            self.issues.append(Issue(
                issue_type="percent_spacing",
                description="Espace insécable manquante avant %",
                position=idx,
                original_text=original_text,
                suggested_text=suggested_text,
                severity="low",
            ))