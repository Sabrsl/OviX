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


@router.get("/published-uncorrected-dead-links")
async def get_published_uncorrected_dead_links(db = Depends(get_database)):
    """
    Get published articles with uncorrected dead links.
    
    Returns articles where:
    - status = 'published'
    - dead_links_count > 0 (at least one dead link)
    - dead_links_count > corrected_links_count (at least 1 uncorrected dead link)
    """
    try:
        if not db:
            logger.warning("Database not available, returning empty list")
            return []

        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT article_title, dead_links_count, corrected_links_count, 
                   analysis_date, issues_json, status
            FROM analysis_results
            WHERE status = 'published' 
              AND dead_links_count > 0
              AND dead_links_count > corrected_links_count
            ORDER BY analysis_date DESC
        """)
        
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            article_title = row[0]
            dead_links_count = row[1]
            corrected_links_count = row[2]
            analysis_date = row[3]
            issues_json = row[4]
            status = row[5]
            
            # Calculate uncorrected count
            uncorrected_count = dead_links_count - corrected_links_count
            
            # Parse issues if available
            issues = []
            if issues_json:
                try:
                    import json
                    issues_data = json.loads(issues_json)
                    issues = issues_data if isinstance(issues_data, list) else []
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse issues_json for {article_title}")
            
            articles.append({
                "article_title": article_title,
                "dead_links_count": dead_links_count,
                "corrected_links_count": corrected_links_count,
                "uncorrected_count": uncorrected_count,
                "analysis_date": analysis_date,
                "status": status,
                "issues_count": len(issues),
                "issues": issues[:10]  # Return first 10 issues for preview
            })
        
        logger.info(f"Returning {len(articles)} published articles with uncorrected dead links")
        return {
            "success": True,
            "count": len(articles),
            "articles": articles
        }
        
    except Exception as e:
        logger.error(f"Failed to get published uncorrected dead links: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "count": 0,
            "articles": []
        }


@router.get("/analyzed-uncorrected-dead-links")
async def get_analyzed_uncorrected_dead_links(db = Depends(get_database)):
    """
    Get all analyzed articles with uncorrected dead links (any status).
    
    Returns articles where:
    - dead_links_count > 0 (at least one dead link)
    - dead_links_count > corrected_links_count (at least 1 uncorrected dead link)
    """
    try:
        if not db:
            logger.warning("Database not available, returning empty list")
            return []

        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT article_title, dead_links_count, corrected_links_count, 
                   analysis_date, issues_json, status
            FROM analysis_results
            WHERE dead_links_count > 0
              AND dead_links_count > corrected_links_count
            ORDER BY analysis_date DESC
        """)
        
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            article_title = row[0]
            dead_links_count = row[1]
            corrected_links_count = row[2]
            analysis_date = row[3]
            issues_json = row[4]
            status = row[5]
            
            # Calculate uncorrected count
            uncorrected_count = dead_links_count - corrected_links_count
            
            # Parse issues if available
            issues = []
            if issues_json:
                try:
                    import json
                    issues_data = json.loads(issues_json)
                    issues = issues_data if isinstance(issues_data, list) else []
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse issues_json for {article_title}")
            
            articles.append({
                "article_title": article_title,
                "dead_links_count": dead_links_count,
                "corrected_links_count": corrected_links_count,
                "uncorrected_count": uncorrected_count,
                "analysis_date": analysis_date,
                "status": status,
                "issues_count": len(issues),
                "issues": issues[:10]  # Return first 10 issues for preview
            })
        
        logger.info(f"Returning {len(articles)} analyzed articles with uncorrected dead links")
        return {
            "success": True,
            "count": len(articles),
            "articles": articles
        }
        
    except Exception as e:
        logger.error(f"Failed to get analyzed uncorrected dead links: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "count": 0,
            "articles": []
        }


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


@router.get("/article/{article_title}/dead-links")
async def get_article_dead_links(article_title: str, db = Depends(get_database)):
    """
    Get detailed dead links information for a specific article.
    
    Returns the article details with dead links information including:
    - Article metadata
    - Dead links count
    - Corrected links count
    - Uncorrected count
    - Analysis date
    - Issues with dead link details
    """
    try:
        if not db:
            logger.warning("Database not available")
            return {
                "success": False,
                "error": "Database not available",
                "article": None
            }

        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT article_title, dead_links_count, corrected_links_count, 
                   analysis_date, issues_json, status
            FROM analysis_results
            WHERE article_title = ?
        """, (article_title,))
        
        row = cursor.fetchone()
        
        if not row:
            return {
                "success": False,
                "error": f"Article '{article_title}' not found",
                "article": None
            }
        
        article_title = row[0]
        dead_links_count = row[1]
        corrected_links_count = row[2]
        analysis_date = row[3]
        issues_json = row[4]
        status = row[5]
        
        # Calculate uncorrected count
        uncorrected_count = dead_links_count - corrected_links_count
        
        # Parse issues to extract dead links
        issues = []
        dead_links = []
        if issues_json:
            try:
                import json
                issues_data = json.loads(issues_json)
                issues = issues_data if isinstance(issues_data, list) else []
                
                # Extract dead links from issues - check multiple possible structures
                for issue in issues:
                    if isinstance(issue, dict):
                        # Check for dead_link type
                        if issue.get('type') == 'dead_link':
                            dead_links.append({
                                "url": issue.get('url', issue.get('link', '')),
                                "status": issue.get('status', 'broken'),
                                "error_message": issue.get('error_message', issue.get('message', '')),
                                "reference": issue.get('reference', issue.get('context', '')),
                                "line_number": issue.get('line_number', issue.get('line', ''))
                            })
                        # Check for url field (general link issues)
                        elif 'url' in issue:
                            dead_links.append({
                                "url": issue.get('url', ''),
                                "status": issue.get('status', 'broken'),
                                "error_message": issue.get('error_message', issue.get('message', '')),
                                "reference": issue.get('reference', issue.get('context', '')),
                                "line_number": issue.get('line_number', issue.get('line', ''))
                            })
                        # Check for link field
                        elif 'link' in issue:
                            dead_links.append({
                                "url": issue.get('link', ''),
                                "status": issue.get('status', 'broken'),
                                "error_message": issue.get('error_message', issue.get('message', '')),
                                "reference": issue.get('reference', issue.get('context', '')),
                                "line_number": issue.get('line_number', issue.get('line', ''))
                            })
                
                logger.info(f"Extracted {len(dead_links)} dead links from {len(issues)} issues for article {article_title}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse issues_json for {article_title}: {e}")
        
        article = {
            "article_title": article_title,
            "dead_links_count": dead_links_count,
            "corrected_links_count": corrected_links_count,
            "uncorrected_count": uncorrected_count,
            "analysis_date": analysis_date,
            "status": status,
            "issues_count": len(issues),
            "issues": issues,
            "dead_links": dead_links
        }
        
        logger.info(f"Returning dead links details for article: {article_title}")
        return {
            "success": True,
            "article": article
        }
        
    except Exception as e:
        logger.error(f"Failed to get article dead links: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "article": None
        }
