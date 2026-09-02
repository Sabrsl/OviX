"""
Article Scheduler API Routes

Semi-automatic scheduler for processing articles from the analysis queue.
This works with articles from /articles/to-analyze endpoint and adds
articles with valid corrections to the publication queue for programmed
publication by the main scheduler.
"""

import logging
import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from wikipedia_maintenance.utils.database import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Request/Response Models
# ============================================================================

class ArticleSchedulerConfig(BaseModel):
    """Configuration for article scheduler."""
    article_count: int = 10
    publish_automatically: bool = False
    dry_run: bool = True

class ArticleSchedulerStatus(BaseModel):
    """Status of article scheduler."""
    is_active: bool
    is_paused: bool
    session_id: Optional[str] = None
    total_articles: int = 0
    processed_articles: int = 0
    current_article: Optional[str] = None
    current_step: Optional[str] = None
    progress_percentage: float = 0.0
    articles_analyzed: int = 0
    articles_corrected: int = 0
    articles_published: int = 0
    articles_error: int = 0
    started_at: Optional[str] = None
    estimated_completion: Optional[str] = None
    config: Optional[ArticleSchedulerConfig] = None

class ArticleSchedulerStartResponse(BaseModel):
    """Response when starting article scheduler."""
    success: bool
    message: str
    session_id: Optional[str] = None
    status: Optional[ArticleSchedulerStatus] = None

class ArticleProgress(BaseModel):
    """Progress information for a single article."""
    title: str
    status: str  # pending, analyzing, correcting, validating, ready_to_publish, published, error
    current_step: Optional[str] = None
    progress: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

# ============================================================================
# Global State Management
# ============================================================================

class ArticleSchedulerState:
    """Global state for article scheduler."""
    
    def __init__(self):
        self.is_active = False
        self.is_paused = False
        self.session_id: Optional[str] = None
        self.total_articles = 0
        self.processed_articles = 0
        self.current_article: Optional[str] = None
        self.current_step: Optional[str] = None
        self.articles_analyzed = 0
        self.articles_corrected = 0
        self.articles_published = 0
        self.articles_error = 0
        self.started_at: Optional[str] = None
        self.config: Optional[ArticleSchedulerConfig] = None
        self.article_progress: Dict[str, ArticleProgress] = {}
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    def reset(self):
        """Reset scheduler state."""
        self.is_active = False
        self.is_paused = False
        self.session_id = None
        self.total_articles = 0
        self.processed_articles = 0
        self.current_article = None
        self.current_step = None
        self.articles_analyzed = 0
        self.articles_corrected = 0
        self.articles_published = 0
        self.articles_error = 0
        self.started_at = None
        self.config = None
        self.article_progress = {}
        self._task = None
        self._stop_event.clear()
        
    def get_status(self) -> ArticleSchedulerStatus:
        """Get current scheduler status."""
        progress_percentage = 0.0
        if self.total_articles > 0:
            progress_percentage = (self.processed_articles / self.total_articles) * 100
            
        return ArticleSchedulerStatus(
            is_active=self.is_active,
            is_paused=self.is_paused,
            session_id=self.session_id,
            total_articles=self.total_articles,
            processed_articles=self.processed_articles,
            current_article=self.current_article,
            current_step=self.current_step,
            progress_percentage=progress_percentage,
            articles_analyzed=self.articles_analyzed,
            articles_corrected=self.articles_corrected,
            articles_published=self.articles_published,
            articles_error=self.articles_error,
            started_at=self.started_at,
            config=self.config
        )

# Global scheduler state instance
_article_scheduler_state = ArticleSchedulerState()

# ============================================================================
# Dependencies
# ============================================================================

def get_database():
    """Get database dependency."""
    from backend.api.main import get_database
    return get_database()

def get_event_manager():
    """Get event manager dependency."""
    try:
        from wikipedia_maintenance.utils.event_manager import get_event_manager
        return get_event_manager()
    except Exception as e:
        logger.warning(f"Event manager not available: {e}")
        return None

def get_event_type():
    """Get EventType for event manager."""
    try:
        from wikipedia_maintenance.utils.event_manager import EventType
        return EventType
    except Exception as e:
        logger.warning(f"EventType not available: {e}")
        return None

def get_wikipedia_session():
    """Get Wikipedia session dependency."""
    from backend.api.routes.auth import get_wikipedia_session as get_session
    return get_session()

# ============================================================================
# Processing Logic
# ============================================================================

