"""
OVIX Backend API - Articles Routes

Handles article retrieval and information.
"""

import logging
import uuid
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
import pywikibot
import os

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Models
# ============================================================================

class CategorySearchRequest(BaseModel):
    """Category search request."""
    category: str
    limit: int = 100
    recursive: bool = False
    exclude_published: bool = True
    include_analyzed: bool = False


class ManualSearchRequest(BaseModel):
    """Manual article search request."""
    titles: List[str]
    exclude_published: bool = True
    include_analyzed: bool = False


class PetScanSearchRequest(BaseModel):
    """PetScan search request."""
    psid: str
    limit: int = 100
    exclude_published: bool = True
    include_analyzed: bool = False


class FileSearchRequest(BaseModel):
    """File search request."""
    file_path: str
    limit: int = 100
    include_analyzed: bool = False


class UserContribsSearchRequest(BaseModel):
    """User contributions search request."""
    username: str
    limit: int = 100
    exclude_published: bool = True
    include_analyzed: bool = False


class ArticleInfo(BaseModel):
    """Article information."""
    title: str
    page_id: int
    revision_id: int
    url: str
    content: Optional[str] = None
    length: Optional[int] = None


class ArticleStatusResponse(BaseModel):
    """Article status response."""
    title: str
    page_id: Optional[int] = None
    revision_id: Optional[int] = None
    status: str
    analysis_date: Optional[str] = None
    changes_count: Optional[int] = None
    summary: Optional[str] = None
    corrected_content: Optional[str] = None
    character_count: Optional[int] = None
    score: Optional[float] = None
    decision: Optional[str] = None
    mode: Optional[str] = None
    # Progress tracking fields
    progress: Optional[float] = None
    current_step: Optional[str] = None
    analyzers_status: Optional[Dict[str, str]] = None
    elapsed_time_seconds: Optional[float] = None
    # Database fields for article results
    original_content: Optional[str] = None
    total_links: Optional[int] = None
    dead_links_count: Optional[int] = None
    corrected_links_count: Optional[int] = None
    human_verified: Optional[bool] = None
    # Normalization fields
    normalization_changes_count: Optional[int] = None
    normalization_ignored_count: Optional[int] = None
    normalization_reports: Optional[str] = None


class ArticleHistoryResponse(BaseModel):
    """Article history response."""
    title: str
    page_id: Optional[int] = None
    revision_id: Optional[int] = None
    status: str
    analysis_date: Optional[str] = None
    changes_count: Optional[int] = None
    summary: Optional[str] = None
    published_date: Optional[str] = None
    published_revision_id: Optional[int] = None
    original_content: Optional[str] = None
    corrected_content: Optional[str] = None
    mode: Optional[str] = None
    character_count: Optional[int] = None
    dead_links_count: Optional[int] = None
    corrected_links_count: Optional[int] = None
    normalization_changes_count: Optional[int] = None
    normalization_ignored_count: Optional[int] = None


class ArticleAnalysisRequest(BaseModel):
    """Request to analyze an article."""
    mode: str = "regex"


class ArticlesResponse(BaseModel):
    """Articles response."""
    success: bool
    articles: List[ArticleInfo]
    count: int
    message: str


class ArticleToAnalyze(BaseModel):
    """Article to analyze."""
    id: str
    title: str
    page_id: Optional[int] = None
    revision_id: Optional[int] = None
    source: str
    source_details: str
    priority: str
    added_at: str
    status: str


class ArticlesToAnalyzeResponse(BaseModel):
    """Articles to analyze response."""
    success: bool
    articles: List[ArticleToAnalyze]
    count: int


# ============================================================================
# Dependencies
# ============================================================================

def get_wikipedia_session():
    """Get current Wikipedia session from auth module."""
    from backend.api.routes.auth import get_wikipedia_session as get_session
    return get_session()


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


def get_automation_state():
    """Get automation state manager."""
    from backend.api.main import get_automation_state
    return get_automation_state()


def get_database():
    """Get database manager."""
    from wikipedia_maintenance.utils.database import DatabaseManager
    project_root = os.environ.get('PROJECT_ROOT')
    if project_root:
        db_path = str(Path(project_root) / "data" / "wikipedia_maintenance.db")
        return DatabaseManager(db_path)
    return DatabaseManager()


