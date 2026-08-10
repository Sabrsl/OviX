"""
Pending Publish Queue Manager

Manages the queue of articles that have been analyzed and are waiting to be published.
This separates the analysis phase from the publication phase.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from .edit_summaries import get_random_summary

logger = logging.getLogger(__name__)


@dataclass
class PendingArticle:
    """An article that has been analyzed and is waiting to be published."""
    title: str
    corrected_content: str
    summary: str
    mode: str  # "regex" or "IA"
    changes_count: int
    analyzed_at: str  # ISO format timestamp
    revision_id: Optional[int] = None
    page_id: Optional[int] = None
    category: Optional[str] = None


class PendingPublishQueue:
    """Manages the queue of pending articles for publication."""
    
    def __init__(self, queue_file: str = "data/pending_publish_queue.json"):
        """
        Initialize the pending publish queue manager.
        
        Args:
            queue_file: Path to the JSON file storing the queue.
        """
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self._queue: List[Dict[str, Any]] = []
        self._load_queue()
    
    def _load_queue(self) -> None:
        """Load queue from file if exists."""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    self._queue = json.load(f)
                logger.info(f"Loaded pending publish queue from {self.queue_file} ({len(self._queue)} articles)")
            except Exception as e:
                logger.error(f"Error loading pending publish queue: {e}")
                self._queue = []
        else:
            logger.info("No pending publish queue file found, starting with empty queue")
    
    def _save_queue(self) -> None:
        """Save queue to file."""
        try:
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(self._queue, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved pending publish queue to {self.queue_file}")
        except Exception as e:
            logger.error(f"Error saving pending publish queue: {e}")
    
    def add_article(
        self,
        title: str,
        corrected_content: str,
        summary: str,
        mode: str,
        changes_count: int,
        revision_id: Optional[int] = None,
        page_id: Optional[int] = None,
        category: Optional[str] = None
    ) -> None:
        """
        Add an article to the pending publish queue.
        
        Args:
            title: Article title.
            corrected_content: Corrected wikitext content.
            summary: Edit summary (can be None, will be selected randomly if needed).
            mode: Analysis mode ("regex" or "IA").
            changes_count: Number of changes made.
            revision_id: Wikipedia revision ID.
            page_id: Wikipedia page ID.
            category: Article category.
        """
        # If no summary provided, select one randomly (fallback only)
        if not summary:
            logger.warning(f"No summary provided for {title}, using random fallback")
            summary = get_random_summary()
        
        article = PendingArticle(
            title=title,
            corrected_content=corrected_content,
            summary=summary,
            mode=mode,
            changes_count=changes_count,
            analyzed_at=datetime.now().isoformat(),
            revision_id=revision_id,
            page_id=page_id,
            category=category
        )
        
        self._queue.append(asdict(article))
        self._save_queue()
        logger.info(f"Added article to pending publish queue: {title} (mode: {mode}, summary: {summary})")
    
    def get_next_article(self) -> Optional[Dict[str, Any]]:
        """
        Get the next article from the queue (FIFO).
        
        Returns:
            Article data dictionary or None if queue is empty.
        """
        if not self._queue:
            return None
        
        article = self._queue.pop(0)
        self._save_queue()
        logger.info(f"Removed article from pending publish queue: {article.get('title')}")
        return article
    
    def peek_next_article(self) -> Optional[Dict[str, Any]]:
        """
        Peek at the next article without removing it from the queue.
        
        Returns:
            Article data dictionary or None if queue is empty.
        """
        if not self._queue:
            return None
        return self._queue[0]
    
    def get_queue_size(self) -> int:
        """Get the current size of the queue."""
        return len(self._queue)
    
    def get_all_articles(self) -> List[Dict[str, Any]]:
        """Get all articles currently in the queue."""
        return self._queue.copy()
    
    def clear_queue(self) -> None:
        """Clear all articles from the queue."""
        self._queue = []
        self._save_queue()
        logger.info("Cleared pending publish queue")
    
    def remove_article_by_title(self, title: str) -> bool:
        """
        Remove an article from the queue by title.
        
        Args:
            title: Title of the article to remove.
        
        Returns:
            True if article was removed, False if not found.
        """
        for i, article in enumerate(self._queue):
            if article.get('title') == title:
                self._queue.pop(i)
                self._save_queue()
                logger.info(f"Removed article from queue by title: {title}")
                return True
        return False
    
    def update_article_summary(self, title: str, new_summary: str) -> bool:
        """
        Update the edit summary for an article in the queue.
        
        Args:
            title: Title of the article.
            new_summary: New edit summary.
        
        Returns:
            True if article was updated, False if not found.
        """
        for article in self._queue:
            if article.get('title') == title:
                article['summary'] = new_summary
                self._save_queue()
                logger.info(f"Updated summary for {title}: {new_summary}")
                return True
        return False


def get_pending_publish_queue(queue_file: str = "data/pending_publish_queue.json") -> PendingPublishQueue:
    """
    Get or create a PendingPublishQueue instance.
    
    Args:
        queue_file: Path to the queue file.
    
    Returns:
        PendingPublishQueue instance.
    """
    return PendingPublishQueue(queue_file)
