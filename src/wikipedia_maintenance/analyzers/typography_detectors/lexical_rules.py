"""Règles lexicales pour corrections de mots."""

import re
from typing import List, Tuple
from dataclasses import dataclass

from ..base import Issue
from ..typography_data import ACRONYM_WHITELIST


@dataclass
class _WordRule:
    pattern: re.Pattern[str]
    correction: str
    issue_type: str
    description: str
    severity: str = "low"


def _rule(expr: str, correction: str, issue_type: str, description: str, severity: str = "low") -> _WordRule:
    return _WordRule(re.compile(expr, re.IGNORECASE), correction, issue_type, description, severity)


# Ordinaux : fautes non ambiguës, une lettre accentuée en plus, aucun risque
# de confusion avec un autre mot. issue_type conservé à "typo" pour rester
# compatible avec le code existant qui consommait ce type.
_ORDINAL_RULES: List[_WordRule] = [
    _rule(r"\bdeuxieme\b", "deuxième", "typo", "Faute typographique courante"),
    _rule(r"\bdeuxiemes\b", "deuxièmes", "typo", "Faute typographique courante"),
    _rule(r"\btroisieme\b", "troisième", "typo", "Faute typographique courante"),
    _rule(r"\btroisiemes\b", "troisièmes", "typo", "Faute typographique courante"),
    _rule(r"\bquatrieme\b", "quatrième", "typo", "Faute typographique courante"),
    _rule(r"\bquatriemes\b", "quatrièmes", "typo", "Faute typographique courante"),
    _rule(r"\bcinquieme\b", "cinquième", "typo", "Faute typographique courante"),
    _rule(r"\bcinquiemes\b", "cinquièmes", "typo", "Faute typographique courante"),
    _rule(r"\bsixieme\b", "sixième", "typo", "Faute typographique courante"),
    _rule(r"\bseptieme\b", "septième", "typo", "Faute typographique courante"),
    _rule(r"\bhuitieme\b", "huitième", "typo", "Faute typographique courante"),
    _rule(r"\bneuvieme\b", "neuvième", "typo", "Faute typographique courante"),
    _rule(r"\bdixieme\b", "dixième", "typo", "Faute typographique courante"),
    _rule(r"\bonzieme\b", "onzième", "typo", "Faute typographique courante"),
    _rule(r"\bdouzieme\b", "douzième", "typo", "Faute typographique courante"),
    _rule(r"\bvingtieme\b", "vingtième", "typo", "Faute typographique courante"),
    _rule(r"\bcentieme\b", "centième", "typo", "Faute typographique courante"),
    _rule(r"\bderniere\b", "dernière", "typo", "Faute typographique courante"),
    _rule(r"\bdernieres\b", "dernières", "typo", "Faute typographique courante"),
    # "premiere" est exclu du piège "Adobe Premiere" (logiciel), sinon
    # sujet au même traitement que "derniere".
    _rule(r"(?<!adobe )\bpremiere\b", "première", "typo", "Faute typographique courante"),
    _rule(r"(?<!adobe )\bpremieres\b", "premières", "typo", "Faute typographique courante"),
]

