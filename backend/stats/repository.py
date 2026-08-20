"""
StatsRepository - Database access layer for statistics.

This repository is responsible ONLY for database access.
All SQL queries for statistics are centralized here.

IMPORTANT: Fallback behavior
- When a table/column doesn't exist, we return 0 or {} as fallback
- This is intentional for backward compatibility
- TODO: Consider distinguishing between 0 (true data) and None (unavailable)
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class StatsRepository:
    """
    Repository for statistics database access.
    
    Single source of truth for all database statistics queries.
    
    NOTE: Fallback behavior returns 0 or {} when tables/columns are missing.
    This is intentional for backward compatibility but may need refinement
    to distinguish between "true zero" and "data unavailable".
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the repository.
        
        Args:
            db_path: Path to the SQLite database. If None, uses default path.
        """
        if db_path is None:
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            db_path = str(project_root / "data" / "wikipedia_maintenance.db")
        
        self.db_path = db_path
        logger.info(f"StatsRepository initialized with database: {db_path}")

    def _get_connection(self):
        """Get database connection."""
        import sqlite3
        return sqlite3.connect(self.db_path)

    def get_article_stats(self) -> Dict[str, int]:
        """
        Get article statistics from database.
        
        Returns:
            Dictionary with article counts by status.
        """
        stats = {
            'total': 0,
            'analyzed': 0,
            'published': 0,
            'pending': 0,
            'rejected': 0,
            'ignored': 0,
            'error': 0,
            'skipped': 0
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total
                cursor.execute("SELECT COUNT(*) FROM analysis_results")
                stats['total'] = cursor.fetchone()[0] or 0
                
                # Analyzed = published + rejected + ignored + error
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE status IN ('published', 'rejected', 'ignored', 'error')"
                )
                stats['analyzed'] = cursor.fetchone()[0] or 0
                
                # By status
                for status in ['published', 'pending', 'rejected', 'ignored', 'error']:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_results WHERE status = ?",
                        (status,)
                    )
                    stats[status] = cursor.fetchone()[0] or 0
                
                # Skipped (if status exists, otherwise 0)
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE status = 'skipped'"
                )
                stats['skipped'] = cursor.fetchone()[0] or 0
                
                logger.info(f"Article stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting article stats: {e}", exc_info=True)
            return stats

    def get_analysis_stats(self) -> Dict[str, Any]:
        """
        Get analysis statistics from database.
        
        Returns:
            Dictionary with analysis statistics.
        """
        stats = {
            'total': 0,
            'pending': 0,
            'running': 0,
            'completed': 0,
            'successful': 0,
            'failed': 0,
            'cancelled': 0,
            'success_rate': 0.0,
            'failure_rate': 0.0,
            'average_duration': 0.0,
            'dead_links_detected': 0,
            'dead_links_corrected': 0,
            'total_links': 0,
            'changes_count': 0,
            'character_count': 0
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total analyses (from analysis_results as fallback if analysis_jobs doesn't exist)
                try:
                    cursor.execute("SELECT COUNT(*) FROM analysis_jobs")
                    stats['total'] = cursor.fetchone()[0] or 0
                except Exception:
                    # Fallback to analysis_results
                    cursor.execute("SELECT COUNT(*) FROM analysis_results")
                    stats['total'] = cursor.fetchone()[0] or 0
                
                # By status (from analysis_results as fallback)
                try:
                    for status in ['pending', 'running', 'completed', 'failed', 'cancelled']:
                        cursor.execute(
                            "SELECT COUNT(*) FROM analysis_jobs WHERE status = ?",
                            (status,)
                        )
                        stats[status] = cursor.fetchone()[0] or 0
                except Exception:
                    # Fallback to analysis_results status mapping
                    status_map = {
                        'pending': 'pending',
                        'running': 'analyzing',
                        'completed': 'published',
                        'failed': 'error',
                        'cancelled': 'rejected'
                    }
                    for new_status, old_status in status_map.items():
                        cursor.execute(
                            "SELECT COUNT(*) FROM analysis_results WHERE status = ?",
                            (old_status,)
                        )
                        stats[new_status] = cursor.fetchone()[0] or 0
                
                # Successful = published + ignored (from analysis_results)
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE status IN ('published', 'ignored')"
                )
                stats['successful'] = cursor.fetchone()[0] or 0
                
                # Calculate rates
                if stats['completed'] > 0:
                    stats['success_rate'] = (stats['successful'] / stats['completed']) * 100
                    stats['failure_rate'] = (stats['failed'] / stats['completed']) * 100
                
                # Average duration (fallback to 0 if no analysis_jobs)
                try:
                    cursor.execute(
                        "SELECT AVG(julianday(completed_at) - julianday(started_at)) * 86400 FROM analysis_jobs WHERE status = 'completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL"
                    )
                    avg_duration = cursor.fetchone()[0]
                    stats['average_duration'] = avg_duration if avg_duration else 0.0
                except Exception:
                    stats['average_duration'] = 0.0
                
                # Dead links statistics (from analysis_results)
                cursor.execute(
                    "SELECT SUM(dead_links_count) FROM analysis_results WHERE dead_links_count IS NOT NULL"
                )
                stats['dead_links_detected'] = cursor.fetchone()[0] or 0
                
                cursor.execute(
                    "SELECT SUM(corrected_links_count) FROM analysis_results WHERE corrected_links_count IS NOT NULL"
                )
                stats['dead_links_corrected'] = cursor.fetchone()[0] or 0
                
                # Total links
                cursor.execute(
                    "SELECT SUM(total_links) FROM analysis_results WHERE total_links IS NOT NULL"
                )
                stats['total_links'] = cursor.fetchone()[0] or 0
                
                # Changes count
                cursor.execute(
                    "SELECT SUM(changes_count) FROM analysis_results WHERE changes_count IS NOT NULL"
                )
                stats['changes_count'] = cursor.fetchone()[0] or 0
                
                # Character count
                cursor.execute(
                    "SELECT SUM(character_count) FROM analysis_results WHERE character_count IS NOT NULL"
                )
                stats['character_count'] = cursor.fetchone()[0] or 0
                
                logger.info(f"Analysis stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting analysis stats: {e}", exc_info=True)
            return stats

    def get_publication_stats(self) -> Dict[str, Any]:
        """
        Get publication statistics from database.
        
        Returns:
            Dictionary with publication statistics including time-based counts.
        """
        stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'pending': 0,
            'cancelled': 0,
            'publication_rate': 0.0,
            'success_rate': 0.0,
            'recent_24h': 0,
            'recent_7d': 0,
            'recent_30d': 0
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total published
                cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE status = 'published'")
                stats['total'] = cursor.fetchone()[0] or 0
                
                # Successful publications (from actions if exists, else use published)
                try:
                    cursor.execute("SELECT COUNT(*) FROM actions WHERE action_type = 'publish'")
                    stats['successful'] = cursor.fetchone()[0] or 0
                except Exception:
                    # Fallback to published count
                    stats['successful'] = stats['total']
                
                # Failed publications (from actions if exists)
                try:
                    cursor.execute("SELECT COUNT(*) FROM actions WHERE action_type = 'publish_failed'")
                    stats['failed'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['failed'] = 0
                
                # Pending publications (published but not yet processed)
                try:
                    cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE status = 'published' AND human_verified = 0")
                    stats['pending'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['pending'] = 0
                
                # Cancelled publications (from actions if exists)
                try:
                    cursor.execute("SELECT COUNT(*) FROM actions WHERE action_type = 'cancel'")
                    stats['cancelled'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['cancelled'] = 0
                
                # Publication success rate
                total_attempts = stats['successful'] + stats['failed']
                if total_attempts > 0:
                    stats['success_rate'] = (stats['successful'] / total_attempts) * 100
                
                # Publication rate (published / analyzed)
                cursor.execute("SELECT COUNT(*) FROM analysis_results")
                total_articles = cursor.fetchone()[0] or 0
                if total_articles > 0:
                    stats['publication_rate'] = (stats['total'] / total_articles) * 100
                
                # Time-based statistics
                now = datetime.now()
                time_24h = now - timedelta(hours=24)
                time_7d = now - timedelta(days=7)
                time_30d = now - timedelta(days=30)
                
                # Recent 24h
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE status = 'published' AND analysis_date >= ?",
                    (time_24h.isoformat(),)
                )
                stats['recent_24h'] = cursor.fetchone()[0] or 0
                
                # Recent 7d
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE status = 'published' AND analysis_date >= ?",
                    (time_7d.isoformat(),)
                )
                stats['recent_7d'] = cursor.fetchone()[0] or 0
                
                # Recent 30d
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE status = 'published' AND analysis_date >= ?",
                    (time_30d.isoformat(),)
                )
                stats['recent_30d'] = cursor.fetchone()[0] or 0
                
                logger.info(f"Publication stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting publication stats: {e}", exc_info=True)
            return stats

    def get_database_stats(self) -> Dict[str, int]:
        """
        Get database content statistics.
        
        Returns:
            Dictionary with database table counts.
        """
        stats = {
            'articles_total': 0,
            'issues_total': 0,
            'actions_total': 0,
            'articles_with_changes': 0
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Articles total
                cursor.execute("SELECT COUNT(*) FROM articles")
                stats['articles_total'] = cursor.fetchone()[0] or 0
                
                # Issues total
                cursor.execute("SELECT COUNT(*) FROM issues")
                stats['issues_total'] = cursor.fetchone()[0] or 0
                
                # Actions total
                cursor.execute("SELECT COUNT(*) FROM actions")
                stats['actions_total'] = cursor.fetchone()[0] or 0
                
                # Articles with changes
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE changes_count > 0"
                )
                stats['articles_with_changes'] = cursor.fetchone()[0] or 0
                
                logger.info(f"Database stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}", exc_info=True)
            return stats

    def get_correction_stats(self) -> Dict[str, int]:
        """
        Get correction/modification statistics.
        
        Returns:
            Dictionary with correction statistics.
        """
        stats = {
            'total_corrections': 0,
            'typos_fixed': 0,
            'formatting_fixed': 0,
            'dead_links_detected': 0,
            'dead_links_corrected': 0,
            'http_links_corrected': 0
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total corrections (sum of changes_count)
                cursor.execute(
                    "SELECT SUM(changes_count) FROM analysis_results WHERE changes_count IS NOT NULL"
                )
                stats['total_corrections'] = cursor.fetchone()[0] or 0
                
                # Typos fixed (from issue_type if exists)
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM issues WHERE issue_type LIKE '%typo%'"
                    )
                    stats['typos_fixed'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['typos_fixed'] = 0
                
                # Formatting fixed (from issue_type if exists)
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM issues WHERE issue_type LIKE '%format%'"
                    )
                    stats['formatting_fixed'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['formatting_fixed'] = 0
                
                # Dead links detected and corrected (from analysis_results)
                cursor.execute(
                    "SELECT SUM(dead_links_count) FROM analysis_results WHERE dead_links_count IS NOT NULL"
                )
                stats['dead_links_detected'] = cursor.fetchone()[0] or 0
                
                cursor.execute(
                    "SELECT SUM(corrected_links_count) FROM analysis_results WHERE corrected_links_count IS NOT NULL"
                )
                stats['dead_links_corrected'] = cursor.fetchone()[0] or 0
                
                # HTTP links corrected to HTTPS (from issues if exists)
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM issues WHERE issue_type LIKE '%http%' AND suggested_text LIKE 'https%'"
                    )
                    stats['http_links_corrected'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['http_links_corrected'] = 0
                
                logger.info(f"Correction stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting correction stats: {e}", exc_info=True)
            return stats

    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue statistics.
        """
        stats = {
            'total': 0,
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0,
            'success_rate': 0.0,
            'average_wait_time': 0.0
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total queue items (if table exists)
                try:
                    cursor.execute("SELECT COUNT(*) FROM articles_to_analyze")
                    stats['total'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['total'] = 0
                
                # By status (if table exists)
                try:
                    for status in ['pending', 'analyzing', 'analyzed', 'error', 'cancelled']:
                        cursor.execute(
                            f"SELECT COUNT(*) FROM articles_to_analyze WHERE status = ?",
                            (status,)
                        )
                        if status == 'analyzing':
                            stats['processing'] = cursor.fetchone()[0] or 0
                        elif status == 'analyzed':
                            stats['completed'] = cursor.fetchone()[0] or 0
                        else:
                            stats[status] = cursor.fetchone()[0] or 0
                except Exception:
                    pass
                
                # Success rate
                total_processed = stats['completed'] + stats['failed']
                if total_processed > 0:
                    stats['success_rate'] = (stats['completed'] / total_processed) * 100
                
                # Average wait time (if table exists)
                try:
                    cursor.execute(
                        "SELECT AVG(julianday(started_at) - julianday(added_at)) * 86400 FROM articles_to_analyze WHERE status IN ('analyzed', 'error') AND started_at IS NOT NULL AND added_at IS NOT NULL"
                    )
                    avg_wait = cursor.fetchone()[0]
                    stats['average_wait_time'] = avg_wait if avg_wait else 0.0
                except Exception:
                    stats['average_wait_time'] = 0.0
                
                logger.info(f"Queue stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}", exc_info=True)
            return stats

    def get_quality_stats(self) -> Dict[str, Any]:
        """
        Get quality statistics.
        
        Returns:
            Dictionary with quality statistics.
        """
        stats = {
            'articles_with_issues': 0,
            'articles_without_issues': 0,
            'issues_by_severity': {},
            'errors_by_type': {},
            'issue_rate': 0.0,
            'dead_link_rate': 0.0,
            'correction_rate': 0.0
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Articles with/without issues
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE changes_count > 0"
                )
                stats['articles_with_issues'] = cursor.fetchone()[0] or 0
                
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE changes_count = 0"
                )
                stats['articles_without_issues'] = cursor.fetchone()[0] or 0
                
                # Issues by severity (if table and column exist)
                try:
                    cursor.execute(
                        "SELECT severity, COUNT(*) FROM issues GROUP BY severity"
                    )
                    for row in cursor.fetchall():
                        stats['issues_by_severity'][row[0]] = row[1]
                except Exception:
                    stats['issues_by_severity'] = {}
                
                # Errors by type (if table and column exist)
                try:
                    cursor.execute(
                        "SELECT issue_type, COUNT(*) FROM issues WHERE severity = 'error' GROUP BY issue_type"
                    )
                    for row in cursor.fetchall():
                        stats['errors_by_type'][row[0]] = row[1]
                except Exception:
                    stats['errors_by_type'] = {}
                
                # Calculate rates
                total_articles = stats['articles_with_issues'] + stats['articles_without_issues']
                if total_articles > 0:
                    stats['issue_rate'] = (stats['articles_with_issues'] / total_articles) * 100
                
                # Dead link rate
                cursor.execute(
                    "SELECT SUM(dead_links_count), SUM(total_links) FROM analysis_results WHERE total_links IS NOT NULL"
                )
                dead_links, total_links = cursor.fetchone()
                if total_links and total_links > 0:
                    stats['dead_link_rate'] = ((dead_links or 0) / total_links) * 100
                
                # Correction rate
                try:
                    cursor.execute(
                        "SELECT SUM(dead_links_corrected), SUM(dead_links_detected) FROM analysis_results WHERE dead_links_detected IS NOT NULL"
                    )
                    corrected, detected = cursor.fetchone()
                    if detected and detected > 0:
                        stats['correction_rate'] = ((corrected or 0) / detected) * 100
                except Exception:
                    stats['correction_rate'] = 0.0
                
                logger.info(f"Quality stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting quality stats: {e}", exc_info=True)
            return stats

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics.
        
        Returns:
            Dictionary with pipeline statistics.
        """
        stats = {
            'runs': 0,
            'success': 0,
            'failed': 0,
            'running': 0,
            'articles_processed': 0,
            'articles_remaining': 0,
            'analyses_completed': 0,
            'publications_completed': 0,
            'pipeline_duration': 0.0,
            'average_processing_time': 0.0
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Pipeline runs (from sessions if exists)
                try:
                    cursor.execute("SELECT COUNT(*) FROM sessions")
                    stats['runs'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['runs'] = 0
                
                # Success (sessions that ended)
                try:
                    cursor.execute("SELECT COUNT(*) FROM sessions WHERE ended_at IS NOT NULL")
                    stats['success'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['success'] = 0
                
                # Failed (sessions that started but didn't end within 1 hour)
                try:
                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    cursor.execute(
                        "SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL AND started_at < ?",
                        (one_hour_ago.isoformat(),)
                    )
                    stats['failed'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['failed'] = 0
                
                # Running (sessions currently active)
                try:
                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    cursor.execute(
                        "SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL AND started_at >= ?",
                        (one_hour_ago.isoformat(),)
                    )
                    stats['running'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['running'] = 0
                
                # Articles processed (sum from sessions if exists)
                try:
                    cursor.execute("SELECT SUM(articles_analyzed) FROM sessions WHERE articles_analyzed IS NOT NULL")
                    stats['articles_processed'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['articles_processed'] = 0
                
                # Articles remaining (pending in queue if exists)
                try:
                    cursor.execute("SELECT COUNT(*) FROM articles_to_analyze WHERE status = 'pending'")
                    stats['articles_remaining'] = cursor.fetchone()[0] or 0
                except Exception:
                    stats['articles_remaining'] = 0
                
                # Analyses completed (from analysis_jobs if exists, else from analysis_results)
                try:
                    cursor.execute("SELECT COUNT(*) FROM analysis_jobs WHERE status = 'completed'")
                    stats['analyses_completed'] = cursor.fetchone()[0] or 0
                except Exception:
                    cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE status IN ('published', 'rejected', 'ignored', 'error')")
                    stats['analyses_completed'] = cursor.fetchone()[0] or 0
                
                # Publications completed
                cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE status = 'published'")
                stats['publications_completed'] = cursor.fetchone()[0] or 0
                
                # Average pipeline duration (from sessions if exists)
                try:
                    cursor.execute(
                        "SELECT AVG(julianday(ended_at) - julianday(started_at)) * 86400 FROM sessions WHERE ended_at IS NOT NULL AND started_at IS NOT NULL"
                    )
                    avg_duration = cursor.fetchone()[0]
                    stats['pipeline_duration'] = avg_duration if avg_duration else 0.0
                except Exception:
                    stats['pipeline_duration'] = 0.0
                
                # Average processing time per article (from analysis_jobs if exists)
                try:
                    cursor.execute(
                        "SELECT AVG(julianday(completed_at) - julianday(started_at)) * 86400 FROM analysis_jobs WHERE status = 'completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL"
                    )
                    avg_processing = cursor.fetchone()[0]
                    stats['average_processing_time'] = avg_processing if avg_processing else 0.0
                except Exception:
                    stats['average_processing_time'] = 0.0
                
                logger.info(f"Pipeline stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting pipeline stats: {e}", exc_info=True)
            return stats

    def get_temporal_stats(self) -> Dict[str, int]:
        """
        Get time-based statistics.
        
        Returns:
            Dictionary with temporal statistics.
        """
        stats = {
            'articles_published_today': 0,
            'analyses_today': 0,
            'corrections_today': 0,
            'errors_today': 0,
            'articles_published_7d': 0,
            'analyses_7d': 0,
            'corrections_7d': 0,
            'errors_7d': 0,
            'articles_published_30d': 0,
            'analyses_30d': 0,
            'corrections_30d': 0,
            'errors_30d': 0
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                now = datetime.now()
                today = now.replace(hour=0, minute=0, second=0, microsecond=0)
                time_7d = now - timedelta(days=7)
                time_30d = now - timedelta(days=30)
                
                # Today's statistics
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE status = 'published' AND analysis_date >= ?",
                    (today.isoformat(),)
                )
                stats['articles_published_today'] = cursor.fetchone()[0] or 0
                
                # Analyses today (from analysis_jobs if exists, else from analysis_results)
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_jobs WHERE created_at >= ?",
                        (today.isoformat(),)
                    )
                    stats['analyses_today'] = cursor.fetchone()[0] or 0
                except Exception:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_results WHERE analysis_date >= ?",
                        (today.isoformat(),)
                    )
                    stats['analyses_today'] = cursor.fetchone()[0] or 0
                
                cursor.execute(
                    "SELECT SUM(changes_count) FROM analysis_results WHERE analysis_date >= ? AND changes_count IS NOT NULL",
                    (today.isoformat(),)
                )
                stats['corrections_today'] = cursor.fetchone()[0] or 0
                
                # Errors today (from analysis_jobs if exists)
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_jobs WHERE status = 'failed' AND created_at >= ?",
                        (today.isoformat(),)
                    )
                    stats['errors_today'] = cursor.fetchone()[0] or 0
                except Exception:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_results WHERE status = 'error' AND analysis_date >= ?",
                        (today.isoformat(),)
                    )
                    stats['errors_today'] = cursor.fetchone()[0] or 0
                
                # 7 days statistics
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE status = 'published' AND analysis_date >= ?",
                    (time_7d.isoformat(),)
                )
                stats['articles_published_7d'] = cursor.fetchone()[0] or 0
                
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_jobs WHERE created_at >= ?",
                        (time_7d.isoformat(),)
                    )
                    stats['analyses_7d'] = cursor.fetchone()[0] or 0
                except Exception:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_results WHERE analysis_date >= ?",
                        (time_7d.isoformat(),)
                    )
                    stats['analyses_7d'] = cursor.fetchone()[0] or 0
                
                cursor.execute(
                    "SELECT SUM(changes_count) FROM analysis_results WHERE analysis_date >= ? AND changes_count IS NOT NULL",
                    (time_7d.isoformat(),)
                )
                stats['corrections_7d'] = cursor.fetchone()[0] or 0
                
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_jobs WHERE status = 'failed' AND created_at >= ?",
                        (time_7d.isoformat(),)
                    )
                    stats['errors_7d'] = cursor.fetchone()[0] or 0
                except Exception:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_results WHERE status = 'error' AND analysis_date >= ?",
                        (time_7d.isoformat(),)
                    )
                    stats['errors_7d'] = cursor.fetchone()[0] or 0
                
                # 30 days statistics
                cursor.execute(
                    "SELECT COUNT(*) FROM analysis_results WHERE status = 'published' AND analysis_date >= ?",
                    (time_30d.isoformat(),)
                )
                stats['articles_published_30d'] = cursor.fetchone()[0] or 0
                
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_jobs WHERE created_at >= ?",
                        (time_30d.isoformat(),)
                    )
                    stats['analyses_30d'] = cursor.fetchone()[0] or 0
                except Exception:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_results WHERE analysis_date >= ?",
                        (time_30d.isoformat(),)
                    )
                    stats['analyses_30d'] = cursor.fetchone()[0] or 0
                
                cursor.execute(
                    "SELECT SUM(changes_count) FROM analysis_results WHERE analysis_date >= ? AND changes_count IS NOT NULL",
                    (time_30d.isoformat(),)
                )
                stats['corrections_30d'] = cursor.fetchone()[0] or 0
                
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_jobs WHERE status = 'failed' AND created_at >= ?",
                        (time_30d.isoformat(),)
                    )
                    stats['errors_30d'] = cursor.fetchone()[0] or 0
                except Exception:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_results WHERE status = 'error' AND analysis_date >= ?",
                        (time_30d.isoformat(),)
                    )
                    stats['errors_30d'] = cursor.fetchone()[0] or 0
                
                logger.info(f"Temporal stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting temporal stats: {e}", exc_info=True)
            return stats

    def get_error_stats(self) -> Dict[str, Any]:
        """
        Get error statistics.
        
        Returns:
            Dictionary with error statistics.
        """
        stats = {
            'total': 0,
            'today': 0,
            'by_type': {},
            'by_module': {},
            'by_stage': {}
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total errors (failed jobs if table exists)
                try:
                    cursor.execute("SELECT COUNT(*) FROM analysis_jobs WHERE status = 'failed'")
                    stats['total'] = cursor.fetchone()[0] or 0
                except Exception:
                    # Fallback to analysis_results with error status
                    cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE status = 'error'")
                    stats['total'] = cursor.fetchone()[0] or 0
                
                # Errors today
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_jobs WHERE status = 'failed' AND created_at >= ?",
                        (today.isoformat(),)
                    )
                    stats['today'] = cursor.fetchone()[0] or 0
                except Exception:
                    cursor.execute(
                        "SELECT COUNT(*) FROM analysis_results WHERE status = 'error' AND analysis_date >= ?",
                        (today.isoformat(),)
                    )
                    stats['today'] = cursor.fetchone()[0] or 0
                
                # Errors by type (from error field if table exists)
                try:
                    cursor.execute(
                        "SELECT error, COUNT(*) FROM analysis_jobs WHERE status = 'failed' AND error IS NOT NULL GROUP BY error"
                    )
                    for row in cursor.fetchall():
                        stats['by_type'][row[0]] = row[1]
                except Exception:
                    stats['by_type'] = {}
                
                # Errors by module (deduced from mode if table exists)
                try:
                    cursor.execute(
                        "SELECT mode, COUNT(*) FROM analysis_jobs WHERE status = 'failed' GROUP BY mode"
                    )
                    for row in cursor.fetchall():
                        stats['by_module'][row[0]] = row[1]
                except Exception:
                    stats['by_module'] = {}
                
                # Errors by stage (deduced from job context if table exists)
                try:
                    cursor.execute(
                        "SELECT status, COUNT(*) FROM analysis_jobs WHERE status = 'failed' GROUP BY status"
                    )
                    for row in cursor.fetchall():
                        stats['by_stage'][row[0]] = row[1]
                except Exception:
                    stats['by_stage'] = {}
                
                logger.info(f"Error stats retrieved: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting error stats: {e}", exc_info=True)
            return stats

    def get_issues_by_severity(self) -> Dict[str, int]:
        """
        Get issues grouped by severity.
        
        Returns:
            Dictionary mapping severity to count.
        """
        severity_stats = {}
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT severity, COUNT(*) FROM issues GROUP BY severity"
                )
                for row in cursor.fetchall():
                    severity_stats[row[0]] = row[1]
                
                logger.info(f"Issues by severity retrieved: {severity_stats}")
                return severity_stats
                
        except Exception as e:
            logger.error(f"Error getting issues by severity: {e}", exc_info=True)
            return severity_stats

    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get all statistics in a single call.
        
        Returns:
            Dictionary with all statistics covering all 8 families.
        """
        return {
            'articles': self.get_article_stats(),
            'analysis': self.get_analysis_stats(),
            'publication': self.get_publication_stats(),
            'corrections': self.get_correction_stats(),
            'queue': self.get_queue_stats(),
            'quality': self.get_quality_stats(),
            'pipeline': self.get_pipeline_stats(),
            'temporal': self.get_temporal_stats(),
            'errors': self.get_error_stats(),
            'database': self.get_database_stats(),
            'issues_by_severity': self.get_issues_by_severity()
        }
