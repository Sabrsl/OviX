"""
OVIX Backend API - Publication Routes

Handles article publication using the existing Publisher.
"""

import logging
import uuid
import os
import asyncio
import json
from typing import Optional, Dict, Any, Union
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime

# Import AnalysisStatus for updating analyzed tracker
from wikipedia_maintenance.utils.analyzed_tracker import AnalysisStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Models
# ============================================================================

class PublicationValidationRequest(BaseModel):
    """Publication validation request."""
    article_title: str
    corrected_content: str
    original_content: str = ""  # Optional, will be fetched if needed
    summary: str
    dry_run: bool = True


class PublicationRequest(BaseModel):
    """Publication request."""
    article_title: str
    corrected_content: str
    original_content: str = ""  # Optional, will be fetched if needed
    summary: str
    dry_run: bool = True


class PublicationResponse(BaseModel):
    """Publication response."""
    success: bool
    publication_id: str
    status: str
    message: str


class PublicationStatusResponse(BaseModel):
    """Publication status response."""
    publication_id: str
    status: str
    message: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    revision_id: Optional[Union[int, str]] = None  # Accept both int and str for backward compatibility
    diff: Optional[str] = None


# ============================================================================
# Publication Job Management
# ============================================================================

# In-memory publication job storage
_publication_jobs: Dict[str, Dict[str, Any]] = {}


def create_publication_job(article_title: str, dry_run: bool) -> str:
    """Create a new publication job."""
    publication_id = str(uuid.uuid4())
    
    _publication_jobs[publication_id] = {
        "id": publication_id,
        "article_title": article_title,
        "dry_run": dry_run,
        "status": "pending",
        "message": "Publication queued",
        "started_at": None,
        "completed_at": None,
        "error": None,
        "revision_id": None,
        "diff": None
    }
    
    return publication_id


def update_publication_job(publication_id: str, **kwargs):
    """Update publication job status."""
    if publication_id in _publication_jobs:
        _publication_jobs[publication_id].update(kwargs)


def get_publication_job(publication_id: str) -> Optional[Dict[str, Any]]:
    """Get publication job."""
    return _publication_jobs.get(publication_id)


# ============================================================================
# Dependencies
# ============================================================================

def get_wikipedia_session():
    """Get current Wikipedia session."""
    from backend.api.routes.auth import get_wikipedia_session as get_session
    return get_session()


def get_kill_switch():
    """Get kill switch manager."""
    try:
        from backend.api.main import get_kill_switch
        return get_kill_switch()
    except Exception as e:
        logger.warning(f"Kill switch manager not available: {e}")
        return None


def get_published_tracker():
    """Get published tracker."""
    from backend.api.main import get_published_tracker
    return get_published_tracker()


def get_database():
    """Get database."""
    try:
        from backend.api.main import get_database
        return get_database()
    except Exception as e:
        logger.warning(f"Database not available: {e}")
        return None


def get_analyzed_tracker():
    """Get analyzed tracker."""
    from backend.api.main import get_analyzed_tracker
    return get_analyzed_tracker()


# ============================================================================
# Publication Worker
# ============================================================================

