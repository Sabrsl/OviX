"""
SQLite-based Scheduler State Manager - SINGLE SOURCE OF TRUTH

Replaces JSON-based state management with SQLite persistence.
All scheduler state (queue, counters, status, statistics) is stored in SQLite database.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SchedulerState:
    """Persistent state of the scheduler (SQLite-backed)."""
    is_active: bool = False
    is_paused: bool = False
    daily_published_count: int = 0
    daily_reset_date: Optional[str] = None
    queue_size: int = 0
    next_publish_time: Optional[str] = None
    next_pause_start: Optional[str] = None
    next_pause_end: Optional[str] = None
    long_pauses_today: List[Dict[str, str]] = None
    statistics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.long_pauses_today is None:
            self.long_pauses_today = []
        if self.statistics is None:
            self.statistics = {
                'total_published': 0,
                'total_analyzed': 0,
                'total_ignored': 0,
                'total_errors': 0,
                'avg_publish_delay': 0.0,
                'avg_processing_time': 0.0,
            }
    
    @property
    def queue(self) -> List[Dict[str, Any]]:
        """
        Get queue from database for backward compatibility.
        This property is kept for API compatibility with JSON version.
        """
        # Return empty list - actual queue should be accessed via state manager methods
        return []


class SQLiteStateManager:
    """
    SQLite-based state manager for scheduler - SINGLE SOURCE OF TRUTH.
    
    Replaces JSON file-based state management with database persistence.
    All operations are atomic and transactional.
    """
    
    def __init__(self, db_manager):
        """
        Initialize SQLite state manager.
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager
        self._state_cache: Optional[SchedulerState] = None
        self._refresh_cache()
    
    def _refresh_cache(self) -> None:
        """Refresh cached state from database."""
        try:
            db_state = self.db_manager.get_scheduler_state()
            self._state_cache = SchedulerState(
                is_active=bool(db_state.get('is_active', 0)),
                is_paused=bool(db_state.get('is_paused', 0)),
                daily_published_count=db_state.get('daily_published_count', 0),
                daily_reset_date=db_state.get('daily_reset_date'),
                queue_size=db_state.get('queue_size', 0),
                next_publish_time=db_state.get('next_publish_time'),
                next_pause_start=db_state.get('next_pause_start'),
                next_pause_end=db_state.get('next_pause_end'),
                statistics=db_state.get('statistics', {})
            )
        except Exception as e:
            logger.error(f"Error refreshing state cache: {e}")
            self._state_cache = SchedulerState()
    
    def get_state(self) -> SchedulerState:
        """Get current state (with fresh data from SQLite)."""
        self._refresh_cache()
        return self._state_cache
    
    def update_state(self, **kwargs) -> None:
        """
        Update state with given fields (persisted to SQLite).
        
        Args:
            **kwargs: Fields to update in the state.
        """
        if self.db_manager.update_scheduler_state(**kwargs):
            self._refresh_cache()
        else:
            logger.warning(f"Failed to update state: {kwargs}")
    
    def reset_daily_counters(self) -> None:
        """Reset daily counters if the day has changed."""
        if self.db_manager.reset_daily_counters():
            self._refresh_cache()
    
    def add_to_queue(self, article_data: Dict[str, Any]) -> None:
        """
        Add article to publication queue (persisted to SQLite).
        
        Args:
            article_data: Dictionary with article information
        """
        if self.db_manager.add_to_scheduler_queue(article_data):
            self._refresh_cache()
    
    def pop_from_queue(self) -> Optional[Dict[str, Any]]:
        """
        Remove and return the next article from queue (from SQLite).
        
        Returns:
            Article data or None if queue is empty.
        """
        article = self.db_manager.pop_from_scheduler_queue()
        if article is not None:
            self._refresh_cache()
        return article
    
    def get_queue_size(self) -> int:
        """Get current queue size from SQLite."""
        return self.db_manager.get_scheduler_queue_size()
    
    def get_queue(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get articles from queue (from SQLite)."""
        return self.db_manager.get_scheduler_queue(limit)
    
    def increment_daily_published(self) -> None:
        """Increment daily published counter (persisted to SQLite)."""
        if self.db_manager.increment_daily_published():
            self._refresh_cache()
    
    def update_statistics(self, **kwargs) -> None:
        """
        Update statistics (persisted to SQLite).
        
        Args:
            **kwargs: Statistics fields to update.
        """
        if self.db_manager.update_scheduler_statistics(**kwargs):
            self._refresh_cache()
    
    def set_active(self, is_active: bool) -> None:
        """
        Set scheduler active status (persisted to SQLite).
        
        Args:
            is_active: True to activate, False to stop.
        """
        if self.db_manager.set_scheduler_active(is_active):
            self._refresh_cache()
        logger.info(f"Scheduler set to {'ACTIVE' if is_active else 'STOPPED'} (SQLite)")
    
    def set_paused(self, is_paused: bool) -> None:
        """
        Set scheduler paused status (persisted to SQLite).
        
        Args:
            is_paused: True to pause, False to resume.
        """
        if self.db_manager.set_scheduler_paused(is_paused):
            self._refresh_cache()
        logger.info(f"Scheduler set to {'PAUSED' if is_paused else 'RESUMED'} (SQLite)")
    
    def clear_queue(self) -> None:
        """Clear all pending items from queue (from SQLite)."""
        if self.db_manager.clear_scheduler_queue():
            self._refresh_cache()
    
    def mark_queue_item_processed(self, article_id: int, status: str) -> bool:
        """
        Mark a queue item as processed.
        
        Args:
            article_id: Queue item ID
            status: New status
            
        Returns:
            True if successful
        """
        result = self.db_manager.mark_queue_item_processed(article_id, status)
        if result:
            self._refresh_cache()
        return result