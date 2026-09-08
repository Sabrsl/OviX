"""
Domain Enrichment API endpoints.

Provides REST API endpoints for:
- Starting/stopping/pausing/resuming enrichment
- Getting progress and status
- Previewing changes
- Writing to YAML
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from wikipedia_maintenance.utils.domain_enrichment_service import (
    DomainEnrichmentService,
    CategoryConfig,
    EnrichmentState,
)
from wikipedia_maintenance.utils.wikipedia_api import WikipediaAPIClient
from wikipedia_maintenance.utils.wikidata_client import WikidataClient
from wikipedia_maintenance.utils.api_throttler import APIThrottler
from wikipedia_maintenance.utils.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Domain Enrichment"])

# Global service instance
_enrichment_service: Optional[DomainEnrichmentService] = None


def get_enrichment_service(force_reset: bool = False) -> DomainEnrichmentService:
    """Get or create the global enrichment service instance.
    
    Args:
        force_reset: If True, force recreation of the service instance
    """
    global _enrichment_service
    if force_reset or _enrichment_service is None:
        # Initialize clients
        config = Config()
        wikipedia_client = WikipediaAPIClient(language=config.wikipedia.lang)
        wikidata_client = WikidataClient()
        throttler = APIThrottler()
        
        wikipedia_client.set_throttler(throttler)
        wikidata_client.throttler = throttler
        
        _enrichment_service = DomainEnrichmentService(
            wikipedia_client=wikipedia_client,
            wikidata_client=wikidata_client,
            throttler=throttler,
        )
    return _enrichment_service


# ----------------------------------------------------------------------
# Request/Response Models
# ----------------------------------------------------------------------


class CategoryConfigRequest(BaseModel):
    """Request model for category configuration."""
    wiki: str
    category: str
    priority: int


class StartEnrichmentRequest(BaseModel):
    """Request model for starting enrichment."""
    categories: List[CategoryConfigRequest]
    dry_run: bool = True
    max_pages: Optional[int] = None
    keep_www: bool = False


class EnrichmentStatusResponse(BaseModel):
    """Response model for enrichment status."""
    state: str
    current_category: Optional[str]
    pages_analyzed: int
    total_pages: int
    skipped: int
    p856_found: int
    new_domains: int
    already_present: int
    conflicts: int
    review_required: int
    errors: int
    started_at: Optional[str]
    completed_at: Optional[str]
    recent_activity: List[str]


class PreviewResponse(BaseModel):
    """Response model for preview.
    
    Summary includes:
    - estimated_total: entries with www variants
    - domains: number of unique domains
    - already_present: already in database
    - conflicts: conflicting entries
    - review_required: entries needing review
    - errors: processing errors
    """
    new_entries: List[dict]
    summary: dict


class WriteYamlRequest(BaseModel):
    """Request model for writing to YAML."""
    entries: List[dict]


# ----------------------------------------------------------------------
# API Endpoints
# ----------------------------------------------------------------------


@router.get("/status")
async def get_status() -> EnrichmentStatusResponse:
    """
    Get current enrichment status and progress.
    
    Returns:
        Current state and progress information
    """
    service = get_enrichment_service()
    progress = service.get_progress()
    
    return EnrichmentStatusResponse(
        state=progress.state.value,
        current_category=progress.current_category,
        pages_analyzed=progress.pages_analyzed,
        total_pages=progress.total_pages,
        skipped=progress.skipped,
        p856_found=progress.p856_found,
        new_domains=progress.new_domains,
        already_present=progress.already_present,
        conflicts=progress.conflicts,
        review_required=progress.review_required,
        errors=progress.errors,
        started_at=progress.started_at.isoformat() if progress.started_at else None,
        completed_at=progress.completed_at.isoformat() if progress.completed_at else None,
        recent_activity=progress.recent_activity,
    )


@router.post("/start")
async def start_enrichment(
    request: StartEnrichmentRequest,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Start the enrichment process.
    
    Args:
        request: Enrichment configuration
        background_tasks: FastAPI background tasks
        
    Returns:
        Success message
    """
    service = get_enrichment_service()
    
    # Check if service is already running
    if service.get_state() != EnrichmentState.IDLE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start: current state is {service.get_state().value}"
        )
    
    # Convert request models to domain models
    categories = [
        CategoryConfig(wiki=cat.wiki, category=cat.category, priority=cat.priority)
        for cat in request.categories
    ]
    
    # Start enrichment in background
    def run_enrichment():
        try:
            service.start_enrichment(categories=categories, dry_run=request.dry_run, max_pages=request.max_pages, keep_www=request.keep_www)
        except Exception as e:
            logger.error(f"Enrichment background task failed: {e}", exc_info=True)
    
    background_tasks.add_task(run_enrichment)
    
    return {
        "success": True,
        "message": "Enrichment started",
        "dry_run": request.dry_run,
        "categories_count": len(categories),
    }


