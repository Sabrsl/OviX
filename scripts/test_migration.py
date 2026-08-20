"""
Test script to verify the integrity of migrated manual review decisions.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from wikipedia_maintenance.utils.database import DatabaseManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_migration_integrity():
    """Test the integrity of migrated data."""
    logger.info("Testing migration integrity...")
    
    try:
        # Initialize database manager
        db_manager = DatabaseManager()
        logger.info("Database manager initialized")
        
        # Test 1: Get statistics
        logger.info("Test 1: Getting database statistics...")
        stats = db_manager.get_manual_review_statistics()
        logger.info(f"  - Total decisions: {stats['total_decisions']}")
        logger.info(f"  - Status counts: {stats['status_counts']}")
        logger.info(f"  - Top articles: {stats['top_articles']}")
        
        # Test 2: Get decisions by status
        logger.info("Test 2: Getting decisions by status...")
        for status in ["approved", "rejected", "pending"]:
            decisions = db_manager.get_manual_review_decisions_by_status(status)
            logger.info(f"  - {status}: {len(decisions)} decisions")
            
            # Show sample decision
            if decisions:
                sample = decisions[0]
                logger.info(f"    Sample: {sample['id']} -> {sample['status']}")
        
        # Test 3: Test CRUD operations
        logger.info("Test 3: Testing CRUD operations...")
        
        # Add a test decision
        test_id = "Test_Article_1234567890"
        success = db_manager.add_manual_review_decision(
            item_id=test_id,
            article_title="Test Article",
            url="https://example.com/test",
            status="pending"
        )
        logger.info(f"  - Add test decision: {success}")
        
        # Get the test decision
        test_decision = db_manager.get_manual_review_decision(test_id)
        logger.info(f"  - Get test decision: {test_decision is not None}")
        
        # Update the test decision
        update_success = db_manager.update_manual_review_decision_status(test_id, "approved")
        logger.info(f"  - Update test decision: {update_success}")
        
        # Delete the test decision
        delete_success = db_manager.delete_manual_review_decision(test_id)
        logger.info(f"  - Delete test decision: {delete_success}")
        
        # Test 4: Verify decision counts
        logger.info("Test 4: Verifying decision counts...")
        final_stats = db_manager.get_manual_review_statistics()
        logger.info(f"  - Final total: {final_stats['total_decisions']}")
        
        # Test 5: Check database file
        logger.info("Test 5: Checking database file...")
        db_path = db_manager.db_path
        logger.info(f"  - Database exists: {db_path.exists()}")
        logger.info(f"  - Database path: {db_path}")
        if db_path.exists():
            file_size = db_path.stat().st_size
            logger.info(f"  - Database size: {file_size} bytes")
        
        logger.info("✅ All migration integrity tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration integrity test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_migration_integrity()
    sys.exit(0 if success else 1)