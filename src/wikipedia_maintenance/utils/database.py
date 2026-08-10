"""
Database module for Wikipedia Maintenance Tool.
Handles SQLite database operations for logging and history.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


class DatabaseManager:
    """Manages SQLite database for Wikipedia maintenance operations."""
    
    def __init__(self, db_path: str = "data/wikipedia_maintenance.db"):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Create database tables if they don't exist."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # Articles table - stores analyzed articles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                page_id INTEGER,
                retrieved_at TIMESTAMP,
                last_revision_id INTEGER,
                source_type TEXT,
                source_info TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        # Issues table - stores detected issues
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                issue_type TEXT NOT NULL,
                description TEXT,
                position INTEGER,
                original_text TEXT,
                suggested_text TEXT,
                severity TEXT DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles (id)
            )
        """)
        
        # Actions table - stores user actions (approve, ignore, modify)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                action_type TEXT NOT NULL,
                edit_summary TEXT,
                revision_id INTEGER,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles (id)
            )
        """)
        
        # Sessions table - stores analysis sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                articles_analyzed INTEGER DEFAULT 0,
                articles_approved INTEGER DEFAULT 0,
                articles_ignored INTEGER DEFAULT 0,
                source_type TEXT,
                notes TEXT
            )
        """)
        
        # Settings table - stores UI settings and preferences
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # HTTPS verification cache table - stores HTTPS availability results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS https_verification_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                https_url TEXT,
                http_status_code INTEGER,
                redirect_url TEXT,
                error_type TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_title 
            ON articles(title)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_issues_article_id 
            ON issues(article_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_issues_type 
            ON issues(issue_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_actions_article_id 
            ON actions(article_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_https_cache_domain 
            ON https_verification_cache(domain)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_https_cache_expires 
            ON https_verification_cache(expires_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_https_cache_status 
            ON https_verification_cache(status)
        """)
        
        self.conn.commit()
    
    def add_article(self, title: str, page_id: Optional[int] = None,
                    source_type: str = "manual", source_info: Optional[str] = None) -> int:
        """Add an article to the database.
        
        Args:
            title: Article title
            page_id: Wikipedia page ID
            source_type: How the article was retrieved (category, manual, etc.)
            source_info: Additional source information
            
        Returns:
            Article ID
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO articles 
                (title, page_id, retrieved_at, source_type, source_info, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """, (title, page_id, datetime.now().isoformat(), source_type, source_info))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Article already exists, return its ID
            cursor.execute("SELECT id FROM articles WHERE title = ?", (title,))
            return cursor.fetchone()['id']
    
    def get_article(self, title: str) -> Optional[Dict[str, Any]]:
        """Get article by title.
        
        Args:
            title: Article title
            
        Returns:
            Article data or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM articles WHERE title = ?", (title,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_article_by_id(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get article by ID.
        
        Args:
            article_id: Article ID
            
        Returns:
            Article data or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_article_status(self, article_id: int, status: str, 
                             revision_id: Optional[int] = None):
        """Update article status.
        
        Args:
            article_id: Article ID
            status: New status (pending, approved, ignored, modified)
            revision_id: Wikipedia revision ID if published
        """
        cursor = self.conn.cursor()
        if revision_id:
            cursor.execute("""
                UPDATE articles 
                SET status = ?, last_revision_id = ?
                WHERE id = ?
            """, (status, revision_id, article_id))
        else:
            cursor.execute("""
                UPDATE articles 
                SET status = ?
                WHERE id = ?
            """, (status, article_id))
        self.conn.commit()
    
    def add_issue(self, article_id: int, issue_type: str, description: str,
                  position: Optional[int] = None, original_text: Optional[str] = None,
                  suggested_text: Optional[str] = None, severity: str = "medium") -> int:
        """Add an issue to the database.
        
        Args:
            article_id: Article ID
            issue_type: Type of issue (e.g., "double_space", "bare_link")
            description: Human-readable description
            position: Position in text (if applicable)
            original_text: Original problematic text
            suggested_text: Suggested correction
            severity: Issue severity (low, medium, high)
            
        Returns:
            Issue ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO issues 
            (article_id, issue_type, description, position, original_text, suggested_text, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (article_id, issue_type, description, position, original_text, suggested_text, severity))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_issues(self, article_id: int) -> List[Dict[str, Any]]:
        """Get all issues for an article.
        
        Args:
            article_id: Article ID
            
        Returns:
            List of issues
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM issues 
            WHERE article_id = ?
            ORDER BY id
        """, (article_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def add_action(self, article_id: int, action_type: str, 
                   edit_summary: Optional[str] = None, revision_id: Optional[int] = None) -> int:
        """Record a user action.
        
        Args:
            article_id: Article ID
            action_type: Type of action (approve, ignore, modify)
            edit_summary: Edit summary used
            revision_id: Wikipedia revision ID if published
            
        Returns:
            Action ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO actions (article_id, action_type, edit_summary, revision_id)
            VALUES (?, ?, ?, ?)
        """, (article_id, action_type, edit_summary, revision_id))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_actions(self, article_id: int) -> List[Dict[str, Any]]:
        """Get all actions for an article.
        
        Args:
            article_id: Article ID
            
        Returns:
            List of actions
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM actions 
            WHERE article_id = ?
            ORDER BY performed_at DESC
        """, (article_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def start_session(self, source_type: str, notes: Optional[str] = None) -> int:
        """Start a new analysis session.
        
        Args:
            source_type: Type of article source
            notes: Session notes
            
        Returns:
            Session ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (source_type, notes)
            VALUES (?, ?)
        """, (source_type, notes))
        self.conn.commit()
        return cursor.lastrowid
    
    def end_session(self, session_id: int, articles_analyzed: int,
                   articles_approved: int, articles_ignored: int):
        """End a session with statistics.
        
        Args:
            session_id: Session ID
            articles_analyzed: Number of articles analyzed
            articles_approved: Number of articles approved
            articles_ignored: Number of articles ignored
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE sessions 
            SET ended_at = ?, articles_analyzed = ?, 
                articles_approved = ?, articles_ignored = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), articles_analyzed, 
              articles_approved, articles_ignored, session_id))
        self.conn.commit()
    
    def get_session_stats(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get session statistics.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data or None
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_recent_articles(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently analyzed articles.
        
        Args:
            limit: Maximum number of articles to return
            
        Returns:
            List of articles
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM articles 
            ORDER BY retrieved_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics.
        
        Returns:
            Dictionary with statistics
        """
        cursor = self.conn.cursor()
        
        # Total articles
        cursor.execute("SELECT COUNT(*) as count FROM articles")
        total_articles = cursor.fetchone()['count']
        
        # Articles by status
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM articles 
            GROUP BY status
        """)
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # Total issues
        cursor.execute("SELECT COUNT(*) as count FROM issues")
        total_issues = cursor.fetchone()['count']
        
        # Issues by type
        cursor.execute("""
            SELECT issue_type, COUNT(*) as count 
            FROM issues 
            GROUP BY issue_type
        """)
        issue_types = {row['issue_type']: row['count'] for row in cursor.fetchall()}
        
        # Total actions
        cursor.execute("SELECT COUNT(*) as count FROM actions")
        total_actions = cursor.fetchone()['count']
        
        return {
            'total_articles': total_articles,
            'status_counts': status_counts,
            'total_issues': total_issues,
            'issue_types': issue_types,
            'total_actions': total_actions
        }
    
    # Settings methods
    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value.
        
        Args:
            key: Setting key
            value: Setting value (JSON string for complex values)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, datetime.now().isoformat()))
        self.conn.commit()
    
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value.
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default
    
    def get_all_settings(self) -> Dict[str, str]:
        """Get all settings.
        
        Returns:
            Dictionary of all settings
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {row['key']: row['value'] for row in cursor.fetchall()}
    
    # HTTPS verification cache methods
    def get_https_verification(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get HTTPS verification result from cache.
        
        Args:
            domain: Domain to check
            
        Returns:
            Verification result or None if not found/expired
        """
        # Normalize domain (lowercase, remove trailing slash)
        normalized_domain = domain.lower().rstrip('/')
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM https_verification_cache 
            WHERE domain = ? AND expires_at > ?
            ORDER BY checked_at DESC
            LIMIT 1
        """, (normalized_domain, datetime.now().isoformat()))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def set_https_verification(self, domain: str, status: str, ttl_days: int,
                              https_url: Optional[str] = None, http_status_code: Optional[int] = None,
                              redirect_url: Optional[str] = None, error_type: Optional[str] = None) -> None:
        """Set HTTPS verification result in cache.
        
        Args:
            domain: Domain that was checked
            status: Verification status (HTTPS_AVAILABLE, HTTPS_UNAVAILABLE, CHECK_FAILED)
            ttl_days: Time to live in days
            https_url: HTTPS URL that was checked
            http_status_code: HTTP status code from check
            redirect_url: Final URL after redirects
            error_type: Type of error if check failed
        """
        # Normalize domain
        normalized_domain = domain.lower().rstrip('/')
        
        # Calculate expiration
        from datetime import timedelta
        expires_at = datetime.now() + timedelta(days=ttl_days)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO https_verification_cache 
            (domain, status, https_url, http_status_code, redirect_url, error_type, 
             checked_at, expires_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (normalized_domain, status, https_url, http_status_code, redirect_url, 
              error_type, datetime.now().isoformat(), expires_at.isoformat(), 
              datetime.now().isoformat()))
        self.conn.commit()
    
    def invalidate_https_verification(self, domain: str) -> None:
        """Invalidate HTTPS verification cache entry.
        
        Args:
            domain: Domain to invalidate
        """
        normalized_domain = domain.lower().rstrip('/')
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM https_verification_cache WHERE domain = ?", 
                     (normalized_domain,))
        self.conn.commit()
    
    def cleanup_expired_https_verifications(self) -> int:
        """Remove expired HTTPS verification entries.
        
        Returns:
            Number of entries removed
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM https_verification_cache 
            WHERE expires_at < ?
        """, (datetime.now().isoformat(),))
        deleted = cursor.rowcount
        self.conn.commit()
        return deleted
    
    def delete_setting(self, key: str) -> None:
        """Delete a setting.
        
        Args:
            key: Setting key
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
        self.conn.commit()
    
    def clear_settings(self) -> None:
        """Clear all settings."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM settings")
        self.conn.commit()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