@router.post("/pause")
async def pause_enrichment() -> dict:
    """
    Pause the enrichment process.
    
    Returns:
        Success message
    """
    service = get_enrichment_service()
    
    if service.get_state() != EnrichmentState.RUNNING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause: current state is {service.get_state().value}"
        )
    
    service.pause()
    
    return {
        "success": True,
        "message": "Enrichment paused",
    }


@router.post("/resume")
async def resume_enrichment() -> dict:
    """
    Resume a paused enrichment process.
    
    Returns:
        Success message
    """
    service = get_enrichment_service()
    
    if service.get_state() != EnrichmentState.PAUSED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume: current state is {service.get_state().value}"
        )
    
    service.resume()
    
    return {
        "success": True,
        "message": "Enrichment resumed",
    }


@router.post("/cancel")
async def cancel_enrichment() -> dict:
    """
    Cancel the enrichment process.
    
    Returns:
        Success message
    """
    service = get_enrichment_service()
    
    if service.get_state() not in [EnrichmentState.RUNNING, EnrichmentState.PAUSED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel: current state is {service.get_state().value}"
        )
    
    service.cancel()
    
    return {
        "success": True,
        "message": "Enrichment cancelled",
    }


@router.get("/preview")
async def get_preview() -> PreviewResponse:
    """
    Get a preview of changes that would be made.
    
    Returns:
        Preview information with new entries and summary
    """
    service = get_enrichment_service()
    
    if service.get_state() not in [EnrichmentState.COMPLETED, EnrichmentState.FAILED, EnrichmentState.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot get preview: current state is {service.get_state().value}"
        )
    
    preview = service.get_preview()
    
    return PreviewResponse(
        new_entries=preview['new_entries'],
        summary=preview['summary'],
    )


@router.post("/write")
async def write_to_yaml(request: WriteYamlRequest) -> dict:
    """
    Write approved entries to case_normalization_data.yaml.
    
    Args:
        request: Entries to write
        
    Returns:
        Success message
    """
    service = get_enrichment_service()
    
    # Convert dict entries to DomainEntry objects
    from wikipedia_maintenance.utils.domain_enrichment_service import DomainEntry, EntryStatus
    
    entries = [
        DomainEntry(
            domain=entry['domain'],
            site_name=entry['site_name'],
            status=EntryStatus.NEW,
            original_url=entry.get('original_url'),
            page_title=entry.get('page_title'),
            qid=entry.get('qid'),
        )
        for entry in request.entries
    ]
    
    success, entries_added = service.write_to_yaml(entries)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to write to YAML file"
        )
    
    return {
        "success": True,
        "message": f"Successfully wrote {entries_added} entries ({len(entries)} domains with variants) to case_normalization_data.yaml",
        "entries_count": entries_added,
        "domains_count": len(entries),
    }


@router.post("/reset")
async def reset_enrichment() -> dict:
    """
    Reset the enrichment service to initial state.
    Clears all progress, results, and tracking data to allow a fresh start.
    Also forces recreation of the service instance to clear in-memory state.
    
    Returns:
        Success message
    """
    # Force recreation of the service instance to clear in-memory state
    service = get_enrichment_service(force_reset=True)
    
    # The reset() method is called in __init__ when the instance is recreated,
    # but we call it explicitly to be sure and to clear any files
    service.reset()
    
    return {
        "success": True,
        "message": "Enrichment service reset to initial state",
    }