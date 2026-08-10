"""
Analyzers for detecting Wikipedia article issues.
"""

from .base import BaseAnalyzer, Issue
from .links import LinkAnalyzer
from .whitespace import WhitespaceAnalyzer
from .typography import TypographyAnalyzer
from .templates import TemplateAnalyzer
from .categories import CategoryAnalyzer
from .html import HTMLAnalyzer
from .reference_analyzer import ReferenceAnalyzer
from .structure_analyzer import StructureAnalyzer
from .works_list_analyzer import WorksListAnalyzer
from .http_links import HttpLinksAnalyzer
from .dead_links import DeadLinkAnalyzer

__all__ = [
    'BaseAnalyzer',
    'Issue',
    'LinkAnalyzer',
    'WhitespaceAnalyzer',
    'TypographyAnalyzer',
    'TemplateAnalyzer',
    'CategoryAnalyzer',
    'HTMLAnalyzer',
    'ReferenceAnalyzer',
    'StructureAnalyzer',
    'WorksListAnalyzer',
    'HttpLinksAnalyzer',
    'DeadLinkAnalyzer'
]
