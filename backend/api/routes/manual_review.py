"""
OVIX Backend API - Manual Review Routes

Handles links requiring manual review before correction.
"""

import logging
import hashlib
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)

router = APIRouter()

def _deterministic_hash(value: str) -> str:
    """
    Generate a deterministic hash for consistent IDs across sessions.
    Uses SHA-256 and returns the first 16 characters for shorter IDs.
    """
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]

def get_database():
    """Dependency to get database manager."""
    try:
        from backend.api.main import get_database
        return get_database()
    except Exception as e:
        logger.warning(f"Database not available: {e}")
        return None

# ============================================================================
# Models
# ============================================================================

class ManualReviewItem(BaseModel):
    """Manual review item."""
    id: str
    article_title: str
    url: str
    status: str  # 'pending', 'reviewed', 'approved', 'rejected'
    detected_at: str
    context: Optional[str] = None
    suggested_replacement: Optional[str] = None


class ManualReviewAction(BaseModel):
    """Action on a manual review item."""
    action: str  # 'approve' or 'reject'
    article_title: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None


# ============================================================================
# In-memory storage (could be enhanced with database)
# ============================================================================

# Removed JSON-based storage - now using SQLite database for professional data management


# ============================================================================
# Routes
# ============================================================================

@router.get("/manual-review-analyzed-debug")
async def debug_manual_review():
    """
    Debug endpoint to see what's in analyzed_articles.json and why no items are found.
    """
    try:
        tracker_file = Path("data/analyzed_articles.json")
        debug_info = {
            "file_exists": tracker_file.exists(),
            "file_path": str(tracker_file.absolute()),
            "total_records": 0,
            "records_with_manual_review_urls": 0,
            "records_with_unresolved_dead_links": 0,
            "sample_records": []
        }
        
        if not tracker_file.exists():
            return debug_info
        
        with open(tracker_file, 'r', encoding='utf-8') as f:
            analyzed_data = json.load(f)
        
        debug_info["total_records"] = len(analyzed_data)
        
        for record in analyzed_data[:10]:  # Sample first 10 records
            dead_links_count = record.get('dead_links_count')
            if dead_links_count is None:
                dead_links_count = 0
            corrected_links_count = record.get('corrected_links_count')
            if corrected_links_count is None:
                corrected_links_count = 0
            
            sample = {
                "title": record.get('title', 'Unknown'),
                "manual_review_urls": record.get('manual_review_urls', []),
                "dead_links_count": dead_links_count,
                "corrected_links_count": corrected_links_count,
                "has_unresolved": dead_links_count > corrected_links_count,
                "status": record.get('status', 'unknown')
            }
            debug_info["sample_records"].append(sample)
            
            if record.get('manual_review_urls'):
                debug_info["records_with_manual_review_urls"] += 1
            if dead_links_count > corrected_links_count:
                debug_info["records_with_unresolved_dead_links"] += 1
        
        return debug_info
        
    except Exception as e:
        return {"error": str(e), "traceback": str(e.__traceback__)}