async def run_publication_worker(
    publication_id: str,
    article_title: str,
    corrected_content: str,
    summary: str,
    dry_run: bool,
    original_content: str,
    publisher
):
    """
    Background worker to run publication.
    
    This function uses the existing Publisher to publish the article
    while respecting all safety checks (Kill Switch, throttling, etc.).
    """
    try:
        # Update job status
        update_publication_job(
            publication_id,
            status="running",
            message="Starting publication",
            started_at=datetime.now().isoformat()
        )
        
        # Check Kill Switch BEFORE publication
        kill_switch = get_kill_switch()
        if kill_switch and kill_switch.is_enabled():
            state = kill_switch.get_state()
            raise Exception(
                f"Publication blocked: Kill switch enabled. "
                f"Reason: {state.reason}, Source: {state.trigger_source}"
            )
        
        # Update publisher settings
        publisher.set_dry_run(dry_run)
        
        # Generate detailed edit summary with URL mapping for dead links
        try:
            import re
            # Extract dead link replacements from the diff
            dead_link_mapping = []
            error_codes = set()
            
            # Find all web.archive.org URLs in corrected content
            archive_pattern = r'https://web\.archive\.org/web/(\d+)/https?://([^/]+)'
            archive_matches = re.findall(archive_pattern, corrected_content)
            
            # Extract domain names for shorter display (without www.)
            for timestamp, domain in archive_matches:
                # Remove www. if present
                clean_domain = domain.replace('www.', '')
                dead_link_mapping.append(f"{clean_domain} → web.archive.org/{timestamp}")
            
            # Extract HTTP error codes from original content if available
            if original_content:
                # Look for common HTTP error codes mentioned in comments or context
                error_pattern = r'(?:HTTP\s*|status\s*|error\s*)[\'":\s]*(40[0-9]|41[0-9]|50[0-9])'
                error_matches = re.findall(error_pattern, original_content, re.IGNORECASE)
                error_codes.update(error_matches)
            
            # Default error codes if none found
            if not error_codes:
                error_codes = {'404', '410'}  # Common dead link codes
            
            # Generate summary based on findings
            if dead_link_mapping:
                # Format: "Correction liens morts 404 - 410 - fix Vérifiabilité : domain1 → archive1, domain2 → archive2... - actions réalisées dans le cadre de tests"
                error_codes_str = " - ".join(sorted(error_codes))
                links_str = ", ".join(dead_link_mapping[:2])  # Limit to 2 links
                if len(dead_link_mapping) > 2:
                    links_str += "..."
                summary = f"Correction liens morts {error_codes_str} - fix [[Wikipédia:Vérifiabilité|Vérifiabilité]] : {links_str} - actions réalisées dans le cadre de tests"
                logger.info(f"Generated detailed dead link summary: {summary}")
            else:
                # Fallback to standard summary generation
                professional_summary = publisher.generate_edit_summary(
                    num_corrections=1,
                    correction_types=['correction']
                )
                summary = professional_summary
                logger.info(f"Generated standard summary: {summary}")
                
        except Exception as e:
            logger.warning(f"Could not generate detailed summary, using provided: {e}")
            # Use provided summary as fallback
        
        # Perform publication
        update_publication_job(
            publication_id,
            message="Publishing to Wikipedia"
        )
        
        success, revision_id = publisher.publish(
            page_title=article_title,
            content=corrected_content,
            summary=summary
        )
        
        if not success:
            raise Exception(f"Publication failed: {revision_id}")
        
        # Track publication
        published_tracker = get_published_tracker()
        if published_tracker:
            published_tracker.mark_as_published(
                article_title=article_title,
                category="unknown",
                mode="api",
                summary=summary,
                revision_id=int(revision_id) if revision_id.isdigit() else None
            )

        # Update database status to published
        database = get_database()
        if database:
            try:
                cursor = database.conn.cursor()
                cursor.execute("""
                    UPDATE analysis_results 
                    SET status = 'published',
                        revision_id = ?,
                        summary = ?,
                        published_at = ?,
                        human_verified = 1
                    WHERE article_title = ?
                """, (
                    int(revision_id) if revision_id.isdigit() else None,
                    summary,
                    datetime.now().isoformat(),
                    article_title
                ))
                database.conn.commit()
                logger.info(f"Updated database status to 'published' for article '{article_title}'")
            except Exception as e:
                logger.error(f"Failed to update database for article '{article_title}': {e}")

        # Update analyzed tracker status to published
        analyzed_tracker = get_analyzed_tracker()
        if analyzed_tracker:
            try:
                record = analyzed_tracker.get_record(article_title)
                if record:
                    # Update the status to published with existing data
                    analyzed_tracker.record_analysis(
                        title=article_title,
                        page_id=record.page_id,
                        revision_id=record.revision_id,
                        status=AnalysisStatus.PUBLISHED,
                        score=record.score,
                        decision=record.decision,
                        mode=record.mode,
                        changes_count=record.changes_count,
                        summary=summary,
                        original_content=record.original_content,
                        corrected_content=record.corrected_content,
                        character_count=record.character_count,
                        total_links=record.total_links,
                        dead_links_count=record.dead_links_count,
                        corrected_links_count=record.corrected_links_count,
                        human_verified=True,  # Manual publication implies human verification
                        manual_review_urls=record.manual_review_urls
                    )
                    logger.info(f"Updated analyzed tracker status to 'published' for article '{article_title}'")
                else:
                    logger.warning(f"Article '{article_title}' not found in analyzed tracker, cannot update status")
            except Exception as e:
                logger.error(f"Failed to update analyzed tracker for '{article_title}': {e}")

        # Update article status in the analysis queue (remove or mark as published)
        from wikipedia_maintenance.utils.database import DatabaseManager
        try:
            project_root = os.environ.get('PROJECT_ROOT')
            if project_root:
                db_path = str(Path(project_root) / "data" / "wikipedia_maintenance.db")
                db = DatabaseManager(db_path)
            else:
                db = DatabaseManager()
            
            cursor = db.conn.cursor()

            # Check if article exists in queue before deletion
            cursor.execute("SELECT id FROM articles_to_analyze WHERE title = ?", (article_title,))
            exists = cursor.fetchone()

            if exists:
                # Remove from queue since it's published
                cursor.execute("DELETE FROM articles_to_analyze WHERE title = ?", (article_title,))
                db.conn.commit()
                logger.info(f"Removed published article '{article_title}' from analysis queue (ID: {exists[0]})")
            else:
                logger.warning(f"Article '{article_title}' not found in analysis queue for deletion")
        except Exception as e:
            logger.error(f"Failed to remove published article '{article_title}' from analysis queue: {e}", exc_info=True)
        
        # Update job with success
        update_publication_job(
            publication_id,
            status="completed",
            message="Publication successful",
            completed_at=datetime.now().isoformat(),
            revision_id=int(revision_id) if revision_id and revision_id.isdigit() else None
        )
        
        logger.info(f"Publication {publication_id} completed for article {article_title}")
        
    except Exception as e:
        logger.error(f"Publication {publication_id} failed: {e}", exc_info=True)
        update_publication_job(
            publication_id,
            status="failed",
            message=f"Publication failed: {str(e)}",
            completed_at=datetime.now().isoformat(),
            error=str(e)
        )


