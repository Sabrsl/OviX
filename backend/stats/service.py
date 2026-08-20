"""
StatsService - Business logic layer for statistics.

This service is responsible for business logic and aggregations.
It uses the repository for database access and applies business rules.
"""

import logging
from typing import Optional, Dict, Any
from .repository import StatsRepository
from .schemas import (
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
    SystemStats,
    StatsResponse
)

logger = logging.getLogger(__name__)


class StatsService:
    """
    Centralized statistics service.
    
    Single source of truth for all statistics business logic.
    All components should use this service instead of direct database access.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the statistics service.
        
        Args:
            db_path: Path to the SQLite database. If None, uses default path.
        """
        self.repository = StatsRepository(db_path)
        logger.info("StatsService initialized")

    def get_article_stats(self) -> ArticleStats:
        """
        Get article statistics.
        
        Returns:
            ArticleStats object with article statistics.
        """
        try:
            stats_dict = self.repository.get_article_stats()
            return ArticleStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting article stats: {e}", exc_info=True)
            return ArticleStats()

    def get_analysis_stats(self) -> AnalysisStats:
        """
        Get analysis statistics.
        
        Returns:
            AnalysisStats object with analysis statistics.
        """
        try:
            stats_dict = self.repository.get_analysis_stats()
            return AnalysisStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting analysis stats: {e}", exc_info=True)
            return AnalysisStats()

    def get_publication_stats(self) -> PublicationStats:
        """
        Get publication statistics.
        
        Returns:
            PublicationStats object with publication statistics.
        """
        try:
            stats_dict = self.repository.get_publication_stats()
            return PublicationStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting publication stats: {e}", exc_info=True)
            return PublicationStats()

    def get_database_stats(self) -> DatabaseStats:
        """
        Get database statistics.
        
        Returns:
            DatabaseStats object with database statistics.
        """
        try:
            stats_dict = self.repository.get_database_stats()
            return DatabaseStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting database stats: {e}", exc_info=True)
            return DatabaseStats()

    def get_correction_stats(self) -> CorrectionStats:
        """
        Get correction statistics.
        
        Returns:
            CorrectionStats object with correction statistics.
        """
        try:
            stats_dict = self.repository.get_correction_stats()
            return CorrectionStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting correction stats: {e}", exc_info=True)
            return CorrectionStats()

    def get_queue_stats(self) -> QueueStats:
        """
        Get queue statistics.
        
        Returns:
            QueueStats object with queue statistics.
        """
        try:
            stats_dict = self.repository.get_queue_stats()
            return QueueStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}", exc_info=True)
            return QueueStats()

    def get_quality_stats(self) -> QualityStats:
        """
        Get quality statistics.
        
        Returns:
            QualityStats object with quality statistics.
        """
        try:
            stats_dict = self.repository.get_quality_stats()
            return QualityStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting quality stats: {e}", exc_info=True)
            return QualityStats()

    def get_pipeline_stats(self) -> PipelineStats:
        """
        Get pipeline statistics.
        
        Returns:
            PipelineStats object with pipeline statistics.
        """
        try:
            stats_dict = self.repository.get_pipeline_stats()
            return PipelineStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting pipeline stats: {e}", exc_info=True)
            return PipelineStats()

    def get_temporal_stats(self) -> TemporalStats:
        """
        Get temporal statistics.
        
        Returns:
            TemporalStats object with temporal statistics.
        """
        try:
            stats_dict = self.repository.get_temporal_stats()
            return TemporalStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting temporal stats: {e}", exc_info=True)
            return TemporalStats()

    def get_error_stats(self) -> ErrorStats:
        """
        Get error statistics.
        
        Returns:
            ErrorStats object with error statistics.
        """
        try:
            stats_dict = self.repository.get_error_stats()
            return ErrorStats(**stats_dict)
        except Exception as e:
            logger.error(f"Error getting error stats: {e}", exc_info=True)
            return ErrorStats()

    def get_system_stats(self) -> SystemStats:
        """
        Get complete system statistics.
        
        Returns:
            SystemStats object with all statistics covering all 8 families.
        """
        try:
            all_stats = self.repository.get_all_stats()
            
            return SystemStats(
                articles=ArticleStats(**all_stats['articles']),
                analysis=AnalysisStats(**all_stats['analysis']),
                publication=PublicationStats(**all_stats['publication']),
                corrections=CorrectionStats(**all_stats['corrections']),
                queue=QueueStats(**all_stats['queue']),
                quality=QualityStats(**all_stats['quality']),
                pipeline=PipelineStats(**all_stats['pipeline']),
                temporal=TemporalStats(**all_stats['temporal']),
                errors=ErrorStats(**all_stats['errors']),
                database=DatabaseStats(**all_stats['database'])
            )
        except Exception as e:
            logger.error(f"Error getting system stats: {e}", exc_info=True)
            return SystemStats()

    def get_stats_response(self) -> StatsResponse:
        """
        Get statistics in standard API response format.
        
        Returns:
            StatsResponse object ready for API serialization.
        """
        try:
            system_stats = self.get_system_stats()
            return StatsResponse(
                success=True,
                stats=system_stats,
                source="database"
            )
        except Exception as e:
            logger.error(f"Error getting stats response: {e}", exc_info=True)
            return StatsResponse(
                success=False,
                stats=SystemStats(),
                source="database_error"
            )

    def get_legacy_format(self) -> Dict[str, Any]:
        """
        Get statistics in legacy format for backward compatibility.
        
        This method returns statistics in the same format as the old /api/history/statistics
        endpoint to allow gradual migration.
        
        Returns:
            Dictionary in legacy format.
        """
        try:
            system_stats = self.get_system_stats()
            
            # Convert to legacy format
            legacy_stats = {
                # Article stats
                'analyzed_total': system_stats.articles.total,
                'analyzed_published': system_stats.articles.published,
                'analyzed_pending': system_stats.articles.pending,
                'analyzed_rejected': system_stats.articles.rejected,
                'analyzed_ignored': system_stats.articles.ignored,
                'analyzed_error': system_stats.articles.error,
                'analyzed_analyzing': 0,  # Not in new schema, default to 0
                
                # Analysis stats
                'dead_links_detected': system_stats.analysis.dead_links_detected,
                'dead_links_corrected': system_stats.analysis.dead_links_corrected,
                
                # Publication stats
                'published_total': system_stats.publication.total,
                'published_recent': system_stats.publication.recent_7d,
                'publication_rate': system_stats.publication.publication_rate,
                
                # Database stats
                'db_articles_total': system_stats.database.articles_total,
                'db_issues_total': system_stats.database.issues_total,
                'db_actions_total': system_stats.database.actions_total,
                
                # Issues by severity
                'issues_by_severity': system_stats.quality.issues_by_severity
            }
            
            logger.info("Legacy format stats generated successfully")
            return legacy_stats
            
        except Exception as e:
            logger.error(f"Error getting legacy format stats: {e}", exc_info=True)
            return {}


# Global service instance
_global_service: Optional[StatsService] = None


def get_stats_service(db_path: Optional[str] = None) -> StatsService:
    """
    Get or create the global stats service instance.
    
    Args:
        db_path: Path to the SQLite database. If None, uses default path.
        
    Returns:
        Global StatsService instance.
    """
    global _global_service
    if _global_service is None:
        _global_service = StatsService(db_path)
    return _global_service


def reset_global_service() -> None:
    """Reset the global stats service instance."""
    global _global_service
    _global_service = None