# Accents manquants. issue_type conservé à "missing_accent" (compatibilité).
# Les règles les plus spécifiques sont placées AVANT les règles génériques :
# le moteur de correspondance (voir _apply_word_rules) empêche une règle
# plus générale de re-matcher une portée déjà couverte par une règle plus
# spécifique appliquée avant elle (ex. "peut etre" avant "etre" seul).
#
# Chaque mot ajouté ici a été vérifié pour écarter toute ambiguïté avec un
# nom propre, une abréviation ou un emprunt à l'anglais courant sur
# Wikipédia (même logique que l'exclusion historique de "a"->"à", "ca"->"ça"
# ou "meme"->"même", volontairement absents : trop de faux positifs
# probables — verbe "il a", symbole chimique "Ca", emprunt "meme"/mème
# internet). Pour la même raison, des mots comme "general" ou "materiel"
# (noms propres anglophones fréquents : "General Motors", grade militaire
# "General", emprunt "matériel"/"materiel" en anglais) sont volontairement
# exclus de cette liste malgré leur fréquence, le risque de faux positif
# étant jugé trop élevé.
#
# Protection complémentaire (voir _apply_word_rules) : si le texte matché
# est écrit ENTIÈREMENT en capitales dans l'article (collision possible
# avec un sigle réel — ETE, DEJA...), la correction n'est pas appliquée
# automatiquement, quel que soit le mot de la liste ci-dessous.
_ACCENT_RULES: List[_WordRule] = [
    _rule(
        r"\bpeut etre\b", "peut être", "missing_accent", "Accent manquant ; vérifier aussi s'il s'agit de l'adverbe « peut-être »",
        severity="medium",
    ),
    # NB : "etre" (4 lettres, sans accent) est la graphie non accentuée de
    # « être » (infinitif). Le fichier d'origine mappait par erreur "ete"
    # (3 lettres) vers "être" alors que "ete" correspond à « été »
    # (participe passé / nom, ex. « l'été »). Les deux mots sont désormais
    # traités séparément.
    _rule(r"\betre\b", "être", "missing_accent", "Accent manquant possible"),
    _rule(r"\bete\b", "été", "missing_accent", "Accent manquant possible"),
    _rule(r"\bparait\b", "paraît", "missing_accent", "Accent manquant possible"),
    _rule(r"\bdeja\b", "déjà", "missing_accent", "Accent manquant possible"),
    _rule(r"\bvoila\b", "voilà", "missing_accent", "Accent manquant possible"),
    # -- Ajouts : mots courants, orthographe non ambiguë en français --------
    _rule(r"\bprobleme\b", "problème", "missing_accent", "Accent manquant possible"),
    _rule(r"\bproblemes\b", "problèmes", "missing_accent", "Accent manquant possible"),
    _rule(r"\bsysteme\b", "système", "missing_accent", "Accent manquant possible"),
    _rule(r"\bsystemes\b", "systèmes", "missing_accent", "Accent manquant possible"),
    _rule(r"\binteret\b", "intérêt", "missing_accent", "Accent manquant possible"),
    _rule(r"\binterets\b", "intérêts", "missing_accent", "Accent manquant possible"),
    _rule(r"\binteressant\b", "intéressant", "missing_accent", "Accent manquant possible"),
    _rule(r"\binteressants\b", "intéressants", "missing_accent", "Accent manquant possible"),
    _rule(r"\binteressante\b", "intéressante", "missing_accent", "Accent manquant possible"),
    _rule(r"\binteressantes\b", "intéressantes", "missing_accent", "Accent manquant possible"),
    _rule(r"\bdeces\b", "décès", "missing_accent", "Accent manquant possible"),
    _rule(r"\bproces\b", "procès", "missing_accent", "Accent manquant possible"),
    _rule(r"\bsucces\b", "succès", "missing_accent", "Accent manquant possible"),
    _rule(r"\btheoreme\b", "théorème", "missing_accent", "Accent manquant possible"),
    _rule(r"\btheoremes\b", "théorèmes", "missing_accent", "Accent manquant possible"),
    _rule(r"\bevenement\b", "événement", "missing_accent", "Accent manquant possible"),
    _rule(r"\bevenements\b", "événements", "missing_accent", "Accent manquant possible"),
    _rule(r"\bannee\b", "année", "missing_accent", "Accent manquant possible"),
    _rule(r"\bannees\b", "années", "missing_accent", "Accent manquant possible"),
    _rule(r"\bresultat\b", "résultat", "missing_accent", "Accent manquant possible"),
    _rule(r"\bresultats\b", "résultats", "missing_accent", "Accent manquant possible"),
    _rule(r"\bspecifique\b", "spécifique", "missing_accent", "Accent manquant possible"),
    _rule(r"\bspecifiques\b", "spécifiques", "missing_accent", "Accent manquant possible"),
    _rule(r"\bnecessaire\b", "nécessaire", "missing_accent", "Accent manquant possible"),
    _rule(r"\bnecessaires\b", "nécessaires", "missing_accent", "Accent manquant possible"),
    _rule(r"\belectrique\b", "électrique", "missing_accent", "Accent manquant possible"),
    _rule(r"\belectriques\b", "électriques", "missing_accent", "Accent manquant possible"),
    _rule(r"\bperiode\b", "période", "missing_accent", "Accent manquant possible"),
    _rule(r"\bperiodes\b", "périodes", "missing_accent", "Accent manquant possible"),
    _rule(r"\bmodele\b", "modèle", "missing_accent", "Accent manquant possible"),
    _rule(r"\bmodeles\b", "modèles", "missing_accent", "Accent manquant possible"),
    _rule(r"\bregle\b", "règle", "missing_accent", "Accent manquant possible"),
    _rule(r"\bregles\b", "règles", "missing_accent", "Accent manquant possible"),
    # CORRECTIF DE SÉCURITÉ (bug n°6) :
    # Ajout de "siecle"/"siecles" - mot très fréquent dans les articles historiques
    _rule(r"\bsiecle\b", "siècle", "missing_accent", "Accent manquant possible"),
    _rule(r"\bsiecles\b", "siècles", "missing_accent", "Accent manquant possible"),
    _rule(r"\beleve\b", "élève", "missing_accent", "Accent manquant possible"),
    _rule(r"\beleves\b", "élèves", "missing_accent", "Accent manquant possible"),
    _rule(r"\bcategorie\b", "catégorie", "missing_accent", "Accent manquant possible"),
    _rule(r"\bcategories\b", "catégories", "missing_accent", "Accent manquant possible"),
]


