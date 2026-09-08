"""
Integration utility for XML-based typography analyzer.

This module provides safe integration functions to use the XML typography analyzer
alongside the existing AI-based correction system without breaking it.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

from wikipedia_maintenance.analyzers.typography_xml import XMLTypographyAnalyzer
from wikipedia_maintenance.utils.config import load_config

logger = logging.getLogger(__name__)


def get_xml_analyzer() -> Optional[XMLTypographyAnalyzer]:
    """
    Get an XML typography analyzer instance based on configuration.
    
    Returns:
        XMLTypographyAnalyzer instance if enabled in config, None otherwise
    """
    try:
        config = load_config()
        
        # Check if XML typography analyzer is enabled
        if hasattr(config, 'typography') and hasattr(config.typography, 'use_xml_rules'):
            if config.typography.use_xml_rules:
                # Get custom XML path if specified
                xml_path = getattr(config.typography, 'xml_rules_path', None)
                
                analyzer = XMLTypographyAnalyzer(xml_path=xml_path, enabled=True)
                logger.info("XML typography analyzer enabled")
                return analyzer
        
        logger.debug("XML typography analyzer disabled in config")
        return None
        
    except Exception as e:
        logger.error(f"Failed to initialize XML typography analyzer: {e}")
        return None


def apply_xml_corrections_safely(text: str) -> Tuple[str, int, bool]:
    """
    Apply XML-based typography corrections safely.
    
    This function is designed to be called alongside existing correction systems.
    It will only apply corrections if the XML analyzer is enabled and configured.
    
    Args:
        text: The original text to correct
        
    Returns:
        Tuple of (corrected_text, number_of_corrections, was_applied)
        - corrected_text: The text after XML corrections (or original if disabled)
        - number_of_corrections: Number of corrections applied (0 if disabled)
        - was_applied: True if XML corrections were applied, False otherwise
    """
    analyzer = get_xml_analyzer()
    
    if analyzer is None:
        logger.debug("XML typography analyzer not available, returning original text")
        return text, 0, False
    
    try:
        corrected_text, corrections_count = analyzer.apply_corrections(text)
        logger.info(f"XML typography corrections applied: {corrections_count} corrections")
        return corrected_text, corrections_count, True
        
    except Exception as e:
        logger.error(f"Error applying XML typography corrections: {e}")
        # Return original text on error to avoid breaking the system
        return text, 0, False


def analyze_with_xml(text: str) -> Tuple[list, bool]:
    """
    Analyze text using XML typography rules.
    
    Args:
        text: The text to analyze
        
    Returns:
        Tuple of (issues, was_analyzed)
        - issues: List of typography issues found (empty list if disabled)
        - was_analyzed: True if XML analysis was performed, False otherwise
    """
    analyzer = get_xml_analyzer()
    
    if analyzer is None:
        logger.debug("XML typography analyzer not available, returning empty issues")
        return [], False
    
    try:
        issues = analyzer.analyze(text)
        logger.info(f"XML typography analysis found {len(issues)} issues")
        return issues, True
        
    except Exception as e:
        logger.error(f"Error analyzing with XML typography: {e}")
        return [], False
