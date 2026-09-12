"""
Module de logging dédié pour les opérations LIA et les publications.
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Configuration du logger LIA
lia_logger = logging.getLogger("lia_operations")
lia_logger.setLevel(logging.INFO)

# Handler pour le fichier lia_operations.log
lia_handler = logging.FileHandler("lia_operations.log", encoding='utf-8')
lia_handler.setLevel(logging.INFO)
lia_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
lia_handler.setFormatter(lia_formatter)
lia_logger.addHandler(lia_handler)

# Configuration du logger pour les publications
pub_logger = logging.getLogger("published_articles")
pub_logger.setLevel(logging.INFO)

# Handler pour le fichier published_articles.log
pub_handler = logging.FileHandler("published_articles.log", encoding='utf-8')
pub_handler.setLevel(logging.INFO)
pub_formatter = logging.Formatter('%(asctime)s - %(message)s')
pub_handler.setFormatter(pub_formatter)
pub_logger.addHandler(pub_handler)


def log_lia_operation(article_title: str, operation: str, details: Dict[str, Any]):
    """
    Enregistre une opération LIA dans le fichier lia_operations.log.

    Args:
        article_title: Titre de l'article
        operation: Type d'opération (ex: "correction", "erreur", "fallback")
        details: Dictionnaire avec les détails de l'opération
    """
    log_entry = {
        "article": article_title,
        "operation": operation,
        "timestamp": datetime.now().isoformat(),
        "details": details
    }
    lia_logger.info(json.dumps(log_entry, ensure_ascii=False))


def log_published_article(article_title: str, mode: str, summary: str, changes: Optional[Dict[str, Any]] = None):
    """
    Enregistre un article publié dans le fichier published_articles.log.

    Args:
        article_title: Titre de l'article
        mode: Mode de traitement (LIA ou regex)
        summary: Résumé de modification
        changes: Dictionnaire avec les détails des changements (optionnel)
    """
    log_entry = {
        "article": article_title,
        "mode": mode,
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "changes": changes or {}
    }
    pub_logger.info(json.dumps(log_entry, ensure_ascii=False))
