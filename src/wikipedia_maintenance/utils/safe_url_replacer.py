"""
Safe URL Replacer for exact occurrence replacement.

This service ensures that only the specific occurrence of a URL
that was analyzed is replaced, not all occurrences in the document.
"""

import re
import logging
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class ReplacementResult:
    """Result of URL replacement."""
    success: bool
    new_content: Optional[str] = None
    reason: Optional[str] = None
    changed_position: Optional[int] = None
    old_length: Optional[int] = None
    new_length: Optional[int] = None


class SafeURLReplacer:
    """
    Service for safe URL replacement in wikitext.
    
    Design principles:
    - Replace only the exact occurrence at the specified position
    - Preserve all other occurrences of the same URL
    - Validate that only the URL changes, nothing else
    - Provide detailed logging of the replacement
    """
    
    # Fixed regex to properly exclude template delimiters |{}[] that cause malformed URLs
    URL_PATTERN = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=%]+', re.IGNORECASE)
    
    def __init__(self):
        """Initialize safe URL replacer."""
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def replace_exact_occurrence(self, content: str, old_url: str, new_url: str, position: int) -> ReplacementResult:
        """
        Replace the exact occurrence of old_url at the specified position.
        
        This method:
        1. Validates that old_url exists at the specified position
        2. Replaces only that specific occurrence
        3. Validates that only the URL changes
        4. Returns the new content with the replacement
        
        Args:
            content: Original wikitext content
            old_url: URL to replace
            new_url: New URL to replace with
            position: Position of the URL to replace (must match old_url)
            
        Returns:
            ReplacementResult with success status and new content
        """
        # Validate that old_url exists at the specified position
        if not self._validate_url_at_position(content, old_url, position):
            return ReplacementResult(
                success=False,
                reason=f"URL '{old_url}' not found at position {position}"
            )
        
        # Perform the replacement
        new_content = content[:position] + new_url + content[position + len(old_url):]
        
        # Validate the diff
        diff_validation = self._validate_minimal_diff(content, new_content, position, len(old_url), len(new_url))
        if not diff_validation:
            return ReplacementResult(
                success=False,
                reason="Diff validation failed - unexpected changes detected"
            )
        
        self._logger.info(
            f"SAFE_REPLACEMENT | old_url={old_url} | new_url={new_url} | "
            f"position={position} | old_length={len(old_url)} | new_length={len(new_url)}"
        )
        
        return ReplacementResult(
            success=True,
            new_content=new_content,
            changed_position=position,
            old_length=len(old_url),
            new_length=len(new_url)
        )
    
    def _validate_url_at_position(self, content: str, url: str, position: int) -> bool:
        """
        Validate that the URL exists at the specified position.
        
        Args:
            content: Content to check
            url: URL to validate
            position: Position where URL should be
            
        Returns:
            True if URL exists at position
        """
        if position < 0 or position >= len(content):
            return False
        
        if position + len(url) > len(content):
            return False
        
        actual_url = content[position:position + len(url)]
        return actual_url == url
    
    def _validate_minimal_diff(self, old_content: str, new_content: str, 
                              position: int, old_length: int, new_length: int) -> bool:
        """
        Validate that only the URL changes, nothing else.
        
        Args:
            old_content: Original content
            new_content: New content after replacement
            position: Position of the change
            old_length: Length of old URL
            new_length: Length of new URL
            
        Returns:
            True if diff is minimal (only URL changed)
        """
        # Check content before position (should be identical)
        if old_content[:position] != new_content[:position]:
            self._logger.warning(f"Diff validation failed: content before position {position} changed")
            return False
        
        # Check content after the URL (should be identical)
        old_after = old_content[position + old_length:]
        new_after = new_content[position + new_length:]
        
        if old_after != new_after:
            self._logger.warning(f"Diff validation failed: content after URL changed")
            return False
        
        # Calculate expected diff
        expected_diff = abs(new_length - old_length)
        actual_diff = abs(len(new_content) - len(old_content))
        
        if actual_diff != expected_diff:
            self._logger.warning(
                f"Diff validation failed: expected diff {expected_diff}, got {actual_diff}"
            )
            return False
        
        return True
    
    def find_url_context(self, content: str, url: str, position: int, context_chars: int = 50) -> str:
        """
        Find the context around a URL at a specific position.
        
        Args:
            content: Content to search
            url: URL to find context for
            position: Position of the URL
            context_chars: Number of characters before and after to include
            
        Returns:
            Context string with the URL
        """
        start = max(0, position - context_chars)
        end = min(len(content), position + len(url) + context_chars)
        
        context = content[start:end]
        return context
