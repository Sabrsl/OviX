"""
Gestion du suivi des articles publiés sur Wikipédia.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PublishedTracker:
    """
    Suit les articles publiés pour éviter de les republier trop fréquemment.
    """
    
    def __init__(self, tracker_file: str = "published_articles.json", archive_file: str = "published_articles_archive.json"):
        """
        Initialise le tracker d'articles publiés.

        Args:
            tracker_file: Chemin vers le fichier JSON de suivi.
            archive_file: Chemin vers le fichier d'archive pour les entrées anciennes.
        """
        self.tracker_file = Path(tracker_file)
        self.archive_file = Path(archive_file)
        self.published_articles: Dict[str, dict] = {}
        self._load_tracker()
    
    def _load_tracker(self) -> None:
        """Charge les données de suivi depuis le fichier JSON."""
        if self.tracker_file.exists():
            try:
                with open(self.tracker_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.published_articles = data.get('published_articles', {})
                logger.info(f"Chargé {len(self.published_articles)} articles publiés depuis {self.tracker_file}")
                
                # Archivage automatique si trop d'entrées (> 5000)
                if len(self.published_articles) > 5000:
                    self.archive_old_entries(months=12)
                    logger.info(f"Archivage automatique effectué")
            except Exception as e:
                logger.error(f"Erreur lors du chargement du tracker: {e}")
                self.published_articles = {}
        else:
            logger.info(f"Fichier tracker {self.tracker_file} inexistant, création d'un nouveau tracker")
            self.published_articles = {}
    
    def _save_tracker(self) -> None:
        """Sauvegarde les données de suivi dans le fichier JSON."""
        try:
            with open(self.tracker_file, 'w', encoding='utf-8') as f:
                json.dump({'published_articles': self.published_articles}, f, indent=2, ensure_ascii=False)
            logger.info(f"Sauvegardé {len(self.published_articles)} articles publiés dans {self.tracker_file}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du tracker: {e}")
    
    def _load_archive(self) -> Dict[str, dict]:
        """Charge les données d'archive depuis le fichier JSON."""
        if self.archive_file.exists():
            try:
                with open(self.archive_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    archived = data.get('archived_articles', {})
                logger.info(f"Chargé {len(archived)} articles archivés depuis {self.archive_file}")
                return archived
            except Exception as e:
                logger.error(f"Erreur lors du chargement de l'archive: {e}")
                return {}
        return {}
    
    def _append_to_archive(self, entries_to_archive: Dict[str, dict]) -> None:
        """Ajoute des entrées à l'archive existante."""
        archived = self._load_archive()
        archived.update(entries_to_archive)
        
        try:
            with open(self.archive_file, 'w', encoding='utf-8') as f:
                json.dump({'archived_articles': archived}, f, indent=2, ensure_ascii=False)
            logger.info(f"Archivé {len(entries_to_archive)} entrées dans {self.archive_file}")
        except Exception as e:
            logger.error(f"Erreur lors de l'archivage: {e}")
    
    def archive_old_entries(self, months: int = 12) -> int:
        """
        Archive les entrées anciennes du tracker pour alléger le fichier principal.
        Les données archivées sont conservées dans un fichier séparé.

        Args:
            months: Nombre de mois de rétention dans le tracker principal (défaut: 12 mois)
            
        Returns:
            Nombre d'entrées archivées
        """
        threshold = datetime.now() - timedelta(days=months * 30)
        
        # Séparer les entrées récentes et anciennes
        entries_to_archive = {}
        remaining = {}
        for title, data in self.published_articles.items():
            if datetime.fromisoformat(data['published_at']) > threshold:
                remaining[title] = data
            else:
                entries_to_archive[title] = data
        
        self.published_articles = remaining
        
        archived_count = len(entries_to_archive)
        if archived_count > 0:
            self._append_to_archive(entries_to_archive)
            self._save_tracker()
            logger.info(f"Archivé {archived_count} entrées anciennes (>{months} mois) dans {self.archive_file}")
        
        return archived_count
    
    def mark_as_published(self, article_title: str, category: str = "unknown", mode: str = "regex", summary: str = "", revision_id: Optional[int] = None) -> None:
        """
        Marque un article comme publié.

        Args:
            article_title: Titre de l'article.
            category: Catégorie de l'article.
            mode: Mode de traitement (LIA ou regex).
            summary: Résumé de modification (edit summary).
            revision_id: ID de révision Wikipédia pour améliorer l'idempotence (P1 FIX).
        """
        entry = {
            'published_at': datetime.now().isoformat(),
            'category': category,
            'mode': mode,
            'summary': summary
        }
        
        # Add revision_id if provided for better idempotence
        if revision_id is not None:
            entry['revision_id'] = revision_id
            logger.info(f"Marqué '{article_title}' comme publié avec revision_id={revision_id}")
        else:
            logger.info(f"Marqué '{article_title}' comme publié sans revision_id")
            
        self.published_articles[article_title] = entry
        self._save_tracker()
        logger.info(f"Article '{article_title}' marqué comme publié (catégorie: {category}, mode: {mode})")
    
    def is_recently_published(self, article_title: str, months: int = 6, current_revision_id: Optional[int] = None) -> bool:
        """
        Vérifie si un article a été publié récemment.

        Args:
            article_title: Titre de l'article.
            months: Nombre de mois à considérer comme "récent" (défaut: 6).
            current_revision_id: ID de révision actuel pour vérifier les conflits (P1 FIX).

        Returns:
            True si l'article a été publié depuis moins de `months` mois.
        """
        if article_title not in self.published_articles:
            return False
        
        entry = self.published_articles[article_title]
        published_at_str = entry['published_at']
        published_at = datetime.fromisoformat(published_at_str)
        threshold = datetime.now() - timedelta(days=months * 30)
        
        # P1 FIX: Check revision_id for better idempotence
        if current_revision_id is not None and 'revision_id' in entry:
            published_revision_id = entry['revision_id']
            if current_revision_id != published_revision_id:
                logger.warning(f"Article '{article_title}' a été modifié depuis publication (revision_id: {published_revision_id} -> {current_revision_id})")
                # Return False to allow republication since content has changed
                return False
        
        is_recent = published_at > threshold
        if is_recent:
            logger.info(f"Article '{article_title}' publié récemment ({published_at.strftime('%Y-%m-%d')})")
        
        return is_recent
    
    def get_published_date(self, article_title: str) -> Optional[datetime]:
        """
        Récupère la date de publication d'un article.

        Args:
            article_title: Titre de l'article.

        Returns:
            Date de publication ou None si l'article n'est pas dans le tracker.
        """
        if article_title not in self.published_articles:
            return None
        
        published_at_str = self.published_articles[article_title]['published_at']
        return datetime.fromisoformat(published_at_str)
    
    def filter_recently_published(self, article_titles: list, months: int = 6) -> list:
        """
        Filtre une liste d'articles pour exclure ceux publiés récemment.
        Optimisé pour les grandes listes (O(n) avec set lookup).

        Args:
            article_titles: Liste des titres d'articles.
            months: Nombre de mois à considérer comme "récent" (défaut: 6).

        Returns:
            Liste des articles non publiés récemment.
        """
        threshold = datetime.now() - timedelta(days=months * 30)
        
        # Créer un set des titres publiés récemment pour O(1) lookup
        recently_published = {
            title for title, data in self.published_articles.items()
            if datetime.fromisoformat(data['published_at']) > threshold
        }
        
        # Filtrer en une seule passe
        filtered = [title for title in article_titles if title not in recently_published]
        removed = len(article_titles) - len(filtered)
        
        if removed > 0:
            logger.info(f"Filtré {removed} articles publiés récemment sur {len(article_titles)}")
        
        return filtered
    
    def get_stats(self) -> dict:
        """
        Récupère des statistiques sur les articles publiés.

        Returns:
            Dictionnaire de statistiques.
        """
        total = len(self.published_articles)
        recent_6mo = sum(
            1 for article in self.published_articles.values()
            if datetime.fromisoformat(article['published_at']) > datetime.now() - timedelta(days=180)
        )
        
        return {
            'total_published': total,
            'published_last_6_months': recent_6mo,
            'published_before_6_months': total - recent_6mo
        }
