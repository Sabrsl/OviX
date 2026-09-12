"""
SQLite-based Automation State Manager - SINGLE SOURCE OF TRUTH

Replaces JSON-based automation state management with SQLite persistence.
All automation session state (sessions, article states, interruptions) is stored in SQLite database.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Status of an automation session."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class ArticleProcessingStatus(Enum):
    """Status of an article in the processing queue."""
    PENDING = "pending"
    RETRIEVING = "retrieving"
    ANALYZING = "analyzing"
    CORRECTING = "correcting"
    QUEUED = "queued"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass
class ArticleState:
    """State of a single article in the automation session."""
    title: str
    page_id: Optional[int] = None
    revision_id: Optional[int] = None
    status: str = ArticleProcessingStatus.PENDING.value
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    changes_count: Optional[int] = None
    summary: Optional[str] = None
    progress: Optional[float] = None
    current_step: Optional[str] = None
    elapsed_time_seconds: Optional[float] = None


@dataclass
class AutomationSessionState:
    """Complete state of an automation session (SQLite-backed)."""
    session_id: str
    status: str = SessionStatus.NOT_STARTED.value
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_step: str = "not_started"
    current_article_index: int = 0
    total_articles: int = 0
    articles_processed: int = 0
    articles_published: int = 0
    articles_error: int = 0
    category_name: Optional[str] = None
    max_articles: int = 0
    mode: str = "regex"
    article_states: List[Dict[str, Any]] = None
    interruptions: List[Dict[str, Any]] = None
    last_saved_at: Optional[str] = None
    
    def __post_init__(self):
        if self.article_states is None:
            self.article_states = []
        if self.interruptions is None:
            self.interruptions = []


class SQLiteAutomationStateManager:
    """
    SQLite-based automation state manager - SINGLE SOURCE OF TRUTH.
    
    Replaces JSON file-based automation state management with database persistence.
    All operations are atomic and transactional.
    """
    
    def __init__(self, db_manager):
        """
        Initialize SQLite automation state manager.
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager
        self._current_state: Optional[AutomationSessionState] = None
        self._load_state()
    
    def _load_state(self) -> None:
        """Load state from SQLite database."""
        try:
            # Get the latest session
            session_data = self.db_manager.get_latest_automation_session()
            
            if session_data:
                session_id = session_data['session_id']
                
                # Get article states for this session
                article_states_data = self.db_manager.get_article_states(session_id)
                article_states = [
                    {
                        'title': state['article_title'],
                        'page_id': state['page_id'],
                        'revision_id': state['revision_id'],
                        'status': state['status'],
                        'progress': state['progress'],
                        'current_step': state['current_step'],
                        'error_message': state['error_message'],
                        'changes_count': state['changes_count'],
                        'elapsed_time_seconds': state['elapsed_time_seconds']
                    }
                    for state in article_states_data
                ]
                
                # Get interruptions for this session
                cursor = self.db_manager.conn.cursor()
                cursor.execute("""
                    SELECT * FROM automation_interruptions 
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                """, (session_id,))
                interruptions = [dict(row) for row in cursor.fetchall()]
                
                self._current_state = AutomationSessionState(
                    session_id=session_id,
                    status=session_data['status'],
                    started_at=session_data['started_at'],
                    completed_at=session_data['completed_at'],
                    current_step=session_data['current_step'],
                    current_article_index=session_data['current_article_index'],
                    total_articles=session_data['total_articles'],
                    articles_processed=session_data['articles_processed'],
                    articles_published=session_data['articles_published'],
                    articles_error=session_data['articles_error'],
                    category_name=session_data['category_name'],
                    max_articles=session_data['max_articles'],
                    mode=session_data['mode'],
                    article_states=article_states,
                    interruptions=interruptions,
                    last_saved_at=session_data['last_saved_at']
                )
                
                logger.info(f"Loaded automation state from SQLite: session {session_id}")
            else:
                self._current_state = None
                logger.info("No active automation session in SQLite")
                
        except Exception as e:
            logger.error(f"Error loading automation state from SQLite: {e}")
            self._current_state = None
    
    def get_state(self) -> Optional[AutomationSessionState]:
        """Get current automation session state."""
        self._load_state()  # Always fresh from SQLite
        return self._current_state
    
    def create_session(self, session_id: str, **kwargs) -> AutomationSessionState:
        """
        Create a new automation session.
        
        Args:
            session_id: Unique session identifier
            **kwargs: Session parameters
            
        Returns:
            Created session state
        """
        if self.db_manager.create_automation_session(session_id, **kwargs):
            self._load_state()
            return self._current_state
        raise Exception(f"Failed to create automation session: {session_id}")
    
    def update_session(self, **kwargs) -> None:
        """
        Update current session fields (persisted to SQLite).
        
        Args:
            **kwargs: Fields to update
        """
        if self._current_state:
            if self.db_manager.update_automation_session(self._current_state.session_id, **kwargs):
                self._load_state()
    
    def start_session(self) -> None:
        """Mark current session as started."""
        if self._current_state:
            if self.db_manager.start_automation_session(self._current_state.session_id):
                self._load_state()
    
    def complete_session(self, status: str = 'completed') -> None:
        """
        Mark current session as completed.
        
        Args:
            status: Final status
        """
        if self._current_state:
            if self.db_manager.complete_automation_session(self._current_state.session_id, status):
                self._load_state()
    
    def add_article_state(self, article_title: str, **kwargs) -> None:
        """
        Add article state to current session.
        
        Args:
            article_title: Article title
            **kwargs: Article state fields
        """
        if self._current_state:
            if self.db_manager.create_article_state(self._current_state.session_id, article_title, **kwargs):
                self._load_state()
    
    def update_article_state(self, article_title: str, **kwargs) -> None:
        """
        Update article state in current session.
        
        Args:
            article_title: Article title
            **kwargs: Fields to update
        """
        if self._current_state:
            if self.db_manager.update_article_state(self._current_state.session_id, article_title, **kwargs):
                self._load_state()
    
    def get_article_states(self) -> List[Dict[str, Any]]:
        """Get all article states for current session."""
        if self._current_state:
            return self._current_state.article_states
        return []
    
    def record_interruption(self, reason: str, **kwargs) -> None:
        """
        Record an interruption during automation.
        
        Args:
            reason: Interruption reason
            **kwargs: Additional interruption data
        """
        if self._current_state:
            from datetime import datetime
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                INSERT INTO automation_interruptions (
                    session_id, timestamp, reason, duration_seconds, resolved_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                self._current_state.session_id,
                datetime.now().isoformat(),
                reason,
                kwargs.get('duration_seconds'),
                kwargs.get('resolved_at')
            ))
            self.db_manager.conn.commit()
            self._load_state()
    
    def cleanup_stale_states(self, timeout_minutes: int = 30) -> int:
        """
        Clean up stale article states.
        
        Args:
            timeout_minutes: Timeout before considering state stale
            
        Returns:
            Number of states cleaned up
        """
        cleaned = self.db_manager.cleanup_stale_article_states(timeout_minutes)
        if cleaned > 0:
            self._load_state()
        return cleaned
    
    def clear_state(self) -> None:
        """Clear current state (for new session)."""
        self._current_state = None
    
    def update_status(self, status: str) -> None:
        """
        Update session status (persisted to SQLite).
        
        Args:
            status: New session status
        """
        if self._current_state:
            if self.db_manager.update_automation_session(self._current_state.session_id, status=status):
                self._load_state()
    
    def update_step(self, step: str) -> None:
        """
        Update current processing step (persisted to SQLite).
        
        Args:
            step: Current step description
        """
        if self._current_state:
            if self.db_manager.update_automation_session(self._current_state.session_id, current_step=step):
                self._load_state()
    
    def update_progress(
        self,
        current_index: int,
        articles_processed: int,
        articles_published: int,
        articles_error: int
    ) -> None:
        """
        Update processing progress (persisted to SQLite).
        
        Args:
            current_index: Current article index
            articles_processed: Total articles processed
            articles_published: Total articles published
            articles_error: Total articles with errors
        """
        if self._current_state:
            if self.db_manager.update_automation_session(
                self._current_state.session_id,
                current_article_index=current_index,
                articles_processed=articles_processed,
                articles_published=articles_published,
                articles_error=articles_error
            ):
                self._load_state()
    
    def can_resume(self) -> bool:
        """Check if there's a resumable session."""
        if self._current_state:
            return self._current_state.status in [
                SessionStatus.RUNNING.value,
                SessionStatus.INTERRUPTED.value,
                SessionStatus.PAUSED.value
            ]
        return False
    
    def get_interruption_summary(self) -> Dict[str, Any]:
        """
        Get summary of interruptions.
        
        Returns:
            Dictionary with interruption statistics
        """
        if not self._current_state:
            return {
                'total_interruptions': 0,
                'total_duration_seconds': 0,
                'resolved_count': 0,
                'unresolved_count': 0
            }
        
        total_duration = 0
        resolved_count = 0
        unresolved_count = 0
        
        for int_dict in self._current_state.interruptions:
            if int_dict.get('resolved_at'):
                total_duration += int_dict.get('duration_seconds', 0)
                resolved_count += 1
            else:
                unresolved_count += 1
        
        return {
            'total_interruptions': len(self._current_state.interruptions),
            'total_duration_seconds': total_duration,
            'resolved_count': resolved_count,
            'unresolved_count': unresolved_count
        }
    
    def resolve_interruption(self, record: Any) -> None:
        """
        Mark an interruption as resolved (persisted to SQLite).
        
        Args:
            record: Interruption record to resolve
        """
        if self._current_state:
            from datetime import datetime
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                UPDATE automation_interruptions
                SET resolved_at = ?, duration_seconds = ?
                WHERE session_id = ? AND timestamp = ?
            """, (
                datetime.now().isoformat(),
                (datetime.now() - datetime.fromisoformat(record.timestamp)).total_seconds() if hasattr(record, 'timestamp') else None,
                self._current_state.session_id,
                record.timestamp if hasattr(record, 'timestamp') else None
            ))
            self.db_manager.conn.commit()
            self._load_state()
    
    def save_state(self) -> None:
        """
        Save state (no-op for SQLite - state is always persisted).
        Kept for API compatibility with JSON version.
        """
        # SQLite automatically persists all changes, so this is a no-op
        pass