"""
Analyzers for detecting Wikipedia article issues.
Dead Linker Project - Specialized in dead link detection and repair.
"""

from .base import BaseAnalyzer, Issue
from .dead_links import DeadLinkAnalyzer
from .http_links import HttpLinksAnalyzer
from .reference_enricher_analyzer import ReferenceEnricherAnalyzer
from .reference_analyzer import ReferenceAnalyzer
from .reference_validator_analyzer import ReferenceValidatorAnalyzer
from .broken_link_analyzer import BrokenLinkAnalyzer
from .typography_xml import XMLTypographyAnalyzer

__all__ = [
    'BaseAnalyzer',
    'Issue',
    'DeadLinkAnalyzer',
    'HttpLinksAnalyzer',
    'ReferenceEnricherAnalyzer',
    'ReferenceAnalyzer',
    'ReferenceValidatorAnalyzer',
    'BrokenLinkAnalyzer',
    'XMLTypographyAnalyzer'
]
