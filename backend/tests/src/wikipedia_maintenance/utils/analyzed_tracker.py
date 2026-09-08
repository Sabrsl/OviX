"""
Tracker for articles already analyzed by AI.

This module provides a persistent tracking system for articles that have been analyzed
by the AI (Gemini/LIA), preventing re-analysis of the same articles during system restarts.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class AnalysisStatus(Enum):
    """Status of article analysis."""
    ANALYZING = "analyzing"  # Currently being analyzed
    PENDING = "pending"  # Analyzed, waiting for publication
    PUBLISHED = "published"  # Published to Wikipedia
    REJECTED = "rejected"  # Rejected
    IGNORED = "ignored"  # Ignored
    ERROR = "error"  # Analysis failed


@dataclass
class AnalysisRecord:
    """Record of an article analysis."""
    title: str
    page_id: int
    revision_id: int
    analysis_date: str  # ISO format datetime
    status: str  # AnalysisStatus value
    score: Optional[float] = None
    decision: Optional[str] = None  # Final decision
    mode: str = "IA"  # Analysis mode (IA or regex)
    changes_count: Optional[int] = None
    summary: Optional[str] = None
    original_content: Optional[str] = None  # Store the original content for diff
    corrected_content: Optional[str] = None  # Store the corrected content
    character_count: Optional[int] = None  # Character count of the article
    total_links: Optional[int] = None  # Total number of links in article
    dead_links_count: Optional[int] = None  # Number of dead links found
    corrected_links_count: Optional[int] = None  # Number of links corrected
    human_verified: Optional[bool] = None  # Whether human verification was done
    manual_review_urls: Optional[List[str]] = None  # URLs requiring manual review


class AnalyzedTracker:
    """
    Tracker for articles already analyzed by AI.
    
    Maintains a persistent record of analyzed articles to prevent re-analysis
    of the same articles with the same revision ID.
    """
    
    def __init__(self, tracker_file: str = "data/analyzed_articles.json"):
        """
        Initialize the analyzed tracker.
        
        Args:
            tracker_file: Path to the tracker JSON file
        """
        self.tracker_file = Path(tracker_file)
        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage
        self._records: Dict[str, AnalysisRecord] = {}  # Key: title
        self._by_revision: Dict[int, str] = {}  # Key: revision_id, Value: title
        
        # Load existing data
        self._load()

        logger.info(f"AnalyzedTracker initialized with {len(self._records)} records")

    def _load(self) -> None:
        """Load records from file."""
        if not self.tracker_file.exists():
            logger.info("No existing tracker file found, starting fresh")
            return

        try:
            with open(self.tracker_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for record_data in data:
                record = AnalysisRecord(**record_data)
                self._records[record.title] = record
                self._by_revision[record.revision_id] = record.title

            logger.info(f"Loaded {len(self._records)} analysis records from file")
        except Exception as e:
            logger.error(f"Error loading tracker file: {e}")
            self._records = {}
            self._by_revision = {}
    
    def _save(self) -> None:
        """Save records to file."""
        try:
            records_list = [asdict(record) for record in self._records.values()]
            with open(self.tracker_file, 'w', encoding='utf-8') as f:
                json.dump(records_list, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(records_list)} analysis records to file")
        except Exception as e:
            logger.error(f"Error saving tracker file: {e}")
    
    def is_analyzed(self, title: str, revision_id: int) -> bool:
        """
        Check if an article has been analyzed with the given revision ID.
        
        Args:
            title: Article title
            revision_id: Current Wikipedia revision ID
            
        Returns:
            True if article was analyzed with this revision ID
        """
        if title not in self._records:
            return False
        
        record = self._records[title]
        return record.revision_id == revision_id
    
    def get_record(self, title: str) -> Optional[AnalysisRecord]:
        """
        Get the analysis record for an article.
        
        Args:
            title: Article title
            
        Returns:
            AnalysisRecord if found, None otherwise
        """
        return self._records.get(title)
    
    def record_analysis(
        self,
        title: str,
        page_id: int,
        revision_id: int,
        status: AnalysisStatus,
        score: Optional[float] = None,
        decision: Optional[str] = None,
        mode: str = "IA",
        changes_count: Optional[int] = None,
        summary: Optional[str] = None,
        original_content: Optional[str] = None,
        corrected_content: Optional[str] = None,
        character_count: Optional[int] = None,
        total_links: Optional[int] = None,
        dead_links_count: Optional[int] = None,
        corrected_links_count: Optional[int] = None,
        human_verified: Optional[bool] = None,
        manual_review_urls: Optional[List[str]] = None
    ) -> None:
        """
        Record an article analysis.
        
        Args:
            title: Article title
            page_id: Wikipedia page ID
            revision_id: Wikipedia revision ID
            status: Analysis status
            score: Analysis score (optional)
            decision: Final decision (optional)
            mode: Analysis mode (IA or regex)
            changes_count: Number of changes made (optional)
            summary: Edit summary (optional)
            original_content: Original wikicode content (optional)
            corrected_content: Corrected wikicode content (optional)
            character_count: Character count of the article (optional)
            total_links: Total number of links in article (optional)
            dead_links_count: Number of dead links found (optional)
            corrected_links_count: Number of links corrected (optional)
            human_verified: Whether human verification was done (optional)
        """
        # Remove old record if exists with different revision
        if title in self._records and self._records[title].revision_id != revision_id:
            old_revision = self._records[title].revision_id
            if old_revision in self._by_revision:
                del self._by_revision[old_revision]
            logger.info(f"Updating record for '{title}' (revision changed from {old_revision} to {revision_id})")
        
        # Update existing record or create new one
        if title in self._records and self._records[title].revision_id == revision_id:
            # Update existing record, preserve original analysis date
            record = self._records[title]
            record.status = status.value
            record.decision = decision if decision is not None else record.decision
            record.changes_count = changes_count if changes_count is not None else record.changes_count
            record.summary = summary if summary is not None else record.summary
            record.original_content = original_content if original_content is not None else record.original_content
            record.corrected_content = corrected_content if corrected_content is not None else record.corrected_content
            record.character_count = character_count if character_count is not None else record.character_count
            record.total_links = total_links if total_links is not None else record.total_links
            record.dead_links_count = dead_links_count if dead_links_count is not None else record.dead_links_count
            record.corrected_links_count = corrected_links_count if corrected_links_count is not None else record.corrected_links_count
            record.human_verified = human_verified if human_verified is not None else record.human_verified
            record.manual_review_urls = manual_review_urls if manual_review_urls is not None else record.manual_review_urls
            record.manual_review_urls = manual_review_urls if manual_review_urls is not None else record.manual_review_urls
            # Update other fields only if provided
            if score is not None:
                record.score = score
            if mode:
                record.mode = mode
            logger.debug(f"Updated existing record for '{title}' with status: {status.value}")
        elif title in self._records:
            # Fallback: update by title if revision_id doesn't match (for backward compatibility)
            record = self._records[title]
            record.status = status.value
            record.decision = decision if decision is not None else record.decision
            record.changes_count = changes_count if changes_count is not None else record.changes_count
            record.summary = summary if summary is not None else record.summary
            record.revision_id = revision_id  # Update revision_id
            record.page_id = page_id  # Update page_id
            record.original_content = original_content if original_content is not None else record.original_content
            record.corrected_content = corrected_content if corrected_content is not None else record.corrected_content
            record.character_count = character_count if character_count is not None else record.character_count
            record.total_links = total_links if total_links is not None else record.total_links
            record.dead_links_count = dead_links_count if dead_links_count is not None else record.dead_links_count
            record.corrected_links_count = corrected_links_count if corrected_links_count is not None else record.corrected_links_count
            record.human_verified = human_verified if human_verified is not None else record.human_verified
            record.manual_review_urls = manual_review_urls if manual_review_urls is not None else record.manual_review_urls
            if score is not None:
                record.score = score
            if mode:
                record.mode = mode
            logger.info(f"Updated existing record for '{title}' by title (revision mismatch, updated to {revision_id})")
        else:
            # Create new record
            record = AnalysisRecord(
                title=title,
                page_id=page_id,
                revision_id=revision_id,
                analysis_date=datetime.now().isoformat(),
                status=status.value,
                score=score,
                decision=decision,
                mode=mode,
                changes_count=changes_count,
                summary=summary,
                original_content=original_content,
                corrected_content=corrected_content,
                character_count=character_count,
                total_links=total_links,
                dead_links_count=dead_links_count,
                corrected_links_count=corrected_links_count,
                human_verified=human_verified,
                manual_review_urls=manual_review_urls
            )
            logger.debug(f"Created new record for '{title}' with status: {status.value}")
        
        self._records[title] = record
        self._by_revision[revision_id] = title
        
        # Save to file
        self._save()
        
        logger.info(f"Recorded analysis for '{title}' (status: {status.value}, revision: {revision_id})")
    
    def filter_analyzed_articles(self, articles: List) -> List:
        """
        Filter out articles that have already been analyzed (any revision).
        
        Args:
            articles: List of article objects with title and revision_id attributes
            
        Returns:
            List of articles that need analysis (not analyzed at all)
        """
        filtered = []
        skipped = []
        
        for article in articles:
            title = article.title if hasattr(article, 'title') else article.get('title')
            revision_id = article.revision_id if hasattr(article, 'revision_id') else article.get('revision_id')
            
            if not title:
                logger.warning(f"Article missing title, including anyway")
                filtered.append(article)
                continue
            
            # Filter if article has any analysis record (any revision)
            if title in self._records:
                skipped.append(title)
                logger.debug(f"Skipping already analyzed article: {title} (any revision)")
            else:
                filtered.append(article)
        
        if skipped:
            logger.info(f"Filtered out {len(skipped)} already analyzed articles: {', '.join(skipped[:5])}{'...' if len(skipped) > 5 else ''}")
        
        return filtered
    
    def get_records_by_status(self, status: AnalysisStatus) -> List[AnalysisRecord]:
        """
        Get all records with a specific status.
        
        Args:
            status: Analysis status to filter by
            
        Returns:
            List of AnalysisRecord objects
        """
        return [record for record in self._records.values() if record.status == status.value]
    
    def get_analyzed_but_not_published(self, max_count: int = None) -> List[AnalysisRecord]:
        """
        Get articles that have been analyzed but not yet published.
        
        Args:
            max_count: Maximum number of records to return (None for all)
            
        Returns:
            List of AnalysisRecord objects with status PENDING or ERROR
        """
        # Get articles that are analyzed but not published
        non_published_statuses = [AnalysisStatus.PENDING.value, AnalysisStatus.ERROR.value]
        records = [record for record in self._records.values() 
                  if record.status in non_published_statuses]
        
        # Shuffle for randomness
        import random
        random.shuffle(records)
        
        if max_count is not None:
            records = records[:max_count]
        
        return records
    
    def get_all_records(self) -> List[AnalysisRecord]:
        """
        Get all analysis records.
        
        Returns:
            List of all AnalysisRecord objects
        """
        return list(self._records.values())
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about analyzed articles.
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total': len(self._records),
            'published': 0,
            'rejected': 0,
            'ignored': 0,
            'pending': 0,
            'error': 0
        }
        
        for record in self._records.values():
            if record.status in stats:
                stats[record.status] += 1
        
        return stats
    
    def clear_old_records(self, days: int = 30) -> int:
        """
        Clear records older than specified days.
        
        Args:
            days: Number of days to keep records
            
        Returns:
            Number of records cleared
        """
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        cleared = 0
        
        to_remove = []
        for title, record in self._records.items():
            if not record.analysis_date:
                continue
            record_date = datetime.fromisoformat(record.analysis_date).timestamp()
            if record_date < cutoff_date:
                to_remove.append(title)
        
        for title in to_remove:
            revision_id = self._records[title].revision_id
            del self._records[title]
            if revision_id in self._by_revision:
                del self._by_revision[revision_id]
            cleared += 1
        
        if cleared > 0:
            self._save()
            logger.info(f"Cleared {cleared} records older than {days} days")
        
        return cleared


# Global tracker instance
_global_tracker: Optional[AnalyzedTracker] = None


def get_analyzed_tracker(tracker_file: str = "data/analyzed_articles.json") -> AnalyzedTracker:
    """
    Get or create the global analyzed tracker instance.
    
    Args:
        tracker_file: Path to the tracker file
        
    Returns:
        Global AnalyzedTracker instance
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = AnalyzedTracker(tracker_file)
    return _global_tracker


def reset_global_tracker() -> None:
    """Reset the global tracker instance."""
    global _global_tracker
    _global_tracker = None
