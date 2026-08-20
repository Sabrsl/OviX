"""
Automation execution state manager for robust session persistence.

Provides persistent storage of automation session state to enable
automatic recovery after interruptions, network failures, or restarts.
"""

import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Any
from pathlib import Path
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
    # Progress tracking fields
    progress: Optional[float] = None  # 0.0 to 100.0
    current_step: Optional[str] = None  # Detailed current step description
    analyzers_status: Optional[Dict[str, str]] = None  # Status per analyzer
    elapsed_time_seconds: Optional[float] = None


@dataclass
class InterruptionRecord:
    """Record of an interruption during automation."""
    timestamp: str
    reason: str
    duration_seconds: Optional[float] = None
    resolved_at: Optional[str] = None


@dataclass
class AutomationSessionState:
    """Complete state of an automation session."""
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
    article_states: List[Dict[str, Any]] = field(default_factory=list)
    interruptions: List[Dict[str, Any]] = field(default_factory=list)
    last_saved_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AutomationSessionState':
        """Create from dictionary."""
        # Convert article states dicts to ArticleState objects
        article_states = [
            ArticleState(**state) if isinstance(state, dict) else state
            for state in data.get('article_states', [])
        ]
        data['article_states'] = [asdict(s) for s in article_states]
        
        # Convert interruption records dicts to InterruptionRecord objects
        interruptions = [
            InterruptionRecord(**record) if isinstance(record, dict) else record
            for record in data.get('interruptions', [])
        ]
        data['interruptions'] = [asdict(r) for r in interruptions]
        
        return cls(**data)


