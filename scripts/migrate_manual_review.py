"""
Script to migrate manual review decisions from JSON to SQLite database.
Run this script to perform the migration safely with automatic backups.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from backend.utils.migration import DataMigration
from wikipedia_maintenance.utils.database import DatabaseManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Execute the migration."""
    logger.info("Starting manual review decisions migration...")
    
    try:
        # Initialize database manager
        db_manager = DatabaseManager()
        logger.info("Database manager initialized")
        
        # Initialize migration tool
        json_file_path = "data/manual_review_decisions.json"
        migration = DataMigration(json_file_path, db_manager)
        
        # Check if JSON file exists
        if not Path(json_file_path).exists():
            logger.warning(f"JSON file does not exist: {json_file_path}")
            logger.info("No migration needed - starting fresh with SQLite")
            return
        
        # Perform migration
        logger.info("Starting migration process...")
        result = migration.migrate_manual_review_decisions()
        
        # Log results
        logger.info(f"Migration completed:")
        logger.info(f"  - Success: {result['success']}")
        logger.info(f"  - JSON records: {result['json_records']}")
        logger.info(f"  - Migrated: {result['migrated']}")
        logger.info(f"  - Skipped: {result['skipped']}")
        logger.info(f"  - Errors: {result['errors']}")
        logger.info(f"  - Backup: {result.get('backup_path', 'N/A')}")
        
        # Verify migration
        if result['success']:
            logger.info("Verifying migration...")
            verification = migration.verify_migration()
            logger.info(f"Verification results:")
            logger.info(f"  - JSON count: {verification['json_count']}")
            logger.info(f"  - DB count: {verification['db_count']}")
            logger.info(f"  - Verified: {verification['verified']}")
            
            if verification['verified']:
                logger.info("✅ Migration successful and verified!")
                
                # Cleanup old backups (keep last 5)
                deleted = migration.cleanup_old_backups(keep_count=5)
                logger.info(f"Cleaned up {deleted} old backups")
            else:
                logger.warning("⚠️ Migration completed but verification failed")
        else:
            logger.error("❌ Migration failed")
            if result['backup_path']:
                logger.info(f"You can rollback using backup: {result['backup_path']}")
    
    except Exception as e:
        logger.error(f"Migration failed with exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()