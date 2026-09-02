"""
Module de gestion des résumés d'édition pour Wikipedia.

Fournit une collection de résumés d'édition naturels et variés pour la wikification,
avec sélection aléatoire pour éviter la répétition et paraître plus humains.

Format OviX: Action principale — page(s) de référence/correction — (Test OviX)

FIX: `_build_corrections_parts` et `_compose_summary` étaient définies mais
jamais appelées nulle part dans le module — `get_summary` passe uniquement
par `_build_ovix_summary` pour les deux chemins (`issue_types` et l'ancienne
interface `correction_types`). Ce code mort risquait de se désynchroniser
silencieusement du comportement réel si quelqu'un le modifiait en pensant
qu'il était actif (ex: changer le libellé "casse" là-bas n'aurait eu aucun
effet observable). Supprimé ; aucun changement de comportement, car ces
fonctions n'étaient de toute façon jamais exécutées.
"""

import logging
import random
from typing import Dict, Final, List, Optional

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Format OviX: Action principale — page(s) de référence/correction — (Test OviX)
# ----------------------------------------------------------------------
TEST_SIGNATURE = "Test [[Utilisateur:OviXCore|OviX]]"

# Pages de référence Wikipedia pour chaque type de correction
REFERENCE_PAGES: Final[Dict[str, List[str]]] = {
    "dead_link": ["[[Wikipédia:Vérifiabilité|Vérifiabilité]]"],
    "http_link": ["[[Wikipédia:Liens externes|Liens externes]]"],
    "reference_enrichment": ["[[Wikipédia:Vérifiabilité|Vérifiabilité]]"],
    "case_normalization": [],  # Pas de page de référence spécifique
    "lia_correction": [],  # Pas de page de référence spécifique
    "typo": [],  # Pas de page de référence spécifique
}

# Actions principales pour chaque type de correction
ACTIONS: Final[Dict[str, List[str]]] = {
    "dead_link": [
        "Réparation de liens morts (404/410)",
    ],
    "http_link": [
        "Sécurisation des liens (HTTPS)",
    ],
    "reference_enrichment": [
        "Complément de références (site, date de consultation)",
    ],
    "case_normalization": [
        "Harmonisation typographique (casse)",
    ],
    "lia_correction": [
        "Correction typographique",
        "Correction typo",
        "Correction typographique"
    ],
    "typo": [
        "Correction typographique",
        "Correction typo",
        "Correction typographique"
    ],
}

# Résumés génériques pour compatibilité (ancien format conservé pour fallback)
GENERIC_EDIT_SUMMARIES: Final[List[str]] = [
    "Correction partielle : typographie (Test [[Utilisateur:OviXCore|OviX]])",
    "Harmonisation partielle : typographique (Test [[Utilisateur:OviXCore|OviX]])",
]

HTTP_LINKS_EDIT_SUMMARIES: Final[List[str]] = [
    "Correction : liens HTTP vers HTTPS (domaines vérifiés) (Test [[Utilisateur:OviXCore|OviX]])",
    "Amélioration : liens sécurisés (domaines vérifiés) (Test [[Utilisateur:OviXCore|OviX]])",
]

DEAD_LINKS_EDIT_SUMMARIES: Final[List[str]] = [
    "fix liens morts 404 - 410 - [[Wikipédia:Vérifiabilité|Vérifiabilité]] (Test [[Utilisateur:OviXCore|OviX]])",
]

REFERENCE_ENRICHMENT_EDIT_SUMMARIES: Final[List[str]] = [
    "Complément de références - [[Wikipédia:Vérifiabilité|Vérifiabilité]] (Test [[Utilisateur:OviXCore|OviX]])",
]

LIA_EDIT_SUMMARIES: Final[List[str]] = [
    "Correction : typographie (Test [[Utilisateur:OviXCore|OviX]])",
    "Harmonisation : typographique (Test [[Utilisateur:OviXCore|OviX]])",
]

CASE_NORMALIZATION_EDIT_SUMMARIES: Final[List[str]] = [
    "Correction : normalisation de la casse - [[Wikipédia:Typographie|Typographie]] (Test [[Utilisateur:OviXCore|OviX]])",
    "Harmonisation : majuscules/minuscules - [[Wikipédia:Typographie|Typographie]] (Test [[Utilisateur:OviXCore|OviX]])",
]

MIXED_EDIT_SUMMARIES: Final[List[str]] = [
    "Correction partielle : typographie et URLs (Test [[Utilisateur:OviXCore|OviX]])",
    "Harmonisation partielle : typo et HTTPS (Test [[Utilisateur:OviXCore|OviX]])",
]