@router.get("/manual-review-analyzed", response_model=List[ManualReviewItem])
async def get_manual_review_from_analyzed(db = Depends(get_database)):
    """
    Get manual review items from SQLite database.

    This reads the analysis_results table and returns items that have
    manual_review_urls field populated (URLs requiring manual review).
    """
    try:
        if not db:
            logger.warning("Database not available, returning empty list")
            return []

        import json
        
        # Get all analysis results with manual_review_urls
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT article_title, manual_review_urls, analysis_date
            FROM analysis_results
            WHERE manual_review_urls IS NOT NULL AND manual_review_urls != ''
            ORDER BY analysis_date DESC
        """)
        
        rows = cursor.fetchall()
        
        # Convert database rows to ManualReviewItem format
        manual_review_items = []
        for row in rows:
            article_title = row[0]
            manual_review_urls_json = row[1]
            analysis_date = row[2]
            
            try:
                manual_review_urls = json.loads(manual_review_urls_json) if manual_review_urls_json else []
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse manual_review_urls JSON for {article_title}")
                manual_review_urls = []
            
            # Create a manual review item for each URL
            for url in manual_review_urls:
                # Generate deterministic ID for the item
                item_id = _deterministic_hash(f"{article_title}_{url}")
                
                # Check if there's already a decision for this item
                existing_decision = db.get_manual_review_decision(item_id)
                status = existing_decision["status"] if existing_decision else "pending"
                
                item = ManualReviewItem(
                    id=item_id,
                    article_title=article_title,
                    url=url,
                    status=status,
                    detected_at=analysis_date,
                    context="From analysis result",
                    suggested_replacement=None
                )
                manual_review_items.append(item)

        logger.info(f"Returning {len(manual_review_items)} manual review items from database")
        return manual_review_items

    except Exception as e:
        logger.error(f"Failed to get manual review items: {e}", exc_info=True)
        return []


@router.get("/manual-review", response_model=List[ManualReviewItem])
async def get_manual_review_items(
    status: Optional[str] = None,
    db = Depends(get_database)
):
    """
    Get all manual review items from database, optionally filtered by status.
    """
    try:
        if not db:
            logger.warning("Database not available, returning empty list")
            return []
        
        # Get decisions from database based on status
        if status:
            decisions = db.get_manual_review_decisions_by_status(status)
        else:
            # Get all decisions by fetching each status
            decisions = []
            for status_type in ["approved", "rejected", "pending"]:
                decisions.extend(db.get_manual_review_decisions_by_status(status_type))
        
        # Convert database decisions to ManualReviewItem format
        items = []
        for decision in decisions:
            item = ManualReviewItem(
                id=decision["id"],
                article_title=decision["article_title"],
                url=decision["url"],
                status=decision["status"],
                detected_at=decision["decision_date"],
                context="Decision from database",
                suggested_replacement=None
            )
            items.append(item)
        
        return items
        
    except Exception as e:
        logger.error(f"Failed to get manual review items: {e}", exc_info=True)
        # Return empty list instead of raising exception to allow UI to load
        return []


@router.post("/manual-review/{item_id}/action")
async def perform_manual_review_action(
    item_id: str,
    action: ManualReviewAction,
    db = Depends(get_database)
):
    """
    Perform an action (approve/reject) on a manual review item.
    
    Now uses SQLite database for professional data management.
    """
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Database not available")
        
        # Convert action to proper status format
        status = "approved" if action.action == "approve" else "rejected"
        
        # Extract article title and URL from action data
        article_title = action.article_title or "Unknown"
        url = action.url or ""
        
        logger.info(f"Manual review action received: item_id={item_id}, action={action.action}, article_title={article_title}, url={url}")
        
        # Check if decision already exists
        existing_decision = db.get_manual_review_decision(item_id)
        if existing_decision:
            logger.info(f"Existing decision found: {existing_decision}")
            # Always update to the new decision (user might want to change their mind)
            logger.info(f"Updating existing decision to: {status}")

        # Store decision in database
        success = db.add_manual_review_decision(
            item_id=item_id,
            article_title=article_title,
            url=url,
            status=status
        )

        if success:
            logger.info(f"Manual review decision stored in database: {item_id} -> {status}")
            # Verify the decision was stored
            verify_decision = db.get_manual_review_decision(item_id)
            logger.info(f"Verification of stored decision: {verify_decision}")
            return {"success": True, "message": f"Decision stored for {action.action}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to store decision in database")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform action on item {item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to perform action: {str(e)}")


@router.delete("/manual-review/{item_id}")
async def delete_manual_review_item(item_id: str, db = Depends(get_database)):
    """
    Delete a manual review item from database.
    """
    try:
        success = db.delete_manual_review_decision(item_id)
        
        if success:
            return {"success": True, "message": "Item deleted"}
        else:
            raise HTTPException(status_code=404, detail="Item not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete item {item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete item: {str(e)}")
