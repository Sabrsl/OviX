#!/usr/bin/env python3
"""
Verification de longueur d'article AVANT tout appel au modele Ollama.
Le comptage est fait uniquement par regex - jamais par le modele lui-meme.

Usage:
    python verif_longueur.py chemin_article.txt
    -> code retour 0 si OK, 1 si refus (article trop long)
"""

import re
import sys
import logging
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

# S'assurer que le logger est configuré
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# --- A AJUSTER selon ton num_ctx reel (voir tableau plus bas) ---
# Load from config.yaml or use default
DEFAULT_LIMITE_CARACTERES = 10800  # Correspond à num_ctx 8192 (bon compromis vitesse/capacité)

def _get_limite_caracteres() -> int:
    """Load character limit from config.yaml or use default."""
    try:
        config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config and 'other' in config and 'character_limit' in config['other']:
                    return config['other']['character_limit']
                if config and 'ai' in config and 'gemini' in config['ai'] and 'limit' in config['ai']['gemini']:
                    return config['ai']['gemini']['limit']
    except Exception:
        pass
    return DEFAULT_LIMITE_CARACTERES

LIMITE_CARACTERES = _get_limite_caracteres()

PALIERS_TIMEOUT = [
    (3200, 600),   # num_ctx 4096 → 10 min
    (10800, 1800), # num_ctx 8192 → 30 min
    (25000, 1800), # num_ctx 16384 → 60 min
]

def calculer_timeout(nb_caracteres: int) -> int:
    """Calcule le timeout en fonction du nombre de caractères."""
    for seuil, timeout in PALIERS_TIMEOUT:
        if nb_caracteres <= seuil:
            return timeout
    return PALIERS_TIMEOUT[-1][1]


def extraire_texte_utile(wikicode: str) -> str:
    """Retire balises/modeles/refs pour ne garder que le texte lisible."""
    texte = re.sub(r"<ref[^>]*>.*?</ref>", "", wikicode, flags=re.DOTALL)
    texte = re.sub(r"<ref[^>]*/>", "", texte)
    texte = re.sub(r"\{\{[^{}]*\}\}", "", texte)
    texte = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", texte)  # garde le libelle du lien
    texte = re.sub(r"'{2,}", "", texte)  # italique/gras wiki
    texte = re.sub(r"[=]{2,}.*?[=]{2,}", "", texte)  # titres de section
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def verifier_fidelite(entree: str, sortie: str, seuil_similarite: float = 0.90) -> bool:
    """Compare le texte utile entree/sortie. Rejette si trop divergent.
    Seuil réduit à 90% pour permettre les articles avec beaucoup de corrections."""
    from difflib import SequenceMatcher
    t_entree = extraire_texte_utile(entree)
    t_sortie = extraire_texte_utile(sortie)
    ratio = SequenceMatcher(None, t_entree, t_sortie).ratio()
    try:
        logger.info(f"Fidélité: {ratio:.2%} (seuil: {seuil_similarite:.2%})")
    except NameError:
        pass  # Logger non disponible, ignorer
    return ratio >= seuil_similarite
# ------------------------------------------------------------------

def compter_caracteres(texte: str) -> int:
    """
    Compte les caracteres du wikicode brut (espaces/retours multiples
    normalises en un seul espace pour eviter qu'une mise en forme
    aeree fausse le compte). Aucune interpretation, aucune estimation :
    juste re.sub + len().
    """
    normalise = re.sub(r"\s+", " ", texte).strip()
    return len(normalise)


def verifier(texte: str, limite: int = LIMITE_CARACTERES):
    n = compter_caracteres(texte)
    return (n <= limite), n


def main():
    if len(sys.argv) != 2:
        print("Usage: python verif_longueur.py chemin_article.txt")
        sys.exit(2)

    with open(sys.argv[1], encoding="utf-8") as f:
        article = f.read()

    ok, n = verifier(article)

    if not ok:
        print(
            f"REFUS : article trop long ({n} caracteres, "
            f"limite = {LIMITE_CARACTERES}). "
            f"A diviser en sections avant retraitement."
        )
        sys.exit(1)

    print(f"OK : {n} caracteres (limite = {LIMITE_CARACTERES}). Envoi au modele autorise.")
    sys.exit(0)


if __name__ == "__main__":
    main()

# ------------------------------------------------------------------
# Tableau de reference (num_ctx -> LIMITE_CARACTERES), meme logique
# de calcul que precedemment : marge de securite + article reproduit
# integralement dans la sortie (donc budget divise ~2).
#
#   num_ctx 2048  -> LIMITE_CARACTERES = 1800   (deconseille pour cette tache)
#   num_ctx 4096  -> LIMITE_CARACTERES = 3200
#   num_ctx 8192  -> LIMITE_CARACTERES = 10800
#   num_ctx 16384 -> LIMITE_CARACTERES = 25000
#   num_ctx 32768 -> LIMITE_CARACTERES = 55000
# ------------------------------------------------------------------