def add_articles_to_queue(articles: List, source: str, source_details: str = "") -> int:
    """
    Add retrieved articles to the analysis queue in database.
    
    Args:
        articles: List of article objects with title, page_id, revision_id
        source: Source type (category, manual, petscan, file, user-contribs)
        source_details: Additional source information
        
    Returns:
        Number of articles added to queue
    """
    db = get_database()
    added_count = 0
    
    try:
        for article in articles:
            article_title = article.title if hasattr(article, 'title') else article.get('title')
            page_id = article.page_id if hasattr(article, 'page_id') else article.get('page_id')
            revision_id = article.revision_id if hasattr(article, 'revision_id') else article.get('revision_id')
            
            if not article_title:
                continue
            
            # Generate unique ID
            import hashlib
            article_id = f"{article_title}_{revision_id if revision_id else 0}"
            
            # Try to add to queue
            try:
                cursor = db.conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO articles_to_analyze
                    (id, title, page_id, revision_id, source, source_details, priority, added_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'medium', ?, 'pending')
                """, (article_id, article_title, page_id, revision_id, source, source_details, 
                      datetime.now().isoformat()))
                db.conn.commit()
                
                if cursor.rowcount > 0:
                    added_count += 1
                    logger.debug(f"Added article to queue: {article_title}")
                    
            except Exception as e:
                logger.warning(f"Failed to add article {article_title} to queue: {e}")
                db.conn.rollback()
                
    except Exception as e:
        logger.error(f"Error adding articles to queue: {e}")
    
    return added_count


# ============================================================================
# Routes
# ============================================================================

@router.post("/category", response_model=ArticlesResponse)
async def search_category(
    request: CategorySearchRequest,
    session: dict = Depends(get_wikipedia_session),
    published_tracker = Depends(get_published_tracker),
    analyzed_tracker = Depends(get_analyzed_tracker)
):
    """
    Retrieve articles from a Wikipedia category.

    Uses the existing CategoryRetriever to fetch articles from the specified category.
    Supports filtering by published and analyzed articles.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")

        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")

        # Import existing retriever
        from wikipedia_maintenance.retrievers import CategoryRetriever

        # Create retriever with published tracker
        retriever = CategoryRetriever(site=site, tracker_file="published_articles.json")

        # Normalize category name
        category_name = request.category
        if not category_name.startswith("Category:"):
            category_name = f"Category:{category_name}"

        # Retrieve articles with pagination (like Streamlit)
        logger.info(f"Starting category retrieval: {category_name}, limit={request.limit}, recursive={request.recursive}")

        new_articles = []
        offset = 0
        batch_size = request.limit * 2  # Fetch in batches to account for filtering
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        consecutive_empty_batches = 0  # Track consecutive empty batches

        while len(new_articles) < request.limit and iteration < max_iterations:
            iteration += 1
            logger.info(f"Fetching batch {iteration} with offset {offset}, target: {request.limit}, current: {len(new_articles)}")

            batch_articles = retriever.retrieve(
                category_name=category_name,
                max_articles=batch_size,
                recursive=request.recursive,
                exclude_published=False,  # Don't filter here, let API handle it
                offset=offset
            )

            if not batch_articles:
                logger.info(f"No more articles available in category, stopping with {len(new_articles)} articles")
                break

            # Filter out recently published articles if requested
            if request.exclude_published and published_tracker:
                article_titles = [article.title for article in batch_articles]
                filtered_titles = published_tracker.filter_recently_published(article_titles, months=6)
                batch_articles = [article for article in batch_articles if article.title in filtered_titles]
                logger.info(f"Filtered {len(article_titles) - len(filtered_titles)} recently published articles")

            # Filter out already analyzed articles (unless include_analyzed is True)
            if analyzed_tracker and not request.include_analyzed:
                batch_articles = analyzed_tracker.filter_analyzed_articles(batch_articles)
                logger.info(f"Filtered analyzed articles, remaining: {len(batch_articles)}")

            if len(batch_articles) == 0:
                consecutive_empty_batches += 1
                logger.info(f"Batch {iteration} fully filtered out ({consecutive_empty_batches} consecutive empty batches)")
                if consecutive_empty_batches >= 3:  # Stop after 3 consecutive empty batches
                    logger.info(f"Too many consecutive empty batches, stopping with {len(new_articles)} articles")
                    break
            else:
                consecutive_empty_batches = 0  # Reset counter when we get articles

            new_articles.extend(batch_articles)
            offset += batch_size

        # Take only what we need
        articles = new_articles[:request.limit]

        if iteration > 1:
            logger.info(f"Retrieval completed in {iteration} batches, final count: {len(articles)} articles")

        # Convert to response format
        article_infos = []
        for article in articles:
            # Get content length if available
            length = None
            if article.content:
                length = len(article.content)

            article_infos.append(ArticleInfo(
                title=article.title,
                page_id=article.page_id,
                revision_id=article.revision_id,
                url=article.url,
                content=article.content,
                length=length
            ))

        logger.info(f"Retrieved {len(article_infos)} articles from category {request.category}")

        # Automatically add retrieved articles to analysis queue
        queue_added = add_articles_to_queue(articles, "category", request.category)
        logger.info(f"Added {queue_added} articles to analysis queue")

        return ArticlesResponse(
            success=True,
            articles=article_infos,
            count=len(article_infos),
            message=f"Retrieved {len(article_infos)} articles ({queue_added} added to queue)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search category: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Category search failed: {str(e)}")


@router.post("/manual", response_model=ArticlesResponse)
async def search_manual(
    request: ManualSearchRequest,
    session: dict = Depends(get_wikipedia_session),
    published_tracker = Depends(get_published_tracker),
    analyzed_tracker = Depends(get_analyzed_tracker)
):
    """
    Retrieve articles from a manual list of titles.
    
    Uses the existing ManualRetriever to fetch articles from the provided list.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        # Import existing retriever
        from wikipedia_maintenance.retrievers import ManualRetriever
        
        # Create retriever (use database instead of published tracker if not available)
        tracker_file = None if not published_tracker else "published_articles.json"
        retriever = ManualRetriever(tracker_file=tracker_file)
        retriever.set_site(site)
        
        # Retrieve articles
        articles = retriever.retrieve(
            titles=request.titles,
            exclude_published=request.exclude_published
        )
        
        # Filter analyzed articles if requested
        if analyzed_tracker and not request.include_analyzed:
            articles = analyzed_tracker.filter_analyzed_articles(articles)
        
        # Convert to response format
        article_infos = []
        for article in articles:
            article_infos.append(ArticleInfo(
                title=article.title,
                page_id=article.page_id,
                revision_id=article.revision_id,
                url=article.url
            ))
        
        logger.info(f"Retrieved {len(article_infos)} articles from manual list")
        
        # Automatically add retrieved articles to analysis queue
        queue_added = add_articles_to_queue(articles, "manual", "Manual entry")
        logger.info(f"Added {queue_added} articles to analysis queue")
        
        return ArticlesResponse(
            success=True,
            articles=article_infos,
            count=len(article_infos),
            message=f"Retrieved {len(article_infos)} articles ({queue_added} added to queue)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search manual: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Manual search failed: {str(e)}")


@router.post("/petscan", response_model=ArticlesResponse)
async def search_petscan(
    request: PetScanSearchRequest,
    session: dict = Depends(get_wikipedia_session),
    published_tracker = Depends(get_published_tracker),
    analyzed_tracker = Depends(get_analyzed_tracker)
):
    """
    Retrieve articles from PetScan.
    
    Uses the existing PetScanRetriever to fetch articles from PetScan.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        # Validate psid
        if not request.psid.isdigit():
            raise HTTPException(status_code=400, detail="PetScan ID must be a number")
        
        # Import existing retriever
        from wikipedia_maintenance.retrievers import PetScanRetriever
        
        # Create retriever
        retriever = PetScanRetriever()
        
        # Retrieve articles (fetch more to account for filtering)
        articles = retriever.retrieve(
            psid=int(request.psid),
            max_articles=request.limit * 10,  # Fetch more to account for filtering
            exclude_published=request.exclude_published
        )
        
        # Filter analyzed articles if requested
        if analyzed_tracker and not request.include_analyzed:
            articles = analyzed_tracker.filter_analyzed_articles(articles)
        
        # Take only what we need
        articles = articles[:request.limit]
        
        # Convert to response format
        article_infos = []
        for article in articles:
            article_infos.append(ArticleInfo(
                title=article.title,
                page_id=article.page_id,
                revision_id=article.revision_id,
                url=article.url
            ))
        
        logger.info(f"Retrieved {len(article_infos)} articles from PetScan")
        
        # Automatically add retrieved articles to analysis queue
        queue_added = add_articles_to_queue(articles, "petscan", f"PetScan ID: {request.psid}")
        logger.info(f"Added {queue_added} articles to analysis queue")
        
        return ArticlesResponse(
            success=True,
            articles=article_infos,
            count=len(article_infos),
            message=f"Retrieved {len(article_infos)} articles ({queue_added} added to queue)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search PetScan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PetScan search failed: {str(e)}")


