"""
Configuration des catégories Wikipédia prédéfinies pour la maintenance.
"""

PREDEFINED_CATEGORIES = {
    "fr": {
        "Article à wikifier": "Article à wikifier",
        "Article à wikifier/Liste complète": "Article à wikifier/Liste complète",
        "Article avec section à wikifier": "Article avec section à wikifier",
        "Article à sourcer": "Article à sourcer",
        "Article à vérifier": "Article à vérifier",
        "Article à recycler": "Article à recycler",
        "Article en cours de rédaction": "Article en cours de rédaction",
        "Article de qualité à vérifier": "Article de qualité à vérifier",
        "Bon article en liste de suivi": "Bon article en liste de suivi",
        "Wikipédia:Ébauche": "Wikipédia:Ébauche",
        "Portail:Biographie/Articles liés": "Portail:Biographie/Articles liés",
        "Portail:Histoire/Articles liés": "Portail:Histoire/Articles liés",
    }
}


def get_predefined_categories(lang: str = "fr") -> dict:
    """
    Récupère les catégories prédéfinies pour une langue donnée.

    Args:
        lang: Code de langue (ex: 'fr')

    Returns:
        Dictionnaire des catégories prédéfinies pour la langue demandée,
        ou dictionnaire vide si la langue n'est pas supportée.
    """
    return PREDEFINED_CATEGORIES.get(lang, {})


def get_category_names(lang: str = "fr") -> list:
    """
    Récupère uniquement les noms des catégories (sans le préfixe 'Catégorie:'),
    pratique pour construire des requêtes API MediaWiki.

    Args:
        lang: Code de langue (ex: 'fr')

    Returns:
        Liste des noms de catégories.
    """
    return list(get_predefined_categories(lang).values())


def add_category(name: str, lang: str = "fr") -> None:
    """
    Ajoute dynamiquement une catégorie à la configuration en mémoire.

    Args:
        name: Nom de la catégorie (sans préfixe 'Catégorie:')
        lang: Code de langue (ex: 'fr')
    """
    PREDEFINED_CATEGORIES.setdefault(lang, {})[name] = name