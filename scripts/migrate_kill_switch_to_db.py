"""
Migration script to move kill switch state from JSON file to database.
This script reads the existing .kill_switch_state.json file and migrates it to the database.
"""

import json
import logging
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_kill_switch():
    """Migrate kill switch state from JSON to database."""

    json_file = Path(".kill_switch_state.json")

    if not json_file.exists():
        logger.info("No existing kill_switch_state.json file found. Database will use default state.")
        return

    try:
        # Read JSON file (try different encodings)
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except UnicodeDecodeError:
            # Try UTF-16 if UTF-8 fails
            with open(json_file, 'r', encoding='utf-16') as f:
                json_data = json.load(f)

        logger.info(f"Read kill switch state from JSON: {json_data}")

        # Direct database connection
        db_path = Path("data/wikipedia_maintenance.db")
        if not db_path.exists():
            logger.error(f"Database file not found at: {db_path}")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='kill_switch_state'
        """)
        if not cursor.fetchone():
            logger.error("kill_switch_state table does not exist in database. Please restart the backend first to create the table.")
            conn.close()
            return

        # Check if there's already data in the database
        cursor.execute("SELECT enabled FROM kill_switch_state WHERE id = 1")
        existing = cursor.fetchone()

        if existing:
            logger.info("Kill switch state already exists in database. Updating with JSON values...")
            cursor.execute("""
                UPDATE kill_switch_state
                SET enabled = ?,
                    reason = ?,
                    trigger_source = ?,
                    requested_by = ?,
                    requested_at = ?,
                    last_checked = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (
                1 if json_data.get('enabled', False) else 0,
                json_data.get('reason', ''),
                json_data.get('trigger_source', ''),
                json_data.get('requested_by', ''),
                json_data.get('requested_at'),
                json_data.get('last_checked')
            ))
        else:
            logger.info("Inserting kill switch state into database...")
            cursor.execute("""
                INSERT INTO kill_switch_state (id, enabled, reason, trigger_source, requested_by, requested_at, last_checked)
                VALUES (1, ?, ?, ?, ?, ?, ?)
            """, (
                1 if json_data.get('enabled', False) else 0,
                json_data.get('reason', ''),
                json_data.get('trigger_source', ''),
                json_data.get('requested_by', ''),
                json_data.get('requested_at'),
                json_data.get('last_checked')
            ))

        conn.commit()
        logger.info("✅ Kill switch state migrated to database successfully")

        # Backup the JSON file
        backup_file = json_file.with_suffix('.json.backup')
        json_file.rename(backup_file)
        logger.info(f"JSON file backed up to: {backup_file}")

        # Verify migration
        cursor.execute("SELECT enabled, reason, trigger_source, requested_by FROM kill_switch_state WHERE id = 1")
        row = cursor.fetchone()
        logger.info(f"Verified database state: enabled={bool(row[0])}, reason={row[1]}, source={row[2]}, by={row[3]}")

        conn.close()

    except Exception as e:
        logger.error(f"Failed to migrate kill switch state: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    migrate_kill_switch()
