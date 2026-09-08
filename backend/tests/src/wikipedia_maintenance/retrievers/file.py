"""
File retriever for Wikipedia articles.
"""

from pathlib import Path
from typing import List
from .base import BaseRetriever, Article
from ..utils.published_tracker import PublishedTracker


class FileRetriever(BaseRetriever):
    """Retrieves articles from a text file containing page titles."""
    
    def __init__(self, tracker_file: str = "published_articles.json"):
        """Initialize retriever.
        
        Args:
            tracker_file: Path to published articles tracker file
        """
        super().__init__()
        self.tracker = PublishedTracker(tracker_file)
    
    def retrieve(self, file_path: str, encoding: str = 'utf-8', exclude_published: bool = True) -> List[Article]:
        """Retrieve articles from a text file.
        
        Args:
            file_path: Path to text file containing article titles (one per line)
            encoding: File encoding
            exclude_published: Whether to exclude recently published articles (default: True)
            
        Returns:
            List of Article objects (without page content, just titles)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        articles = []
        with open(file_path, 'r', encoding=encoding) as f:
            for line in f:
                title = line.strip()
                if title and not title.startswith('#'):  # Skip empty lines and comments
                    if exclude_published and self.tracker.is_recently_published(title):
                        continue
                    articles.append(Article(title=title))
        
        return articles
    
    def get_source_type(self) -> str:
        """Get source type identifier."""
        return "file"
