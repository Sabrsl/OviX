"""
Statistics schemas - Centralized data contracts for all statistics.

These schemas define the standard structure for statistics across the entire application.
All components must use these contracts to ensure consistency.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ArticleStats(BaseModel):
    """Statistics about articles."""
    total: int = Field(default=0, description="Total number of articles")
    analyzed: int = Field(default=0, description="Analyzed articles")
    published: int = Field(default=0, description="Published articles")
    pending: int = Field(default=0, description="Pending articles")
    rejected: int = Field(default=0, description="Rejected articles")
    ignored: int = Field(default=0, description="Ignored articles")
    error: int = Field(default=0, description="Articles with errors")
    skipped: int = Field(default=0, description="Skipped articles")


class AnalysisStats(BaseModel):
    """Statistics about article analyses."""
    total: int = Field(default=0, description="Total number of analyses")
    pending: int = Field(default=0, description="Pending analyses")
    running: int = Field(default=0, description="Running analyses")
    completed: int = Field(default=0, description="Completed analyses")
    successful: int = Field(default=0, description="Successful analyses")
    failed: int = Field(default=0, description="Failed analyses")
    cancelled: int = Field(default=0, description="Cancelled analyses")
    success_rate: float = Field(default=0.0, description="Success rate (percentage)")
    failure_rate: float = Field(default=0.0, description="Failure rate (percentage)")
    average_duration: float = Field(default=0.0, description="Average analysis duration in seconds")
    dead_links_detected: int = Field(default=0, description="Total dead links detected")
    dead_links_corrected: int = Field(default=0, description="Total dead links corrected")
    total_links: int = Field(default=0, description="Total links analyzed")
    changes_count: int = Field(default=0, description="Total changes made")
    character_count: int = Field(default=0, description="Total characters analyzed")


class PublicationStats(BaseModel):
    """Statistics about publications."""
    total: int = Field(default=0, description="Total publications")
    successful: int = Field(default=0, description="Successful publications")
    failed: int = Field(default=0, description="Failed publications")
    pending: int = Field(default=0, description="Pending publications")
    cancelled: int = Field(default=0, description="Cancelled publications")
    publication_rate: float = Field(default=0.0, description="Publication rate (percentage)")
    success_rate: float = Field(default=0.0, description="Publication success rate (percentage)")
    recent_24h: int = Field(default=0, description="Publications in last 24 hours")
    recent_7d: int = Field(default=0, description="Publications in last 7 days")
    recent_30d: int = Field(default=0, description="Publications in last 30 days")


class CorrectionStats(BaseModel):
    """Statistics about corrections/modifications."""
    total_corrections: int = Field(default=0, description="Total corrections made")
    typos_fixed: int = Field(default=0, description="Typos fixed")
    formatting_fixed: int = Field(default=0, description="Formatting issues fixed")
    dead_links_detected: int = Field(default=0, description="Dead links detected")
    dead_links_corrected: int = Field(default=0, description="Dead links corrected")
    http_links_corrected: int = Field(default=0, description="HTTP links corrected to HTTPS")


class QueueStats(BaseModel):
    """Statistics about the analysis queue."""
    total: int = Field(default=0, description="Total items in queue")
    pending: int = Field(default=0, description="Pending items")
    processing: int = Field(default=0, description="Processing items")
    completed: int = Field(default=0, description="Completed items")
    failed: int = Field(default=0, description="Failed items")
    cancelled: int = Field(default=0, description="Cancelled items")
    success_rate: float = Field(default=0.0, description="Queue success rate (percentage)")
    average_wait_time: float = Field(default=0.0, description="Average wait time in seconds")


class QualityStats(BaseModel):
    """Statistics about content quality."""
    articles_with_issues: int = Field(default=0, description="Articles with issues")
    articles_without_issues: int = Field(default=0, description="Articles without issues")
    issues_by_severity: Dict[str, int] = Field(default_factory=dict, description="Issues grouped by severity")
    errors_by_type: Dict[str, int] = Field(default_factory=dict, description="Errors grouped by type")
    issue_rate: float = Field(default=0.0, description="Issue rate (percentage)")
    dead_link_rate: float = Field(default=0.0, description="Dead link rate (percentage)")
    correction_rate: float = Field(default=0.0, description="Correction rate (percentage)")


class PipelineStats(BaseModel):
    """Statistics about the automation pipeline."""
    runs: int = Field(default=0, description="Total pipeline runs")
    success: int = Field(default=0, description="Successful pipeline runs")
    failed: int = Field(default=0, description="Failed pipeline runs")
    running: int = Field(default=0, description="Currently running pipeline runs")
    articles_processed: int = Field(default=0, description="Articles processed by pipeline")
    articles_remaining: int = Field(default=0, description="Articles remaining in queue")
    analyses_completed: int = Field(default=0, description="Analyses completed by pipeline")
    publications_completed: int = Field(default=0, description="Publications completed by pipeline")
    pipeline_duration: float = Field(default=0.0, description="Average pipeline duration in seconds")
    average_processing_time: float = Field(default=0.0, description="Average processing time per article in seconds")


class TemporalStats(BaseModel):
    """Time-based statistics."""
    articles_published_today: int = Field(default=0, description="Articles published today")
    analyses_today: int = Field(default=0, description="Analyses completed today")
    corrections_today: int = Field(default=0, description="Corrections made today")
    errors_today: int = Field(default=0, description="Errors occurred today")
    articles_published_7d: int = Field(default=0, description="Articles published in last 7 days")
    analyses_7d: int = Field(default=0, description="Analyses completed in last 7 days")
    corrections_7d: int = Field(default=0, description="Corrections made in last 7 days")
    errors_7d: int = Field(default=0, description="Errors occurred in last 7 days")
    articles_published_30d: int = Field(default=0, description="Articles published in last 30 days")
    analyses_30d: int = Field(default=0, description="Analyses completed in last 30 days")
    corrections_30d: int = Field(default=0, description="Corrections made in last 30 days")
    errors_30d: int = Field(default=0, description="Errors occurred in last 30 days")


class ErrorStats(BaseModel):
    """Statistics about errors."""
    total: int = Field(default=0, description="Total errors")
    today: int = Field(default=0, description="Errors today")
    by_type: Dict[str, int] = Field(default_factory=dict, description="Errors grouped by type")
    by_module: Dict[str, int] = Field(default_factory=dict, description="Errors grouped by module")
    by_stage: Dict[str, int] = Field(default_factory=dict, description="Errors grouped by stage")


class DatabaseStats(BaseModel):
    """Statistics about database content."""
    articles_total: int = Field(default=0, description="Total articles in database")
    issues_total: int = Field(default=0, description="Total issues in database")
    actions_total: int = Field(default=0, description="Total actions in database")
    articles_with_changes: int = Field(default=0, description="Articles with changes")


class SystemStats(BaseModel):
    """Overall system statistics - covers all 8 families."""
    articles: ArticleStats = Field(default_factory=ArticleStats)
    analysis: AnalysisStats = Field(default_factory=AnalysisStats)
    publication: PublicationStats = Field(default_factory=PublicationStats)
    corrections: CorrectionStats = Field(default_factory=CorrectionStats)
    queue: QueueStats = Field(default_factory=QueueStats)
    quality: QualityStats = Field(default_factory=QualityStats)
    pipeline: PipelineStats = Field(default_factory=PipelineStats)
    temporal: TemporalStats = Field(default_factory=TemporalStats)
    errors: ErrorStats = Field(default_factory=ErrorStats)
    database: DatabaseStats = Field(default_factory=DatabaseStats)


class StatsResponse(BaseModel):
    """Standard statistics API response."""
    success: bool
    stats: SystemStats
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    source: str = Field(default="database", description="Source of statistics")


class ComparisonResult(BaseModel):
    """Result of comparing old vs new statistics."""
    success: bool
    old_stats: Dict[str, Any]
    new_stats: Dict[str, Any]
    differences: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
