"""
Migration tool for moving from JSON file storage to SQLite database.
Provides backup, migration, and rollback capabilities.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class DataMigration:
    """Handles migration from JSON files to SQLite database."""
    
    def __init__(self, json_file_path: str, db_manager):
        """
        Initialize migration tool.
        
        Args:
            json_file_path: Path to the JSON file to migrate
            db_manager: DatabaseManager instance
        """
        self.json_file_path = Path(json_file_path)
        self.db_manager = db_manager
        self.backup_dir = Path("data/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self) -> str:
        """
        Create a backup of the JSON file.
        
        Returns:
            Path to the backup file
        """
        if not self.json_file_path.exists():
            logger.warning(f"JSON file does not exist: {self.json_file_path}")
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{self.json_file_path.stem}_{timestamp}.json"
        
        shutil.copy2(self.json_file_path, backup_path)
        logger.info(f"Backup created: {backup_path}")
        return str(backup_path)
    
    def create_db_backup(self) -> str:
        """
        Create a backup of the SQLite database.
        
        Returns:
            Path to the backup file
        """
        db_path = self.db_manager.db_path
        if not db_path.exists():
            logger.warning(f"Database file does not exist: {db_path}")
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{db_path.stem}_{timestamp}.db"
        
        shutil.copy2(db_path, backup_path)
        logger.info(f"Database backup created: {backup_path}")
        return str(backup_path)
    
    def load_json_data(self) -> Dict[str, Any]:
        """
        Load data from JSON file.
        
        Returns:
            Dictionary with JSON data
        """
        if not self.json_file_path.exists():
            logger.warning(f"JSON file does not exist: {self.json_file_path}")
            return {}
        
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} records from JSON file")
            return data
        except Exception as e:
            logger.error(f"Error loading JSON file: {e}")
            return {}
    
    def migrate_manual_review_decisions(self) -> Dict[str, Any]:
        """
        Migrate manual review decisions from JSON to SQLite.
        
        Returns:
            Migration result with statistics
        """
        result = {
            "success": False,
            "json_records": 0,
            "migrated": 0,
            "skipped": 0,
            "errors": 0,
            "backup_path": "",
            "rollback_data": {}
        }
        
        try:
            # Create backups
            result["backup_path"] = self.create_backup()
            result["db_backup_path"] = self.create_db_backup()
            
            # Load JSON data
            json_data = self.load_json_data()
            result["json_records"] = len(json_data)
            
            if not json_data:
                logger.info("No data to migrate")
                result["success"] = True
                return result
            
            # Migrate each decision
            for item_id, decision_data in json_data.items():
                try:
                    # Handle both old format (string) and new format (dict)
                    if isinstance(decision_data, str):
                        status = decision_data
                        url = ""
                        article_title = "Unknown"
                    else:
                        status = decision_data.get("status", "pending")
                        url = decision_data.get("url", "")
                        article_title = decision_data.get("article_title", "Unknown")
                    
                    # Normalize status
                    if status == "reject":
                        status = "rejected"
                    
                    # Check if already exists in database
                    existing = self.db_manager.get_manual_review_decision(item_id)
                    if existing:
                        result["skipped"] += 1
                        logger.debug(f"Skipping existing decision: {item_id}")
                        continue
                    
                    # Add to database
                    success = self.db_manager.add_manual_review_decision(
                        item_id=item_id,
                        article_title=article_title,
                        url=url,
                        status=status
                    )
                    
                    if success:
                        result["migrated"] += 1
                        result["rollback_data"][item_id] = decision_data
                    else:
                        result["errors"] += 1
                        
                except Exception as e:
                    logger.error(f"Error migrating decision {item_id}: {e}")
                    result["errors"] += 1
            
            result["success"] = result["errors"] == 0
            logger.info(f"Migration completed: {result['migrated']} migrated, {result['skipped']} skipped, {result['errors']} errors")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            result["success"] = False
        
        return result
    
    def rollback_migration(self, backup_path: str) -> bool:
        """
        Rollback migration by restoring JSON file from backup.
        
        Args:
            backup_path: Path to the backup file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                logger.error(f"Backup file does not exist: {backup_path}")
                return False
            
            # Restore JSON file
            shutil.copy2(backup_file, self.json_file_path)
            logger.info(f"JSON file restored from backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = 5) -> int:
        """
        Clean up old backup files, keeping only the most recent ones.
        
        Args:
            keep_count: Number of recent backups to keep
            
        Returns:
            Number of files deleted
        """
        try:
            # Get all backup files
            backup_files = list(self.backup_dir.glob("*.json")) + list(self.backup_dir.glob("*.db"))
            
            # Sort by modification time (newest first)
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Delete old backups
            deleted = 0
            for old_backup in backup_files[keep_count:]:
                old_backup.unlink()
                deleted += 1
                logger.info(f"Deleted old backup: {old_backup}")
            
            logger.info(f"Cleanup completed: {deleted} old backups deleted")
            return deleted
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
            return 0
    
    def verify_migration(self) -> Dict[str, Any]:
        """
        Verify that migration was successful by comparing counts.
        
        Returns:
            Verification result
        """
        result = {
            "json_count": 0,
            "db_count": 0,
            "verified": False,
            "differences": []
        }
        
        try:
            # Count JSON records
            json_data = self.load_json_data()
            result["json_count"] = len(json_data)
            
            # Count database records
            stats = self.db_manager.get_manual_review_statistics()
            result["db_count"] = stats.get("total_decisions", 0)
            
            # Simple verification (should have same or more in DB due to existing data)
            result["verified"] = result["db_count"] >= result["json_count"]
            
            if result["verified"]:
                logger.info(f"Migration verified: {result['db_count']} DB records >= {result['json_count']} JSON records")
            else:
                logger.warning(f"Migration verification failed: {result['db_count']} DB records < {result['json_count']} JSON records")
                
        except Exception as e:
            logger.error(f"Verification failed: {e}")
        
        return result