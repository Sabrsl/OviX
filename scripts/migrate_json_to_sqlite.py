"""
Migration script: Move data from JSON files to SQLite database.

This script migrates data from analyzed_articles.json and manual_review_decisions.json
to the new SQLite database structure, providing a single source of truth.
"""

import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.utils.database import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_analyzed_articles(db: DatabaseManager, json_file: Path) -> dict:
    """
    Migrate analyzed articles from JSON to SQLite.
    
    Args:
        db: DatabaseManager instance
        json_file: Path to analyzed_articles.json
        
    Returns:
        Migration statistics
    """
    if not json_file.exists():
        logger.warning(f"analyzed_articles.json not found at {json_file}")
        return {"json_exists": False, "migrated": 0, "skipped": 0}
    
    logger.info(f"Starting migration from {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stats = {
        "json_exists": True,
        "total_records": len(data),
        "migrated": 0,
        "skipped": 0,
        "errors": 0
    }
    
    for record in data:
        try:
            # Generate IDs
            article_title = record.get('title', 'Unknown')
            result_id = f"{article_title}_{record.get('revision_id', 0)}"
            job_id = f"migrated_{article_title}_{record.get('revision_id', 0)}"
            
            # Create corresponding job
            db.create_analysis_job(
                job_id=job_id,
                article_title=article_title,
                mode=record.get('mode', 'regex'),
                status='completed',  # Already analyzed
                started_at=record.get('analysis_date'),
                completed_at=record.get('analysis_date')
            )
            
            # Create result
            db.create_analysis_result(
                result_id=result_id,
                job_id=job_id,
                article_title=article_title,
                page_id=record.get('page_id', 0),
                revision_id=record.get('revision_id', 0),
                status=record.get('status', 'pending'),
                mode=record.get('mode', 'regex'),
                changes_count=record.get('changes_count'),
                summary=record.get('summary'),
                original_content=record.get('original_content'),
                corrected_content=record.get('corrected_content'),
                character_count=record.get('character_count'),
                total_links=record.get('total_links'),
                dead_links_count=record.get('dead_links_count'),
                corrected_links_count=record.get('corrected_links_count'),
                human_verified=record.get('human_verified', False),
                analysis_date=record.get('analysis_date')
            )
            
            stats["migrated"] += 1
            logger.debug(f"Migrated: {article_title}")
            
        except Exception as e:
            logger.error(f"Error migrating record {record.get('title')}: {e}")
            stats["errors"] += 1
    
    logger.info(f"Migration completed: {stats['migrated']}/{stats['total_records']} records migrated")
    return stats


def migrate_manual_review_decisions(db: DatabaseManager, json_file: Path) -> dict:
    """
    Migrate manual review decisions from JSON to SQLite.
    
    Args:
        db: DatabaseManager instance
        json_file: Path to manual_review_decisions.json
        
    Returns:
        Migration statistics
    """
    if not json_file.exists():
        logger.warning(f"manual_review_decisions.json not found at {json_file}")
        return {"json_exists": False, "migrated": 0, "skipped": 0}
    
    logger.info(f"Starting migration from {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stats = {
        "json_exists": True,
        "total_records": len(data),
        "migrated": 0,
        "skipped": 0,
        "errors": 0
    }
    
    for item_id, decision_data in data.items():
        try:
            # Handle both old and new format
            if isinstance(decision_data, dict) and 'status' in decision_data:
                # New format
                article_title = decision_data.get('article_title', 'Unknown')
                url = decision_data.get('url', '')
                status = decision_data['status']
                decision_date = decision_data.get('decision_date')
            else:
                # Old format (status only)
                article_title = item_id.split('_')[0] if '_' in item_id else item_id
                url = ''
                status = decision_data
                decision_date = datetime.now().isoformat()
            
            # Migrate to SQLite
            success = db.add_manual_review_decision(
                item_id=item_id,
                article_title=article_title,
                url=url,
                status=status,
                decision_date=decision_date
            )
            
            if success:
                stats["migrated"] += 1
                logger.debug(f"Migrated decision: {item_id}")
            else:
                stats["skipped"] += 1
                
        except Exception as e:
            logger.error(f"Error migrating decision {item_id}: {e}")
            stats["errors"] += 1
    
    logger.info(f"Migration completed: {stats['migrated']}/{stats['total_records']} decisions migrated")
    return stats


def backup_json_files(data_dir: Path) -> dict:
    """
    Create backups of JSON files before migration.
    
    Args:
        data_dir: Data directory path
        
    Returns:
        Backup statistics
    """
    import shutil
    from datetime import datetime
    
    backup_dir = data_dir / "backups" / f"migration_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    stats = {
        "backup_dir": str(backup_dir),
        "files_backed": 0,
        "errors": 0
    }
    
    json_files = [
        "analyzed_articles.json",
        "manual_review_decisions.json"
    ]
    
    for json_file in json_files:
        source = data_dir / json_file
        if source.exists():
            try:
                shutil.copy2(source, backup_dir / json_file)
                stats["files_backed"] += 1
                logger.info(f"Backed up: {json_file}")
            except Exception as e:
                logger.error(f"Error backing up {json_file}: {e}")
                stats["errors"] += 1
    
    return stats


def main():
    """Main migration function."""
    logger.info("=== STARTING MIGRATION JSON → SQLite ===")
    
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    
    # Create backups first
    logger.info("Creating backups of JSON files...")
    backup_stats = backup_json_files(data_dir)
    
    # Initialize database
    logger.info("Initializing database...")
    db = DatabaseManager()
    
    # Migrate analyzed articles
    logger.info("Migrating analyzed articles...")
    analyzed_stats = migrate_analyzed_articles(db, data_dir / "analyzed_articles.json")
    
    # Migrate manual review decisions
    logger.info("Migrating manual review decisions...")
    manual_stats = migrate_manual_review_decisions(db, data_dir / "manual_review_decisions.json")
    
    # Summary
    logger.info("=== MIGRATION SUMMARY ===")
    logger.info(f"Backup dir: {backup_stats['backup_dir']}")
    logger.info(f"Files backed up: {backup_stats['files_backed']}")
    logger.info(f"Backup errors: {backup_stats['errors']}")
    logger.info(f"Analyzed articles: {analyzed_stats['migrated']}/{analyzed_stats['total_records']} migrated")
    logger.info(f"Manual decisions: {manual_stats['migrated']}/{manual_stats['total_records']} migrated")
    
    total_migrated = analyzed_stats['migrated'] + manual_stats['migrated']
    total_errors = analyzed_stats['errors'] + manual_stats['errors']
    
    if total_migrated > 0:
        logger.info(f"✅ Migration successful: {total_migrated} records migrated")
    else:
        logger.warning("⚠️  No records migrated")
    
    if total_errors > 0:
        logger.warning(f"⚠️  {total_errors} errors encountered during migration")
    
    logger.info("=== MIGRATION COMPLETE ===")
    
    # Close database
    db.close()


if __name__ == "__main__":
    main()