# Types d'issues regroupés sous l'étiquette "typographie" — centralisé pour
# ne plus dupliquer cette liste entre les deux implémentations (issue_types
# et correction_types) qui pouvaient auparavant driver l'une de l'autre.
_TYPO_ISSUE_TYPES: Final[frozenset] = frozenset({
    "double_space", "trailing_space", "multiple_blank_lines",
    "punctuation_spacing", "french_quotes", "numeric_interval",
    "percent_spacing", "unit_spacing", "degree_spacing",
})

_KNOWN_CORRECTION_TYPES: Final[frozenset] = frozenset({
    "dead_link", "http_link", "case_normalization", "lia_correction", "reference_enrichment",
})


__all__ = [
    'GENERIC_EDIT_SUMMARIES',
    'HTTP_LINKS_EDIT_SUMMARIES',
    'DEAD_LINKS_EDIT_SUMMARIES',
    'REFERENCE_ENRICHMENT_EDIT_SUMMARIES',
    'CASE_NORMALIZATION_EDIT_SUMMARIES',
    'LIA_EDIT_SUMMARIES',
    'MIXED_EDIT_SUMMARIES',
    'get_random_summary',
    'get_summary',
]


def get_random_summary(summary_list: Optional[List[str]] = None) -> str:
    """
    Retourne un résumé d'édition aléatoire.

    Args:
        summary_list: Liste de résumés à utiliser (optionnel, utilise
            GENERIC_EDIT_SUMMARIES par défaut). Si la liste fournie est
            vide, retombe aussi sur GENERIC_EDIT_SUMMARIES.

    Returns:
        Un résumé d'édition choisi aléatoirement.
    """
    if not summary_list:
        summary_list = GENERIC_EDIT_SUMMARIES
    return random.choice(summary_list)


def _build_ovix_summary(correction_counts: Dict[str, int]) -> str:
    """
    Construit un résumé au format OviX: Action avec compteurs — page(s) de référence — (Test OviX)

    Args:
        correction_counts: Dictionnaire des types de corrections et leurs compteurs
                          (ex: {"dead_link": 5, "http_link": 3})

    Returns:
        Résumé au format OviX avec compteurs
    """
    if not correction_counts:
        return f"Maintenance — {TEST_SIGNATURE}"

    # Filtrer les corrections avec compteur > 0. Copie défensive: on ne
    # doit jamais muter le dict fourni par l'appelant.
    active_corrections = {k: v for k, v in correction_counts.items() if v > 0}

    if not active_corrections:
        return f"Maintenance — {TEST_SIGNATURE}"

    # Fusionner les compteurs de typo et lia_correction
    typo_total = active_corrections.get("typo", 0) + active_corrections.get("lia_correction", 0)
    if typo_total > 0:
        active_corrections["typo"] = typo_total
        if "lia_correction" in active_corrections:
            del active_corrections["lia_correction"]

    # Déterminer l'action principale basée sur la priorité des corrections
    # Priorité: dead_link > reference_enrichment > http_link > case_normalization > typo
    priority_order = ["dead_link", "reference_enrichment", "http_link", "case_normalization", "typo"]

    primary_correction = None
    for correction_type in priority_order:
        if correction_type in active_corrections:
            primary_correction = correction_type
            break

    if not primary_correction:
        primary_correction = list(active_corrections.keys())[0]

    # Construire l'action principale avec compteur
    base_action = random.choice(ACTIONS.get(primary_correction, ["Maintenance"]))
    count = active_corrections[primary_correction]
    action_with_count = f"{base_action} ({count})"

    # Ajouter les autres corrections avec leurs compteurs
    other_corrections = []
    for correction_type in active_corrections:
        if correction_type != primary_correction:
            count = active_corrections[correction_type]
            # Utiliser les termes courts pour les corrections secondaires
            if correction_type == "dead_link":
                other_corrections.append(f"liens morts ({count})")
            elif correction_type == "http_link":
                other_corrections.append(f"HTTPS ({count})")
            elif correction_type == "case_normalization":
                other_corrections.append(f"casse ({count})")
            elif correction_type == "reference_enrichment":
                other_corrections.append(f"réf ({count})")
            elif correction_type == "typo":
                other_corrections.append(f"typo ({count})")

    # Collecter toutes les pages de référence uniques
    reference_pages = []
    for correction_type in active_corrections.keys():
        pages = REFERENCE_PAGES.get(correction_type, [])
        reference_pages.extend(pages)

    # Éliminer les doublons tout en préservant l'ordre
    unique_references = []
    seen = set()
    for page in reference_pages:
        if page not in seen:
            seen.add(page)
            unique_references.append(page)

    # Construire le résumé
    if other_corrections:
        action_str = f"{action_with_count}, {', '.join(other_corrections)}"
    else:
        action_str = action_with_count

    if unique_references:
        references_str = " — ".join(unique_references)
        return f"{action_str} — {references_str} — {TEST_SIGNATURE}"
    else:
        return f"{action_str} — {TEST_SIGNATURE}"


