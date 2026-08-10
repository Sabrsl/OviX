"""
Automation report generator for Wikipedia maintenance.

This module provides functionality to generate and store reports after each
automation execution, tracking statistics and performance metrics.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AutomationReport:
    """Report data for a single automation execution."""
    report_id: str
    start_time: str  # ISO format
    end_time: str  # ISO format
    duration_seconds: float
    
    # Article counts
    articles_retrieved: int
    articles_excluded_published: int
    articles_excluded_analyzed: int
    articles_excluded_length: int
    articles_excluded_duplicates: int
    articles_analyzed: int
    articles_published: int
    articles_rejected: int
    articles_ignored: int
    articles_error: int
    
    # AI-specific metrics
    gemini_calls: int = 0
    gemini_tokens_input: int = 0
    gemini_tokens_output: int = 0
    gemini_cost_usd: float = 0.0
    
    # Interruption statistics
    total_interruptions: int = 0
    total_interruption_duration_seconds: float = 0.0
    resolved_interruptions: int = 0
    unresolved_interruptions: int = 0
    was_resumed: bool = False
    
    # Errors
    errors: List[str] = None
    
    # Configuration
    mode: str = "regex"  # "IA" or "regex"
    max_articles_requested: int = 0
    character_limit: int = 0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class ReportGenerator:
    """
    Generator and manager for automation reports.
    
    Stores reports in JSON format for historical tracking and analysis.
    """
    
    def __init__(self, reports_dir: str = "data/automation_reports"):
        """
        Initialize the report generator.
        
        Args:
            reports_dir: Directory to store report files
        """
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"ReportGenerator initialized: {self.reports_dir}")
    
    def _generate_report_id(self) -> str:
        """Generate a unique report ID based on timestamp."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _get_report_file_path(self, report_id: str) -> Path:
        """Get the file path for a report."""
        return self.reports_dir / f"report_{report_id}.json"
    
    def create_report(
        self,
        start_time: datetime,
        end_time: datetime,
        articles_retrieved: int,
        articles_excluded_published: int,
        articles_excluded_analyzed: int,
        articles_excluded_length: int,
        articles_excluded_duplicates: int,
        articles_analyzed: int,
        articles_published: int,
        articles_rejected: int,
        articles_ignored: int,
        articles_error: int,
        mode: str = "regex",
        max_articles_requested: int = 0,
        character_limit: int = 0,
        gemini_calls: int = 0,
        gemini_tokens_input: int = 0,
        gemini_tokens_output: int = 0,
        gemini_cost_usd: float = 0.0,
        errors: Optional[List[str]] = None,
        total_interruptions: int = 0,
        total_interruption_duration_seconds: float = 0.0,
        resolved_interruptions: int = 0,
        unresolved_interruptions: int = 0,
        was_resumed: bool = False
    ) -> AutomationReport:
        """
        Create an automation report.
        
        Args:
            start_time: Start time of automation
            end_time: End time of automation
            articles_retrieved: Total articles retrieved from Wikipedia
            articles_excluded_published: Articles excluded (already published)
            articles_excluded_analyzed: Articles excluded (already analyzed)
            articles_excluded_length: Articles excluded (too long)
            articles_excluded_duplicates: Articles excluded (duplicates)
            articles_analyzed: Articles successfully analyzed
            articles_published: Articles successfully published
            articles_rejected: Articles rejected
            articles_ignored: Articles ignored
            articles_error: Articles with errors
            mode: Analysis mode (IA or regex)
            max_articles_requested: Maximum articles requested
            character_limit: Character limit for AI mode
            gemini_calls: Number of Gemini API calls
            gemini_tokens_input: Total input tokens
            gemini_tokens_output: Total output tokens
            gemini_cost_usd: Total cost in USD
            errors: List of error messages
            
        Returns:
            AutomationReport object
        """
        duration = (end_time - start_time).total_seconds()
        report_id = self._generate_report_id()
        
        report = AutomationReport(
            report_id=report_id,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            articles_retrieved=articles_retrieved,
            articles_excluded_published=articles_excluded_published,
            articles_excluded_analyzed=articles_excluded_analyzed,
            articles_excluded_length=articles_excluded_length,
            articles_excluded_duplicates=articles_excluded_duplicates,
            articles_analyzed=articles_analyzed,
            articles_published=articles_published,
            articles_rejected=articles_rejected,
            articles_ignored=articles_ignored,
            articles_error=articles_error,
            gemini_calls=gemini_calls,
            gemini_tokens_input=gemini_tokens_input,
            gemini_tokens_output=gemini_tokens_output,
            gemini_cost_usd=gemini_cost_usd,
            total_interruptions=total_interruptions,
            total_interruption_duration_seconds=total_interruption_duration_seconds,
            resolved_interruptions=resolved_interruptions,
            unresolved_interruptions=unresolved_interruptions,
            was_resumed=was_resumed,
            errors=errors or [],
            mode=mode,
            max_articles_requested=max_articles_requested,
            character_limit=character_limit
        )
        
        return report
    
    def save_report(self, report: AutomationReport) -> None:
        """
        Save a report to file.
        
        Args:
            report: AutomationReport to save
        """
        try:
            report_file = self._get_report_file_path(report.report_id)
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(report), f, indent=2, ensure_ascii=False)
            logger.info(f"Report saved: {report_file}")
        except Exception as e:
            logger.error(f"Error saving report: {e}")
    
    def load_report(self, report_id: str) -> Optional[AutomationReport]:
        """
        Load a report from file.
        
        Args:
            report_id: Report ID to load
            
        Returns:
            AutomationReport if found, None otherwise
        """
        try:
            report_file = self._get_report_file_path(report_id)
            if not report_file.exists():
                return None
            
            with open(report_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return AutomationReport(**data)
        except Exception as e:
            logger.error(f"Error loading report {report_id}: {e}")
            return None
    
    def get_all_reports(self) -> List[AutomationReport]:
        """
        Get all reports.
        
        Returns:
            List of all AutomationReport objects, sorted by date (newest first)
        """
        reports = []
        
        for report_file in self.reports_dir.glob("report_*.json"):
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                reports.append(AutomationReport(**data))
            except Exception as e:
                logger.warning(f"Error loading report file {report_file}: {e}")
        
        # Sort by start time (newest first)
        reports.sort(key=lambda r: r.start_time, reverse=True)
        
        return reports
    
    def get_reports_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all reports.
        
        Returns:
            Dictionary with summary statistics
        """
        reports = self.get_all_reports()
        
        if not reports:
            return {
                'total_reports': 0,
                'total_articles_analyzed': 0,
                'total_articles_published': 0,
                'total_gemini_cost': 0.0
            }
        
        total_analyzed = sum(r.articles_analyzed for r in reports)
        total_published = sum(r.articles_published for r in reports)
        total_cost = sum(r.gemini_cost_usd for r in reports)
        
        return {
            'total_reports': len(reports),
            'total_articles_analyzed': total_analyzed,
            'total_articles_published': total_published,
            'total_gemini_cost': round(total_cost, 4),
            'latest_report_date': reports[0].start_time if reports else None
        }
    
    def clear_old_reports(self, days: int = 30) -> int:
        """
        Clear reports older than specified days.
        
        Args:
            days: Number of days to keep reports
            
        Returns:
            Number of reports cleared
        """
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        cleared = 0
        
        for report_file in self.reports_dir.glob("report_*.json"):
            try:
                # Extract date from report_id (format: YYYYMMDD_HHMMSS)
                report_id = report_file.stem.replace("report_", "")
                report_date = datetime.strptime(report_id, "%Y%m%d_%H%M%S").timestamp()
                
                if report_date < cutoff_date:
                    report_file.unlink()
                    cleared += 1
            except Exception as e:
                logger.warning(f"Error checking report file {report_file}: {e}")
        
        if cleared > 0:
            logger.info(f"Cleared {cleared} reports older than {days} days")
        
        return cleared


# Global report generator instance
_global_report_generator: Optional[ReportGenerator] = None


def get_report_generator(reports_dir: str = "data/automation_reports") -> ReportGenerator:
    """
    Get or create the global report generator instance.
    
    Args:
        reports_dir: Directory to store reports
        
    Returns:
        Global ReportGenerator instance
    """
    global _global_report_generator
    if _global_report_generator is None:
        _global_report_generator = ReportGenerator(reports_dir)
    return _global_report_generator


def reset_global_report_generator() -> None:
    """Reset the global report generator instance."""
    global _global_report_generator
    _global_report_generator = None
