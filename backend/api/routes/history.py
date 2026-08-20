"""
OVIX Backend API - History Routes

Handles historical data using existing trackers.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import AnalysisStatus for filtering
from wikipedia_maintenance.utils.analyzed_tracker import AnalysisStatus

router = APIRouter()

# ============================================================================
# Models
# ============================================================================

class HistoryItem(BaseModel):
    """History item."""
    title: str
    published_at: str
    category: str
    mode: str
    summary: str
    revision_id: Optional[int] = None
    changes_count: Optional[int] = None
    total_links: Optional[int] = None
    dead_links_count: Optional[int] = None
    corrected_links_count: Optional[int] = None
    character_count: Optional[int] = None
    job_id: Optional[str] = None
    page_id: Optional[int] = None


class HistoryResponse(BaseModel):
    """History response."""
    success: bool
    items: List[HistoryItem]
    count: int


class AnalyzedItem(BaseModel):
    """Analyzed item."""
    title: str
    page_id: int
    revision_id: Optional[int] = None
    analysis_date: str
    status: str
    mode: str
    changes_count: Optional[int] = None
    summary: Optional[str] = None
    job_id: Optional[str] = None
    character_count: Optional[int] = None
    total_links: Optional[int] = None
    dead_links_count: Optional[int] = None
    corrected_links_count: Optional[int] = None
    human_verified: Optional[bool] = None


class AnalyzedResponse(BaseModel):
    """Analyzed history response."""
    success: bool
    items: List[AnalyzedItem]
    count: int


class StatisticsResponse(BaseModel):
    """Statistics response."""
    success: bool
    stats: dict


# ============================================================================
# Dependencies
# ============================================================================

def get_published_tracker():
    """Get published tracker."""
    try:
        from backend.api.main import get_published_tracker
        return get_published_tracker()
    except Exception as e:
        logger.warning(f"Published tracker not available: {e}")
        return None


def get_analyzed_tracker():
    """Get analyzed tracker."""
    try:
        from backend.api.main import get_analyzed_tracker
        return get_analyzed_tracker()
    except Exception as e:
        logger.warning(f"Analyzed tracker not available: {e}")
        return None


def get_database():
    """Get database manager."""
    try:
        from backend.api.main import get_database
        return get_database()
    except Exception as e:
        logger.warning(f"Database not available: {e}")
        return None


# ============================================================================
# Routes
# ============================================================================

# IMPORTANT: Specific routes must be defined BEFORE generic routes with path parameters
# Otherwise FastAPI will match "statistics" as a title in the /{title:path} route

@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """
    Get overall statistics (LEGACY - DEPRECATED).

    ⚠️ This endpoint is DEPRECATED. Use /api/stats/v2/system instead.
    
    This endpoint now uses the centralized StatsService as the single source of truth.
    The fallback to JSON trackers has been removed to ensure consistency.
    """
    try:
        logger.info("Fetching statistics from centralized StatsService")
        
        # Import StatsService
        from backend.stats import StatsService
        
        # Use centralized StatsService
        service = StatsService()
        legacy_stats = service.get_legacy_format()
        
        logger.info(f"Statistics successfully retrieved from StatsService")
        
        return StatisticsResponse(
            success=True,
            stats=legacy_stats
        )

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get("/published", response_model=HistoryResponse)
async def get_published_history(
    limit: int = 100,
    offset: int = 0,
    published_tracker = Depends(get_published_tracker),
    database = Depends(get_database)
):
    """
    Get published articles history.

    Uses database as primary source for complete data including statistics.
    Falls back to PublishedTracker if database is not available.
    """
    try:
        # Try database first for complete data including statistics
        if database:
            try:
                cursor = database.conn.cursor()
                cursor.execute("""
                    SELECT article_title, revision_id, analysis_date, summary, changes_count,
                           total_links, dead_links_count, corrected_links_count,
                           character_count, job_id, page_id, mode
                    FROM analysis_results
                    WHERE status = 'published'
                    ORDER BY analysis_date DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))

                history_items = []
                for row in cursor.fetchall():
                    article_title = row[0]
                    db_summary = row[3] or ""
                    
                    # Use published tracker summary if available (real publication comment)
                    final_summary = db_summary
                    if published_tracker and article_title in published_tracker.published_articles:
                        tracker_summary = published_tracker.published_articles[article_title].get('summary', '')
                        if tracker_summary:
                            final_summary = tracker_summary
                    
                    history_items.append(HistoryItem(
                        title=row[0],
                        published_at=row[2],
                        category="unknown",
                        mode=row[11] or "unknown",
                        summary=final_summary,
                        revision_id=row[1],
                        changes_count=row[4],
                        total_links=row[5],
                        dead_links_count=row[6],
                        corrected_links_count=row[7],
                        character_count=row[8],
                        job_id=row[9],
                        page_id=row[10]
                    ))
                
                return HistoryResponse(
                    success=True,
                    items=history_items,
                    count=len(history_items)
                )
            except Exception as e:
                logger.warning(f"Failed to get published history from database: {e}")
        
        # Fallback to published_tracker if database is not available
        if published_tracker:
            # Get all published articles
            all_published = published_tracker.published_articles

            # Convert to list and sort by date
            items_list = [
                {
                    "title": title,
                    "data": data
                }
                for title, data in all_published.items()
            ]
            items_list.sort(key=lambda x: x["data"]["published_at"], reverse=True)

            # Apply pagination
            paginated_items = items_list[offset:offset + limit]

            # Convert to response format
            history_items = []
            for item in paginated_items:
                history_items.append(HistoryItem(
                    title=item["title"],
                    published_at=item["data"]["published_at"],
                    category=item["data"].get("category", "unknown"),
                    mode=item["data"].get("mode", "unknown"),
                    summary=item["data"].get("summary", ""),
                    revision_id=item["data"].get("revision_id")
                ))

            return HistoryResponse(
                success=True,
                items=history_items,
                count=len(history_items)
            )
        
        return HistoryResponse(success=True, items=[], count=0)

    except Exception as e:
        logger.error(f"Failed to get published history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/analyzed", response_model=AnalyzedResponse)
