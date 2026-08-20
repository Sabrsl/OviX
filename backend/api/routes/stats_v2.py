"""
Stats V2 API Routes - Centralized statistics endpoints.

These endpoints use the new StatsService as the single source of truth.
They provide the same statistics as the old endpoints but with a centralized architecture.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Optional

from backend.stats import StatsService, StatsResponse
from backend.stats.schemas import (
    ArticleStats,
    AnalysisStats,
    PublicationStats,
    CorrectionStats,
    QueueStats,
    QualityStats,
    PipelineStats,
    TemporalStats,
    ErrorStats,
    DatabaseStats,
    SystemStats
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats/v2", tags=["stats-v2"])


@router.get("/system", response_model=StatsResponse)
async def get_system_stats_v2():
    """
    Get complete system statistics (V2).
    
    This endpoint uses the centralized StatsService as the single source of truth.
    It replaces the old /api/history/statistics and /api/system/status endpoints.
    
    Returns:
        StatsResponse with all system statistics.
    """
    try:
        service = StatsService()
        return service.get_stats_response()
    except Exception as e:
        logger.error(f"Error getting system stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get system stats: {str(e)}")


@router.get("/articles", response_model=ArticleStats)
async def get_article_stats_v2():
    """
    Get article statistics (V2).
    
    Returns:
        ArticleStats with article counts by status.
    """
    try:
        service = StatsService()
        return service.get_article_stats()
    except Exception as e:
        logger.error(f"Error getting article stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get article stats: {str(e)}")


@router.get("/analysis", response_model=AnalysisStats)
async def get_analysis_stats_v2():
    """
    Get analysis statistics (V2).
    
    Returns:
        AnalysisStats with analysis statistics.
    """
    try:
        service = StatsService()
        return service.get_analysis_stats()
    except Exception as e:
        logger.error(f"Error getting analysis stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get analysis stats: {str(e)}")


@router.get("/publication", response_model=PublicationStats)
async def get_publication_stats_v2():
    """
    Get publication statistics (V2).
    
    Returns:
        PublicationStats with publication statistics.
    """
    try:
        service = StatsService()
        return service.get_publication_stats()
    except Exception as e:
        logger.error(f"Error getting publication stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get publication stats: {str(e)}")


@router.get("/database", response_model=DatabaseStats)
async def get_database_stats_v2():
    """
    Get database statistics (V2).
    
    Returns:
        DatabaseStats with database content statistics.
    """
    try:
        service = StatsService()
        return service.get_database_stats()
    except Exception as e:
        logger.error(f"Error getting database stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get database stats: {str(e)}")


@router.get("/corrections", response_model=CorrectionStats)
async def get_correction_stats_v2():
    """
    Get correction statistics (V2).
    
    Returns:
        CorrectionStats with correction/modification statistics.
    """
    try:
        service = StatsService()
        return service.get_correction_stats()
    except Exception as e:
        logger.error(f"Error getting correction stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get correction stats: {str(e)}")


@router.get("/queue", response_model=QueueStats)
async def get_queue_stats_v2():
    """
    Get queue statistics (V2).
    
    Returns:
        QueueStats with queue statistics.
    """
    try:
        service = StatsService()
        return service.get_queue_stats()
    except Exception as e:
        logger.error(f"Error getting queue stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get queue stats: {str(e)}")


@router.get("/quality", response_model=QualityStats)
async def get_quality_stats_v2():
    """
    Get quality statistics (V2).
    
    Returns:
        QualityStats with quality statistics.
    """
    try:
        service = StatsService()
        return service.get_quality_stats()
    except Exception as e:
        logger.error(f"Error getting quality stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get quality stats: {str(e)}")


@router.get("/pipeline", response_model=PipelineStats)
async def get_pipeline_stats_v2():
    """
    Get pipeline statistics (V2).
    
    Returns:
        PipelineStats with pipeline statistics.
    """
    try:
        service = StatsService()
        return service.get_pipeline_stats()
    except Exception as e:
        logger.error(f"Error getting pipeline stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get pipeline stats: {str(e)}")


@router.get("/temporal", response_model=TemporalStats)
async def get_temporal_stats_v2():
    """
    Get temporal statistics (V2).
    
    Returns:
        TemporalStats with time-based statistics.
    """
    try:
        service = StatsService()
        return service.get_temporal_stats()
    except Exception as e:
        logger.error(f"Error getting temporal stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get temporal stats: {str(e)}")


@router.get("/errors", response_model=ErrorStats)
async def get_error_stats_v2():
    """
    Get error statistics (V2).
    
    Returns:
        ErrorStats with error statistics.
    """
    try:
        service = StatsService()
        return service.get_error_stats()
    except Exception as e:
        logger.error(f"Error getting error stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get error stats: {str(e)}")


@router.get("/legacy")
async def get_legacy_stats_v2():
    """
    Get statistics in legacy format (V2).
    
    This endpoint returns statistics in the same format as the old /api/history/statistics
    endpoint to allow gradual migration without breaking existing consumers.
    
    Returns:
        Dictionary in legacy format.
    """
    try:
        service = StatsService()
        legacy_stats = service.get_legacy_format()
        return {
            "success": True,
            "stats": legacy_stats
        }
    except Exception as e:
        logger.error(f"Error getting legacy stats V2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get legacy stats: {str(e)}")