async def process_article(
    article_title: str,
    config: ArticleSchedulerConfig,
    database,
    wikipedia_session,
    event_manager,
    EventType
) -> Dict[str, Any]:
    """
    Process a single article through the analysis pipeline.
    
    Args:
        article_title: Title of the article to process
        config: Scheduler configuration
        database: Database manager
        wikipedia_session: Wikipedia session
        event_manager: Event manager for real-time updates
    
    Returns:
        Processing result with status and details
    """
    try:
        # Update current step
        _article_scheduler_state.current_step = "Analyzing"
        _article_scheduler_state.current_article = article_title
        
        if event_manager and EventType:
            await event_manager.emit(
                EventType.ANALYSIS_STARTED,
                {"title": article_title, "session_id": _article_scheduler_state.session_id}
            )
        
        # Call the existing analysis worker directly
        try:
            from backend.api.routes.analysis import run_analysis_worker, create_analysis_job
            
            # Get or create site
            site = wikipedia_session.get("site")
            if site is None:
                # Create site if not available (using lang/family from session or defaults)
                import pywikibot
                lang = wikipedia_session.get("lang") or "fr"
                family = wikipedia_session.get("family") or "wikipedia"
                site = pywikibot.Site(lang, family)
                logger.info(f"Created site for {lang}.{family}")
            
            # Create analysis job
            job_id = create_analysis_job(
                article_title=article_title,
                mode="regex"  # Default to regex mode
            )
            
            # Run analysis worker (this will handle the full pipeline)
            await run_analysis_worker(
                analysis_id=job_id,
                article_title=article_title,
                mode="regex",
                site=site,
                ai_provider=None,
                ai_character_limit=10800,
                gemini_api_key=None,
                gemini_project_id=None
            )
            
            # Check job status for result
            job_status = None
            try:
                from backend.api.routes.analysis import get_analysis_job
                job_status = get_analysis_job(job_id)
            except Exception as e:
                logger.warning(f"Could not get job status: {e}")
            
            # Determine success based on job status
            if job_status and job_status.get("status") == "completed":
                analysis_success = True
            else:
                analysis_success = False
                
        except Exception as e:
            logger.error(f"Analysis call failed for {article_title}: {e}")
            return {
                "success": False,
                "status": "error",
                "error": f"Analysis failed: {str(e)}"
            }
        
        _article_scheduler_state.articles_analyzed += 1
        
        if event_manager and EventType:
            await event_manager.emit(
                EventType.ANALYSIS_COMPLETED,
                {"title": article_title, "session_id": _article_scheduler_state.session_id}
            )
        
        # Check if analysis was successful
        if not analysis_success:
            return {
                "success": False,
                "status": "error",
                "error": "Analysis failed to complete"
            }

        # The existing analysis pipeline includes analysis, detection, correction, and validation
        # Update progress to reflect actual completion of the full pipeline
        _article_scheduler_state.current_step = "Analysis pipeline completed"

        # Update article progress - real pipeline completion (100% after full analysis pipeline)
        if article_title in _article_scheduler_state.article_progress:
            _article_scheduler_state.article_progress[article_title].status = "ready_to_publish"
            _article_scheduler_state.article_progress[article_title].progress = 100.0

        # Get analysis result to check for valid corrections
        db = DatabaseManager(database.db_path)
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT corrected_content, original_content, summary, corrected_links_count, page_id, revision_id, character_count, total_links, dead_links_count, changes_count, mode
            FROM analysis_results
            WHERE article_title = ?
            ORDER BY analysis_date DESC
            LIMIT 1
        """, (article_title,))
        row = cursor.fetchone()

        if not row:
            logger.warning(f"No analysis result found for {article_title}, cannot add to publication queue")
            return {
                "success": False,
                "status": "error",
                "error": "No analysis result available"
            }

        corrected_content, original_content, summary, corrected_links_count, page_id, revision_id, character_count, total_links, dead_links_count, changes_count, mode = row

        # Only add to publication queue if there are valid corrections
        if corrected_links_count > 0:
            logger.info(f"Article {article_title} has {corrected_links_count} valid corrections, adding to publication queue")

            # Add to scheduler queue for programmed publication
            article_data = {
                'title': article_title,
                'page_id': page_id,
                'revision_id': revision_id,
                'corrected_content': corrected_content,
                'summary': summary or "Dead link corrections via OVIX",
                'changes_count': changes_count,
                'original_content': original_content,
                'character_count': character_count,
                'total_links': total_links,
                'dead_links_count': dead_links_count,
                'corrected_links_count': corrected_links_count,
                'mode': mode
            }

            queue_added = database.add_to_scheduler_queue(article_data)
            if queue_added:
                _article_scheduler_state.articles_corrected += 1
                logger.info(f"Article {article_title} added to publication queue successfully")
            else:
                logger.error(f"Failed to add article {article_title} to publication queue")
                _article_scheduler_state.articles_error += 1
                return {
                    "success": False,
                    "status": "error",
                    "error": "Failed to add to publication queue"
                }
        else:
            logger.info(f"Article {article_title} has no valid corrections (corrected_links_count={corrected_links_count}), skipping publication queue")

            # Article analyzed but no corrections - mark as completed but not queued for publication
            if article_title in _article_scheduler_state.article_progress:
                _article_scheduler_state.article_progress[article_title].status = "no_corrections"
                _article_scheduler_state.article_progress[article_title].completed_at = datetime.now().isoformat()

            return {
                "success": True,
                "status": "no_corrections",
                "message": f"Article analyzed but no valid corrections found (corrected_links_count={corrected_links_count})"
            }

        # Publication step (if configured and not dry run) - DEPRECATED in favor of scheduler queue
        # This is kept for backward compatibility but should not be used
        if config.publish_automatically and not config.dry_run:
            _article_scheduler_state.current_step = "Publishing"
            
            if event_manager and EventType:
                await event_manager.emit(
                    EventType.PUBLISHING_STARTED,
                    {"title": article_title, "session_id": _article_scheduler_state.session_id}
                )
            
            # Call the existing publication worker
            try:
                from backend.api.routes.publication import run_publication_worker, create_publication_job

                # Get analysis result to obtain corrected content
                db = DatabaseManager(database.db_path)
                cursor = db.conn.cursor()
                cursor.execute("""
                    SELECT corrected_content, original_content, summary
                    FROM analysis_results
                    WHERE article_title = ?
                    ORDER BY analysis_date DESC
                    LIMIT 1
                """, (article_title,))
                row = cursor.fetchone()
                
                if not row:
                    logger.warning(f"No analysis result found for {article_title}, skipping publication")
                    return {
                        "success": False,
                        "status": "error",
                        "error": "No analysis result available for publication"
                    }
                
                corrected_content, original_content, summary = row
                
                # Create publication job
                publication_id = create_publication_job(
                    article_title=article_title,
                    dry_run=False  # Real publication since we passed the dry_run check
                )
                
                # Get publisher from session
                publisher = wikipedia_session.get("publisher")
                if not publisher:
                    logger.error(f"Publisher not available for {article_title}")
                    return {
                        "success": False,
                        "status": "error",
                        "error": "Publisher not available"
                    }
                
                # Run publication worker
                await run_publication_worker(
                    publication_id=publication_id,
                    article_title=article_title,
                    corrected_content=corrected_content,
                    summary=summary or "Dead link corrections via OVIX",
                    dry_run=False,
                    original_content=original_content or "",
                    publisher=publisher
                )
                
                # Check publication job status
                from backend.api.routes.publication import get_publication_job
                pub_job_status = get_publication_job(publication_id)
                
                if pub_job_status and pub_job_status.get("status") == "completed":
                    publish_success = True
                else:
                    publish_success = False
                
                if publish_success:
                    _article_scheduler_state.articles_published += 1
                    
                    if event_manager and EventType:
                        await event_manager.emit(
                            EventType.PUBLISHED,
                            {"title": article_title, "session_id": _article_scheduler_state.session_id}
                        )
                    
                    if article_title in _article_scheduler_state.article_progress:
                        _article_scheduler_state.article_progress[article_title].status = "published"
                        _article_scheduler_state.article_progress[article_title].progress = 100.0
                    
                    return {
                        "success": True,
                        "status": "published",
                        "message": "Article processed and published successfully"
                    }
                else:
                    # Publication failed but article was processed
                    _article_scheduler_state.articles_error += 1
                    
                    error_msg = "Publication failed"
                    if pub_job_status:
                        error_msg = pub_job_status.get("message", "Publication failed")
                    
                    if article_title in _article_scheduler_state.article_progress:
                        _article_scheduler_state.article_progress[article_title].status = "error"
                        _article_scheduler_state.article_progress[article_title].error_message = error_msg
                        _article_scheduler_state.article_progress[article_title].completed_at = datetime.now().isoformat()
                    
                    return {
                        "success": False,
                        "status": "error",
                        "error": error_msg
                    }
            except Exception as e:
                logger.error(f"Publication failed for {article_title}: {e}")
                _article_scheduler_state.articles_error += 1
                
                if article_title in _article_scheduler_state.article_progress:
                    _article_scheduler_state.article_progress[article_title].status = "error"
                    _article_scheduler_state.article_progress[article_title].error_message = str(e)
                
                return {
                    "success": False,
                    "status": "error",
                    "error": f"Publication failed: {str(e)}"
                }
        elif config.dry_run:
            # Dry run mode - no actual publication
            if event_manager and EventType:
                await event_manager.emit(
                    EventType.PUBLISHING_STARTED,
                    {"title": article_title, "session_id": _article_scheduler_state.session_id, "dry_run": True}
                )
            
            if article_title in _article_scheduler_state.article_progress:
                _article_scheduler_state.article_progress[article_title].status = "dry_run"
            
            return {
                "success": True,
                "status": "dry_run",
                "message": "Article processed in dry run mode (no publication)"
            }
        else:
            # Ready to publish but auto-publish disabled
            if article_title in _article_scheduler_state.article_progress:
                _article_scheduler_state.article_progress[article_title].status = "ready_to_publish"
            
            return {
                "success": True,
                "status": "ready_to_publish",
                "message": "Article processed and ready for manual publication"
            }
        
    except Exception as e:
        logger.error(f"Error processing article {article_title}: {e}", exc_info=True)
        _article_scheduler_state.articles_error += 1
        
        if article_title in _article_scheduler_state.article_progress:
            _article_scheduler_state.article_progress[article_title].status = "error"
            _article_scheduler_state.article_progress[article_title].error_message = str(e)
        
        if event_manager and EventType:
            await event_manager.emit(
                EventType.ERROR,
                {"title": article_title, "error": str(e), "session_id": _article_scheduler_state.session_id}
            )
        
        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }

async def process_articles_queue(
    articles: List[Dict[str, Any]],
    config: ArticleSchedulerConfig,
    database,
    wikipedia_session,
    event_manager,
    session_id: str,
    EventType
):
    """
    Process a queue of articles through the analysis pipeline.
    
    Args:
        articles: List of articles to process
        config: Scheduler configuration
        database: Database manager
        wikipedia_session: Wikipedia session
        event_manager: Event manager for real-time updates
    """
    try:
        _article_scheduler_state.is_active = True
        _article_scheduler_state.started_at = datetime.now().isoformat()
        _article_scheduler_state.total_articles = len(articles)
        _article_scheduler_state.config = config
        
        # Initialize article progress tracking
        for article in articles:
            title = article.get("title")
            if title:
                _article_scheduler_state.article_progress[title] = ArticleProgress(
                    title=title,
                    status="pending",
                    progress=0.0,
                    started_at=datetime.now().isoformat()
                )
        
        if event_manager and EventType:
            await event_manager.emit(
                EventType.AUTOMATION_STARTED,
                {
                    "total_articles": len(articles),
                    "config": config.dict(),
                    "session_id": _article_scheduler_state.session_id
                }
            )
        
        # Process each article
        for i, article in enumerate(articles):
            # Check if we should stop
            if _article_scheduler_state._stop_event.is_set():
                logger.info("Article scheduler stopped by user")
                break
            
            # Check if paused
            while _article_scheduler_state.is_paused:
                if _article_scheduler_state._stop_event.is_set():
                    logger.info("Article scheduler stopped while paused")
                    break
                await asyncio.sleep(0.5)
            
            if _article_scheduler_state._stop_event.is_set():
                break
            
            # Process the article
            article_title = article.get("title")
            if not article_title:
                continue
                
            logger.info(f"Processing article {i+1}/{len(articles)}: {article_title}")
            
            result = await process_article(
                article_title=article_title,
                config=config,
                database=database,
                wikipedia_session=wikipedia_session,
                event_manager=event_manager,
                EventType=EventType
            )
            
            _article_scheduler_state.processed_articles += 1
            
            # Update current step
            _article_scheduler_state.current_step = f"Completed {i+1}/{len(articles)}"
        
        # Processing complete
        if event_manager and EventType:
            await event_manager.emit(
                EventType.AUTOMATION_STOPPED,
                {
                    "session_id": _article_scheduler_state.session_id,
                    "processed": _article_scheduler_state.processed_articles,
                    "published": _article_scheduler_state.articles_published,
                    "errors": _article_scheduler_state.articles_error
                }
            )
        
        logger.info(f"Article scheduler completed. Processed {_article_scheduler_state.processed_articles} articles")
        
    except Exception as e:
        logger.error(f"Error in articles queue processing: {e}", exc_info=True)
        
        if event_manager and EventType:
            await event_manager.emit(
                EventType.ERROR,
                {"error": str(e), "session_id": _article_scheduler_state.session_id}
            )
    finally:
        _article_scheduler_state.is_active = False
        _article_scheduler_state.current_step = None
        _article_scheduler_state.current_article = None
        
        # Release database lock using existing mechanism
        try:
            if session_id:
                database.release_automation_lock(session_id)
                logger.info(f"Released article scheduler lock for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to release database lock: {e}")

# ============================================================================
# API Routes
# ============================================================================

@router.get("/status", response_model=ArticleSchedulerStatus)
async def get_article_scheduler_status():
    """
    Get the current status of the article scheduler.
    
    Returns detailed information about the scheduler state, progress,
    and processing statistics.
    """
    return _article_scheduler_state.get_status()

@router.post("/start", response_model=ArticleSchedulerStartResponse)
async def start_article_scheduler(
    config: ArticleSchedulerConfig,
    background_tasks: BackgroundTasks,
    database = Depends(get_database),
    event_manager = Depends(get_event_manager),
    wikipedia_session = Depends(get_wikipedia_session),
    EventType = Depends(get_event_type)
):
    """
    Start the article scheduler with the given configuration.
    
    Processes articles from the analysis queue (/articles/to-analyze)
    according to the specified configuration.
    """
    # Use existing database-level locking to prevent concurrent starts (atomic operation)
    try:
        # Attempt to acquire lock using the existing automation lock mechanism
        session_id = f"article_scheduler_{uuid.uuid4().hex[:8]}"
        
        # Use the existing acquire_automation_lock method with automation_type='article_scheduler'
        lock_acquired = database.acquire_automation_lock(
            session_id=session_id,
            locked_by="api",
            automation_type="article_scheduler"
        )
        
        if not lock_acquired:
            # Get current lock status for better error message
            lock_status = database.get_automation_lock_status()
            existing_session_id = lock_status.get('session_id', 'unknown')
            logger.warning(f"Article scheduler lock already held by session {existing_session_id}")
            return ArticleSchedulerStartResponse(
                success=False,
                message=f"Article scheduler is already running (session: {existing_session_id})",
                status=_article_scheduler_state.get_status()
            )
        
        logger.info(f"Acquired article scheduler lock for session {session_id}")
        
    except Exception as e:
        logger.error(f"Failed to acquire database lock: {e}")
        return ArticleSchedulerStartResponse(
            success=False,
            message=f"Failed to acquire lock: {str(e)}"
        )
    
    try:
        # Get articles from the analysis queue using the existing repository logic
        # This ensures we use the same source of truth as the rest of the application
        cursor = database.conn.cursor()
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
        
        # Filter only pending articles and limit to config.article_count
        all_articles = []
        for row in cursor.fetchall():
            all_articles.append({
                "id": row[0],
                "title": row[1],
                "page_id": row[2],
                "revision_id": row[3],
                "source": row[4],
                "source_details": row[5],
                "priority": row[6],
                "added_at": row[7],
                "status": row[8]
            })
        
        # Filter pending articles and limit
        pending_articles = [a for a in all_articles if a['status'] == 'pending'][:config.article_count]
        
        if not pending_articles:
            return ArticleSchedulerStartResponse(
                success=False,
                message="No pending articles available in the analysis queue"
            )
        
        articles = pending_articles
        
        # Generate session ID
        session_id = f"article_scheduler_{uuid.uuid4().hex[:8]}"
        _article_scheduler_state.session_id = session_id
        
        # Reset state
        _article_scheduler_state.reset()
        _article_scheduler_state.session_id = session_id
        
        # Start processing in background
        async def run_processing():
            await process_articles_queue(
                articles=articles,
                config=config,
                database=database,
                wikipedia_session=wikipedia_session,
                event_manager=event_manager,
                session_id=session_id,
                EventType=EventType
            )
        
        # Create background task
        _article_scheduler_state._task = asyncio.create_task(run_processing())
        
        return ArticleSchedulerStartResponse(
            success=True,
            message=f"Started processing {len(articles)} articles",
            session_id=session_id,
            status=_article_scheduler_state.get_status()
        )
        
    except Exception as e:
        logger.error(f"Failed to start article scheduler: {e}", exc_info=True)
        
        # Release lock on error using existing mechanism
        try:
            if session_id:
                database.release_automation_lock(session_id)
        except Exception as lock_error:
            logger.error(f"Failed to release lock on error: {lock_error}")
        
        return ArticleSchedulerStartResponse(
            success=False,
            message=f"Failed to start article scheduler: {str(e)}"
        )

@router.post("/pause")
async def pause_article_scheduler(
    database = Depends(get_database),
    EventType = Depends(get_event_type)
):
    """
    Pause the article scheduler.

    The scheduler will stop processing new articles but can be resumed.
    Already processed articles are not affected.
    """
    if not _article_scheduler_state.is_active:
        return {
            "success": False,
            "message": "Article scheduler is not running"
        }

    if _article_scheduler_state.is_paused:
        return {
            "success": False,
            "message": "Article scheduler is already paused"
        }

    _article_scheduler_state.is_paused = True
    
    # Emit pause event if event manager available
    try:
        event_manager = get_event_manager()
        if event_manager and EventType:
            await event_manager.emit(
                EventType.AUTOMATION_PAUSED,
                {"session_id": _article_scheduler_state.session_id}
            )
    except Exception as e:
        logger.warning(f"Failed to emit pause event: {e}")
    
    return {
        "success": True,
        "message": "Article scheduler paused",
        "status": _article_scheduler_state.get_status()
    }

@router.post("/resume")
async def resume_article_scheduler(
    database = Depends(get_database),
    EventType = Depends(get_event_type)
):
    """
    Resume the article scheduler.

    The scheduler will continue processing from where it left off.
    """
    if not _article_scheduler_state.is_active:
        return {
            "success": False,
            "message": "Article scheduler is not running"
        }

    if not _article_scheduler_state.is_paused:
        return {
            "success": False,
            "message": "Article scheduler is not paused"
        }

    _article_scheduler_state.is_paused = False
    
    return {
        "success": True,
        "message": "Article scheduler resumed",
        "status": _article_scheduler_state.get_status()
    }

@router.post("/stop")
async def stop_article_scheduler(
    database = Depends(get_database),
    EventType = Depends(get_event_type)
):
    """
    Stop the article scheduler.
    
    The scheduler will stop processing and cannot be resumed.
    Already processed articles remain in their final state.
    """
    if not _article_scheduler_state.is_active:
        return {
            "success": False,
            "message": "Article scheduler is not running"
        }
    
    # Set stop event
    _article_scheduler_state._stop_event.set()
    
    # Cancel the background task if it exists
    if _article_scheduler_state._task:
        _article_scheduler_state._task.cancel()
    
    # Emit stop event if event manager available
    try:
        event_manager = get_event_manager()
        if event_manager and EventType:
            await event_manager.emit(
                EventType.AUTOMATION_STOPPED,
                {"session_id": _article_scheduler_state.session_id}
            )
    except Exception as e:
        logger.warning(f"Failed to emit stop event: {e}")
    
    # Release database lock using existing mechanism
    try:
        if _article_scheduler_state.session_id:
            database.release_automation_lock(_article_scheduler_state.session_id)
            logger.info(f"Released article scheduler lock for session {_article_scheduler_state.session_id}")
    except Exception as e:
        logger.error(f"Failed to release database lock: {e}")
    
    # Wait a moment for cleanup
    await asyncio.sleep(0.5)
    
    # Reset state
    _article_scheduler_state.reset()
    
    return {
        "success": True,
        "message": "Article scheduler stopped",
        "status": _article_scheduler_state.get_status()
    }

@router.get("/articles")
async def get_scheduled_articles():
    """
    Get the list of articles currently being processed with their progress.
    
    Returns detailed progress information for each article in the current batch.
    """
    if not _article_scheduler_state.is_active:
        return {
            "success": True,
            "articles": [],
            "message": "No active processing session"
        }
    
    articles = []
    for title, progress in _article_scheduler_state.article_progress.items():
        articles.append({
            "title": title,
            "status": progress.status,
            "current_step": progress.current_step,
            "progress": progress.progress,
            "started_at": progress.started_at,
            "completed_at": progress.completed_at,
            "error_message": progress.error_message
        })
    
    return {
        "success": True,
        "articles": articles,
        "total": len(articles)
    }