"""
OVIX Backend API - Migration Routes

Handles data migration from JSON files to SQLite database.
"""

import logging
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def get_database_path():
    """Get the absolute path to the database."""
    project_root = os.environ.get('PROJECT_ROOT')
    if project_root:
        return str(Path(project_root) / "data" / "wikipedia_maintenance.db")
    return "data/wikipedia_maintenance.db"

router = APIRouter()


class MigrationRequest(BaseModel):
    """Migration request."""
    json_file_path: str
    backup_before: bool = True


class MigrationResponse(BaseModel):
    """Migration response."""
    success: bool
    message: str
    json_records: int = 0
    migrated: int = 0
    skipped: int = 0
    errors: int = 0
    backup_path: str = ""
    verification: Optional[Dict[str, Any]] = None


@router.post("/migrate-manual-review", response_model=MigrationResponse)
async def migrate_manual_review(request: MigrationRequest):
    """
    Migrate manual review decisions from JSON to SQLite database.
    
    This endpoint performs a safe migration with automatic backups.
    """
    try:
        from backend.utils.migration import DataMigration
        from wikipedia_maintenance.utils.database import DatabaseManager
        
        # Initialize database manager
        db_manager = DatabaseManager()
        
        # Initialize migration tool
        migration = DataMigration(request.json_file_path, db_manager)
        
        # Perform migration
        result = migration.migrate_manual_review_decisions()
        
        # Verify migration
        verification = migration.verify_migration()
        result["verification"] = verification
        
        if result["success"]:
            message = f"Migration successful: {result['migrated']} records migrated, {result['skipped']} skipped"
        else:
            message = f"Migration failed with {result['errors']} errors"
        
        return MigrationResponse(
            success=result["success"],
            message=message,
            json_records=result["json_records"],
            migrated=result["migrated"],
            skipped=result["skipped"],
            errors=result["errors"],
            backup_path=result.get("backup_path", ""),
            verification=verification
        )
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@router.post("/rollback-migration")
async def rollback_migration(backup_path: str):
    """
    Rollback migration by restoring from backup.
    
    Args:
        backup_path: Path to the backup file to restore from
    """
    try:
        from backend.utils.migration import DataMigration
        from wikipedia_maintenance.utils.database import DatabaseManager
        
        # Initialize database manager
        db_manager = DatabaseManager()
        
        # Initialize migration tool
        migration = DataMigration("data/manual_review_decisions.json", db_manager)
        
        # Perform rollback
        success = migration.rollback_migration(backup_path)
        
        if success:
            return {"success": True, "message": "Rollback successful"}
        else:
            raise HTTPException(status_code=400, detail="Rollback failed")
            
    except Exception as e:
        logger.error(f"Rollback failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")


@router.get("/migration-status")
async def get_migration_status():
    """
    Get migration status and statistics.
    """
    try:
        from wikipedia_maintenance.utils.database import DatabaseManager
        from pathlib import Path
        
        db_manager = DatabaseManager()
        
        # Get database statistics
        db_stats = db_manager.get_manual_review_statistics()
        
        # Check JSON file
        json_file = Path("data/manual_review_decisions.json")
        json_exists = json_file.exists()
        json_count = 0
        
        if json_exists:
            import json
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            json_count = len(json_data)
        
        return {
            "json_file_exists": json_exists,
            "json_record_count": json_count,
            "db_record_count": db_stats.get("total_decisions", 0),
            "db_status_counts": db_stats.get("status_counts", {}),
            "migration_needed": json_exists and json_count > db_stats.get("total_decisions", 0)
        }
        
    except Exception as e:
        logger.error(f"Failed to get migration status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get migration status: {str(e)}")


@router.post("/cleanup-backups")
async def cleanup_backups(keep_count: int = 5):
    """
    Clean up old backup files.
    
    Args:
        keep_count: Number of recent backups to keep
    """
    try:
        from backend.utils.migration import DataMigration
        from wikipedia_maintenance.utils.database import DatabaseManager
        
        db_manager = DatabaseManager()
        migration = DataMigration("data/manual_review_decisions.json", db_manager)
        
        deleted = migration.cleanup_old_backups(keep_count)
        
        return {"success": True, "message": f"Cleaned up {deleted} old backups", "deleted_count": deleted}
        
    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backup cleanup failed: {str(e)}")