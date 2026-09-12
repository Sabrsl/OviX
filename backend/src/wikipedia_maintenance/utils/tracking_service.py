"""
Tracking Service for DeadLink Operations

This module provides a centralized tracking service for DeadLink operations,
establishing SQLite as the single source of truth for operation state and history.

Key features:
- Records DeadLink operations with unique operation IDs
- Tracks state transitions via event history
- Supports idempotency to prevent duplicate operations
- Enables crash recovery through stale operation detection
- Correlates Issue, Correction, and Publication via operation_id

Phase 1: Contract Tracking - Parallel write to old and new systems
"""

import uuid
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from dataclasses import dataclass, asdict

from .database import DatabaseManager

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize URL for idempotency.
    
    Normalization includes:
    - Lowercasing scheme and netloc
    - Standardizing trailing slashes
    - Removing default ports
    
    Note: This does NOT remove www. or m. prefixes from URLs, as www.example.com
    and example.com may have different content. www. removal is only done for
    the 'Site' parameter in reference templates, not for URL normalization.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL string
    """
    try:
        parsed = urlparse(url)
        # Normalize scheme and netloc to lowercase
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        
        # Build normalized path
        path = parsed.path
        if path and not path.endswith('/'):
            # Remove trailing slash unless it's the root
            pass
        elif not path:
            path = '/'
        
        normalized = f"{scheme}://{netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        if parsed.fragment:
            normalized += f"#{parsed.fragment}"
        
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize URL {url}: {e}")
        return url


def compute_idempotency_key(
    article_title: str,
    revision_id: int,
    url_original: str,
    context_type: str,
    reference_type: str
) -> str:
    """
    Compute idempotency key for DeadLink operation.
    
    The idempotency key ensures that the same operation is not processed twice.
    It combines article, revision, URL, context, and reference type.
    
    Args:
        article_title: Article title
        revision_id: Wikipedia revision ID
        url_original: Original URL
        context_type: Context type (ref, template, bare_url)
        reference_type: Reference type (lien_web, ouvrage, etc.)
        
    Returns:
        SHA256 hash as hex string
    """
    normalized_url = normalize_url(url_original)
    key_string = f"{article_title}:{revision_id}:{normalized_url}:{context_type}:{reference_type}"
    return hashlib.sha256(key_string.encode()).hexdigest()


@dataclass
class DeadLinkOperation:
    """
    Dataclass representing a DeadLink operation.
    
    This structure captures all metadata about a DeadLink operation
    from detection through publication.
    """
    id: str  # UUID
    article_title: str
    revision_id: Optional[int]
    operation_id: str  # UUID unique to this operation
    
    # URL and context (immutable)
    url_original: str
    url_normalized: str
    context_type: Optional[str]
    reference_type: Optional[str]
    template_name: Optional[str]
    field_name: Optional[str]
    
    # Metadata
    idempotency_key: Optional[str]
    retry_count: int = 0
    
    # Final status
    final_status: Optional[str] = None
    publication_status: Optional[str] = None
    
    # Correlation
    issue_id: Optional[str] = None
    correction_id: Optional[str] = None
    publication_job_id: Optional[str] = None
    
    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    detected_at: Optional[str] = None
    published_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return asdict(self)


@dataclass
class DeadLinkOperationEvent:
    """
    Dataclass representing a state transition event.
    
    Events capture the history of state transitions for audit trail
    and crash recovery.
    """
    operation_id: str
    event_type: str  # DETECTED, VALIDATED, REPAIR_CANDIDATE, etc.
    event_data: Optional[str]  # JSON string with event-specific details
    timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return asdict(self)


class TrackingService:
    """
    Centralized tracking service for DeadLink operations.
    
    This service provides the single source of truth for DeadLink operation
    state and history. It records operations, tracks state transitions,
    and enables crash recovery.
    
    Phase 1: Parallel write - records to new system while old systems continue
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize tracking service.
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
        self._logger = logging.getLogger(f"{__name__}.TrackingService")
    
    def record_operation(self, operation: DeadLinkOperation) -> bool:
        """
        Record a new DeadLink operation.
        
        This is called when a DeadLink operation is first detected.
        
        Args:
            operation: DeadLinkOperation to record
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Check if operation already exists (idempotency)
            if operation.idempotency_key:
                cursor.execute(
                    "SELECT id FROM deadlink_operations WHERE idempotency_key = ?",
                    (operation.idempotency_key,)
                )
                existing = cursor.fetchone()
                if existing:
                    self._logger.info(
                        f"Operation already exists with idempotency_key: {operation.idempotency_key}"
                    )
                    return True
            
            # Insert operation
            op_dict = operation.to_dict()
            columns = list(op_dict.keys())
            placeholders = ', '.join(['?' for _ in columns])
            values = [op_dict[col] for col in columns]
            
            cursor.execute(f"""
                INSERT OR REPLACE INTO deadlink_operations ({', '.join(columns)})
                VALUES ({placeholders})
            """, values)
            
            # Record initial DETECTED event
            self._record_event(
                operation.operation_id,
                "DETECTED",
                {"url": operation.url_original, "context": operation.context_type}
            )
            
            self.db.conn.commit()
            self._logger.info(f"Recorded operation: {operation.operation_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to record operation: {e}")
            self.db.conn.rollback()
            return False
    
    def update_operation(
        self,
        operation_id: str,
        **updates
    ) -> bool:
        """
        Update an existing DeadLink operation.
        
        This is called when the operation state changes (e.g., VALIDATED, REPAIR_CONFIRMED).
        
        Args:
            operation_id: Operation ID to update
            **updates: Fields to update (e.g., final_status='VALIDATED')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.db.conn.cursor()
            
            if not updates:
                self._logger.warning("No updates provided for operation")
                return False
            
            # Build update query
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [datetime.now().isoformat(), operation_id]
            
            cursor.execute(f"""
                UPDATE deadlink_operations
                SET {set_clause}, updated_at = ?
                WHERE operation_id = ?
            """, values)
            
            # Record state transition event if final_status changed
            if 'final_status' in updates:
                self._record_event(
                    operation_id,
                    updates['final_status'],
                    updates
                )
            
            self.db.conn.commit()
            self._logger.info(f"Updated operation {operation_id}: {updates}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to update operation: {e}")
            self.db.conn.rollback()
            return False
    
    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get operation by operation_id.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            Operation data or None if not found
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM deadlink_operations WHERE operation_id = ?",
                (operation_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            self._logger.error(f"Failed to get operation: {e}")
            return None
    
    def get_operation_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get operation by URL.
        
        Args:
            url: URL to search for
            
        Returns:
            Operation data or None if not found
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM deadlink_operations WHERE url_original = ? ORDER BY created_at DESC LIMIT 1",
                (url,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            self._logger.error(f"Failed to get operation by URL: {e}")
            return None
    
    def get_operation_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """
        Get operation by idempotency key.
        
        Args:
            idempotency_key: Idempotency key
            
        Returns:
            Operation data or None if not found
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM deadlink_operations WHERE idempotency_key = ?",
                (idempotency_key,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            self._logger.error(f"Failed to get operation by idempotency key: {e}")
            return None
    
    def get_stale_operations(self, stale_threshold_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Get operations that are in intermediate state (stale).
        
        These are operations that may have been interrupted by a crash.
        
        Args:
            stale_threshold_minutes: Minutes threshold for staleness
            
        Returns:
            List of stale operations
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Define intermediate states
            intermediate_states = [
                'DETECTED', 'VALIDATED', 'REPAIR_CANDIDATE', 
                'REPAIR_CONFIRMED', 'CORRECTION_READY', 'APPLYING', 'APPLIED'
            ]
            
            placeholders = ', '.join(['?' for _ in intermediate_states])
            
            cursor.execute(f"""
                SELECT * FROM deadlink_operations
                WHERE final_status IN ({placeholders})
                AND updated_at < datetime('now', '-{stale_threshold_minutes} minutes')
                ORDER BY updated_at ASC
            """, intermediate_states)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            self._logger.error(f"Failed to get stale operations: {e}")
            return []
    
    def get_operation_events(self, operation_id: str) -> List[Dict[str, Any]]:
        """
        Get event history for an operation.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            List of events in chronological order
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM deadlink_operation_events
                WHERE operation_id = ?
                ORDER BY timestamp ASC
                """,
                (operation_id,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            self._logger.error(f"Failed to get operation events: {e}")
            return []
    
    def _record_event(self, operation_id: str, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Record a state transition event.
        
        Args:
            operation_id: Operation ID
            event_type: Event type (DETECTED, VALIDATED, etc.)
            event_data: Event-specific data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.db.conn.cursor()
            
            event = DeadLinkOperationEvent(
                operation_id=operation_id,
                event_type=event_type,
                event_data=json.dumps(event_data) if event_data else None,
                timestamp=datetime.now().isoformat()
            )
            
            event_dict = event.to_dict()
            columns = list(event_dict.keys())
            placeholders = ', '.join(['?' for _ in columns])
            values = [event_dict[col] for col in columns]
            
            cursor.execute(f"""
                INSERT INTO deadlink_operation_events ({', '.join(columns)})
                VALUES ({placeholders})
            """, values)
            
            return True
        except Exception as e:
            self._logger.error(f"Failed to record event: {e}")
            return False
    
    def generate_operation_id(self) -> str:
        """
        Generate a unique operation ID.
        
        Returns:
            UUID string
        """
        return str(uuid.uuid4())
