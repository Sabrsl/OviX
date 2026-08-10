"""
Base analyzer class for detecting Wikipedia article issues.

This module defines the core data structures and abstract base class
used by all specialized analyzers. It has been enhanced with additional
metadata, helper methods, and configuration support while maintaining
full backward compatibility with existing analyzers.

Conventions:
    - All positions are zero‑based character offsets from the start of the
      wikitext, unless otherwise noted.
    - Severity levels: 'low', 'medium', 'high', 'critical'.
    - The `Issue` dataclass is immutable after creation (frozen=True) to
      prevent accidental modifications.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple, Union
from enum import Enum
import json


class Severity(Enum):
    """Standardised severity levels for issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Issue:
    """
    Represents a detected issue in an article.

    Extended attributes (all optional to preserve compatibility):
        - line: line number (1‑based) where the issue occurs.
        - column: column number (1‑based) within the line.
        - context: a short snippet of surrounding wikitext.
        - confidence: a float between 0.0 and 1.0 indicating detection certainty.
        - rule_reference: URL or identifier of the Wikipedia rule being violated.
        - fix_options: a list of alternative suggested fixes (each a string).
        - extra: any additional structured data.

    The original fields (issue_type, description, position, original_text,
    suggested_text, severity) remain unchanged.
    """
    issue_type: str
    description: str
    position: Optional[int] = None
    original_text: Optional[str] = None
    suggested_text: Optional[str] = None
    severity: Union[str, Severity] = Severity.MEDIUM

    # ---- New optional fields ----
    line: Optional[int] = None
    column: Optional[int] = None
    context: Optional[str] = None
    confidence: float = 1.0
    rule_reference: Optional[str] = None
    fix_options: Optional[List[str]] = None
    extra: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Normalise severity to a string and ensure confidence is clamped."""
        # Normalise severity
        if isinstance(self.severity, Severity):
            object.__setattr__(self, 'severity', self.severity.value)
        # Clamp confidence
        if not (0.0 <= self.confidence <= 1.0):
            object.__setattr__(self, 'confidence', min(1.0, max(0.0, self.confidence)))

    def to_dict(self) -> Dict[str, Any]:
        """Convert the issue to a dictionary (including all new fields)."""
        result = {
            'issue_type': self.issue_type,
            'description': self.description,
            'position': self.position,
            'original_text': self.original_text,
            'suggested_text': self.suggested_text,
            'severity': self.severity,
            'line': self.line,
            'column': self.column,
            'context': self.context,
            'confidence': self.confidence,
            'rule_reference': self.rule_reference,
            'fix_options': self.fix_options,
            'extra': self.extra,
        }
        # Remove keys with None to keep the dict clean (optional)
        return {k: v for k, v in result.items() if v is not None}

    def to_json(self, **kwargs) -> str:
        """Return a JSON representation of the issue."""
        return json.dumps(self.to_dict(), **kwargs)


class BaseAnalyzer(ABC):
    """
    Abstract base class for all article analyzers.

    Provides common utilities for protected‑area masking, logging,
    issue filtering, and result serialization, while preserving the
    minimal interface required by existing code.
    """

    # Pre‑compiled regex for common protected areas (nowiki, comments, etc.)
    _PROTECTED_BLOCK_RE = re.compile(
        r"<nowiki>.*?</nowiki>"
        r"|<pre>.*?</pre>"
        r"|<syntaxhighlight[^>]*>.*?</syntaxhighlight>"
        r"|<source[^>]*>.*?</source>"
        r"|<math[^>]*>.*?</math>"
        r"|<!--.*?-->",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, name: Optional[str] = None):
        """
        Initialize the analyzer.

        Args:
            name: Optional custom name; if not provided, the class name is used.
        """
        self.issues: List[Issue] = []
        self._name = name or self.__class__.__name__
        self._logger = logging.getLogger(f"wikipedia_analyzer.{self._name}")

    # ------------------------------------------------------------------
    # Abstract methods (must be implemented by subclasses)
    # ------------------------------------------------------------------

    @abstractmethod
    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze the given wikitext content and return a list of detected issues.

        Args:
            content: The article's wikitext.

        Returns:
            List of Issue objects (the analyzer's internal list is also updated).
        """
        pass

    @abstractmethod
    def get_analyzer_name(self) -> str:
        """Return a human‑readable name for this analyzer."""
        return self._name

    # ------------------------------------------------------------------
    # Existing public methods (preserved and augmented)
    # ------------------------------------------------------------------

    def clear_issues(self) -> None:
        """Clear all currently stored issues."""
        self.issues = []

    def get_issues_by_severity(self, severity: Union[str, Severity]) -> List[Issue]:
        """Return a list of issues filtered by severity."""
        if isinstance(severity, Severity):
            severity = severity.value
        return [i for i in self.issues if i.severity == severity]

    def get_issues_by_type(self, issue_type: str) -> List[Issue]:
        """Return a list of issues with the given type."""
        return [i for i in self.issues if i.issue_type == issue_type]

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of all issues."""
        return {
            'analyzer': self._name,
            'issue_count': len(self.issues),
            'issues': [issue.to_dict() for issue in self.issues],
        }

    def to_json(self, **kwargs) -> str:
        """Return a JSON representation of all issues."""
        return json.dumps(self.to_dict(), **kwargs)

    # ------------------------------------------------------------------
    # New helper methods for subclasses
    # ------------------------------------------------------------------

    def log(self, level: int, msg: str, *args, **kwargs) -> None:
        """
        Log a message using the analyzer's dedicated logger.

        Args:
            level: Logging level (e.g., logging.INFO).
            msg: Message format string.
            *args: Arguments for the message.
            **kwargs: Additional arguments passed to the logger.
        """
        self._logger.log(level, msg, *args, **kwargs)

    def build_protected_mask(self, content: str) -> List[bool]:
        """
        Create a boolean mask indicating which character positions are inside
        protected areas (nowiki, pre, syntaxhighlight, math, comments).

        This is useful for analyzers that need to skip such zones.

        Returns:
            A list of booleans, one per character in `content`, where True
            means the character is protected and should be ignored.
        """
        mask = [False] * len(content)
        for match in self._PROTECTED_BLOCK_RE.finditer(content):
            for idx in range(match.start(), match.end()):
                mask[idx] = True
        return mask

    def is_protected(self, mask: List[bool], pos: int) -> bool:
        """Check if a given position is protected according to the mask."""
        return 0 <= pos < len(mask) and mask[pos]

    def trim_protected_ranges(self, content: str) -> str:
        """
        Return a version of the content with protected areas replaced by
        placeholder characters ('#') to simplify parsing without losing offsets.

        This is a convenience wrapper around build_protected_mask.

        Returns:
            A string where protected characters are replaced by '#'.
        """
        mask = self.build_protected_mask(content)
        chars = list(content)
        for i, protected in enumerate(mask):
            if protected:
                chars[i] = '#'
        return ''.join(chars)

    def get_line_and_column(self, content: str, position: int) -> Tuple[int, int]:
        """
        Convert a character offset to (line, column) in the original text.

        Args:
            content: The full wikitext.
            position: The zero‑based character offset.

        Returns:
            A tuple (line_number_1_based, column_number_1_based).
        """
        if position < 0:
            return (1, 1)
        # Count newlines before the position
        preceding = content[:position]
        lines = preceding.splitlines()
        line = len(lines)
        col = len(lines[-1]) + 1 if lines else 1
        return (line, col)

    # ------------------------------------------------------------------
    # Metadata / configuration (can be overridden)
    # ------------------------------------------------------------------

    def get_config(self) -> Dict[str, Any]:
        """
        Return a configuration dictionary for this analyzer.

        Subclasses may override to provide specific options.
        """
        return {
            'name': self._name,
            'version': '1.0',
        }

    def __repr__(self) -> str:
        return f"<{self._name} issues={len(self.issues)}>"