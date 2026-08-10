"""
Persistent state management for the Wikipedia maintenance scheduler.

Handles persistence and recovery of scheduler state including:
- Queue status
- Daily counters
- Active/Stopped status
- Timing information
- Statistics
"""

import json
import logging
from datetime import datetime, time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class SchedulerState:
    """Persistent state of the scheduler."""
    is_active: bool = True
    daily_published_count: int = 0
    daily_reset_date: str = None  # ISO format date
    queue: List[Dict[str, Any]] = None  # Articles ready to publish
    next_publish_time: Optional[str] = None  # ISO format datetime
    next_pause_start: Optional[str] = None  # ISO format datetime
    next_pause_end: Optional[str] = None  # ISO format datetime
    long_pauses_today: List[Dict[str, str]] = None  # List of {start, end} for today
    statistics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.queue is None:
            self.queue = []
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
        if self.daily_reset_date is None:
            self.daily_reset_date = datetime.now().date().isoformat()


class StateManager:
    """
    Manages persistence and recovery of scheduler state.
    """
    
    def __init__(self, state_file: str = "data/scheduler_state.json"):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to the state JSON file.
        """
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state: Optional[SchedulerState] = None
        self._load_state()
    
    def _load_state(self) -> None:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._state = SchedulerState(**data)
                logger.info(f"Loaded scheduler state from {self.state_file}")
            except Exception as e:
                logger.error(f"Error loading state: {e}")
                self._state = SchedulerState()
        else:
            logger.info(f"No state file found, creating new state")
            self._state = SchedulerState()
    
    def _save_state(self) -> None:
        """Save state to file."""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self._state), f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved scheduler state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def get_state(self) -> SchedulerState:
        """Get current state."""
        return self._state
    
    def update_state(self, **kwargs) -> None:
        """
        Update state with given fields.
        
        Args:
            **kwargs: Fields to update in the state.
        """
        for key, value in kwargs.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)
            else:
                logger.warning(f"Unknown state field: {key}")
        self._save_state()
    
    def reset_daily_counters(self) -> None:
        """Reset daily counters if the day has changed."""
        today = datetime.now().date().isoformat()
        if self._state.daily_reset_date != today:
            logger.info(f"Resetting daily counters (new day: {today})")
            self._state.daily_published_count = 0
            self._state.daily_reset_date = today
            self._state.long_pauses_today = []
            self._save_state()
    
    def add_to_queue(self, article_data: Dict[str, Any]) -> None:
        """
        Add article to publication queue.
        
        Args:
            article_data: Dictionary with article information (title, corrected_content, summary, etc.)
        """
        self._state.queue.append(article_data)
        self._save_state()
        logger.info(f"Added article to queue: {article_data.get('title', 'unknown')}")
    
    def pop_from_queue(self) -> Optional[Dict[str, Any]]:
        """
        Remove and return the next article from queue.
        
        Returns:
            Article data or None if queue is empty.
        """
        if self._state.queue:
            article = self._state.queue.pop(0)
            self._save_state()
            logger.info(f"Removed article from queue: {article.get('title', 'unknown')}")
            return article
        return None
    
    def increment_daily_published(self) -> None:
        """Increment daily published counter."""
        self._state.daily_published_count += 1
        self._state.statistics['total_published'] += 1
        self._save_state()
    
    def update_statistics(self, **kwargs) -> None:
        """
        Update statistics.
        
        Args:
            **kwargs: Statistics fields to update.
        """
        for key, value in kwargs.items():
            if key in self._state.statistics:
                self._state.statistics[key] = value
        self._save_state()
    
    def set_active(self, is_active: bool) -> None:
        """
        Set scheduler active status.
        
        Args:
            is_active: True to activate, False to stop.
        """
        self._state.is_active = is_active
        self._save_state()
        logger.info(f"Scheduler set to {'ACTIVE' if is_active else 'STOPPED'}")
