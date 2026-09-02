"""
Database module for Wikipedia Maintenance Tool.
Handles SQLite database operations for logging and history.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database for Wikipedia maintenance operations."""
    
    def __init__(self, db_path: str = "data/wikipedia_maintenance.db"):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        # Convert relative path to absolute path if needed
        db_path_obj = Path(db_path)
        if not db_path_obj.is_absolute():
            # Try to get PROJECT_ROOT from environment
            import os
            project_root = os.environ.get('PROJECT_ROOT')
            if project_root:
                db_path_obj = Path(project_root) / db_path_obj
            else:
                # Fallback to current working directory
                db_path_obj = Path.cwd() / db_path_obj
                logger.warning(f"PROJECT_ROOT not set, using CWD: {db_path_obj}")
        
        self.db_path = db_path_obj
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Database path: {self.db_path.absolute()}")
        logger.info(f"Database exists: {self.db_path.exists()}")
        
        # PRODUCTION: Disabled automatic database reset to preserve all data
        # Database persists across restarts for professional data management
        # if self.db_path.exists():
        #     try:
        #         import os
        #         os.remove(self.db_path)
        #         logger.info("Reset database for Dead Linker clean state")
        #     except Exception as e:
        #         logger.warning(f"Could not reset database: {e}")
        
        self.conn = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Create database tables if they don't exist."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Set UTF-8 encoding for text handling
        self.conn.execute("PRAGMA encoding = 'UTF-8'")
        
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
        
        # Manual review decisions table - stores human review decisions for links
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manual_review_decisions (
                id TEXT PRIMARY KEY,  -- item_id: "article_title_hash(url)"
                article_title TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL,  -- approved, rejected, pending
                decision_date TIMESTAMP NOT NULL,
                reviewer_id TEXT,  -- For future user tracking
                decision_reason TEXT,  -- For future audit trail
                article_id INTEGER,  -- Link to articles table if available
                url_hash TEXT NOT NULL,  -- Deterministic hash of URL for indexing
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE SET NULL
            )
        """)

        # Articles to analyze queue - persistent queue for articles waiting analysis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles_to_analyze (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                page_id INTEGER,
                revision_id INTEGER,
                source TEXT NOT NULL,  -- category, manual, petscan, file, user-contribs
                source_details TEXT,
                priority TEXT DEFAULT 'medium',  -- low, medium, high
                added_at TIMESTAMP NOT NULL,
                started_at TIMESTAMP,
                analyzed_at TIMESTAMP,
                status TEXT DEFAULT 'pending',  -- pending, analyzing, analyzed
                job_id TEXT,
                FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
            )
        """)
        
        # Analysis jobs table - persistent job storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                id TEXT PRIMARY KEY,
                article_title TEXT NOT NULL,
                mode TEXT NOT NULL,  -- regex, ai
                status TEXT DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
                progress REAL DEFAULT 0.0,
                message TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error TEXT,
                created_at TIMESTAMP NOT NULL,
                ai_provider TEXT,
                ai_character_limit INTEGER,
                gemini_api_key TEXT,
                gemini_project_id TEXT
            )
        """)

        # Kill switch state table - stores kill switch status persistently
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kill_switch_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                reason TEXT,
                trigger_source TEXT,
                requested_by TEXT,
                requested_at TIMESTAMP,
                last_checked TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure there's exactly one row in kill_switch_state
        cursor.execute("""
            INSERT OR IGNORE INTO kill_switch_state (id, enabled, reason, trigger_source, requested_by, requested_at, last_checked)
            VALUES (1, 0, '', '', '', NULL, NULL)
        """)

        # Automation lock table - prevents concurrent automation launches
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automation_lock (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                locked INTEGER NOT NULL DEFAULT 0,
                locked_by TEXT,
                locked_at TIMESTAMP,
                session_id TEXT,
                automation_type TEXT DEFAULT 'manual',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure there's exactly one row in automation_lock
        cursor.execute("""
            INSERT OR IGNORE INTO automation_lock (id, locked, locked_by, locked_at, session_id, automation_type)
            VALUES (1, 0, NULL, NULL, NULL, 'manual')
        """)

        # Analysis results table - persistent result storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                article_title TEXT NOT NULL,
                page_id INTEGER,
                revision_id INTEGER,
                status TEXT NOT NULL,  -- pending, published, rejected, ignored, error
                mode TEXT NOT NULL,
                changes_count INTEGER,
                summary TEXT,
                original_content TEXT,
                corrected_content TEXT,
                character_count INTEGER,
                total_links INTEGER,
                dead_links_count INTEGER,
                corrected_links_count INTEGER,
                human_verified INTEGER DEFAULT 0,
                manual_review_urls TEXT,  -- JSON array of URLs requiring manual review
                issues_json TEXT,  -- JSON array of detailed issue information
                normalization_changes_count INTEGER DEFAULT 0,  -- Number of normalization changes applied
                normalization_ignored_count INTEGER DEFAULT 0,  -- Number of normalization items ignored
                normalization_reports TEXT,  -- JSON array of normalization reports
                analysis_date TIMESTAMP NOT NULL,
                FOREIGN KEY (job_id) REFERENCES analysis_jobs(id) ON DELETE CASCADE
            )
        """)
        
        # Add manual_review_urls column if it doesn't exist (migration)
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'manual_review_urls' not in columns:
            cursor.execute("ALTER TABLE analysis_results ADD COLUMN manual_review_urls TEXT")
            logger.info("Added manual_review_urls column to analysis_results table")
        
        # Add issues_json column if it doesn't exist (migration)
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'issues_json' not in columns:
            cursor.execute("ALTER TABLE analysis_results ADD COLUMN issues_json TEXT")
            logger.info("Added issues_json column to analysis_results table")
        
        # Add normalization-related columns if they don't exist (migration)
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'normalization_changes_count' not in columns:
            cursor.execute("ALTER TABLE analysis_results ADD COLUMN normalization_changes_count INTEGER DEFAULT 0")
            logger.info("Added normalization_changes_count column to analysis_results table")
        
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'normalization_ignored_count' not in columns:
            cursor.execute("ALTER TABLE analysis_results ADD COLUMN normalization_ignored_count INTEGER DEFAULT 0")
            logger.info("Added normalization_ignored_count column to analysis_results table")
        
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'normalization_reports' not in columns:
            cursor.execute("ALTER TABLE analysis_results ADD COLUMN normalization_reports TEXT")
            logger.info("Added normalization_reports column to analysis_results table")
        
        # User contributions table - stores cached user contributions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_contributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                page_id INTEGER NOT NULL,
                revision_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                namespace INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                comment TEXT,
                retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(username, revision_id)
            )
        """)

        # Scheduler state table - SINGLE SOURCE OF TRUTH for scheduler state
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                is_active INTEGER NOT NULL DEFAULT 0,
                is_paused INTEGER NOT NULL DEFAULT 0,
                daily_published_count INTEGER NOT NULL DEFAULT 0,
                daily_reset_date TEXT,
                next_publish_time TEXT,
                next_pause_start TEXT,
                next_pause_end TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure there's exactly one row in scheduler_state
        cursor.execute("""
            INSERT OR IGNORE INTO scheduler_state (id, is_active, is_paused, daily_published_count, daily_reset_date)
            VALUES (1, 0, 0, 0, NULL)
        """)

        # Scheduler queue table - SINGLE SOURCE OF TRUTH for publication queue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_title TEXT NOT NULL,
                page_id INTEGER,
                revision_id INTEGER,
                corrected_content TEXT,
                summary TEXT,
                changes_count INTEGER,
                original_content TEXT,
                character_count INTEGER,
                total_links INTEGER,
                dead_links_count INTEGER,
                corrected_links_count INTEGER,
                mode TEXT NOT NULL,
                queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'queued',
                priority INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                -- State machine fields for crash recovery
                processing_started_at TIMESTAMP,
                last_heartbeat TIMESTAMP,
                validated_at TIMESTAMP,
                publishing_started_at TIMESTAMP,
                published_at TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                timeout_seconds INTEGER DEFAULT 300
            )
        """)
        
        # Migration: Add state machine fields if they don't exist
        cursor.execute("PRAGMA table_info(scheduler_queue)")
        columns = [col[1] for col in cursor.fetchall()]
        
        new_columns = [
            'updated_at',
            'processing_started_at', 'last_heartbeat', 'validated_at',
            'publishing_started_at', 'published_at', 'error_message',
            'retry_count', 'timeout_seconds'
        ]
        
        for col in new_columns:
            if col not in columns:
                col_type = 'TIMESTAMP' if 'at' in col or col == 'last_heartbeat' else ('INTEGER' if col in ['retry_count', 'timeout_seconds'] else 'TEXT')
                cursor.execute(f"ALTER TABLE scheduler_queue ADD COLUMN {col} {col_type}")
                logger.info(f"Added {col} column to scheduler_queue table")
        
        # Update status default from 'pending' to 'queued' for new state machine
        cursor.execute("UPDATE scheduler_queue SET status = 'queued' WHERE status = 'pending'")
        cursor.execute("UPDATE scheduler_queue SET status = 'stale' WHERE status = 'processing'")
        logger.info("Migrated scheduler_queue status to new state machine")

        # Scheduler statistics table - SINGLE SOURCE OF TRUTH for statistics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_statistics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_published INTEGER NOT NULL DEFAULT 0,
                total_analyzed INTEGER NOT NULL DEFAULT 0,
                total_ignored INTEGER NOT NULL DEFAULT 0,
                total_errors INTEGER NOT NULL DEFAULT 0,
                avg_publish_delay REAL DEFAULT 0.0,
                avg_processing_time REAL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure there's exactly one row in scheduler_statistics
        cursor.execute("""
            INSERT OR IGNORE INTO scheduler_statistics (id, total_published, total_analyzed, total_ignored, total_errors)
            VALUES (1, 0, 0, 0, 0)
        """)

        # Scheduler pauses table - track scheduled and executed pauses
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_pauses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pause_type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds INTEGER,
                executed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Automation sessions table - SINGLE SOURCE OF TRUTH for automation sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automation_sessions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'not_started',
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                current_step TEXT,
                current_article_index INTEGER DEFAULT 0,
                total_articles INTEGER DEFAULT 0,
                articles_processed INTEGER DEFAULT 0,
                articles_published INTEGER DEFAULT 0,
                articles_error INTEGER DEFAULT 0,
                category_name TEXT,
                max_articles INTEGER DEFAULT 0,
                mode TEXT DEFAULT 'regex',
                last_saved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Migration: Add created_at column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE automation_sessions ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            self.conn.commit()
            logger.info("Migration: Added created_at column to automation_sessions")
        except Exception as e:
            # Column might already exist, which is fine
            if "duplicate column name" not in str(e).lower():
                logger.warning(f"Migration warning for created_at: {e}")

        # Automation article states table - track individual article processing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automation_article_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                article_title TEXT NOT NULL,
                page_id INTEGER,
                revision_id INTEGER,
                status TEXT DEFAULT 'pending',
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                changes_count INTEGER,
                summary TEXT,
                progress REAL DEFAULT 0.0,
                current_step TEXT,
                elapsed_time_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES automation_sessions(session_id) ON DELETE CASCADE
            )
        """)

        # Automation interruptions table - track interruptions during automation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automation_interruptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                reason TEXT NOT NULL,
                duration_seconds REAL,
                resolved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES automation_sessions(session_id) ON DELETE CASCADE
            )
        """)

        # Daily collection log table - track daily article collection for idempotence
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_collection_log (
                collection_date DATE PRIMARY KEY,
                articles_collected INTEGER NOT NULL DEFAULT 0,
                collected_at TIMESTAMP NOT NULL,
                category TEXT,
                source_details TEXT
            )
        """)

        # DeadLink operations table - SINGLE SOURCE OF TRUTH for DeadLink operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deadlink_operations (
                id TEXT PRIMARY KEY,  -- UUID
                article_title TEXT NOT NULL,
                revision_id INTEGER,
                operation_id TEXT NOT NULL UNIQUE,  -- UUID de l'opération
                
                -- URL et contexte (immutable)
                url_original TEXT NOT NULL,
                url_normalized TEXT NOT NULL,  -- URL normalisée pour idempotence
                context_type TEXT,
                reference_type TEXT,
                template_name TEXT,
                field_name TEXT,
                
                -- Métadonnées
                idempotency_key TEXT UNIQUE,
                retry_count INTEGER DEFAULT 0,
                
                -- Statut final
                final_status TEXT,  -- Dernier état de la machine à états
                publication_status TEXT,
                
                -- Corrélation
                issue_id TEXT,
                correction_id TEXT,
                publication_job_id TEXT,
                
                -- Timestamps clés
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                detected_at TIMESTAMP,
                published_at TIMESTAMP,
                
                FOREIGN KEY (article_title) REFERENCES articles(title)
            )
        """)

        # DeadLink operation events table - historique des transitions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deadlink_operation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id TEXT NOT NULL,
                event_type TEXT NOT NULL,  -- DETECTED, VALIDATED, REPAIR_CANDIDATE, etc.
                event_data TEXT,  -- JSON avec détails spécifiques à l'événement
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (operation_id) REFERENCES deadlink_operations(operation_id)
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
        
        # Indexes for manual_review_decisions table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_manual_review_status
            ON manual_review_decisions(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_manual_review_article_title
            ON manual_review_decisions(article_title)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_manual_review_url_hash
            ON manual_review_decisions(url_hash)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_manual_review_decision_date
            ON manual_review_decisions(decision_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_manual_review_article_id
            ON manual_review_decisions(article_id)
        """)

        # Indexes for articles_to_analyze table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_to_analyze_status
            ON articles_to_analyze(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_to_analyze_priority
            ON articles_to_analyze(priority)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_to_analyze_added_at
            ON articles_to_analyze(added_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_articles_to_analyze_source
            ON articles_to_analyze(source)
        """)
        
        # Indexes for analysis_jobs table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status
            ON analysis_jobs(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_jobs_article_title
            ON analysis_jobs(article_title)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_jobs_created_at
            ON analysis_jobs(created_at)
        """)
        
        # Indexes for analysis_results table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_results_job_id
            ON analysis_results(job_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_results_article_title
            ON analysis_results(article_title)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_results_status
            ON analysis_results(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_results_analysis_date
            ON analysis_results(analysis_date)
        """)

        # Indexes for deadlink_operations table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deadlink_operations_article
            ON deadlink_operations(article_title)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deadlink_operations_url
            ON deadlink_operations(url_original)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deadlink_operations_normalized_url
            ON deadlink_operations(url_normalized)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deadlink_operations_idempotency
            ON deadlink_operations(idempotency_key)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deadlink_operations_final_status
            ON deadlink_operations(final_status)
        """)

        # Indexes for deadlink_operation_events table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deadlink_operation_events_operation
            ON deadlink_operation_events(operation_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deadlink_operation_events_type
            ON deadlink_operation_events(event_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deadlink_operation_events_timestamp
            ON deadlink_operation_events(timestamp)
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
    
    # Manual review decisions methods
    def add_manual_review_decision(self, item_id: str, article_title: str, url: str, 
                                   status: str, article_id: Optional[int] = None,
                                   reviewer_id: Optional[str] = None, 
                                   decision_reason: Optional[str] = None,
                                   decision_date: Optional[str] = None) -> bool:
        """Add or update a manual review decision.
        
        Args:
            item_id: Unique ID for the decision (article_title_hash(url))
            article_title: Title of the article
            url: URL that was reviewed
            status: Decision status (approved, rejected, pending)
            article_id: Link to articles table if available
            reviewer_id: ID of the reviewer (for future user tracking)
            decision_reason: Reason for the decision (for audit trail)
            
        Returns:
            True if successful, False otherwise
        """
        import hashlib
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO manual_review_decisions 
                (id, article_title, url, status, decision_date, reviewer_id, 
                 decision_reason, article_id, url_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, article_title, url, status, decision_date or datetime.now().isoformat(), 
                  reviewer_id, decision_reason, article_id, url_hash, datetime.now().isoformat()))
            self.conn.commit()
            logger.info(f"Manual review decision saved: {item_id} -> {status}")
            return True
        except Exception as e:
            logger.error(f"Error saving manual review decision: {e}")
            self.conn.rollback()
            return False
    
    def get_manual_review_decision(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get a manual review decision by item ID.
        
        Args:
            item_id: Unique ID for the decision
            
        Returns:
            Decision data or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM manual_review_decisions WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_manual_review_decisions_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all manual review decisions with a specific status.
        
        Args:
            status: Status to filter by (approved, rejected, pending)
            
        Returns:
            List of decisions
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM manual_review_decisions 
            WHERE status = ?
            ORDER BY decision_date DESC
        """, (status,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_manual_review_decisions_by_article(self, article_title: str) -> List[Dict[str, Any]]:
        """Get all manual review decisions for a specific article.
        
        Args:
            article_title: Article title
            
        Returns:
            List of decisions
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM manual_review_decisions 
            WHERE article_title = ?
            ORDER BY decision_date DESC
        """, (article_title,))
        return [dict(row) for row in cursor.fetchall()]
    
    def update_manual_review_decision_status(self, item_id: str, new_status: str, 
                                          reviewer_id: Optional[str] = None,
                                          decision_reason: Optional[str] = None) -> bool:
        """Update the status of an existing manual review decision.
        
        Args:
            item_id: Unique ID for the decision
            new_status: New status (approved, rejected, pending)
            reviewer_id: ID of the reviewer
            decision_reason: Reason for the decision change
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            if reviewer_id or decision_reason:
                cursor.execute("""
                    UPDATE manual_review_decisions 
                    SET status = ?, updated_at = ?, reviewer_id = ?, decision_reason = ?
                    WHERE id = ?
                """, (new_status, datetime.now().isoformat(), reviewer_id, decision_reason, item_id))
            else:
                cursor.execute("""
                    UPDATE manual_review_decisions 
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                """, (new_status, datetime.now().isoformat(), item_id))
            self.conn.commit()
            logger.info(f"Manual review decision updated: {item_id} -> {new_status}")
            return True
        except Exception as e:
            logger.error(f"Error updating manual review decision: {e}")
            self.conn.rollback()
            return False
    
    def delete_manual_review_decision(self, item_id: str) -> bool:
        """Delete a manual review decision.
        
        Args:
            item_id: Unique ID for the decision
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM manual_review_decisions WHERE id = ?", (item_id,))
            self.conn.commit()
            logger.info(f"Manual review decision deleted: {item_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting manual review decision: {e}")
            self.conn.rollback()
            return False
    
    def get_manual_review_statistics(self) -> Dict[str, Any]:
        """Get statistics about manual review decisions.
        
        Returns:
            Dictionary with statistics
        """
        cursor = self.conn.cursor()
        
        # Total decisions
        cursor.execute("SELECT COUNT(*) as count FROM manual_review_decisions")
        total_decisions = cursor.fetchone()['count']
        
        # Decisions by status
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM manual_review_decisions 
            GROUP BY status
        """)
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # Decisions by article
        cursor.execute("""
            SELECT article_title, COUNT(*) as count 
            FROM manual_review_decisions 
            GROUP BY article_title 
            ORDER BY count DESC 
            LIMIT 10
        """)
        top_articles = {row['article_title']: row['count'] for row in cursor.fetchall()}
        
        return {
            'total_decisions': total_decisions,
            'status_counts': status_counts,
            'top_articles': top_articles
        }
    
    def clear_settings(self) -> None:
        """Clear all settings."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM settings")
        self.conn.commit()
    
    # Analysis jobs methods
    def create_analysis_job(self, job_id: str, article_title: str, mode: str, 
                           ai_provider: Optional[str] = None, ai_character_limit: Optional[int] = None,
                           gemini_api_key: Optional[str] = None, gemini_project_id: Optional[str] = None,
                           status: Optional[str] = None, started_at: Optional[str] = None, 
                           completed_at: Optional[str] = None) -> bool:
        """Create a new analysis job in database.
        
        Args:
            job_id: Unique job identifier
            article_title: Title of the article to analyze
            mode: Analysis mode (regex, ai)
            ai_provider: AI provider (gemini, ollama)
            ai_character_limit: Character limit for AI mode
            gemini_api_key: Gemini API key
            gemini_project_id: Gemini project ID
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO analysis_jobs 
                (id, article_title, mode, status, progress, message, created_at, 
                 ai_provider, ai_character_limit, gemini_api_key, gemini_project_id, started_at, completed_at)
                VALUES (?, ?, ?, ?, 0.0, 'Job created', ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, article_title, mode, status or 'pending', datetime.now().isoformat(), 
                  ai_provider, ai_character_limit, gemini_api_key, gemini_project_id, started_at, completed_at))
            self.conn.commit()
            logger.info(f"Analysis job created: {job_id} for article {article_title}")
            return True
        except Exception as e:
            logger.error(f"Error creating analysis job: {e}")
            self.conn.rollback()
            return False
    
    def update_analysis_job(self, job_id: str, **kwargs) -> bool:
        """Update analysis job status and progress.
        
        Args:
            job_id: Job identifier
            **kwargs: Fields to update (status, progress, message, started_at, completed_at, error)
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            # Build dynamic update query
            valid_fields = ['status', 'progress', 'message', 'started_at', 'completed_at', 'error', 'results']
            updates = []
            values = []
            
            for field in valid_fields:
                if field in kwargs and kwargs[field] is not None:
                    updates.append(f"{field} = ?")
                    values.append(kwargs[field])
            
            if not updates:
                return True  # Nothing to update
            
            values.append(job_id)
            
            query = f"UPDATE analysis_jobs SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, values)
            self.conn.commit()
            logger.debug(f"Analysis job updated: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating analysis job {job_id}: {e}")
            self.conn.rollback()
            return False
    
    def get_analysis_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get analysis job by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job data or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM analysis_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_analysis_jobs_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all analysis jobs with a specific status.
        
        Args:
            status: Status to filter by (pending, running, completed, failed, cancelled)
            
        Returns:
            List of jobs
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM analysis_jobs 
            WHERE status = ?
            ORDER BY created_at DESC
        """, (status,))
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_analysis_job(self, job_id: str) -> bool:
        """Delete an analysis job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM analysis_jobs WHERE id = ?", (job_id,))
            self.conn.commit()
            logger.info(f"Analysis job deleted: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting analysis job {job_id}: {e}")
            self.conn.rollback()
            return False
    
    # Analysis results methods
    def create_analysis_result(self, result_id: str, job_id: str, article_title: str,
                               page_id: int, revision_id: int, status: str, mode: str,
                               changes_count: Optional[int] = None, summary: Optional[str] = None,
                               original_content: Optional[str] = None, corrected_content: Optional[str] = None,
                               character_count: Optional[int] = None, total_links: Optional[int] = None,
                               dead_links_count: Optional[int] = None, corrected_links_count: Optional[int] = None,
                               human_verified: bool = False, manual_review_urls: Optional[str] = None,
                               issues_json: Optional[str] = None, analysis_date: Optional[str] = None,
                               normalization_changes_count: Optional[int] = None,
                               normalization_ignored_count: Optional[int] = None,
                               normalization_reports: Optional[str] = None) -> bool:
        """Create or update an analysis result in database.
        
        Uses article_title and revision_id as unique key to prevent duplicates.
        
        Args:
            result_id: Unique result identifier (ignored, kept for compatibility)
            job_id: Associated job ID
            article_title: Article title
            page_id: Wikipedia page ID
            revision_id: Wikipedia revision ID
            status: Result status
            mode: Analysis mode
            changes_count: Number of changes made
            summary: Edit summary
            original_content: Original wikicode
            corrected_content: Corrected wikicode
            character_count: Character count
            total_links: Total number of links
            dead_links_count: Number of dead links found
            corrected_links_count: Number of links corrected
            human_verified: Whether human verified the result
            manual_review_urls: JSON array of URLs requiring manual review
            issues_json: JSON array of detailed issue information
            analysis_date: Analysis timestamp
            normalization_changes_count: Number of normalization changes applied
            normalization_ignored_count: Number of normalization items ignored
            normalization_reports: JSON array of normalization reports
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            # Use article_title + revision_id as unique key to prevent duplicates
            cursor.execute("""
                INSERT OR REPLACE INTO analysis_results 
                (id, job_id, article_title, page_id, revision_id, status, mode, 
                 changes_count, summary, original_content, corrected_content, 
                 character_count, total_links, dead_links_count, corrected_links_count, 
                 human_verified, manual_review_urls, issues_json, analysis_date,
                 normalization_changes_count, normalization_ignored_count, normalization_reports)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"{article_title}_{revision_id}", job_id, article_title, page_id, revision_id, status, mode,
                  changes_count, summary, original_content, corrected_content,
                  character_count, total_links, dead_links_count, corrected_links_count,
                  human_verified, manual_review_urls, issues_json, analysis_date or datetime.now().isoformat(),
                  normalization_changes_count or 0, normalization_ignored_count or 0, normalization_reports))
            self.conn.commit()
            logger.info(f"Analysis result saved for article {article_title} (revision {revision_id})")
            return True
        except Exception as e:
            logger.error(f"Error saving analysis result for {article_title}: {e}")
            self.conn.rollback()
            return False
    
    def get_analysis_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Get analysis result by ID.
        
        Args:
            result_id: Result identifier
            
        Returns:
            Result data or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM analysis_results WHERE id = ?", (result_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def save_user_contribution(self, username: str, page_id: int, revision_id: int, 
                              title: str, namespace: int, timestamp, comment: str = '') -> bool:
        """Save a user contribution to the database.
        
        Args:
            username: Wikipedia username
            page_id: Page ID
            revision_id: Revision ID
            title: Page title
            namespace: Namespace number
            timestamp: Timestamp of the contribution
            comment: Edit summary
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            # Convert timestamp to ISO format if it's a datetime object
            if hasattr(timestamp, 'isoformat'):
                timestamp_str = timestamp.isoformat()
            else:
                timestamp_str = str(timestamp)
            
            cursor.execute("""
                INSERT OR REPLACE INTO user_contributions 
                (username, page_id, revision_id, title, namespace, timestamp, comment, retrieved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, page_id, revision_id, title, namespace, timestamp_str, comment, datetime.now().isoformat()))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving user contribution: {e}")
            self.conn.rollback()
            return False
    
    def get_user_contributions(self, username: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent contributions for a user.
        
        Args:
            username: Wikipedia username
            limit: Maximum number of contributions to return
            
        Returns:
            List of contribution data
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT page_id, revision_id, title, namespace, timestamp, comment, retrieved_at
            FROM user_contributions
            WHERE username = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (username, limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_analysis_results_by_article(self, article_title: str) -> List[Dict[str, Any]]:
        """Get all analysis results for a specific article.
        
        Args:
            article_title: Article title
            
        Returns:
            List of results
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM analysis_results 
            WHERE article_title = ?
            ORDER BY analysis_date DESC
        """, (article_title,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_analysis_results_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all analysis results with a specific status.
        
        Args:
            status: Status to filter by (pending, published, rejected, ignored, error)
            
        Returns:
            List of results
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM analysis_results 
            WHERE status = ?
            ORDER BY analysis_date DESC
        """, (status,))
        return [dict(row) for row in cursor.fetchall()]
    
    def update_analysis_result_status(self, result_id: str, new_status: str) -> bool:
        """Update the status of an analysis result.
        
        Args:
            result_id: Result identifier
            new_status: New status
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE analysis_results 
                SET status = ?
                WHERE id = ?
            """, (new_status, result_id))
            self.conn.commit()
            logger.info(f"Analysis result status updated: {result_id} -> {new_status}")
            return True
        except Exception as e:
            logger.error(f"Error updating analysis result status {result_id}: {e}")
            self.conn.rollback()
            return False
    
    # Automation lock methods - prevents concurrent automation launches
    def acquire_automation_lock(self, session_id: str, locked_by: str = "api", 
                                automation_type: str = "manual") -> bool:
        """
        Attempt to acquire the automation lock.
        
        Args:
            session_id: Unique identifier for this automation session
            locked_by: Who is acquiring the lock (e.g., "api", "user")
            automation_type: Type of automation (e.g., "manual", "scheduled")
            
        Returns:
            True if lock was acquired, False if already locked
        """
        cursor = self.conn.cursor()
        try:
            # Check if lock is already held
            cursor.execute("SELECT locked, locked_at, session_id FROM automation_lock WHERE id = 1")
            row = cursor.fetchone()
            
            if row and row['locked'] == 1:
                # Check if the existing lock is stale (older than 1 hour)
                if row['locked_at']:
                    try:
                        from datetime import datetime, timedelta
                        locked_time = datetime.fromisoformat(row['locked_at'])
                        if datetime.now() - locked_time > timedelta(hours=1):
                            # Lock is stale, clear it
                            logger.warning(f"Clearing stale automation lock from session {row['session_id']}")
                            cursor.execute("""
                                UPDATE automation_lock 
                                SET locked = 0, locked_by = NULL, locked_at = NULL, 
                                    session_id = ?, automation_type = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = 1
                            """, (session_id, automation_type))
                            self.conn.commit()
                        else:
                            # Lock is still valid
                            logger.warning(f"Automation lock already held by session {row['session_id']}")
                            return False
                    except Exception as e:
                        logger.error(f"Error checking lock staleness: {e}")
                        return False
                else:
                    logger.warning("Automation lock already held (no timestamp)")
                    return False
            
            # Acquire the lock
            cursor.execute("""
                UPDATE automation_lock 
                SET locked = 1, locked_by = ?, locked_at = CURRENT_TIMESTAMP, 
                    session_id = ?, automation_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (locked_by, session_id, automation_type))
            self.conn.commit()
            
            logger.info(f"Automation lock acquired by {locked_by} for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error acquiring automation lock: {e}", exc_info=True)
            return False
    
    def release_automation_lock(self, session_id: str) -> bool:
        """
        Release the automation lock.
        
        Args:
            session_id: Session ID that acquired the lock
            
        Returns:
            True if lock was released, False if session didn't hold the lock
        """
        cursor = self.conn.cursor()
        try:
            # Verify this session holds the lock
            cursor.execute("SELECT session_id FROM automation_lock WHERE id = 1")
            row = cursor.fetchone()
            
            if not row or row['session_id'] != session_id:
                logger.warning(f"Session {session_id} does not hold the automation lock")
                return False
            
            # Release the lock
            cursor.execute("""
                UPDATE automation_lock 
                SET locked = 0, locked_by = NULL, locked_at = NULL, 
                    session_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """)
            self.conn.commit()
            
            logger.info(f"Automation lock released by session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error releasing automation lock: {e}", exc_info=True)
            return False
    
    def get_automation_lock_status(self) -> Dict[str, Any]:
        """
        Get the current status of the automation lock.
        
        Returns:
            Dictionary with lock status information
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM automation_lock WHERE id = 1")
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                'locked': False,
                'locked_by': None,
                'locked_at': None,
                'session_id': None,
                'automation_type': None
            }
        except Exception as e:
            logger.error(f"Error getting automation lock status: {e}")
            return {
                'locked': False,
                'error': str(e)
            }

    # ============================================================================
    # Scheduler State Methods - SINGLE SOURCE OF TRUTH
    # ============================================================================

    def get_scheduler_state(self) -> Dict[str, Any]:
        """
        Get the current scheduler state from SQLite.
        
        Returns:
            Dictionary with scheduler state
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM scheduler_state WHERE id = 1")
            row = cursor.fetchone()
            if row:
                state = dict(row)
                # Add queue size and statistics
                state['queue_size'] = self.get_scheduler_queue_size()
                state['statistics'] = self.get_scheduler_statistics()
                return state
            return {
                'is_active': False,
                'is_paused': False,
                'daily_published_count': 0,
                'daily_reset_date': None,
                'queue_size': 0,
                'statistics': {}
            }
        except Exception as e:
            logger.error(f"Error getting scheduler state: {e}")
            return {
                'is_active': False,
                'is_paused': False,
                'daily_published_count': 0,
                'queue_size': 0,
                'statistics': {},
                'error': str(e)
            }

    def update_scheduler_state(self, **kwargs) -> bool:
        """
        Update scheduler state fields.
        
        Args:
            **kwargs: Fields to update (is_active, is_paused, daily_published_count, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            valid_fields = ['is_active', 'is_paused', 'daily_published_count', 
                          'daily_reset_date', 'next_publish_time', 
                          'next_pause_start', 'next_pause_end']
            
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in valid_fields:
                    updates.append(f"{key} = ?")
                    values.append(value)
            
            if updates:
                values.append(1)  # id = 1
                query = f"UPDATE scheduler_state SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(query, values)
                self.conn.commit()
                logger.info(f"Scheduler state updated: {kwargs}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating scheduler state: {e}")
            self.conn.rollback()
            return False

    def set_scheduler_active(self, is_active: bool) -> bool:
        """
        Set scheduler active status.
        
        Args:
            is_active: True to activate, False to stop
            
        Returns:
            True if successful
        """
        return self.update_scheduler_state(is_active=1 if is_active else 0)

    def set_scheduler_paused(self, is_paused: bool) -> bool:
        """
        Set scheduler paused status.
        
        Args:
            is_paused: True to pause, False to resume
            
        Returns:
            True if successful
        """
        return self.update_scheduler_state(is_paused=1 if is_paused else 0)

    def increment_daily_published(self) -> bool:
        """
        Increment daily published counter.
        
        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE scheduler_state 
                SET daily_published_count = daily_published_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """)
            self.conn.commit()
            
            # Also update total in statistics
            cursor.execute("""
                UPDATE scheduler_statistics 
                SET total_published = total_published + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """)
            self.conn.commit()
            
            logger.info("Daily published count incremented")
            return True
        except Exception as e:
            logger.error(f"Error incrementing daily published count: {e}")
            self.conn.rollback()
            return False

    def reset_daily_counters(self) -> bool:
        """
        Reset daily counters if the day has changed.
        
        Returns:
            True if counters were reset, False if not needed
        """
        from datetime import date
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT daily_reset_date FROM scheduler_state WHERE id = 1")
            row = cursor.fetchone()
            
            today = date.today().isoformat()
            if not row or row['daily_reset_date'] != today:
                logger.info(f"Resetting daily counters (new day: {today})")
                cursor.execute("""
                    UPDATE scheduler_state 
                    SET daily_published_count = 0,
                        daily_reset_date = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                """, (today,))
                self.conn.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error resetting daily counters: {e}")
            self.conn.rollback()
            return False

    # ============================================================================
    # Scheduler Queue Methods - SINGLE SOURCE OF TRUTH
    # ============================================================================

    # Valid state transitions for queue state machine
    VALID_QUEUE_TRANSITIONS = {
        'queued': ['processing', 'error'],
        'processing': ['validated', 'publishing', 'stale', 'error'],
        'validated': ['publishing', 'error'],
        'publishing': ['published', 'stale', 'error', 'retry'],  # Added retry for failed publications
        'published': [],  # Terminal state - no transitions allowed
        'stale': ['retry', 'error'],
        'retry': ['queued'],  # retry is a transient state, immediately goes to queued
        'error': []  # Terminal state - no transitions allowed
    }

    def add_to_scheduler_queue(self, article_data: Dict[str, Any]) -> bool:
        """
        Add article to publication queue with status 'queued'.
        
        Args:
            article_data: Dictionary with article information
            
        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO scheduler_queue (
                    article_title, page_id, revision_id, corrected_content, 
                    summary, changes_count, original_content, character_count,
                    total_links, dead_links_count, corrected_links_count, mode, status, retry_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?)
            """, (
                article_data.get('title'),
                article_data.get('page_id'),
                article_data.get('revision_id'),
                article_data.get('corrected_content'),
                article_data.get('summary'),
                article_data.get('changes_count'),
                article_data.get('original_content'),
                article_data.get('character_count'),
                article_data.get('total_links'),
                article_data.get('dead_links_count'),
                article_data.get('corrected_links_count'),
                article_data.get('mode', 'regex'),
                article_data.get('retry_count', 0)  # Preserve retry count for requeued items
            ))
            self.conn.commit()
            logger.info(f"Added article to queue: {article_data.get('title', 'unknown')} (retry_count={article_data.get('retry_count', 0)})")
            return True
        except Exception as e:
            logger.error(f"Error adding article to queue: {e}")
            self.conn.rollback()
            return False

    def pop_from_scheduler_queue(self) -> Optional[Dict[str, Any]]:
        """
        Remove and return the next article from queue (FIFO).
        Transitions status from 'queued' to 'processing' with heartbeat.
        
        Returns:
            Article data or None if queue is empty
        """
        from datetime import datetime
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM scheduler_queue 
                WHERE status = 'queued'
                ORDER BY priority DESC, queued_at ASC
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                article_id = row['id']
                article_data = dict(row)
                
                # Mark as processing with heartbeat
                now = datetime.now().isoformat()
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = 'processing', 
                        processing_started_at = ?,
                        last_heartbeat = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (now, now, article_id))
                self.conn.commit()
                
                logger.info(f"Transitioned article to processing: {article_data.get('article_title', 'unknown')}")
                return article_data
            return None
        except Exception as e:
            logger.error(f"Error popping from queue: {e}")
            self.conn.rollback()
            return None

    def get_scheduler_queue_size(self) -> int:
        """
        Get the current queue size (count of 'queued' items).
        
        Returns:
            Number of queued articles in queue
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) as count FROM scheduler_queue 
                WHERE status = 'queued'
            """)
            row = cursor.fetchone()
            return row['count'] if row else 0
        except Exception as e:
            logger.error(f"Error getting queue size: {e}")
            return 0

    def get_scheduler_queue(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get articles from queue (queued status only).
        
        Args:
            limit: Maximum number of articles to return
            
        Returns:
            List of article data
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM scheduler_queue 
                WHERE status = 'queued'
                ORDER BY priority DESC, queued_at ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting queue: {e}")
            return []

    def mark_queue_item_processed(self, article_id: int, status: str) -> bool:
        """
        Mark a queue item as processed (published, rejected, etc).
        
        Args:
            article_id: Queue item ID
            status: New status (published, rejected, error)
            
        Returns:
            True if successful
        """
        from datetime import datetime
        cursor = self.conn.cursor()
        try:
            now = datetime.now().isoformat()
            if status == 'published':
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = 'published', 
                        published_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (now, article_id))
            else:
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, article_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error marking queue item processed: {e}")
            self.conn.rollback()
            return False

    def transition_queue_item(self, article_id: int, new_status: str) -> bool:
        """
        Transition queue item to new state with timestamp.
        State machine: queued → processing → validated → publishing → published
        Also supports: stale → retry, error
        
        Args:
            article_id: Queue item ID
            new_status: New status (queued, processing, validated, publishing, published, stale, error)
            
        Returns:
            True if successful, False if transition is invalid
        """
        from datetime import datetime
        cursor = self.conn.cursor()
        try:
            # Get current status
            cursor.execute("SELECT status FROM scheduler_queue WHERE id = ?", (article_id,))
            row = cursor.fetchone()
            if not row:
                logger.error(f"Queue item {article_id} not found")
                return False
            
            current_status = row['status']
            
            # Validate transition
            if new_status not in self.VALID_QUEUE_TRANSITIONS.get(current_status, []):
                logger.error(
                    f"Invalid state transition: {current_status} → {new_status} "
                    f"for queue item {article_id}. "
                    f"Valid transitions from {current_status}: {self.VALID_QUEUE_TRANSITIONS.get(current_status, [])}"
                )
                return False
            
            now = datetime.now().isoformat()
            
            if new_status == 'processing':
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = 'processing', 
                        processing_started_at = ?,
                        last_heartbeat = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (now, now, article_id))
            elif new_status == 'validated':
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = 'validated', 
                        validated_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (now, article_id))
            elif new_status == 'publishing':
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = 'publishing', 
                        publishing_started_at = ?,
                        last_heartbeat = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (now, now, article_id))
            elif new_status == 'published':
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = 'published', 
                        published_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (now, article_id))
            elif new_status == 'stale':
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = 'stale',
                        error_message = COALESCE(error_message, 'Processing timeout'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (article_id,))
            elif new_status == 'retry':
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = 'queued',
                        retry_count = retry_count + 1,
                        processing_started_at = NULL,
                        last_heartbeat = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (article_id,))
            else:
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_status, article_id))
            
            self.conn.commit()
            logger.info(f"Transitioned queue item {article_id}: {current_status} → {new_status}")
            return True
        except Exception as e:
            logger.error(f"Error transitioning queue item: {e}")
            self.conn.rollback()
            return False

    def update_queue_heartbeat(self, article_id: int) -> bool:
        """
        Update heartbeat timestamp for a processing item.
        
        Args:
            article_id: Queue item ID
            
        Returns:
            True if successful
        """
        from datetime import datetime
        cursor = self.conn.cursor()
        try:
            now = datetime.now().isoformat()
            cursor.execute("""
                UPDATE scheduler_queue 
                SET last_heartbeat = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('processing', 'publishing')
            """, (now, article_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating heartbeat: {e}")
            self.conn.rollback()
            return False

    def detect_stale_queue_items(self, timeout_seconds: int = 300) -> List[Dict[str, Any]]:
        """
        Detect queue items that have exceeded their heartbeat timeout.
        
        Args:
            timeout_seconds: Timeout in seconds (default 5 minutes)
            
        Returns:
            List of stale queue items
        """
        from datetime import datetime, timedelta
        cursor = self.conn.cursor()
        try:
            timeout_time = datetime.now() - timedelta(seconds=timeout_seconds)
            cursor.execute("""
                SELECT * FROM scheduler_queue 
                WHERE status IN ('processing', 'publishing')
                AND (last_heartbeat IS NULL OR last_heartbeat < ?)
            """, (timeout_time.isoformat(),))
            stale_items = [dict(row) for row in cursor.fetchall()]
            
            if stale_items:
                logger.warning(f"Detected {len(stale_items)} stale queue items")
            
            return stale_items
        except Exception as e:
            logger.error(f"Error detecting stale queue items: {e}")
            return []

    def cleanup_stale_queue_items(self, timeout_seconds: int = 300, max_retries: int = 3) -> int:
        """
        Mark stale queue items and retry or error them based on retry count.
        
        Args:
            timeout_seconds: Timeout in seconds (default 5 minutes)
            max_retries: Maximum retry attempts before marking as error
            
        Returns:
            Number of items processed
        """
        stale_items = self.detect_stale_queue_items(timeout_seconds)
        processed = 0
        
        for item in stale_items:
            retry_count = item.get('retry_count', 0)
            if retry_count < max_retries:
                self.transition_queue_item(item['id'], 'retry')
                logger.info(f"Retrying stale item {item['id']} (attempt {retry_count + 1}/{max_retries})")
            else:
                self.transition_queue_item(item['id'], 'error')
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE scheduler_queue 
                    SET error_message = 'Max retries exceeded after timeout',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (item['id'],))
                self.conn.commit()
                logger.error(f"Marked stale item {item['id']} as error (max retries exceeded)")
            processed += 1
        
        return processed

    def clear_scheduler_queue(self) -> bool:
        """
        Clear all queued items from queue.
        
        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM scheduler_queue WHERE status = 'queued'")
            self.conn.commit()
            logger.info("Scheduler queue cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            self.conn.rollback()
            return False

    # ============================================================================
    # Scheduler Statistics Methods - SINGLE SOURCE OF TRUTH
    # ============================================================================

    def get_scheduler_statistics(self) -> Dict[str, Any]:
        """
        Get scheduler statistics.
        
        Returns:
            Dictionary with statistics
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM scheduler_statistics WHERE id = 1")
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                'total_published': 0,
                'total_analyzed': 0,
                'total_ignored': 0,
                'total_errors': 0,
                'avg_publish_delay': 0.0,
                'avg_processing_time': 0.0
            }
        except Exception as e:
            logger.error(f"Error getting scheduler statistics: {e}")
            return {}

    def update_scheduler_statistics(self, **kwargs) -> bool:
        """
        Update scheduler statistics.
        
        Args:
            **kwargs: Statistics fields to update
            
        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        try:
            valid_fields = ['total_published', 'total_analyzed', 'total_ignored', 
                          'total_errors', 'avg_publish_delay', 'avg_processing_time']
            
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in valid_fields:
                    updates.append(f"{key} = ?")
                    values.append(value)
            
            if updates:
                values.append(1)  # id = 1
                query = f"UPDATE scheduler_statistics SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(query, values)
                self.conn.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating scheduler statistics: {e}")
            self.conn.rollback()
            return False

    # ============================================================================
    # Automation Session Methods - SINGLE SOURCE OF TRUTH
    # ============================================================================

    def create_automation_session(self, session_id: str, **kwargs) -> bool:
        """
        Create a new automation session.
        
        Args:
            session_id: Unique session identifier
            **kwargs: Session fields (category_name, max_articles, mode, etc.)
            
        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO automation_sessions (
                    session_id, status, category_name, max_articles, mode
                ) VALUES (?, 'not_started', ?, ?, ?)
            """, (
                session_id,
                kwargs.get('category_name'),
                kwargs.get('max_articles', 0),
                kwargs.get('mode', 'regex')
            ))
            self.conn.commit()
            logger.info(f"Created automation session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error creating automation session: {e}")
            self.conn.rollback()
            return False

    def get_automation_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get automation session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data or None if not found
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM automation_sessions 
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting automation session: {e}")
            return None

    def get_latest_automation_session(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent automation session.
        
        Returns:
            Session data or None if no sessions exist
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM automation_sessions 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting latest automation session: {e}")
            return None

    def update_automation_session(self, session_id: str, **kwargs) -> bool:
        """
        Update automation session fields.
        
        Args:
            session_id: Session identifier
            **kwargs: Fields to update
            
        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        try:
            valid_fields = ['status', 'current_step', 'current_article_index',
                          'total_articles', 'articles_processed', 'articles_published',
                          'articles_error', 'mode', 'last_saved_at']
            
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in valid_fields:
                    updates.append(f"{key} = ?")
                    values.append(value)
            
            if updates:
                values.append(session_id)
                query = f"UPDATE automation_sessions SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?"
                cursor.execute(query, values)
                self.conn.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating automation session: {e}")
            self.conn.rollback()
            return False

    def start_automation_session(self, session_id: str) -> bool:
        """
        Mark automation session as started.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        from datetime import datetime
        return self.update_automation_session(
            session_id,
            status='running',
            started_at=datetime.now().isoformat()
        )

    def complete_automation_session(self, session_id: str, status: str = 'completed') -> bool:
        """
        Mark automation session as completed.
        
        Args:
            session_id: Session identifier
            status: Final status (completed, failed, interrupted)
            
        Returns:
            True if successful
        """
        from datetime import datetime
        return self.update_automation_session(
            session_id,
            status=status,
            completed_at=datetime.now().isoformat()
        )

    # ============================================================================
    # Automation Article States Methods - SINGLE SOURCE OF TRUTH
    # ============================================================================

    def create_article_state(self, session_id: str, article_title: str, **kwargs) -> bool:
        """
        Create article processing state.
        
        Args:
            session_id: Session identifier
            article_title: Article title
            **kwargs: Article state fields
            
        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO automation_article_states (
                    session_id, article_title, page_id, revision_id, status
                ) VALUES (?, ?, ?, ?, 'pending')
            """, (
                session_id,
                article_title,
                kwargs.get('page_id'),
                kwargs.get('revision_id')
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating article state: {e}")
            self.conn.rollback()
            return False

    def update_article_state(self, session_id: str, article_title: str, **kwargs) -> bool:
        """
        Update article processing state.
        
        Args:
            session_id: Session identifier
            article_title: Article title
            **kwargs: Fields to update
            
        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        try:
            valid_fields = ['status', 'progress', 'current_step', 'error_message',
                          'changes_count', 'summary', 'elapsed_time_seconds']
            
            updates = []
            values = []
            for key, value in kwargs.items():
                if key in valid_fields:
                    updates.append(f"{key} = ?")
                    values.append(value)
            
            if updates:
                values.extend([session_id, article_title])
                query = f"""
                    UPDATE automation_article_states 
                    SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP 
                    WHERE session_id = ? AND article_title = ?
                """
                cursor.execute(query, values)
                self.conn.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating article state: {e}")
            self.conn.rollback()
            return False

    def get_article_states(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all article states for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of article states
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM automation_article_states 
                WHERE session_id = ?
                ORDER BY created_at ASC
            """, (session_id,))
            
            states = []
            for row in cursor.fetchall():
                states.append(dict(row))
            return states
        except Exception as e:
            logger.error(f"Error getting article states: {e}")
            return []

    # ============================================================================
    # Daily Collection Log Methods - Idempotence for daily article collection
    # ============================================================================

    def has_collected_today(self) -> bool:
        """
        Check if articles have already been collected today.
        
        Returns:
            True if collection already done today
        """
        from datetime import datetime, date
        cursor = self.conn.cursor()
        try:
            today = date.today()
            cursor.execute("""
                SELECT COUNT(*) FROM daily_collection_log 
                WHERE collection_date = ?
            """, (today.isoformat(),))
            
            count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            logger.error(f"Error checking daily collection: {e}")
            return False

    def log_daily_collection(self, articles_count: int, category: str = None, source_details: str = None) -> bool:
        """
        Log a daily article collection for idempotence.
        
        Args:
            articles_count: Number of articles collected
            category: Category name (optional)
            source_details: Additional source details (optional)
            
        Returns:
            True if successful
        """
        from datetime import datetime, date
        cursor = self.conn.cursor()
        try:
            today = date.today()
            cursor.execute("""
                INSERT OR REPLACE INTO daily_collection_log 
                (collection_date, articles_collected, collected_at, category, source_details)
                VALUES (?, ?, ?, ?, ?)
            """, (today.isoformat(), articles_count, datetime.now().isoformat(), category, source_details))
            self.conn.commit()
            logger.info(f"Logged daily collection: {articles_count} articles from {category}")
            return True
        except Exception as e:
            logger.error(f"Error logging daily collection: {e}")
            self.conn.rollback()
            return False

    def get_daily_collection_info(self, collection_date: str = None) -> Optional[Dict[str, Any]]:
        """
        Get daily collection information.
        
        Args:
            collection_date: Date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Collection info dict or None
        """
        from datetime import date
        cursor = self.conn.cursor()
        try:
            if collection_date is None:
                collection_date = date.today().isoformat()
                
            cursor.execute("""
                SELECT * FROM daily_collection_log 
                WHERE collection_date = ?
            """, (collection_date,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Error getting daily collection info: {e}")
            return False

    def cleanup_stale_article_states(self, timeout_minutes: int = 30) -> int:
        """
        Clean up stale article states (articles stuck in processing status).
        
        Args:
            timeout_minutes: Timeout in minutes before considering state stale
            
        Returns:
            Number of states cleaned up
        """
        from datetime import datetime, timedelta
        cursor = self.conn.cursor()
        try:
            timeout_time = datetime.now() - timedelta(minutes=timeout_minutes)
            cursor.execute("""
                UPDATE automation_article_states 
                SET status = 'error', error_message = 'Processing timeout',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN ('analyzing', 'retrieving', 'correcting')
                AND updated_at < ?
            """, (timeout_time.isoformat(),))
            self.conn.commit()
            cleaned = cursor.rowcount
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} stale article states")
            return cleaned
        except Exception as e:
            logger.error(f"Error cleaning up stale article states: {e}")
            self.conn.rollback()
            return 0
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT * FROM automation_lock WHERE id = 1")
            row = cursor.fetchone()
            
            if row:
                return {
                    'locked': bool(row['locked']),
                    'locked_by': row['locked_by'],
                    'locked_at': row['locked_at'],
                    'session_id': row['session_id'],
                    'automation_type': row['automation_type'],
                    'updated_at': row['updated_at']
                }
            else:
                return {
                    'locked': False,
                    'locked_by': None,
                    'locked_at': None,
                    'session_id': None,
                    'automation_type': None,
                    'updated_at': None
                }
        except Exception as e:
            logger.error(f"Error getting automation lock status: {e}")
            return {
                'locked': False,
                'error': str(e)
            }
    
    def is_automation_locked(self) -> bool:
        """
        Check if automation lock is currently held.
        
        Returns:
            True if locked, False otherwise
        """
        status = self.get_automation_lock_status()
        return status.get('locked', False)

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