@router.post("/file", response_model=ArticlesResponse)
async def search_file(
    request: FileSearchRequest,
    session: dict = Depends(get_wikipedia_session),
    analyzed_tracker = Depends(get_analyzed_tracker)
):
    """
    Retrieve articles from a file.
    
    Uses the existing FileRetriever to fetch articles from a file.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        # Import existing retriever
        from wikipedia_maintenance.retrievers import FileRetriever
        
        # Create retriever
        retriever = FileRetriever()
        
        # Retrieve articles
        articles = retriever.retrieve(file_path=request.file_path)
        
        # Verify existence on wiki
        missing = 0
        for article in articles:
            try:
                page = pywikibot.Page(site, article.title)
                if page.exists():
                    article.page_id = page.pageid
                    article.revision_id = page.latest_revision_id
                    article.url = page.full_url()
                else:
                    missing += 1
            except Exception:
                missing += 1
        
        if missing:
            logger.warning(f"{missing} article(s) not found on wiki and ignored")
        
        # Filter analyzed articles if requested
        if analyzed_tracker and not request.include_analyzed:
            articles = analyzed_tracker.filter_analyzed_articles(articles)
        
        # Take only what we need
        articles = articles[:request.limit]
        
        # Convert to response format
        article_infos = []
        for article in articles:
            article_infos.append(ArticleInfo(
                title=article.title,
                page_id=article.page_id,
                revision_id=article.revision_id,
                url=article.url
            ))
        
        logger.info(f"Retrieved {len(article_infos)} articles from file")
        
        # Automatically add retrieved articles to analysis queue
        queue_added = add_articles_to_queue(articles, "file", request.file_path)
        logger.info(f"Added {queue_added} articles to analysis queue")
        
        return ArticlesResponse(
            success=True,
            articles=article_infos,
            count=len(article_infos),
            message=f"Retrieved {len(article_infos)} articles ({queue_added} added to queue)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File search failed: {str(e)}")


@router.post("/user-contribs", response_model=ArticlesResponse)
async def search_user_contribs(
    request: UserContribsSearchRequest,
    session: dict = Depends(get_wikipedia_session),
    published_tracker = Depends(get_published_tracker),
    analyzed_tracker = Depends(get_analyzed_tracker)
):
    """
    Retrieve articles from user contributions.
    
    Uses the existing UserContribsRetriever to fetch articles from user contributions.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        # Import existing retriever
        from wikipedia_maintenance.retrievers import UserContribsRetriever
        
        # Create retriever
        retriever = UserContribsRetriever(site=site)
        
        # Retrieve articles with pagination (similar to Streamlit)
        articles = []
        iteration = 0
        max_iterations = 10
        consecutive_empty_batches = 0
        needed = request.limit
        
        while len(articles) < needed and iteration < max_iterations:
            iteration += 1
            batch_size = needed * 2
            logger.info(f"Fetching user contributions batch {iteration}, target: {needed}, current: {len(articles)}")
            
            batch_articles = retriever.retrieve(
                username=request.username,
                max_articles=batch_size,
                exclude_published=request.exclude_published
            )
            
            if not batch_articles:
                break
            
            # Filter analyzed articles if requested
            if analyzed_tracker and not request.include_analyzed:
                batch_articles = analyzed_tracker.filter_analyzed_articles(batch_articles)
            
            if len(batch_articles) == 0:
                consecutive_empty_batches += 1
                logger.info(f"Batch {iteration} fully filtered out ({consecutive_empty_batches} consecutive empty batches)")
                if consecutive_empty_batches >= 3:
                    logger.info(f"Too many consecutive empty batches, stopping with {len(articles)} articles")
                    break
            else:
                consecutive_empty_batches = 0
            
            articles.extend(batch_articles)
            
            # If we got fewer articles than requested, we've reached the end
            if len(batch_articles) < batch_size:
                break
        
        # Take only what we need
        articles = articles[:needed]
        
        if iteration > 1:
            logger.info(f"Retrieved in {iteration} batches to get {len(articles)} articles after filtering")
        
        # Convert to response format
        article_infos = []
        for article in articles:
            article_infos.append(ArticleInfo(
                title=article.title,
                page_id=article.page_id,
                revision_id=article.revision_id,
                url=article.url
            ))
        
        logger.info(f"Retrieved {len(article_infos)} articles from user contributions")
        
        # Automatically add retrieved articles to analysis queue
        queue_added = add_articles_to_queue(articles, "user-contribs", request.username)
        logger.info(f"Added {queue_added} articles to analysis queue")
        
        return ArticlesResponse(
            success=True,
            articles=article_infos,
            count=len(article_infos),
            message=f"Retrieved {len(article_infos)} articles ({queue_added} added to queue)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search user contributions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"User contributions search failed: {str(e)}")


@router.get("/user-contributions/history")
async def get_user_contributions_history(
    username: str,
    limit: int = 50,
    database = Depends(get_database)
):
    """Get recent contributions history for a user from database."""
    try:
        contributions = database.get_user_contributions(username, limit)
        return {
            "success": True,
            "username": username,
            "count": len(contributions),
            "contributions": contributions
        }
    except Exception as e:
        logger.error(f"Failed to get user contributions history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get user contributions history: {str(e)}")


@router.get("/results", response_model=List[ArticleStatusResponse])
async def get_all_analysis_results(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    database = Depends(get_database)
):
    """
    Get all analysis results from database.
    
    Returns a unified view of analyzed articles with their current status.
    """
    try:
        cursor = database.conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT article_title, page_id, revision_id, status, analysis_date, changes_count,
                       summary, character_count, mode, human_verified, normalization_changes_count,
                       normalization_ignored_count
                FROM analysis_results
                WHERE status = ?
                ORDER BY analysis_date DESC
                LIMIT ? OFFSET ?
            """, (status, limit, offset))
        else:
            cursor.execute("""
                SELECT article_title, page_id, revision_id, status, analysis_date, changes_count,
                       summary, character_count, mode, human_verified, normalization_changes_count,
                       normalization_ignored_count
                FROM analysis_results
                ORDER BY analysis_date DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            results.append(ArticleStatusResponse(
                title=row[0],
                page_id=row[1],
                revision_id=row[2],
                status=row[3],
                analysis_date=row[4],
                changes_count=row[5],
                summary=row[6],
                character_count=row[7],
                mode=row[8],
                score=None,  # Could be calculated from analysis
                decision=None,  # Could be linked to manual review decisions
                human_verified=row[9],
                normalization_changes_count=row[10],
                normalization_ignored_count=row[11]
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to get analysis results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")


@router.get("/results/count")
async def get_analysis_results_count(
    status: Optional[str] = None,
    database = Depends(get_database)
):
    """
    Get total count of analysis results from database.
    
    Returns the total number of articles in the analysis results table.
    """
    try:
        cursor = database.conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT COUNT(*) FROM analysis_results WHERE status = ?
            """, (status,))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM analysis_results
            """)
        
        total_count = cursor.fetchone()[0]
        
        return {"total": total_count}
        
    except Exception as e:
        logger.error(f"Failed to get analysis results count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get count: {str(e)}")


@router.get("/results/{article_title}", response_model=ArticleStatusResponse)
async def get_article_result(
    article_title: str,
    database = Depends(get_database)
):
    """
    Get analysis result for a specific article.

    Returns detailed analysis status and results for a single article.
    """
    try:
        logger.info(f"Looking for article: '{article_title}'")
        logger.info(f"Database connection: {database.conn}")
        logger.info(f"Database path: {database.db_path}")

        cursor = database.conn.cursor()
        cursor.execute("""
            SELECT article_title, page_id, revision_id, status, analysis_date, changes_count,
                   summary, corrected_content, character_count, mode, human_verified,
                   original_content, total_links, dead_links_count, corrected_links_count,
                   normalization_changes_count, normalization_ignored_count, normalization_reports
            FROM analysis_results
            WHERE article_title = ?
            ORDER BY analysis_date DESC
            LIMIT 1
        """, (article_title,))

        row = cursor.fetchone()
        if not row:
            logger.warning(f"Article not found in database: '{article_title}'")
            # Log some article titles for debugging
            cursor.execute("SELECT article_title FROM analysis_results LIMIT 5")
            sample_titles = cursor.fetchall()
            logger.info(f"Sample article titles in database: {[r[0] for r in sample_titles]}")
            # Log total count
            cursor.execute("SELECT COUNT(*) FROM analysis_results")
            total_count = cursor.fetchone()[0]
            logger.info(f"Total analysis results in database: {total_count}")
            raise HTTPException(status_code=404, detail="Article analysis not found")

        logger.info(f"Found article: {row[0]}")
        result = {
            "title": row[0],
            "page_id": row[1],
            "revision_id": row[2],
            "status": row[3],
            "analysis_date": row[4],
            "changes_count": row[5],
            "summary": row[6],
            "corrected_content": row[7],
            "character_count": row[8],
            "mode": row[9],
            "human_verified": row[10],
            "original_content": row[11],
            "total_links": row[12],
            "dead_links_count": row[13],
            "corrected_links_count": row[14],
            "normalization_changes_count": row[15],
            "normalization_ignored_count": row[16],
            "normalization_reports": row[17]
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get article result: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get result: {str(e)}")


class UpdateSummaryRequest(BaseModel):
    """Request to update article summary."""
    summary: str


@router.put("/results/{article_title}/summary")
async def update_article_summary(
    article_title: str,
    request: UpdateSummaryRequest,
    database = Depends(get_database)
):
    """
    Update the edit summary for an article.

    Updates the summary field in the analysis_results table.
    """
    try:
        cursor = database.conn.cursor()
        cursor.execute("""
            UPDATE analysis_results
            SET summary = ?
            WHERE article_title = ?
        """, (request.summary, article_title))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article analysis not found")

        database.conn.commit()
        logger.info(f"Updated summary for article: {article_title}")

        return {"success": True, "article_title": article_title, "summary": request.summary}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update article summary: {e}", exc_info=True)
        database.conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update summary: {str(e)}")


@router.get("/queue", response_model=ArticlesToAnalyzeResponse)
async def get_analysis_queue(
    status: Optional[str] = None,
    limit: int = 100,
    database = Depends(get_database)
):
    """
    Get articles from the analysis queue.
    
    Returns articles waiting to be analyzed, optionally filtered by status.
    """
    try:
        cursor = database.conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT id, title, page_id, revision_id, source, source_details, priority, added_at, status
                FROM articles_to_analyze
                WHERE status = ?
                ORDER BY priority DESC, added_at ASC
                LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT id, title, page_id, revision_id, source, source_details, priority, added_at, status
                FROM articles_to_analyze
                ORDER BY priority DESC, added_at ASC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            articles.append(ArticleToAnalyze(
                id=row[0],
                title=row[1],
                page_id=row[2],
                revision_id=row[3],
                source=row[4],
                source_details=row[5],
                priority=row[6],
                added_at=row[7],
                status=row[8]
            ))
        
        return ArticlesToAnalyzeResponse(
            success=True,
            articles=articles,
            count=len(articles)
        )
        
    except Exception as e:
        logger.error(f"Failed to get analysis queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get queue: {str(e)}")


@router.post("/queue/{article_id}/analyze")
async def analyze_from_queue(
    article_id: str,
    background_tasks: BackgroundTasks,
    session: dict = Depends(get_wikipedia_session),
    database = Depends(get_database),
    mode: str = "regex"
):
    """
    Analyze a specific article from the queue.
    
    Starts analysis for the specified article and updates its status in the queue.
    
    Args:
        article_id: ID of the article in the queue
        background_tasks: FastAPI background tasks
        session: Wikipedia session
        database: Database manager
        mode: Analysis mode (regex or ia)
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        # Get article from queue
        cursor = database.conn.cursor()
        cursor.execute("""
            SELECT title, page_id, revision_id FROM articles_to_analyze
            WHERE id = ? AND status = 'pending'
        """, (article_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Article not found in queue or already processed")
        
        article_title, page_id, revision_id = row
        
        # Update status to analyzing
        cursor.execute("""
            UPDATE articles_to_analyze
            SET status = 'analyzing', started_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), article_id))
        database.conn.commit()
        
        # Import analysis functions from database to avoid circular import
        from wikipedia_maintenance.utils.database import DatabaseManager
        project_root = os.environ.get('PROJECT_ROOT')
        if project_root:
            db_path = str(Path(project_root) / "data" / "wikipedia_maintenance.db")
            db = DatabaseManager(db_path)
        else:
            db = DatabaseManager()
        
        # Create analysis job with the correct mode from the request
        # Default to regex if not specified
        analysis_mode = mode if mode else "regex"
        
        job_id = str(uuid.uuid4())
        success = db.create_analysis_job(
            job_id=job_id,
            article_title=article_title,
            mode=analysis_mode
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create analysis job")
        
        # Link job to queue article
        cursor.execute("""
            UPDATE articles_to_analyze
            SET job_id = ?
            WHERE id = ?
        """, (job_id, article_id))
        database.conn.commit()
        
        # Import run_analysis_worker from analysis module
        from backend.api.routes.analysis import run_analysis_worker
        
        # Start background analysis
        background_tasks.add_task(
            run_analysis_worker,
            job_id,
            article_title,
            "regex",
            site,
            None,  # ai_provider
            10800,  # ai_character_limit
            None,  # gemini_api_key
            None   # gemini_project_id
        )
        
        logger.info(f"Started analysis for queue article {article_id} -> job {job_id}")
        
        return {"success": True, "job_id": job_id, "message": "Analysis started"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze from queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze: {str(e)}")


@router.post("/queue/analyze-next")
async def analyze_next_from_queue(
    background_tasks: BackgroundTasks,
    session: dict = Depends(get_wikipedia_session),
    database = Depends(get_database)
):
    """
    Analyze the next pending article from the queue.
    
    Automatically selects the highest priority pending article and starts analysis.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        # Get next pending article
        cursor = database.conn.cursor()
        cursor.execute("""
            SELECT id, title, page_id, revision_id
            FROM articles_to_analyze
            WHERE status = 'pending'
            ORDER BY priority DESC, added_at ASC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "No pending articles in queue"}
        
        article_id, article_title, page_id, revision_id = row
        
        # Update status to analyzing
        cursor.execute("""
            UPDATE articles_to_analyze
            SET status = 'analyzing', started_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), article_id))
        database.conn.commit()
        
        # Import analysis functions from database to avoid circular import
        from wikipedia_maintenance.utils.database import DatabaseManager
        project_root = os.environ.get('PROJECT_ROOT')
        if project_root:
            db_path = str(Path(project_root) / "data" / "wikipedia_maintenance.db")
            db = DatabaseManager(db_path)
        else:
            db = DatabaseManager()
        
        # Create analysis job with the correct mode from the request
        # Default to regex if not specified
        analysis_mode = mode if mode else "regex"
        
        job_id = str(uuid.uuid4())
        success = db.create_analysis_job(
            job_id=job_id,
            article_title=article_title,
            mode=analysis_mode
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create analysis job")
        
        # Link job to queue article
        cursor.execute("""
            UPDATE articles_to_analyze
            SET job_id = ?
            WHERE id = ?
        """, (job_id, article_id))
        database.conn.commit()
        
        # Import run_analysis_worker from analysis module
        from backend.api.routes.analysis import run_analysis_worker
        
        # Start background analysis
        background_tasks.add_task(
            run_analysis_worker,
            job_id,
            article_title,
            "regex",
            site,
            None,  # ai_provider
            10800,  # ai_character_limit
            None,  # gemini_api_key
            None   # gemini_project_id
        )
        
        logger.info(f"Started analysis for next queue article {article_id} -> job {job_id}")
        
        return {"success": True, "job_id": job_id, "article_id": article_id, "article_title": article_title, "message": "Analysis started"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze next from queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze: {str(e)}")


@router.delete("/queue/{article_id}")
async def remove_from_queue(
    article_id: str,
    database = Depends(get_database)
):
    """
    Remove an article from the analysis queue.
    """
    try:
        cursor = database.conn.cursor()
        cursor.execute("""
            DELETE FROM articles_to_analyze
            WHERE id = ?
        """, (article_id,))
        database.conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found in queue")
        
        logger.info(f"Removed article {article_id} from queue")
        
        return {"success": True, "message": "Article removed from queue"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove from queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to remove: {str(e)}")


# Specific routes must come before generic path routes to avoid conflicts
@router.get("/categories/predefined")
async def get_predefined_categories(
    lang: str = "fr"
):
    """
    Get predefined categories for a given language.
    
    Returns the list of predefined categories from categories_config.py.
    """
    try:
        # Import categories config
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent.parent
        sys.path.insert(0, str(project_root))
        
        from config.categories_config import get_predefined_categories
        
        categories = get_predefined_categories(lang)
        
        return {
            "success": True,
            "lang": lang,
            "categories": list(categories.values())
        }
        
    except Exception as e:
        logger.error(f"Failed to get predefined categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get predefined categories: {str(e)}")


# ============================================================================
# Article Status and History Routes (must be before generic path routes)
# ============================================================================

@router.get("/{title:path}/status", response_model=ArticleStatusResponse)
async def get_article_status(
    title: str,
    database = Depends(get_database),
    automation_state = Depends(get_automation_state)
):
    """
    Get the current status of an article.
    
    Returns analysis status, publication status, and current processing state.
    Uses SQLite as source of truth (analysis_jobs + analysis_results).
    """
    try:
        cursor = database.conn.cursor()
        
        # Check if there's a running/pending analysis job
        cursor.execute("""
            SELECT id, status, progress, started_at, mode
            FROM analysis_jobs
            WHERE article_title = ? AND status IN ('pending', 'running')
            ORDER BY started_at DESC
            LIMIT 1
        """, (title,))
        
        job_row = cursor.fetchone()
        
        # Check if there's a completed analysis result
        cursor.execute("""
            SELECT page_id, revision_id, status, analysis_date, changes_count,
                   summary, mode, human_verified, character_count
            FROM analysis_results
            WHERE article_title = ?
            ORDER BY analysis_date DESC
            LIMIT 1
        """, (title,))
        
        result_row = cursor.fetchone()
        
        # Get current automation state if article is being processed
        current_state = None
        if automation_state:
            current_state = automation_state.get_article_state(title)
        
        # Build response
        status = "pending"
        page_id = None
        revision_id = None
        analysis_date = None
        changes_count = None
        summary = None
        corrected_content = None
        character_count = None
        score = None
        decision = None
        mode = None
        progress = None
        current_step = None
        analyzers_status = None
        elapsed_time_seconds = None
        
        # Priority: running job > completed result > pending
        if job_row:
            # Article is currently being analyzed
            status = 'analyzing'
            progress = job_row[2] if job_row[2] else 0
            mode = job_row[4]
            analysis_date = job_row[3]  # started_at
        elif result_row:
            # Article has a completed analysis
            page_id = result_row[0]
            revision_id = result_row[1]
            status = result_row[2]
            analysis_date = result_row[3]
            changes_count = result_row[4]
            summary = result_row[5]
            mode = result_row[6]
            character_count = result_row[8]
        
        # Override with automation state if available
        if current_state:
            progress = current_state.progress
            current_step = current_state.current_step
            analyzers_status = current_state.analyzers_status
            elapsed_time_seconds = current_state.elapsed_time_seconds
        
        return ArticleStatusResponse(
            title=title,
            page_id=page_id,
            revision_id=revision_id,
            status=status,
            analysis_date=analysis_date,
            changes_count=changes_count,
            summary=summary,
            corrected_content=corrected_content,
            character_count=character_count,
            score=score,
            decision=decision,
            mode=mode,
            progress=progress,
            current_step=current_step,
            analyzers_status=analyzers_status,
            elapsed_time_seconds=elapsed_time_seconds
        )
        
    except Exception as e:
        logger.error(f"Failed to get article status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get article status: {str(e)}")


@router.get("/{title:path}/exists")
async def check_article_exists(
    title: str,
    session: dict = Depends(get_wikipedia_session)
):
    """
    Check if an article exists on Wikipedia.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        # Check using WikipediaAPIClient
        from wikipedia_maintenance.utils.wikipedia_api import WikipediaAPIClient
        
        api_client = WikipediaAPIClient(language=session["lang"], site=site)
        exists = api_client.page_exists(title)
        
        return {
            "success": True,
            "exists": exists,
            "title": title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check article existence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check existence: {str(e)}")


# ============================================================================
# Article Status and History Routes
# ============================================================================

@router.get("/{title:path}/analysis-result")
async def get_article_analysis_result(
    title: str,
    database = Depends(get_database)
):
    """
    Get the analysis result for an article from SQLite.
    
    Returns the original content, corrected content and analysis details.
    Uses SQLite as source of truth (analysis_results).
    """
    try:
        cursor = database.conn.cursor()
        
        # Check if there's a running/pending analysis job first
        cursor.execute("""
            SELECT id, status, progress, started_at, mode
            FROM analysis_jobs
            WHERE article_title = ? AND status IN ('pending', 'running')
            ORDER BY started_at DESC
            LIMIT 1
        """, (title,))
        
        job_row = cursor.fetchone()
        
        if job_row:
            # Article is currently being analyzed
            return {
                "success": True,
                "title": title,
                "page_id": None,
                "revision_id": None,
                "analysis_date": job_row[3],  # started_at
                "status": 'analyzing',
                "mode": job_row[4],
                "changes_count": 0,
                "summary": f"Analyse en cours ({job_row[2]*100:.0f}%)",
                "original_content": None,
                "corrected_content": None,
                "character_count": None,
                "score": None,
                "decision": None,
                "total_links": None,
                "dead_links_count": None,
                "corrected_links_count": None,
                "human_verified": None
            }
        
        # Check for completed analysis result
        cursor.execute("""
            SELECT page_id, revision_id, status, analysis_date, changes_count,
                   summary, mode, human_verified, character_count,
                   original_content, corrected_content, total_links,
                   dead_links_count, corrected_links_count
            FROM analysis_results
            WHERE article_title = ?
            ORDER BY analysis_date DESC
            LIMIT 1
        """, (title,))
        
        row = cursor.fetchone()
        
        if not row:
            return {
                "success": False,
                "message": f"Article '{title}' not found in analysis results"
            }
        
        return {
            "success": True,
            "title": title,
            "page_id": row[0],
            "revision_id": row[1],
            "analysis_date": row[3],
            "status": row[2],
            "mode": row[5],
            "changes_count": row[4],
            "summary": row[6],
            "original_content": row[9],
            "corrected_content": row[10],
            "character_count": row[8],
            "score": None,  # Could be calculated from analysis
            "decision": None,  # Could be linked to manual review decisions
            "total_links": row[11],
            "dead_links_count": row[12],
            "corrected_links_count": row[13],
            "human_verified": row[7]
        }
        
    except Exception as e:
        logger.error(f"Failed to get analysis result for {title}: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to get analysis result: {str(e)}"
        }


@router.get("/history", response_model=List[ArticleHistoryResponse])
async def get_article_history(
    limit: int = 50,
    offset: int = 0,
    database = Depends(get_database)
):
    """
    Get history of analyzed articles.
    
    Returns a list of recently analyzed articles with their status.
    Uses SQLite as source of truth (analysis_results + analysis_jobs).
    Supports pagination with limit and offset parameters.
    """
    try:
        cursor = database.conn.cursor()
        
        # Get completed analyses from analysis_results
        cursor.execute("""
            SELECT article_title, page_id, revision_id, status, analysis_date, changes_count,
                   summary, mode, human_verified, original_content, corrected_content,
                   character_count, dead_links_count, corrected_links_count
            FROM analysis_results
            ORDER BY analysis_date DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        completed_rows = cursor.fetchall()
        
        # Get running/analyzing analyses from analysis_jobs
        cursor.execute("""
            SELECT article_title, status, progress, started_at
            FROM analysis_jobs
            WHERE status IN ('pending', 'running')
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))
        
        running_rows = cursor.fetchall()
        
        # Build a map of completed articles by title
        completed_map = {}
        for row in completed_rows:
            completed_map[row[0]] = {
                'title': row[0],
                'page_id': row[1],
                'revision_id': row[2],
                'status': row[3],
                'analysis_date': row[4],
                'changes_count': row[5],
                'summary': row[6],
                'mode': row[7],
                'human_verified': row[8],
                'original_content': row[9] if len(row) > 9 else None,
                'corrected_content': row[10] if len(row) > 10 else None,
                'character_count': row[11] if len(row) > 11 else 0,
                'dead_links_count': row[12] if len(row) > 12 else 0,
                'corrected_links_count': row[13] if len(row) > 13 else 0
            }
        
        # Combine running and completed analyses
        # Running analyses take priority (they are currently being analyzed)
        history = []
        seen_titles = set()
        
        # Add running analyses first
        for row in running_rows:
            article_title = row[0]
            if article_title not in seen_titles:
                history.append(ArticleHistoryResponse(
                    title=article_title,
                    page_id=None,  # Will be filled when analysis completes
                    revision_id=None,
                    status='analyzing',  # Override to show as analyzing
                    analysis_date=row[3],  # started_at
                    changes_count=0,
                    summary=f"Analyse en cours ({row[2]*100:.0f}%)",
                    published_date=None,
                    published_revision_id=None
                ))
                seen_titles.add(article_title)
        
        # Add completed analyses (excluding those already in running)
        for row in completed_rows:
            article_title = row[0]
            if article_title not in seen_titles:
                history.append(ArticleHistoryResponse(
                    title=row[0],
                    page_id=row[1],
                    revision_id=row[2],
                    status=row[3],
                    analysis_date=row[4],
                    changes_count=row[5],
                    summary=row[6],
                    published_date=None,
                    published_revision_id=None,
                    original_content=row[9] if len(row) > 9 else None,
                    corrected_content=row[10] if len(row) > 10 else None,
                    mode=row[7],
                    character_count=row[11] if len(row) > 11 else 0,
                    dead_links_count=row[12] if len(row) > 12 else 0,
                    corrected_links_count=row[13] if len(row) > 13 else 0
                ))
                seen_titles.add(article_title)
        
        # Sort by analysis date (most recent first)
        history.sort(key=lambda h: h.analysis_date or "", reverse=True)
        
        # Take only the requested limit
        history = history[:limit]
        
        return history
        
    except Exception as e:
        logger.error(f"Failed to get article history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get article history: {str(e)}")


@router.post("/{title:path}/analyze")
async def analyze_article(
    title: str,
    request: ArticleAnalysisRequest,
    background_tasks: BackgroundTasks,
    session: dict = Depends(get_wikipedia_session)
):
    """
    Trigger analysis of a specific article.
    
    This endpoint initiates analysis of an article and returns immediately.
    The actual analysis happens asynchronously via the analysis worker.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        # Get page info
        page = pywikibot.Page(site, title)
        if not page.exists():
            raise HTTPException(status_code=404, detail=f"Article '{title}' not found")
        
        logger.info(f"Starting analysis for article '{title}' in mode '{request.mode}'")
        
        # Create analysis job and start background worker
        import uuid
        from wikipedia_maintenance.utils.database import DatabaseManager
        from backend.api.routes.analysis import run_analysis_worker, create_analysis_job
        
        project_root = os.environ.get('PROJECT_ROOT')
        if project_root:
            db_path = str(Path(project_root) / "data" / "wikipedia_maintenance.db")
            db = DatabaseManager(db_path)
        else:
            db = DatabaseManager()
        
        job_id = str(uuid.uuid4())
        success = db.create_analysis_job(
            job_id=job_id,
            article_title=title,
            mode=request.mode
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create analysis job")
        
        # Start background analysis - the worker will handle recording the analysis
        background_tasks.add_task(
            run_analysis_worker,
            job_id,
            title,
            request.mode,
            site
        )
        
        return {
            "success": True,
            "message": f"Analysis started for '{title}'",
            "title": title,
            "mode": request.mode,
            "status": "analyzing",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start analysis for {title}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.post("/{title:path}/toggle-verified")
async def toggle_human_verified(
    title: str,
    database = Depends(get_database)
):
    """
    Toggle human_verified status for an article.
    """
    try:
        cursor = database.conn.cursor()
        
        # Get current status
        cursor.execute("""
            SELECT human_verified FROM analysis_results
            WHERE article_title = ?
            ORDER BY analysis_date DESC
            LIMIT 1
        """, (title,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Article not found")
        
        current_status = row[0] if row[0] is not None else False
        new_status = not current_status
        
        # Update status
        cursor.execute("""
            UPDATE analysis_results
            SET human_verified = ?
            WHERE article_title = ?
        """, (1 if new_status else 0, title))
        
        database.conn.commit()
        logger.info(f"Toggled human_verified for '{title}' from {current_status} to {new_status}")
        
        return {
            "success": True,
            "article_title": title,
            "human_verified": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle human_verified for {title}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to toggle human_verified: {str(e)}")


@router.post("/{title:path}/ignore")
async def ignore_article(
    title: str,
    analyzed_tracker = Depends(get_analyzed_tracker)
):
    """
    Mark an article as ignored.
    
    This prevents the article from being processed in future automations.
    """
    try:
        # Get existing record
        record = analyzed_tracker.get_record(title)
        
        if record:
            # Update existing record to ignored
            from wikipedia_maintenance.utils.analyzed_tracker import AnalysisStatus
            
            analyzed_tracker.record_analysis(
                title=title,
                page_id=record.page_id,
                revision_id=record.revision_id,
                status=AnalysisStatus.IGNORED,
                mode=record.mode,
                changes_count=record.changes_count,
                summary=record.summary
            )
        else:
            # Create new ignored record
            from wikipedia_maintenance.utils.analyzed_tracker import AnalysisStatus
            
            analyzed_tracker.record_analysis(
                title=title,
                page_id=None,
                revision_id=None,
                status=AnalysisStatus.IGNORED,
                mode="manual"
            )
        
        logger.info(f"Article '{title}' marked as ignored")
        
        return {
            "success": True,
            "message": f"Article '{title}' marked as ignored",
            "title": title,
            "status": "ignored"
        }
        
    except Exception as e:
        logger.error(f"Failed to ignore article {title}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to ignore article: {str(e)}")


# ============================================================================
# Articles to Analyze Queue (Database Persistence)
# ============================================================================
# These routes must be defined BEFORE the generic route to avoid conflicts

@router.get("/to-analyze", response_model=ArticlesToAnalyzeResponse)
async def get_articles_to_analyze(db = Depends(get_database)):
    """
    Get all articles in the analysis queue from database.

    Returns articles that are waiting to be analyzed with their metadata.
    """
    try:
        cursor = db.conn.cursor()

        cursor.execute("""
            SELECT id, title, page_id, revision_id, source, source_details, priority, added_at, status
            FROM articles_to_analyze
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END,
                added_at DESC
        """)

        articles = []
        for row in cursor.fetchall():
            articles.append(ArticleToAnalyze(
                id=str(row[0]),
                title=row[1],
                page_id=row[2],
                revision_id=row[3],
                source=row[4],
                source_details=row[5],
                priority=row[6],
                added_at=row[7],
                status=row[8]
            ))

        return ArticlesToAnalyzeResponse(
            success=True,
            articles=articles,
            count=len(articles)
        )

    except Exception as e:
        logger.error(f"Failed to get articles to analyze: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get articles to analyze: {str(e)}")


@router.get("/to-analyze/count")
async def get_articles_to_analyze_count(
    status: Optional[str] = None,
    db = Depends(get_database)
):
    """
    Get total count of articles in the analysis queue.
    
    Returns the total number of articles waiting to be analyzed.
    """
    try:
        cursor = db.conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT COUNT(*) FROM articles_to_analyze WHERE status = ?
            """, (status,))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM articles_to_analyze
            """)
        
        total_count = cursor.fetchone()[0]
        
        return {"total": total_count}
        
    except Exception as e:
        logger.error(f"Failed to get articles to analyze count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get count: {str(e)}")


@router.post("/to-analyze")
async def add_article_to_analyze(
    request: dict,
    db = Depends(get_database),
    session: dict = Depends(get_wikipedia_session)
):
    """
    Add an article to the analysis queue.

    Stores the article in the database for persistent tracking.
    """
    try:
        title = request.get("title")
        source = request.get("source", "manual")
        source_details = request.get("source_details", "")
        priority = request.get("priority", "medium")

        if not title:
            raise HTTPException(status_code=400, detail="Title is required")

        cursor = db.conn.cursor()

        # Get page info from Wikipedia
        site = session.get("site")

        page_id = None
        revision_id = None

        if site:
            try:
                page = pywikibot.Page(site, title)
                if page.exists():
                    page_id = page.pageid
                    revision_id = page.latest_revision_id
            except Exception as e:
                logger.warning(f"Could not get page info for {title}: {e}")

        # Insert into database
        import uuid
        from datetime import datetime

        article_id = str(uuid.uuid4())
        added_at = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO articles_to_analyze (id, title, page_id, revision_id, source, source_details, priority, added_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (article_id, title, page_id, revision_id, source, source_details, priority, added_at, 'pending'))

        db.conn.commit()

        return {
            "success": True,
            "article_id": article_id,
            "message": "Article added to analysis queue"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add article to analyze: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add article to analyze: {str(e)}")


@router.delete("/to-analyze/{article_id}")
async def delete_article_to_analyze(
    article_id: str,
    db = Depends(get_database)
):
    """
    Remove an article from the analysis queue.

    Deletes the article from the database.
    """
    try:
        cursor = db.conn.cursor()

        cursor.execute("DELETE FROM articles_to_analyze WHERE id = ?", (article_id,))
        db.conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found in queue")

        return {
            "success": True,
            "message": "Article removed from analysis queue"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete article from queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete article: {str(e)}")


@router.post("/to-analyze/batch")
async def add_articles_to_analyze_batch(
    request: dict,
    db = Depends(get_database),
    session: dict = Depends(get_wikipedia_session)
):
    """
    Add multiple articles to the analysis queue at once.

    Handles duplicate detection and batch insertion.
    """
    try:
        articles_data = request.get("articles", [])
        if not articles_data:
            raise HTTPException(status_code=400, detail="No articles provided")

        cursor = db.conn.cursor()

        added_count = 0
        skipped_count = 0
        from datetime import datetime
        import uuid

        for article_data in articles_data:
            title = article_data.get("title")
            if not title:
                continue

            # Check for duplicates
            cursor.execute("SELECT id FROM articles_to_analyze WHERE title = ?", (title,))
            if cursor.fetchone():
                skipped_count += 1
                continue

            # Get page info from Wikipedia if not provided
            page_id = article_data.get("page_id")
            revision_id = article_data.get("revision_id")

            if not page_id or not revision_id:
                try:
                    site = session.get("site")

                    if site:
                        try:
                            page_obj = pywikibot.Page(site, title)
                            if page_obj.exists():
                                page_id = page_obj.pageid
                                revision_id = page_obj.latest_revision_id
                        except Exception as e:
                            logger.warning(f"Could not get page info for {title}: {e}")
                except Exception as e:
                    logger.warning(f"Could not get Wikipedia session for {title}: {e}")

            article_id = str(uuid.uuid4())
            added_at = datetime.now().isoformat()

            cursor.execute("""
                INSERT OR IGNORE INTO articles_to_analyze (id, title, page_id, revision_id, source, source_details, priority, added_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article_id,
                title,
                page_id,
                revision_id,
                article_data.get("source", "manual"),
                article_data.get("source_details", ""),
                article_data.get("priority", "medium"),
                added_at,
                'pending'
            ))

            added_count += 1

        db.conn.commit()

        return {
            "success": True,
            "added_count": added_count,
            "skipped_count": skipped_count,
            "message": f"Added {added_count} articles to queue, skipped {skipped_count} duplicates"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add articles to queue in batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add articles to queue: {str(e)}")


@router.patch("/to-analyze/{article_id}/status")
async def update_article_status(
    article_id: str,
    request: dict,
    db = Depends(get_database)
):
    """
    Update the status of an article in the analysis queue.

    Changes the status from pending to analyzing to analyzed.
    """
    try:
        new_status = request.get("status")
        if not new_status:
            raise HTTPException(status_code=400, detail="Status is required")

        valid_statuses = ['pending', 'analyzing', 'analyzed']
        if new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

        cursor = db.conn.cursor()

        cursor.execute("""
            UPDATE articles_to_analyze
            SET status = ?
            WHERE id = ?
        """, (new_status, article_id))

        db.conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found in queue")

        return {
            "success": True,
            "message": f"Article status updated to {new_status}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update article status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update article status: {str(e)}")


@router.post("/sync-published")
async def sync_published_articles(
    db = Depends(get_database),
    session: dict = Depends(get_wikipedia_session),
    published_tracker = Depends(get_published_tracker)
):
    """
    Synchronize articles that were published manually on Wikipedia.

    Checks articles in the analysis queue and marks them as published if they
    have recent revisions on Wikipedia that match the corrected content.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")

        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")

        cursor = db.conn.cursor()

        # Get all articles in the analysis queue with status 'analyzed'
        cursor.execute("""
            SELECT id, title, page_id, revision_id
            FROM articles_to_analyze
            WHERE status = 'analyzed'
        """)

        articles_to_check = cursor.fetchall()
        synced_count = 0

        for article in articles_to_check:
            article_id, title, page_id, revision_id = article

            try:
                # Get the page from Wikipedia
                page = pywikibot.Page(site, title)

                if not page.exists():
                    continue

                # Get the latest revision info
                latest_revision = page.latest_revision_id

                # Check if the latest revision is different from the one we have
                if latest_revision != revision_id:
                    # Check if this revision is recent (within last 24 hours)
                    page_history = list(page.revisions(total=1))
                    if page_history:
                        latest_rev = page_history[0]
                        from datetime import datetime, timedelta
                        rev_timestamp = latest_rev['timestamp']
                        now = datetime.now()

                        # If revision is recent, mark as published
                        if (now - rev_timestamp) < timedelta(hours=24):
                            # Record in published tracker
                            if published_tracker:
                                published_tracker.mark_as_published(
                                    article_title=title,
                                    category="unknown",
                                    mode="manual_sync",
                                    summary="Manually published on Wikipedia",
                                    revision_id=latest_revision
                                )

                            # Remove from analysis queue
                            cursor.execute("DELETE FROM articles_to_analyze WHERE id = ?", (article_id,))
                            synced_count += 1
                            logger.info(f"Synced manually published article: {title}")

            except Exception as e:
                logger.warning(f"Failed to check article {title} for manual publication: {e}")
                continue

        db.conn.commit()

        return {
            "success": True,
            "synced_count": synced_count,
            "message": f"Synchronized {synced_count} manually published articles"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync published articles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync published articles: {str(e)}")


# ============================================================================
# Generic Article Route (must be last to avoid conflicts with specific routes)
# ============================================================================

@router.get("/{title:path}", response_model=ArticleInfo)
async def get_article(
    title: str,
    session: dict = Depends(get_wikipedia_session)
):
    """
    Get information about a specific article.

    Retrieves the article content and metadata from Wikipedia.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")

        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")

        # Get page
        page = pywikibot.Page(site, title)

        if not page.exists():
            raise HTTPException(status_code=404, detail=f"Article '{title}' not found")

        # Get content
        content = page.get()

        return ArticleInfo(
            title=page.title(),
            page_id=page.pageid,
            revision_id=page.latest_revision_id,
            url=page.full_url(),
            content=content,
            length=len(content) if content else 0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get article {title}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get article: {str(e)}")
