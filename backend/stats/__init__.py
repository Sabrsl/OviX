"""
OVIX Backend - Statistics Module

Centralized statistics service with single source of truth (database).
"""

from .service import StatsService
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

__all__ = [
    'StatsService',
    'StatsRepository',
    'ArticleStats',
    'AnalysisStats',
    'PublicationStats',
    'CorrectionStats',
    'QueueStats',
    'QualityStats',
    'PipelineStats',
    'TemporalStats',
    'ErrorStats',
    'DatabaseStats',
    'SystemStats',
    'StatsResponse'
]