# ============================================================================
# Routes
# ============================================================================

@router.get("/pending")
async def get_pending_publications():
    """
    Get all pending publications.

    Returns a list of publication jobs that are currently pending or running.
    """
    try:
        pending_jobs = []

        for job_id, job in _publication_jobs.items():
            if job["status"] in ["pending", "running"]:
                pending_jobs.append({
                    "publication_id": job_id,
                    "article_title": job["article_title"],
                    "status": job["status"],
                    "message": job["message"],
                    "started_at": job.get("started_at"),
                    "dry_run": job.get("dry_run", True)
                })

        return {
            "success": True,
            "count": len(pending_jobs),
            "publications": pending_jobs
        }

    except Exception as e:
        logger.error(f"Failed to get pending publications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get pending publications: {str(e)}")

@router.post("/validate")
async def validate_publication(
    request: PublicationValidationRequest,
    session: dict = Depends(get_wikipedia_session),
    kill_switch = Depends(get_kill_switch)
):
    """
    Validate publication without actually publishing.
    
    Performs all safety checks (Kill Switch, authentication, etc.)
    without making actual changes to Wikipedia.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        publisher = session.get("publisher")
        if not publisher:
            raise HTTPException(status_code=500, detail="Publisher not initialized")
        
        # Check Kill Switch (if available)
        if kill_switch and kill_switch.is_enabled():
            state = kill_switch.get_state()
            return {
                "success": False,
                "valid": False,
                "reason": "kill_switch_enabled",
                "message": f"Kill switch enabled: {state.reason}",
                "details": {
                    "trigger_source": state.trigger_source,
                    "requested_by": state.requested_by,
                    "requested_at": state.requested_at
                }
            }
        
        # Check authentication
        if not hasattr(publisher, 'authenticated') or not publisher.authenticated:
            return {
                "success": False,
                "valid": False,
                "reason": "not_authenticated",
                "message": "Publisher not authenticated with Wikipedia"
            }
        
        # Check dry-run mode
        if not request.dry_run:
            return {
                "success": True,
                "valid": True,
                "warning": "production_mode",
                "message": "Validation passed, but this will publish to Wikipedia"
            }
        
        return {
            "success": True,
            "valid": True,
            "message": "Validation passed - ready for publication"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publication validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/publish", response_model=PublicationResponse)
async def publish_article(
    request: PublicationRequest,
    background_tasks: BackgroundTasks,
    session: dict = Depends(get_wikipedia_session),
    kill_switch = Depends(get_kill_switch)
):
    """
    Publish article to Wikipedia.
    
    Creates a background job to publish the article using the existing
    Publisher while respecting all safety checks.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        publisher = session.get("publisher")
        if not publisher:
            raise HTTPException(status_code=500, detail="Publisher not initialized")
        
        # Check Kill Switch BEFORE starting job (if available)
        if kill_switch and kill_switch.is_enabled():
            state = kill_switch.get_state()
            raise HTTPException(
                status_code=403,
                detail=f"Publication blocked: Kill switch enabled. Reason: {state.reason}"
            )
        
        # Create publication job
        publication_id = create_publication_job(request.article_title, request.dry_run)
        
        # Start background worker
        background_tasks.add_task(
            run_publication_worker,
            publication_id,
            request.article_title,
            request.corrected_content,
            request.summary,
            request.dry_run,
            request.original_content,
            publisher
        )
        
        logger.info(f"Started publication {publication_id} for article {request.article_title}")
        
        return PublicationResponse(
            success=True,
            publication_id=publication_id,
            status="pending",
            message="Publication started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start publication: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start publication: {str(e)}")


