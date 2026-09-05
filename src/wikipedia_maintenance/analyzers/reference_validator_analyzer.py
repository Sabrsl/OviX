"""
Reference Validator Analyzer - Validates reference format and structure.

This analyzer:
- Detects uppercase references (parameters with incorrect casing)
- Validates ISBN format
- Checks template type compatibility
- Respects configuration (references.check_uppercase_refs, references.check_isbn_format, references.check_template_type)
"""

import re
import logging
from typing import List, Optional, Dict, Any

from .base import BaseAnalyzer, Issue
from wikipedia_maintenance.utils.config import load_config
from wikipedia_maintenance.utils.reference_utils import validate_isbn

logger = logging.getLogger(__name__)


class ReferenceValidatorAnalyzer(BaseAnalyzer):
    """
    Analyzer for validating reference format and structure.
    
    Detects:
    - Uppercase reference parameters
    - Invalid ISBN format
    - Incorrect template types
    """

    # Pattern to match reference templates
    REF_TEMPLATE_PATTERN = re.compile(r'\{\{(?:Lien web|article|ouvrage|chapitre|livre)[^}]*\}\}', re.IGNORECASE)
    
    # Pattern to match ISBN parameters
    ISBN_PATTERN = re.compile(r'\|\s*isbn\s*=\s*([^\s|}]+)', re.IGNORECASE)
    
    # Common uppercase parameter patterns to flag
    UPPERCASE_PARAM_PATTERN = re.compile(r'\|\s*([A-Z]{2,})\s*=', re.IGNORECASE)

    def __init__(self, name: str = None):
        super().__init__(name)
        
        # Load configuration
        self._load_config()
        
        # Track statistics
        self.stats = {
            'uppercase_found': 0,
            'invalid_isbn_found': 0,
            'template_type_issues': 0,
            'total_issues': 0
        }

    def _load_config(self) -> None:
        """Load reference validator configuration."""
        try:
            config = load_config()
            if hasattr(config, 'references'):
                self.check_uppercase_refs = config.references.check_uppercase_refs
                self.check_isbn_format = config.references.check_isbn_format
                self.check_template_type = config.references.check_template_type
                logger.info(f"ReferenceValidatorAnalyzer config: check_uppercase_refs={self.check_uppercase_refs}, check_isbn_format={self.check_isbn_format}, check_template_type={self.check_template_type}")
            else:
                # Default to enabled if config not found
                self.check_uppercase_refs = True
                self.check_isbn_format = True
                self.check_template_type = True
                logger.warning("references config not found, defaulting to enabled")
        except Exception as e:
            logger.warning(f"Failed to load reference validator config: {e}, defaulting to enabled")
            self.check_uppercase_refs = True
            self.check_isbn_format = True
            self.check_template_type = True

    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze content for reference validation issues.
        
        Args:
            content: Wikicode content to analyze
            
        Returns:
            List of Issue objects
        """
        issues = []
        
        # Check for uppercase parameters if enabled
        if self.check_uppercase_refs:
            uppercase_issues = self._find_uppercase_parameters(content)
            issues.extend(uppercase_issues)
            self.stats['uppercase_found'] = len(uppercase_issues)
        
        # Check for invalid ISBN if enabled
        if self.check_isbn_format:
            isbn_issues = self._find_invalid_isbn(content)
            issues.extend(isbn_issues)
            self.stats['invalid_isbn_found'] = len(isbn_issues)
        
        # Check for template type issues if enabled
        if self.check_template_type:
            template_issues = self._check_template_types(content)
            issues.extend(template_issues)
            self.stats['template_type_issues'] = len(template_issues)
        
        self.stats['total_issues'] = len(issues)
        logger.info(f"ReferenceValidatorAnalyzer: {len(issues)} issues found (uppercase={self.stats['uppercase_found']}, isbn={self.stats['invalid_isbn_found']}, template={self.stats['template_type_issues']})")
        
        return issues

    def _find_uppercase_parameters(self, content: str) -> List[Issue]:
        """
        Find uppercase parameters in reference templates.
        
        Args:
            content: Wikicode content
            
        Returns:
            List of Issue objects for uppercase parameters
        """
        issues = []
        
        # Parameters that should NOT be uppercase (common French template parameters)
        lowercase_params = {'titre', 'auteur', 'éditeur', 'année', 'site', 'date', 'consulté le', 'périodique', 'ouvrage'}
        
        for match in self.REF_TEMPLATE_PATTERN.finditer(content):
            template_text = match.group()
            template_start = match.start()
            
            # Check for uppercase parameters
            for param_match in self.UPPERCASE_PARAM_PATTERN.finditer(template_text):
                param_name = param_match.group(1)
                if param_name.lower() in lowercase_params:
                    # Calculate absolute position in the full content
                    absolute_position = template_start + param_match.start()
                    original_text = param_match.group()
                    suggested_text = param_match.group().replace(param_name, param_name.lower())
                    
                    logger.info(f"Uppercase parameter found: param_name={param_name}, original_text={original_text!r}, suggested_text={suggested_text!r}")
                    
                    issue = Issue(
                        issue_type='uppercase_parameter',
                        description=f"Uppercase parameter '{param_name}' should be lowercase",
                        position=absolute_position,
                        original_text=original_text,
                        suggested_text=suggested_text,
                        severity='low'
                    )
                    issues.append(issue)
        
        return issues

    def _find_invalid_isbn(self, content: str) -> List[Issue]:
        """
        Find invalid ISBN formats in references.
        
        Args:
            content: Wikicode content
            
        Returns:
            List of Issue objects for invalid ISBNs
        """
        issues = []
        
        for match in self.ISBN_PATTERN.finditer(content):
            isbn = match.group(1)
            position = match.start()
            
            if not validate_isbn(isbn):
                issue = Issue(
                    issue_type='invalid_isbn',
                    description=f"Invalid ISBN format: {isbn}",
                    position=position,
                    original_text=match.group(),
                    suggested_text=None,  # No automatic suggestion for invalid ISBN
                    severity='medium'
                )
                issues.append(issue)
        
        return issues

    def _check_template_types(self, content: str) -> List[Issue]:
        """
        Check for template type compatibility issues.
        
        Args:
            content: Wikicode content
            
        Returns:
            List of Issue objects for template type issues
        """
        issues = []
        
        # This is a placeholder for template type validation
        # In a full implementation, this would check:
        # - Whether {{ouvrage}} is used for books
        # - Whether {{article}} is used for articles
        # - Whether {{Lien web}} is used for web pages
        # - Parameter compatibility (e.g., |éditeur should not be in {{Lien web}})
        
        # For now, just detect templates that might be misused
        template_pattern = re.compile(r'\{\{(ouvrage|livre)[^}]*\|\s*url\s*=', re.IGNORECASE)
        
        for match in template_pattern.finditer(content):
            issue = Issue(
                issue_type='template_type_mismatch',
                description=f"Book template ({{ouvrage}}/{{livre}}) should not contain |url= parameter",
                position=match.start(),
                original_text=match.group()[:100],
                suggested_text=None,
                severity='low'
            )
            issues.append(issue)
        
        return issues

    def get_analyzer_name(self) -> str:
        """Return the analyzer name."""
        return "ReferenceValidatorAnalyzer"