@dataclass
class LexicalRulesDetector:
    """Applique les règles lexicales de correction de mots."""
    
    issues: List[Issue]
    
    def _match_case(self, original: str, correction: str) -> str:
        """Reproduit la casse de `original` sur `correction`."""
        if original.isupper():
            return correction.upper()
        if original[0].isupper():
            return correction[0].upper() + correction[1:]
        return correction
    
    def _apply_word_rules(self, original: str, masked: str, rules: List[_WordRule], claimed: List[Tuple[int, int]]) -> None:
        """Applique une liste de règles lexicales, en évitant les chevauchements.
        
        `claimed` est une liste de portées déjà couvertes par une règle précédente
        (pour éviter qu'une règle générique ne re-matche une portion déjà traitée
        par une règle plus spécifique appliquée avant elle).
        """
        for rule in rules:
            for m in rule.pattern.finditer(masked):
                span = (m.start(), m.end())
                # Vérifier si cette portée est déjà couverte
                for claimed_start, claimed_end in claimed:
                    if not (span[1] <= claimed_start or span[0] >= claimed_end):
                        # Chevauchement détecté, sauter
                        break
                else:
                    # Pas de chevauchement, appliquer la règle
                    original_text = original[m.start():m.end()]
                    correction = self._match_case(original_text, rule.correction)
                    
                    # Protection : si le texte est tout en capitales et correspond
                    # à un sigle potentiel (court, tout en capitales), ne pas corriger
                    # automatiquement (collision possible avec un sigle réel).
                    if original_text.isupper() and len(original_text) <= 5:
                        if original_text.upper() in ACRONYM_WHITELIST:
                            continue
                    
                    if correction == original_text:
                        continue
                    
                    self.issues.append(Issue(
                        issue_type=rule.issue_type,
                        description=rule.description,
                        position=m.start(),
                        original_text=original_text,
                        suggested_text=correction,
                        severity=rule.severity,
                    ))
                    # Marquer cette portée comme couverte
                    claimed.append(span)
    
    def apply_ordinal_rules(self, original: str, masked: str, claimed: List[Tuple[int, int]]) -> None:
        """Applique les règles lexicales pour les ordinaux textuels."""
        self._apply_word_rules(original, masked, _ORDINAL_RULES, claimed)
    
    def apply_accent_rules(self, original: str, masked: str, claimed: List[Tuple[int, int]]) -> None:
        """Applique les règles lexicales pour les accents manquants."""
        self._apply_word_rules(original, masked, _ACCENT_RULES, claimed)