class AutomationStateManager:
    """Manages persistent storage of automation session state."""
    
    def __init__(self, state_file: str = "data/automation_state.json"):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to the state file
        """
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._current_state: Optional[AutomationSessionState] = None
        self._load_state()
    
    def _load_state(self) -> None:
        """Load state from file if exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._current_state = AutomationSessionState.from_dict(data)
                logger.info(f"Loaded automation state from {self.state_file}")
            except Exception as e:
                logger.error(f"Error loading state file: {e}")
                self._current_state = None
        else:
            self._current_state = None
    
    def _save_state(self) -> None:
        """Save current state to file."""
        if self._current_state:
            try:
                self._current_state.last_saved_at = datetime.now().isoformat()
                with open(self.state_file, 'w', encoding='utf-8') as f:
                    json.dump(self._current_state.to_dict(), f, indent=2, ensure_ascii=False)
                logger.debug(f"Saved automation state to {self.state_file}")
            except Exception as e:
                logger.error(f"Error saving state file: {e}")
    
    def create_session(
        self,
        session_id: str,
        category_name: str,
        max_articles: int,
        mode: str = "regex"
    ) -> AutomationSessionState:
        """
        Create a new automation session.
        
        Args:
            session_id: Unique session identifier
            category_name: Wikipedia category name
            max_articles: Maximum articles to process
            mode: Analysis mode (regex or IA)
            
        Returns:
            New session state
        """
        self._current_state = AutomationSessionState(
            session_id=session_id,
            status=SessionStatus.NOT_STARTED.value,
            started_at=datetime.now().isoformat(),
            category_name=category_name,
            max_articles=max_articles,
            mode=mode,
            total_articles=max_articles
        )
        self._save_state()
        logger.info(f"Created new automation session: {session_id}")
        return self._current_state
    
    def get_state(self) -> Optional[AutomationSessionState]:
        """Get current session state."""
        return self._current_state
    
    def update_status(self, status: SessionStatus) -> None:
        """
        Update session status.
        
        Args:
            status: New session status
        """
        if self._current_state:
            self._current_state.status = status.value
            if status == SessionStatus.COMPLETED:
                self._current_state.completed_at = datetime.now().isoformat()
            elif status == SessionStatus.FAILED:
                self._current_state.completed_at = datetime.now().isoformat()
            self._save_state()
    
    def update_step(self, step: str) -> None:
        """
        Update current processing step.
        
        Args:
            step: Current step description
        """
        if self._current_state:
            self._current_state.current_step = step
            self._save_state()
    
    def update_progress(
        self,
        current_index: int,
        articles_processed: int,
        articles_published: int,
        articles_error: int
    ) -> None:
        """
        Update processing progress.
        
        Args:
            current_index: Current article index
            articles_processed: Total articles processed
            articles_published: Total articles published
            articles_error: Total articles with errors
        """
        if self._current_state:
            self._current_state.current_article_index = current_index
            self._current_state.articles_processed = articles_processed
            self._current_state.articles_published = articles_published
            self._current_state.articles_error = articles_error
            self._save_state()
    
    def add_article_state(self, article_state: ArticleState) -> None:
        """
        Add or update article state.
        
        Args:
            article_state: Article state to add/update
        """
        if self._current_state:
            # Check if article already exists
            existing_index = None
            for i, state_dict in enumerate(self._current_state.article_states):
                if state_dict.get('title') == article_state.title:
                    existing_index = i
                    break
            
            article_dict = asdict(article_state)
            if existing_index is not None:
                self._current_state.article_states[existing_index] = article_dict
            else:
                self._current_state.article_states.append(article_dict)
                self._current_state.total_articles = len(self._current_state.article_states)
            
            self._save_state()
    
    def get_article_state(self, title: str) -> Optional[ArticleState]:
        """
        Get state for a specific article.
        
        Args:
            title: Article title
            
        Returns:
            Article state if exists, None otherwise
        """
        if self._current_state:
            for state_dict in self._current_state.article_states:
                if state_dict.get('title') == title:
                    return ArticleState(**state_dict)
        return None

    def update_article_progress(
        self,
        title: str,
        progress: float,
        current_step: str,
        analyzers_status: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Update progress for a specific article.

        Args:
            title: Article title
            progress: Progress percentage (0.0 to 100.0)
            current_step: Current step description
            analyzers_status: Optional status per analyzer
        """
        if self._current_state:
            for state_dict in self._current_state.article_states:
                if state_dict.get('title') == title:
                    state_dict['progress'] = progress
                    state_dict['current_step'] = current_step
                    if analyzers_status:
                        state_dict['analyzers_status'] = analyzers_status
                    # Calculate elapsed time
                    if state_dict.get('started_at'):
                        started = datetime.fromisoformat(state_dict['started_at'])
                        elapsed = (datetime.now() - started).total_seconds()
                        state_dict['elapsed_time_seconds'] = elapsed
                    self._save_state()
                    break
    
    def get_pending_articles(self) -> List[ArticleState]:
        """Get list of pending articles."""
        if self._current_state:
            return [
                ArticleState(**state_dict)
                for state_dict in self._current_state.article_states
                if state_dict.get('status') == ArticleProcessingStatus.PENDING.value
            ]
        return []
    
    def record_interruption(self, reason: str) -> InterruptionRecord:
        """
        Record an interruption.
        
        Args:
            reason: Reason for interruption
            
        Returns:
            Interruption record
        """
        record = InterruptionRecord(
            timestamp=datetime.now().isoformat(),
            reason=reason
        )
        
        if self._current_state:
            self._current_state.interruptions.append(asdict(record))
            self.update_status(SessionStatus.INTERRUPTED)
            self._save_state()
        
        return record
    
    def resolve_interruption(self, record: InterruptionRecord) -> None:
        """
        Mark an interruption as resolved.
        
        Args:
            record: Interruption record to resolve
        """
        if self._current_state:
            for i, int_dict in enumerate(self._current_state.interruptions):
                if int_dict.get('timestamp') == record.timestamp:
                    resolved_at = datetime.now().isoformat()
                    duration = (datetime.fromisoformat(resolved_at) - 
                              datetime.fromisoformat(record.timestamp)).total_seconds()
                    self._current_state.interruptions[i]['resolved_at'] = resolved_at
                    self._current_state.interruptions[i]['duration_seconds'] = duration
                    break
            
            self.update_status(SessionStatus.RUNNING)
            self._save_state()
    
    def clear_state(self) -> None:
        """Clear current state (for new session)."""
        self._current_state = None
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("Cleared automation state")
    
    def can_resume(self) -> bool:
        """Check if there's a resumable session."""
        return (
            self._current_state is not None and
            self._current_state.status in [
                SessionStatus.RUNNING.value,
                SessionStatus.INTERRUPTED.value,
                SessionStatus.PAUSED.value
            ]
        )
    
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


def get_automation_state_manager(state_file: str = "data/automation_state.json") -> AutomationStateManager:
    """
    Get or create automation state manager instance.
    
    Args:
        state_file: Path to state file
        
    Returns:
        AutomationStateManager instance
    """
    return AutomationStateManager(state_file)
