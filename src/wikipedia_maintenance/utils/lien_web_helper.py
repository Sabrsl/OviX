"""
Lien Web Template Helper for {{Lien web}} template manipulation.

This module provides utilities for:
- Detecting {{Lien web}} templates in wikitext
- Parsing template parameters
- Generating {{Lien web}} templates with archive as main link
"""

import re
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class LienWebTemplate:
    """Parsed {{Lien web}} template."""
    template_name: str
    parameters: Dict[str, str]
    full_match: str
    start_position: int
    end_position: int


class LienWebHelper:
    """
    Helper for {{Lien web}} template manipulation.

    This handles the specific case where a dead link should be repaired
    using an archive URL as the main link, following Wikipedia template behavior:
    - When 'brisé le' AND 'archive-url' are present, the archive URL becomes
      the main link displayed on the title

    All {{Lien web}} parameters are supported and preserved during repairs.
    """

    # Complete list of {{Lien web}} parameters in preferred order
    # Based on Wikipedia template documentation
    LIEN_WEB_PARAMETERS = [
        # Language
        'langue',

        # Authors (main and variants)
        'auteur', 'auteur prénom', 'auteur nom', 'auteur lien', 'auteur responsabilité', 'auteur directeur',
        'auteur2', 'auteur2 prénom', 'auteur2 nom', 'auteur2 lien', 'auteur2 responsabilité', 'auteur2 directeur',
        'auteur3', 'auteur3 prénom', 'auteur3 nom',
        'auteur4', 'auteur4 prénom', 'auteur4 nom',
        'auteur5', 'auteur5 prénom', 'auteur5 nom',
        'auteur6', 'auteur6 prénom', 'auteur6 nom',
        'auteur7', 'auteur7 prénom', 'auteur7 nom',
        'auteur8', 'auteur8 prénom', 'auteur8 nom',
        'auteur9', 'auteur9 prénom', 'auteur9 nom',
        'auteur10', 'auteur10 prénom', 'auteur10 nom',
        'auteur11', 'auteur11 prénom', 'auteur11 nom',
        'auteur12', 'auteur12 prénom', 'auteur12 nom',
        'auteur13', 'auteur13 prénom', 'auteur13 nom',
        'auteur14', 'auteur14 prénom', 'auteur14 nom',
        'et al.', 'auteur institutionnel',

        # Other contributors
        'traducteur', 'photographe',

        # Title and variants
        'titre', 'sous-titre', 'traduction titre', 'description',

        # URL and access
        'url', 'lire en ligne', 'url texte', 'lien',
        'format électronique', 'accès url',

        # Publication info
        'série', 'work', 'site', 'website', 'périodique',
        'lieu', 'lieu édition', 'location',
        'éditeur', 'publisher', 'editeur',
        'date', 'année', 'year', 'en ligne le', 'en ligne',
        'date jour', 'date mois', 'date année',

        # Archive parameters
        'archive-url', 'archiveurl', 'archive-date', 'archivedate',
        'brisé le', 'dead-url', 'deadurl', 'lien brisé',

        # Identifiers
        'isbn', 'issn', 'e-issn', 'oclc', 'pmid', 'pmcid',
        'doi', 'accès doi', 'jstor', 'bibcode', 'math reviews', 'zbmath', 'arxiv',

        # Consultation and excerpts
        'consulté le', 'extrait', 'citation', 'quote', 'page', 'pages', 'passage',

        # Other
        'id', 'libellé', 'plume', 'nature document', 'afficher plume', 'nocat'
    ]
    
    # Pattern to match {{Lien web}} templates (case-insensitive)
    # Matches: {{Lien web|param1=value1|param2=value2|...}}
    # Also matches with spaces: {{ Lien web | param1=value1 }}
    LIEN_WEB_PATTERN = re.compile(
        r'\{\{\s*[Ll]ien[ _][Ww]eb\s*\|([^}]+)\}\}',
        re.IGNORECASE
    )
    
    # Pattern to extract individual parameters from template
    PARAM_PATTERN = re.compile(r'([^=|]+)=([^|]+)')
    
    def __init__(self):
        """Initialize Lien Web helper."""
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def find_lien_web_template(self, content: str, url: str, position: int) -> Optional[LienWebTemplate]:
        """
        Find if a URL is part of a {{Lien web}} template.
        
        Args:
            content: Full wikitext content
            url: URL to search for
            position: Position of the URL in content
            
        Returns:
            LienWebTemplate if found, None otherwise
        """
        # Search backwards from position to find template start
        template_start = content.rfind('{{', 0, position)
        if template_start == -1:
            return None
        
        # Search forwards from position to find template end
        template_end = content.find('}}', position)
        if template_end == -1:
            return None
        
        # Extract template content
        template_content = content[template_start:template_end + 2]
        
        # Check if it's a {{Lien web}} template
        if not self.LIEN_WEB_PATTERN.search(template_content):
            return None
        
        # Parse parameters
        parameters = self._parse_template_parameters(template_content)
        
        return LienWebTemplate(
            template_name="Lien web",
            parameters=parameters,
            full_match=template_content,
            start_position=template_start,
            end_position=template_end + 2
        )
    
    def _parse_template_parameters(self, template_content: str) -> Dict[str, str]:
        """
        Parse parameters from {{Lien web}} template.

        Args:
            template_content: Full template string including {{...}}

        Returns:
            Dictionary of parameter names to values
        """
        parameters = {}

        # Extract content between {{Lien web| and }}
        inner_content = template_content[template_content.find('|') + 1:-2]

        # Split by | but be careful with values that might contain |
        # Use regex to find all key=value pairs
        # This handles values that might contain special characters
        param_pattern = re.compile(r'([^=|]+)=([^|]+)')
        matches = param_pattern.findall(inner_content)

        for key, value in matches:
            parameters[key.strip()] = value.strip()

        return parameters
    
    def generate_archive_repair_template(
        self,
        original_template: LienWebTemplate,
        archive_url: str,
        archive_date: str,
        original_url: str,
        assume_patch_deployed: bool = True
    ) -> str:
        """
        Generate {{Lien web}} template with archive as main link.

        This produces:
        {{Lien web
         |titre=existing_title
         |url=ARCHIVE_URL  # Archive becomes main link (if patch deployed)
         |site=original_site
         |archive-url=ARCHIVE_URL
         |archive-date=ARCHIVE_DATE
         |brisé le=CURRENT_DATE
        }}

        IMPORTANT: The Wikipedia Lua patch that makes archive the main link
        when "brisé le" + "archive-url" are present may not be deployed yet.
        If assume_patch_deployed=False, we use the original URL as the main link
        to ensure the template works correctly on unpatched wikis.

        Args:
            original_template: Original parsed template
            archive_url: Archive URL to use as main link
            archive_date: Archive date from provider
            original_url: Original dead URL
            assume_patch_deployed: If True, use archive as main link (patched behavior)
                                  If False, use original URL as main link (fallback)

        Returns:
            New {{Lien web}} template string
        """
        params = original_template.parameters.copy()

        # Set url based on patch deployment assumption
        if assume_patch_deployed:
            # Patched behavior: archive becomes main link
            params['url'] = archive_url
        else:
            # Fallback behavior: original URL remains main link
            # Archive is still available via archive-url parameter
            params['url'] = original_url

        # Set archive-url to archive URL
        params['archive-url'] = archive_url

        # Set archive-date
        formatted_archive_date = self._format_archive_date(archive_date)
        params['archive-date'] = formatted_archive_date

        # Set brisé le to current date ONLY if not already present
        # Preserve existing 'brisé le' date if it exists
        if 'brisé le' not in params or not params['brisé le']:
            current_date = datetime.now().strftime('%Y-%m-%d')
            params['brisé le'] = current_date

        # Ensure site parameter exists (extract from original URL if not present)
        if 'site' not in params:
            original_domain = urlparse(original_url).netloc
            params['site'] = original_domain

        # Generate template string
        template_parts = ['{{Lien web']

        # Add parameters in the preferred order from LIEN_WEB_PARAMETERS
        # This ensures all parameters are supported and ordered correctly
        for param in self.LIEN_WEB_PARAMETERS:
            if param in params:
                template_parts.append(f'|{param}={params[param]}')

        # Add any unknown parameters (not in our list but present in template)
        for param, value in params.items():
            if param not in self.LIEN_WEB_PARAMETERS:
                template_parts.append(f'|{param}={value}')

        template_parts.append('}}')

        new_template = ''.join(template_parts)

        self._logger.info(
            f"GENERATED_ARCHIVE_TEMPLATE | original_url={original_url} | "
            f"archive_url={archive_url} | archive_date={formatted_archive_date} | "
            f"assume_patch_deployed={assume_patch_deployed} | main_url={params['url']}"
        )

        return new_template

    def _format_archive_date(self, archive_date: str) -> str:
        """
        Format archive date for {{Lien web}} template.
        
        Archive providers typically return dates in YYYYMMDDHHMMSS format.
        We need to convert to YYYY-MM-DD format for the template.
        
        Args:
            archive_date: Archive date from provider (YYYYMMDDHHMMSS)
            
        Returns:
            Formatted date (YYYY-MM-DD)
        """
        if not archive_date:
            return ""
        
        # If already in YYYY-MM-DD format, return as-is
        if '-' in archive_date and len(archive_date) == 10:
            return archive_date
        
        # Convert from YYYYMMDDHHMMSS to YYYY-MM-DD
        if len(archive_date) >= 8 and archive_date.isdigit():
            year = archive_date[0:4]
            month = archive_date[4:6]
            day = archive_date[6:8]
            return f"{year}-{month}-{day}"
        
        # If format is unrecognized, return as-is
        return archive_date
    
    def should_use_archive_template(self, content: str, url: str, position: int) -> bool:
        """
        Determine if archive template format should be used.
        
        Use archive template format ({{Lien web}} with archive parameters) when:
        - URL is part of a {{Lien web}} template
        - Archive is available and verified
        
        Args:
            content: Full wikitext content
            url: URL being repaired
            position: Position of URL in content
            
        Returns:
            True if archive template format should be used
        """
        template = self.find_lien_web_template(content, url, position)
        return template is not None
