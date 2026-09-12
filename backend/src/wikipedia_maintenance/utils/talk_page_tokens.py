"""
Secure Token Management for Talk Page Kill Switch Control.

This module provides secure one-time-use tokens for emergency bot control
via Wikipedia discussion pages with proper authentication.
"""

import logging
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TokenType(Enum):
    """Types of tokens."""
    EMERGENCY_STOP = "emergency_stop"
    RESUME = "resume"


class TokenStatus(Enum):
    """Token status."""
    VALID = "valid"
    USED = "used"
    EXPIRED = "expired"
    INVALID = "invalid"


@dataclass
class TalkPageToken:
    """Secure token for talk page control."""
    token_id: str  # Unique identifier
    token_hash: str  # SHA256 hash of the actual token
    token_type: TokenType
    created_at: str
    expires_at: str
    used: bool = False
    used_at: Optional[str] = None
    requested_by: str = "operator"
    metadata: Optional[Dict] = None


class TalkPageTokenManager:
    """
    Manager for secure one-time-use tokens for talk page control.
    
    Features:
    - Cryptographically secure random tokens
    - Time-based expiration (default 24 hours)
    - One-time-use (tokens become invalid after use)
    - Database persistence
    - Audit trail
    """
    
    def __init__(self, database=None, token_expiry_hours: int = 24):
        """
        Initialize the token manager.
        
        Args:
            database: DatabaseManager instance
            token_expiry_hours: Token expiration time in hours
        """
        self._database = database
        self._token_expiry_hours = token_expiry_hours
        
        if self._database is None:
            try:
                from wikipedia_maintenance.utils.database import DatabaseManager
                self._database = DatabaseManager()
            except Exception as e:
                logger.warning(f"Could not get database for token manager: {e}")
        
        self._initialize_database()
        logger.info(f"Talk Page Token Manager initialized (expiry: {token_expiry_hours}h)")
    
    def _initialize_database(self) -> None:
        """Initialize database schema for tokens."""
        if not self._database:
            logger.warning("No database available, cannot initialize token table")
            return
        
        try:
            cursor = self._database.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS talk_page_tokens (
                    token_id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL,
                    token_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0,
                    used_at TEXT,
                    requested_by TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Create index for faster cleanup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tokens_expires_at 
                ON talk_page_tokens(expires_at)
            """)
            
            self._database.conn.commit()
            logger.info("Token database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize token database: {e}")
    
    def generate_token(
        self,
        token_type: TokenType,
        requested_by: str = "operator",
        metadata: Optional[Dict] = None
    ) -> Tuple[str, str]:
        """
        Generate a new secure token.
        
        Args:
            token_type: Type of token (STOP or RESUME)
            requested_by: Who requested the token
            metadata: Optional metadata
            
        Returns:
            (token_id, actual_token) tuple
            - token_id: Database identifier (safe to expose)
            - actual_token: The secret token (keep confidential)
        """
        # Generate cryptographically secure random token
        actual_token = secrets.token_urlsafe(32)
        token_id = secrets.token_urlsafe(16)
        
        # Hash the token for storage (never store the actual token)
        token_hash = hashlib.sha256(actual_token.encode()).hexdigest()
        
        # Calculate expiration
        created_at = datetime.now()
        expires_at = created_at + timedelta(hours=self._token_expiry_hours)
        
        # Store in database
        if self._database:
            try:
                cursor = self._database.conn.cursor()
                cursor.execute("""
                    INSERT INTO talk_page_tokens 
                    (token_id, token_hash, token_type, created_at, expires_at, 
                     used, requested_by, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    token_id,
                    token_hash,
                    token_type.value,
                    created_at.isoformat(),
                    expires_at.isoformat(),
                    0,
                    requested_by,
                    str(metadata) if metadata else None
                ))
                self._database.conn.commit()
                
                logger.info(f"Generated {token_type.value} token {token_id} for {requested_by}")
                
            except Exception as e:
                logger.error(f"Failed to store token: {e}")
                raise
        
        return token_id, actual_token
    
    def validate_token(
        self,
        token_id: str,
        actual_token: str
    ) -> Tuple[TokenStatus, Optional[TalkPageToken]]:
        """
        Validate a token and check if it can be used.
        
        Args:
            token_id: Token identifier
            actual_token: The actual token string
            
        Returns:
            (status, token_info) tuple
        """
        if not self._database:
            logger.error("No database available for token validation")
            return TokenStatus.INVALID, None
        
        try:
            cursor = self._database.conn.cursor()
            cursor.execute("""
                SELECT token_id, token_hash, token_type, created_at, expires_at,
                       used, used_at, requested_by, metadata
                FROM talk_page_tokens
                WHERE token_id = ?
            """, (token_id,))
            
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"Token {token_id} not found")
                return TokenStatus.INVALID, None
            
            # Reconstruct token info
            token_info = TalkPageToken(
                token_id=row[0],
                token_hash=row[1],
                token_type=TokenType(row[2]),
                created_at=row[3],
                expires_at=row[4],
                used=bool(row[5]),
                used_at=row[6],
                requested_by=row[7],
                metadata=eval(row[8]) if row[8] else None
            )
            
            # Check if already used
            if token_info.used:
                logger.warning(f"Token {token_id} already used")
                return TokenStatus.USED, token_info
            
            # Check if expired
            if datetime.now() > datetime.fromisoformat(token_info.expires_at):
                logger.warning(f"Token {token_id} expired")
                return TokenStatus.EXPIRED, token_info
            
            # Verify token hash
            provided_hash = hashlib.sha256(actual_token.encode()).hexdigest()
            if provided_hash != token_info.token_hash:
                logger.warning(f"Invalid token hash for {token_id}")
                return TokenStatus.INVALID, token_info
            
            return TokenStatus.VALID, token_info
            
        except Exception as e:
            logger.error(f"Failed to validate token: {e}")
            return TokenStatus.INVALID, None
    
    def use_token(self, token_id: str, actual_token: str) -> Tuple[bool, Optional[TalkPageToken]]:
        """
        Mark a token as used (consumes it).
        
        Args:
            token_id: Token identifier
            actual_token: The actual token string
            
        Returns:
            (success, token_info) tuple
        """
        # First validate
        status, token_info = self.validate_token(token_id, actual_token)
        
        if status != TokenStatus.VALID:
            return False, token_info
        
        # Mark as used
        if self._database:
            try:
                cursor = self._database.conn.cursor()
                cursor.execute("""
                    UPDATE talk_page_tokens
                    SET used = 1, used_at = ?
                    WHERE token_id = ?
                """, (datetime.now().isoformat(), token_id))
                self._database.conn.commit()
                
                logger.info(f"Token {token_id} marked as used")
                token_info.used = True
                token_info.used_at = datetime.now().isoformat()
                
                return True, token_info
                
            except Exception as e:
                logger.error(f"Failed to mark token as used: {e}")
                return False, token_info
        
        return False, token_info
    
    def cleanup_expired_tokens(self) -> int:
        """
        Remove expired tokens from database.
        
        Returns:
            Number of tokens removed
        """
        if not self._database:
            return 0
        
        try:
            cursor = self._database.conn.cursor()
            cursor.execute("""
                DELETE FROM talk_page_tokens
                WHERE expires_at < ?
            """, (datetime.now().isoformat(),))
            
            deleted_count = cursor.rowcount
            self._database.conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired tokens")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")
            return 0
    
    def generate_secure_url(
        self,
        token_id: str,
        actual_token: str,
        base_url: str = "http://localhost:8000"
    ) -> str:
        """
        Generate instructions for using the token securely.
        
        SECURITY: Token is NOT included in URL to prevent leakage in logs/analytics.
        Instead, provide instructions for POST request with token in body.
        
        Args:
            token_id: Token identifier
            actual_token: The actual token string
            base_url: Base URL of the API
            
        Returns:
            Instructions for secure token usage
        """
        return f"""
SECURE TOKEN USAGE INSTRUCTIONS:
================================
Endpoint: {base_url}/api/system/kill-switch/talk-page-activate
Method: POST
Content-Type: application/json

Body:
{{
  "token_id": "{token_id}",
  "token": "{actual_token}",
  "action": "stop",
  "reason": "Emergency stop from Wikipedia talk page"
}}

NOTE: Token is in POST body (not URL) to prevent leakage in logs, analytics, browser history, or Referer headers.
"""


# Global instance
_token_manager: Optional[TalkPageTokenManager] = None


def get_token_manager(database=None, token_expiry_hours: int = 24) -> TalkPageTokenManager:
    """
    Get the global token manager instance.
    
    Args:
        database: Optional DatabaseManager instance
        token_expiry_hours: Token expiration time in hours
        
    Returns:
        TalkPageTokenManager instance
    """
    global _token_manager
    
    if _token_manager is None:
        _token_manager = TalkPageTokenManager(
            database=database,
            token_expiry_hours=token_expiry_hours
        )
    
    return _token_manager