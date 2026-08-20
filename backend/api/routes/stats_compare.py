"""
Stats Comparison API Route - Compare old vs new statistics.

This endpoint compares statistics from the old system (history.py) with the new system (stats_v2)
to validate the migration and identify any discrepancies.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from backend.stats import StatsService
from backend.stats.schemas import ComparisonResult

# Import old system for comparison
from backend.api.routes.history import get_statistics as get_old_statistics
from wikipedia_maintenance.utils.database import DatabaseManager
from wikipedia_maintenance.utils.published_tracker import PublishedTracker
from wikipedia_maintenance.utils.analyzed_tracker import get_analyzed_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["stats-comparison"])


def get_database():
    """Get database dependency."""
    db_path = "data/wikipedia_maintenance.db"
    return DatabaseManager(db_path)


def get_published_tracker():
    """Get published tracker dependency."""
    return PublishedTracker()


def get_analyzed_tracker_dep():
    """Get analyzed tracker dependency."""
    return get_analyzed_tracker()


@router.get("/compare", response_model=ComparisonResult)
async def compare_statistics(
    database = Depends(get_database),
    published_tracker = Depends(get_published_tracker),
    analyzed_tracker = Depends(get_analyzed_tracker_dep)
):
    """
    Compare old vs new statistics.
    
    This endpoint fetches statistics from both the old system (history.py with DB + trackers)
    and the new system (stats_v2 with centralized StatsService) and compares them.
    
    Useful for validating the migration and identifying discrepancies.
    
    Returns:
        ComparisonResult with old stats, new stats, and differences.
    """
    try:
        # Get old statistics (from history.py)
        old_response = await get_old_statistics(database, published_tracker, analyzed_tracker)
        old_stats = old_response.get("stats", {})
        
        # Get new statistics (from StatsService)
        new_service = StatsService()
        new_response = new_service.get_legacy_format()
        
        # Compare statistics
        differences = {}
        
        # Compare all keys that exist in both
        all_keys = set(old_stats.keys()) | set(new_response.keys())
        
        for key in all_keys:
            old_value = old_stats.get(key)
            new_value = new_response.get(key)
            
            # Skip if both are None or equal
            if old_value == new_value:
                continue
            
            # Record difference
            differences[key] = {
                'old': old_value,
                'new': new_value,
                'diff': new_value - old_value if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)) else None
            }
        
        # Log differences
        if differences:
            logger.warning(f"Statistics differences found: {differences}")
        else:
            logger.info("No differences found between old and new statistics")
        
        return ComparisonResult(
            success=True,
            old_stats=old_stats,
            new_stats=new_response,
            differences=differences
        )
        
    except Exception as e:
        logger.error(f"Error comparing statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compare statistics: {str(e)}")


@router.get("/compare/summary")
async def compare_statistics_summary(
    database = Depends(get_database),
    published_tracker = Depends(get_published_tracker),
    analyzed_tracker = Depends(get_analyzed_tracker_dep)
):
    """
    Get a summary of the comparison between old and new statistics.
    
    Returns a simplified view focusing on whether the systems are consistent.
    
    Returns:
        Dictionary with comparison summary.
    """
    try:
        comparison = await compare_statistics(database, published_tracker, analyzed_tracker)
        
        return {
            'success': True,
            'consistent': len(comparison.differences) == 0,
            'total_keys_compared': len(set(comparison.old_stats.keys()) | set(comparison.new_stats.keys())),
            'differences_count': len(comparison.differences),
            'differences': comparison.differences,
            'timestamp': comparison.timestamp
        }
        
    except Exception as e:
        logger.error(f"Error getting comparison summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get comparison summary: {str(e)}")