def get_summary(corrections_count: int = 0,
                correction_types: Optional[List[str]] = None,
                issue_types: Optional[Dict[str, int]] = None) -> str:
    """
    Génère un résumé d'édition basé sur les corrections appliquées.

    Format OviX: Action avec compteurs — page(s) de référence — (Test OviX)

    Args:
        corrections_count: Nombre de corrections appliquées (non utilisé
            directement, conservé pour compatibilité de signature).
        correction_types: Liste des types de corrections (optionnel, déprécié).
        issue_types: Dictionnaire des types d'issues et leurs comptes
                    (ex: {"http_link": 5, "double_space": 2}).

    Returns:
        Un résumé d'édition approprié au format OviX avec compteurs. Ne lève jamais d'exception sur des
        entrées malformées (valeurs négatives, clés inconnues, etc.) —
        retombe sur un résumé générique dans ces cas.
    """
    if issue_types and len(issue_types) > 0:
        # Construire le dictionnaire des compteurs de corrections
        correction_counts = {}

        def _safe_count(value) -> int:
            return value if isinstance(value, int) and value > 0 else 0

        dead_links_count = _safe_count(issue_types.get("dead_link", 0))
        http_links_count = _safe_count(issue_types.get("http_link", 0))
        case_normalization_count = _safe_count(issue_types.get("case_normalization", 0))
        lia_correction_count = _safe_count(issue_types.get("lia_correction", 0))
        reference_enrichment_count = _safe_count(issue_types.get("reference_enrichment", 0))

        # Compter les issues typographiques
        typo_count = sum(
            _safe_count(count) for issue_type, count in issue_types.items()
            if issue_type in _TYPO_ISSUE_TYPES
        )

        # Fusionner les corrections LIA avec les typo (car elles sont toutes deux typographiques)
        total_typo = typo_count + lia_correction_count

        # Construire le dictionnaire des compteurs
        if dead_links_count > 0:
            correction_counts["dead_link"] = dead_links_count
        if http_links_count > 0:
            correction_counts["http_link"] = http_links_count
        if case_normalization_count > 0:
            correction_counts["case_normalization"] = case_normalization_count
        if reference_enrichment_count > 0:
            correction_counts["reference_enrichment"] = reference_enrichment_count
        if total_typo > 0:
            correction_counts["typo"] = total_typo

        logger.info(
            f"get_summary (OviX format with counts): correction_counts={correction_counts}, "
            f"issue_types={issue_types}"
        )

        return _build_ovix_summary(correction_counts)

    # Fallback pour l'ancienne interface avec correction_types
    if correction_types and len(correction_types) > 0:
        # Compter les occurrences de chaque type
        correction_counts = {}

        dead_count = correction_types.count("dead_link")
        http_count = correction_types.count("http_link")
        case_count = correction_types.count("case_normalization")
        lia_count = correction_types.count("lia_correction")
        enrichment_count = correction_types.count("reference_enrichment")

        # Types inconnus considérés comme typo
        unknown_types = [t for t in correction_types if t not in _KNOWN_CORRECTION_TYPES]
        typo_count = len(unknown_types)

        # Fusionner les corrections LIA avec les typo
        total_typo = typo_count + lia_count

        if dead_count > 0:
            correction_counts["dead_link"] = dead_count
        if http_count > 0:
            correction_counts["http_link"] = http_count
        if case_count > 0:
            correction_counts["case_normalization"] = case_count
        if enrichment_count > 0:
            correction_counts["reference_enrichment"] = enrichment_count
        if total_typo > 0:
            correction_counts["typo"] = total_typo

        logger.info(
            f"get_summary (OviX format with counts, old interface): correction_counts={correction_counts}, "
            f"correction_types={correction_types}"
        )

        return _build_ovix_summary(correction_counts)

    # Sinon, retourner un résumé aléatoire générique au format OviX
    return f"Maintenance — {TEST_SIGNATURE}"