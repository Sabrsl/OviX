"""
Migration script: JSON state files → SQLite (Single Source of Truth)

This script migrates data from JSON state files to SQLite database:
- scheduler_state.json → scheduler_state, scheduler_queue, scheduler_statistics tables
- automation_state.json → automation_sessions, automation_article_states tables

After migration, JSON files are renamed with .bak extension for backup.
"""

import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from wikipedia_maintenance.utils.database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_scheduler_state(db_manager: DatabaseManager, json_file: Path):
    """Migrate scheduler state from JSON to SQLite."""
    if not json_file.exists():
        logger.info(f"No scheduler_state.json found, skipping migration")
        return

    logger.info(f"Migrating scheduler state from {json_file}")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Migrate main state
        db_manager.update_scheduler_state(
            is_active=data.get('is_active', False),
            is_paused=data.get('is_paused', False),
            daily_published_count=data.get('daily_published_count', 0),
            daily_reset_date=data.get('daily_reset_date'),
            next_publish_time=data.get('next_publish_time'),
            next_pause_start=data.get('next_pause_start'),
            next_pause_end=data.get('next_pause_end')
        )
        
        # Migrate queue
        queue = data.get('queue', [])
        for article_data in queue:
            db_manager.add_to_scheduler_queue(article_data)
        
        logger.info(f"Migrated {len(queue)} articles from queue")
        
        # Migrate statistics
        stats = data.get('statistics', {})
        db_manager.update_scheduler_statistics(
            total_published=stats.get('total_published', 0),
            total_analyzed=stats.get('total_analyzed', 0),
            total_ignored=stats.get('total_ignored', 0),
            total_errors=stats.get('total_errors', 0),
            avg_publish_delay=stats.get('avg_publish_delay', 0.0),
            avg_processing_time=stats.get('avg_processing_time', 0.0)
        )
        
        logger.info("Scheduler state migration completed")
        
        # Backup JSON file
        backup_file = json_file.with_suffix('.json.bak')
        json_file.rename(backup_file)
        logger.info(f"Backed up JSON file to {backup_file}")
        
    except Exception as e:
        logger.error(f"Error migrating scheduler state: {e}", exc_info=True)
        raise


def migrate_automation_state(db_manager: DatabaseManager, json_file: Path):
    """Migrate automation state from JSON to SQLite."""
    if not json_file.exists():
        logger.info(f"No automation_state.json found, skipping migration")
        return

    logger.info(f"Migrating automation state from {json_file}")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        session_id = data.get('session_id')
        if not session_id:
            logger.warning("No session_id in automation state, skipping")
            return
        
        # Create session
        db_manager.create_automation_session(
            session_id=session_id,
            category_name=data.get('category_name'),
            max_articles=data.get('max_articles', 0),
            mode=data.get('mode', 'regex')
        )
        
        # Update session fields
        db_manager.update_automation_session(
            session_id,
            status=data.get('status', 'not_started'),
            current_step=data.get('current_step'),
            current_article_index=data.get('current_article_index', 0),
            total_articles=data.get('total_articles', 0),
            articles_processed=data.get('articles_processed', 0),
            articles_published=data.get('articles_published', 0),
            articles_error=data.get('articles_error', 0)
        )
        
        # Set timestamps if available
        if data.get('started_at'):
            db_manager.update_automation_session(session_id, started_at=data['started_at'])
        if data.get('completed_at'):
            db_manager.update_automation_session(session_id, completed_at=data['completed_at'])
        
        # Migrate article states
        article_states = data.get('article_states', [])
        for article_state in article_states:
            if isinstance(article_state, dict):
                db_manager.create_article_state(
                    session_id=session_id,
                    article_title=article_state.get('title'),
                    page_id=article_state.get('page_id'),
                    revision_id=article_state.get('revision_id')
                )
                db_manager.update_article_state(
                    session_id,
                    article_state.get('title'),
                    status=article_state.get('status'),
                    progress=article_state.get('progress'),
                    current_step=article_state.get('current_step'),
                    error_message=article_state.get('error_message'),
                    changes_count=article_state.get('changes_count'),
                    elapsed_time_seconds=article_state.get('elapsed_time_seconds')
                )
        
        logger.info(f"Migrated {len(article_states)} article states")
        
        # Migrate interruptions
        interruptions = data.get('interruptions', [])
        for interruption in interruptions:
            if isinstance(interruption, dict):
                cursor = db_manager.conn.cursor()
                cursor.execute("""
                    INSERT INTO automation_interruptions (
                        session_id, timestamp, reason, duration_seconds, resolved_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    interruption.get('timestamp'),
                    interruption.get('reason'),
                    interruption.get('duration_seconds'),
                    interruption.get('resolved_at')
                ))
                db_manager.conn.commit()
        
        logger.info(f"Migrated {len(interruptions)} interruptions")
        logger.info("Automation state migration completed")
        
        # Backup JSON file
        backup_file = json_file.with_suffix('.json.bak')
        json_file.rename(backup_file)
        logger.info(f"Backed up JSON file to {backup_file}")
        
    except Exception as e:
        logger.error(f"Error migrating automation state: {e}", exc_info=True)
        raise


def verify_migration(db_manager: DatabaseManager):
    """Verify that migration was successful."""
    logger.info("Verifying migration...")
    
    # Check scheduler state
    scheduler_state = db_manager.get_scheduler_state()
    logger.info(f"Scheduler state: is_active={scheduler_state.get('is_active')}, queue_size={scheduler_state.get('queue_size')}")
    
    # Check automation sessions
    latest_session = db_manager.get_latest_automation_session()
    if latest_session:
        logger.info(f"Latest automation session: {latest_session.get('session_id')}, status={latest_session.get('status')}")
    else:
        logger.info("No automation sessions found")
    
    logger.info("Migration verification completed")


def main():
    """Main migration function."""
    logger.info("Starting JSON to SQLite migration...")
    
    # Initialize database manager
    db_manager = DatabaseManager()
    
    # Define JSON file paths
    data_dir = project_root / 'data'
    scheduler_json = data_dir / 'scheduler_state.json'
    automation_json = data_dir / 'automation_state.json'
    
    # Migrate scheduler state
    migrate_scheduler_state(db_manager, scheduler_json)
    
    # Migrate automation state
    migrate_automation_state(db_manager, automation_json)
    
    # Verify migration
    verify_migration(db_manager)
    
    logger.info("Migration completed successfully!")
    logger.info("JSON files have been backed up with .bak extension")
    logger.info("SQLite is now the single source of truth for state management")


if __name__ == "__main__":
    main()