@router.get("/{publication_id}", response_model=PublicationStatusResponse)
async def get_publication_status(publication_id: str):
    """
    Get publication job status.

    Returns the current status of a publication job.
    """
    try:
        job = get_publication_job(publication_id)

        if not job:
            raise HTTPException(status_code=404, detail="Publication job not found")

        return PublicationStatusResponse(
            publication_id=job["id"],
            status=job["status"],
            message=job["message"],
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            error=job.get("error"),
            revision_id=job.get("revision_id"),
            diff=job.get("diff")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get publication status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/{publication_id}/stream")
async def stream_publication_status(publication_id: str):
    """
    Stream publication status updates using Server-Sent Events (SSE).

    This endpoint sends real-time updates when the publication status changes.
    """
    async def event_stream():
        job = get_publication_job(publication_id)
        if not job:
            yield f"data: {json.dumps({'error': 'Publication job not found'})}\n\n"
            return

        # Send initial status
        yield f"data: {json.dumps({'status': job['status'], 'message': job['message']})}\n\n"

        # If already completed or failed, send final status and close
        if job['status'] in ['completed', 'failed']:
            yield f"data: {json.dumps({'status': job['status'], 'message': job['message'], 'revision_id': job.get('revision_id'), 'error': job.get('error')})}\n\n"
            return

        # Wait for status changes
        last_status = job['status']
        max_wait = 300  # 5 minutes max
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < max_wait:
            await asyncio.sleep(2)  # Check every 2 seconds

            current_job = get_publication_job(publication_id)
            if not current_job:
                yield f"data: {json.dumps({'error': 'Publication job not found'})}\n\n"
                return

            if current_job['status'] != last_status:
                last_status = current_job['status']
                yield f"data: {json.dumps({'status': current_job['status'], 'message': current_job['message'], 'revision_id': current_job.get('revision_id'), 'error': current_job.get('error')})}\n\n"

                # Close stream if completed or failed
                if current_job['status'] in ['completed', 'failed']:
                    break

        # Timeout
        yield f"data: {json.dumps({'error': 'Timeout waiting for publication'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
