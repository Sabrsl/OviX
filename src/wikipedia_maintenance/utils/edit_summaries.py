"""
Module de gestion des résumés d'édition pour Wikipedia.

Fournit une collection de résumés d'édition naturels et variés pour la wikification,
avec sélection aléatoire pour éviter la répétition et paraître plus humains.
"""

import random
from typing import List, Dict


# ----------------------------------------------------------------------
# Résumés d'édition naturels et variés pour la wikification
# ----------------------------------------------------------------------
GENERIC_EDIT_SUMMARIES: List[str] = [
    "Correction partielle : typographie",
    "Ajustements partielle : typographiques",
    "Retouches partielle : typo",
    "Harmonisation partielle : typographique",
    "Amélioration partielle : de la typographie",
    "Correction partielle : typo mineures",
    "Correction partielle : nettoyage typo",
]

# Résumés spécifiques pour les corrections d'URLs non sécurisées
HTTP_LINKS_EDIT_SUMMARIES: List[str] = [
    "Correction : URLs non sécurisées (domaines vérifiés)",
    "Correction : liens HTTP vers HTTPS (domaines vérifiés)",
    "Correction : sécurisation des URLs (domaines vérifiés)",
    "Correction : conversion HTTP en HTTPS (domaines vérifiés)",
    "Amélioration : liens sécurisés (domaines vérifiés)",
    "Correction : mise à jour des protocoles (domaines vérifiés)",
    "Correction : URLs sécurisées (domaines vérifiés)",
]

# Résumés spécifiques pour les corrections de liens morts
DEAD_LINKS_EDIT_SUMMARIES: List[str] = [
    "Correction : lien mort réparé - actions réalisées dans le cadre de tests - corrections appliquées uniquement aprés validation",
    "Réparation : lien brisé - actions réalisées dans le cadre de tests - corrections appliquées uniquement aprés validation",
    "Correction : remplacement d'un lien mort par son archive valide - actions réalisées dans le cadre de tests - corrections appliquées uniquement aprés validation",
    "Correction : lien inaccessible remplacé par son archive valide - actions réalisées dans le cadre de tests - corrections appliquées uniquement aprés validation",
    "Réparation : lien mort remplacé par son archive valide - actions réalisées dans le cadre de tests - corrections appliquées uniquement aprés validation",
]

# Résumés mixtes (typographie + URLs)
MIXED_EDIT_SUMMARIES: List[str] = [
    "Correction partielle : typographie et URLs",
    "Ajustements partielle : typo et liens sécurisés",
    "Retouches partielle : typographie et protocoles",
    "Harmonisation partielle : typo et HTTPS",
    "Amélioration partielle : typographie et URLs",
]


__all__ = [
    'GENERIC_EDIT_SUMMARIES',
    'HTTP_LINKS_EDIT_SUMMARIES',
    'DEAD_LINKS_EDIT_SUMMARIES',
    'MIXED_EDIT_SUMMARIES',
    'get_random_summary',
    'get_summary',
]


def get_random_summary(summary_list: List[str] = None) -> str:
    """
    Retourne un résumé d'édition aléatoire.
    
    Args:
        summary_list: Liste de résumés à utiliser (optionnel, utilise GENERIC par défaut)
    
    Returns:
        Un résumé d'édition choisi aléatoirement.
    """
    if summary_list is None:
        summary_list = GENERIC_EDIT_SUMMARIES
    return random.choice(summary_list)


def get_summary(corrections_count: int = 0, correction_types: List[str] = None, 
                issue_types: Dict[str, int] = None) -> str:
    """
    Génère un résumé d'édition basé sur les corrections appliquées.
    
    Args:
        corrections_count: Nombre de corrections appliquées.
        correction_types: Liste des types de corrections (optionnel, déprécié).
        issue_types: Dictionnaire des types d'issues et leurs comptes 
                    (ex: {"http_link": 5, "double_space": 2}).
    
    Returns:
        Un résumé d'édition approprié.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Utiliser issue_types si fourni, sinon correction_types
    if issue_types and len(issue_types) > 0:
        # Compter les corrections par catégorie
        http_links_count = issue_types.get("http_link", 0)
        dead_links_count = issue_types.get("dead_link", 0)
        typo_count = sum(
            count for issue_type, count in issue_types.items()
            if issue_type in ["double_space", "trailing_space", "multiple_blank_lines",
                            "punctuation_spacing", "french_quotes", "numeric_interval",
                            "percent_spacing", "unit_spacing", "degree_spacing"]
        )
        
        logger.info(f"get_summary: http_links={http_links_count}, dead_links={dead_links_count}, typo={typo_count}, issue_types={issue_types}")
        
        # Si des liens morts sont présents, utiliser des résumés adaptés
        if dead_links_count > 0:
            logger.info("Using DEAD_LINKS_EDIT_SUMMARIES")
            return get_random_summary(DEAD_LINKS_EDIT_SUMMARIES)
        # Si des liens HTTP sont présents, utiliser des résumés adaptés
        elif http_links_count > 0:
            # Si les liens HTTP sont nettement dominants (> 60%)
            if http_links_count > typo_count * 1.5:  # http_links > 60% of total
                logger.info("Using HTTP_LINKS_EDIT_SUMMARIES (dominant)")
                return get_random_summary(HTTP_LINKS_EDIT_SUMMARIES)
            # Si les liens HTTP sont présents en quantité significative (> 15%)
            elif http_links_count > typo_count * 0.176:  # http_links > 15% of total
                logger.info("Using MIXED_EDIT_SUMMARIES (significant)")
                return get_random_summary(MIXED_EDIT_SUMMARIES)
            # Sinon, typographie dominante mais avec quelques liens HTTP (> 5%)
            elif http_links_count > typo_count * 0.053:  # http_links > 5% of total
                logger.info("Using MIXED_EDIT_SUMMARIES (minor)")
                return get_random_summary(MIXED_EDIT_SUMMARIES)
            # Très peu de liens HTTP (< 5%)
            else:
                logger.info("Using GENERIC_EDIT_SUMMARIES (very minor HTTP)")
                return get_random_summary(GENERIC_EDIT_SUMMARIES)
        else:
            # Uniquement de la typographie
            logger.info("Using GENERIC_EDIT_SUMMARIES (no HTTP)")
            return get_random_summary(GENERIC_EDIT_SUMMARIES)
    
    # Fallback pour l'ancienne interface avec correction_types
    if correction_types and len(correction_types) > 0:
        if "http_link" in correction_types:
            # Vérifier si http_link est dominant
            http_count = correction_types.count("http_link")
            typo_count = len([t for t in correction_types if t != "http_link"])
            
            if http_count > typo_count * 1.5:  # http_links > 60%
                return get_random_summary(HTTP_LINKS_EDIT_SUMMARIES)
            elif http_count > typo_count * 0.176:  # http_links > 15%
                return get_random_summary(MIXED_EDIT_SUMMARIES)
            elif http_count > typo_count * 0.053:  # http_links > 5%
                return get_random_summary(MIXED_EDIT_SUMMARIES)
        
        return get_random_summary()
    
    # Sinon, retourner un résumé aléatoire générique
    return get_random_summary()
