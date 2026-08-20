"""
Analyzers for detecting Wikipedia article issues.
Dead Linker Project - Specialized in dead link detection and repair.
"""

from .base import BaseAnalyzer, Issue
from .dead_links import DeadLinkAnalyzer

__all__ = [
    'BaseAnalyzer',
    'Issue',
    'DeadLinkAnalyzer'
]