async def get_analyzed_history(
    limit: int = 100,
    offset: int = 0,
    status_filter: Optional[str] = None,
    mode_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    date_filter: Optional[str] = None,
    database = Depends(get_database),
    analyzed_tracker = Depends(get_analyzed_tracker)
):
    """
    Get analyzed articles history.

    Uses SQLite database as primary source, falls back to AnalyzedTracker.
    Supports filtering by status, mode, search, and date.
    """
    try:
        analyzed_items = []

        # Try database first
        if database:
            try:
                cursor = database.conn.cursor()
                
                # Build query with filters
                query = "SELECT * FROM analysis_results WHERE 1=1"
                params = []
                
                if status_filter and status_filter != "all":
                    query += " AND status = ?"
                    params.append(status_filter)
                
                if mode_filter and mode_filter != "all":
                    if mode_filter == "ia":
                        query += " AND mode = 'IA'"
                    elif mode_filter == "regex":
                        query += " AND mode = 'regex'"
                
                if search_query:
                    query += " AND article_title LIKE ?"
                    params.append(f"%{search_query}%")
                
                # Date filter
                if date_filter and date_filter != "all":
                    from datetime import datetime, timedelta
                    now = datetime.now()
                    date_cutoff = None
                    if date_filter == "24h":
                        date_cutoff = now - timedelta(days=1)
                    elif date_filter == "7d":
                        date_cutoff = now - timedelta(days=7)
                    elif date_filter == "30d":
                        date_cutoff = now - timedelta(days=30)
                    
                    if date_cutoff:
                        query += " AND analysis_date >= ?"
                        params.append(date_cutoff.isoformat())
                
                query += " ORDER BY analysis_date DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                logger.info(f"Database query returned {len(rows)} rows")
                
                for row in rows:
                    row_dict = dict(row)
                    # Handle encoding issues for special characters
                    title = row_dict.get('article_title', '')
                    if isinstance(title, str):
                        title = title.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
                    
                    summary = row_dict.get('summary')
                    if summary and isinstance(summary, str):
                        summary = summary.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
                    
                    mode_value = row_dict.get('mode', 'unknown')
                    logger.info(f"Article '{title}': mode from DB = '{mode_value}'")
                    
                    analyzed_items.append(AnalyzedItem(
                        title=title,
                        page_id=row_dict.get('page_id', 0),
                        revision_id=row_dict.get('revision_id', 0),
                        analysis_date=row_dict.get('analysis_date', ''),
                        status=row_dict.get('status', 'unknown'),
                        mode=mode_value,
                        changes_count=row_dict.get('changes_count'),
                        summary=summary,
                        job_id=row_dict.get('job_id'),
                        character_count=row_dict.get('character_count', 0),
                        total_links=row_dict.get('total_links'),
                        dead_links_count=row_dict.get('dead_links_count'),
                        corrected_links_count=row_dict.get('corrected_links_count'),
                        human_verified=row_dict.get('human_verified')
                    ))
                
                logger.info(f"Returning {len(analyzed_items)} items from database")
                return AnalyzedResponse(
                    success=True,
                    items=analyzed_items,
                    count=len(analyzed_items)
                )
                
            except Exception as e:
                logger.warning(f"Failed to get analyzed history from database: {e}, falling back to tracker")
        
        # Fallback to tracker
        if not analyzed_tracker:
            raise HTTPException(status_code=500, detail="Analyzed tracker not initialized")

        # Get all analyzed articles
        all_records = analyzed_tracker._records

        # Convert to list and apply filters
        records_list = list(all_records.values())
        
        # Status filter
        if status_filter and status_filter != "all":
            status_map = {
                "published": "published",
                "rejected": "rejected",
                "ignored": "ignored",
                "pending": "pending",
                "analyzing": "analyzing",
                "error": "error"
            }
            if status_filter in status_map:
                records_list = [r for r in records_list if r.status == status_map[status_filter]]
        
        # Mode filter
        if mode_filter and mode_filter != "all":
            if mode_filter == "ia":
                records_list = [r for r in records_list if r.mode == "IA"]
            elif mode_filter == "regex":
                records_list = [r for r in records_list if r.mode == "regex"]
        
        # Search filter
        if search_query:
            records_list = [r for r in records_list if search_query.lower() in r.title.lower()]
        
        # Date filter
        if date_filter and date_filter != "all":
            from datetime import datetime, timedelta
            now = datetime.now()
            date_cutoff = None
            if date_filter == "24h":
                date_cutoff = now - timedelta(days=1)
            elif date_filter == "7d":
                date_cutoff = now - timedelta(days=7)
            elif date_filter == "30d":
                date_cutoff = now - timedelta(days=30)
            
            if date_cutoff:
                records_list = [r for r in records_list if r.analysis_date and datetime.fromisoformat(r.analysis_date) >= date_cutoff]
        
        # Sort by date
        records_list.sort(key=lambda x: x.analysis_date, reverse=True)

        # Apply pagination
        paginated_records = records_list[offset:offset + limit]

        # Convert to response format
        for record in paginated_records:
            analyzed_items.append(AnalyzedItem(
                title=record.title,
                page_id=record.page_id,
                revision_id=record.revision_id,
                analysis_date=record.analysis_date,
                status=record.status,
                mode=record.mode,
                changes_count=record.changes_count,
                summary=record.summary,
                job_id=getattr(record, 'job_id', None),
                character_count=getattr(record, 'character_count', 0),
                total_links=getattr(record, 'total_links', None),
                dead_links_count=getattr(record, 'dead_links_count', None),
                corrected_links_count=getattr(record, 'corrected_links_count', None),
                human_verified=getattr(record, 'human_verified', None)
            ))

        logger.info(f"Returning {len(analyzed_items)} items from tracker")
        return AnalyzedResponse(
            success=True,
            items=analyzed_items,
            count=len(analyzed_items)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analyzed history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get analyzed history: {str(e)}")


@router.get("/{title:path}")
async def get_article_history(
    title: str,
    database = Depends(get_database),
    analyzed_tracker = Depends(get_analyzed_tracker)
):
    """
    Get history for a specific article.

    Retrieves the analysis and publication history for a specific article
    from the database or AnalyzedTracker.
    """
    try:
        # Try to get article from database first
        article = database.get_article(title)

        if not article:
            # If not in database, try AnalyzedTracker
            if analyzed_tracker:
                record = analyzed_tracker.get_record(title)
                if record:
                    # Create a mock article object from tracker record
                    article = {
                        "id": None,
                        "title": record.title,
                        "page_id": record.page_id,
                        "revision_id": record.revision_id,
                        "retrieved_at": record.analysis_date,
                        "status": record.status,
                        "created_at": record.analysis_date
                    }
                else:
                    raise HTTPException(status_code=404, detail=f"Article '{title}' not found in history")
            else:
                raise HTTPException(status_code=404, detail=f"Article '{title}' not found in history")

        # Get issues for this article (only if in database)
        issues = []
        actions = []
        if article.get("id"):
            cursor = database.conn.cursor()
            try:
                cursor.execute("""
                    SELECT issue_type, description, severity, created_at
                    FROM issues
                    WHERE article_id = ?
                    ORDER BY created_at DESC
                """, (article["id"],))

                for row in cursor.fetchall():
                    issues.append({
                        "issue_type": row[0],
                        "description": row[1],
                        "severity": row[2],
                        "created_at": row[3]
                    })

                # Get actions for this article
                cursor.execute("""
                    SELECT action_type, edit_summary, revision_id, performed_at
                    FROM actions
                    WHERE article_id = ?
                    ORDER BY performed_at DESC
                """, (article["id"],))

                for row in cursor.fetchall():
                    actions.append({
                        "action_type": row[0],
                        "edit_summary": row[1],
                        "revision_id": row[2],
                        "performed_at": row[3]
                    })
            except Exception as e:
                logger.warning(f"Failed to get issues/actions from database: {e}")

        # Get character count and corrected content from analyzed tracker if available
        character_count = None
        corrected_content = None
        if analyzed_tracker:
            record = analyzed_tracker.get_record(title)
            if record:
                character_count = getattr(record, 'character_count', None)
                corrected_content = getattr(record, 'corrected_content', None)

        return {
            "success": True,
            "history": {
                "article": article,
                "issues": issues,
                "actions": actions,
                "character_count": character_count,
                "corrected_content": corrected_content
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get article history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get article history: {str(e)}")
