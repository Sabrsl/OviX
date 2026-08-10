"""
Correction proposal module with diff generation.
"""

import re
import difflib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urlparse

from ..analyzers.base import Issue
from .ollama_supervisor import OllamaSupervisor


@dataclass
class Correction:
    """Represents a proposed correction."""
    issue: Issue
    applied: bool = False
    supervisor_decision: Optional[str] = None  # "approve", "reject", "modify", "skipped", "default"
    supervisor_reason: Optional[str] = None
    modified_by_supervisor: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'issue': self.issue.to_dict(),
            'applied': self.applied,
            'supervisor_decision': self.supervisor_decision,
            'supervisor_reason': self.supervisor_reason,
            'modified_by_supervisor': self.modified_by_supervisor
        }


class Corrector:
    """Applies corrections to article content and generates diffs."""
    
    def __init__(self, original_content: str, use_supervisor: bool = False, max_validations: Optional[int] = None):
        """Initialize corrector with original content.
        
        Args:
            original_content: Original article wikicode
            use_supervisor: Whether to use Ollama supervisor for validation
            max_validations: Maximum number of supervisor validations (None = unlimited)
        """
        self.original_content = original_content
        self.current_content = original_content
        self.corrections: List[Correction] = []
        self.use_supervisor = use_supervisor
        self.supervisor = OllamaSupervisor(max_validations=max_validations) if use_supervisor else None
    
    def apply_correction(self, issue: Issue) -> bool:
        """Apply a single correction.
        
        Args:
            issue: Issue to correct
            
        Returns:
            True if correction was applied, False otherwise
        """
        if not issue.suggested_text:
            # Cannot auto-fix issues without suggested text
            return False
        
        # Use position-based replacement if position is available
        if issue.position is not None:
            # Verify the original text matches at the expected position
            start = issue.position
            end = start + len(issue.original_text) if issue.original_text else start
            
            # Check if position is within bounds
            if start >= 0 and end <= len(self.current_content):
                # Verify the text matches (in case of previous corrections)
                if not issue.original_text or self.current_content[start:end] == issue.original_text:
                    # Apply the correction at the specific position
                    self.current_content = (
                        self.current_content[:start] + 
                        issue.suggested_text + 
                        self.current_content[end:]
                    )
                    self.corrections.append(Correction(issue=issue, applied=True))
                    return True
        
        # Fallback to simple string replacement if position not available
        # BUT with context validation to avoid wrong replacements
        if issue.original_text and issue.original_text in self.current_content:
            # Count occurrences to avoid replacing the wrong one
            occurrences = self.current_content.count(issue.original_text)
            if occurrences == 1:
                # Safe to replace: only one occurrence exists
                self.current_content = self.current_content.replace(
                    issue.original_text, 
                    issue.suggested_text, 
                    1  # Replace only first occurrence
                )
                self.corrections.append(Correction(issue=issue, applied=True))
                return True
            elif occurrences > 1:
                # Multiple occurrences - too risky to replace without position
                # Skip this correction to avoid corrupting the wrong occurrence
                logger.warning(f"Skipping correction: {occurrences} occurrences of '{issue.original_text}' found, cannot safely replace without position")
                self.corrections.append(Correction(issue=issue, applied=False))
                return False
        else:
            # Original text not found (might have been changed by previous corrections)
            self.corrections.append(Correction(issue=issue, applied=False))
            return False
    
    def _adjust_position_for_offset(self, position: int, offset: int) -> int:
        """Adjust a position based on text offset from previous corrections.
        
        Args:
            position: Original position
            offset: Cumulative offset from previous corrections
            
        Returns:
            Adjusted position
        """
        return position + offset
    
    def apply_corrections(self, issues: List[Issue], 
                         selected_indices: Optional[List[int]] = None) -> str:
        """Apply multiple corrections.
        
        Args:
            issues: List of issues to correct
            selected_indices: Indices of issues to apply (None = all)
            
        Returns:
            Corrected content
        """
        self.current_content = self.original_content
        self.corrections = []
        
        if selected_indices is None:
            selected_indices = range(len(issues))
        
        # Sort issues by position (reverse order to avoid position shifts)
        # This is a simplified approach - real implementation would be more sophisticated
        sorted_issues = sorted(
            [issues[i] for i in selected_indices],
            key=lambda x: x.position if x.position is not None else 0,
            reverse=True
        )
        
        for issue in sorted_issues:
            self.apply_correction(issue)
        
        return self.current_content
    
    def _check_overlap(self, pos1: int, len1: int, pos2: int, len2: int) -> bool:
        """Check if two spans overlap.
        
        Args:
            pos1: Start position of first span
            len1: Length of first span
            pos2: Start position of second span
            len2: Length of second span
            
        Returns:
            True if spans overlap
        """
        end1 = pos1 + len1
        end2 = pos2 + len2
        return not (end1 <= pos2 or end2 <= pos1)
    
    def apply_corrections_with_offset_tracking(self, issues: List[Issue], 
                                               selected_indices: Optional[List[int]] = None) -> str:
        """Apply multiple corrections with proper offset tracking and overlap detection.
        
        This method:
        - Tracks the cumulative offset from each correction and adjusts subsequent positions
        - Detects and skips overlapping corrections to prevent corruption
        - Logs skipped corrections for debugging
        
        Args:
            issues: List of issues to correct
            selected_indices: Indices of issues to apply (None = all)
            
        Returns:
            Corrected content
        """
        self.current_content = self.original_content
        self.corrections = []
        
        if selected_indices is None:
            selected_indices = range(len(issues))
        
        # Sort issues by position (ascending order) and track offset
        sorted_issues = sorted(
            [issues[i] for i in selected_indices],
            key=lambda x: x.position if x.position is not None else 0
        )
        
        cumulative_offset = 0
        applied_spans = []  # Track (start, end) of applied corrections to detect overlaps
        
        for issue in sorted_issues:
            if not issue.suggested_text:
                continue
            
            # Adjust position based on cumulative offset from previous corrections
            adjusted_position = self._adjust_position_for_offset(
                issue.position if issue.position is not None else 0,
                cumulative_offset
            )
            
            # Calculate the offset this correction will introduce
            original_length = len(issue.original_text) if issue.original_text else 0
            new_length = len(issue.suggested_text)
            offset_delta = new_length - original_length
            
            # Check for overlap with previously applied corrections
            has_overlap = False
            if adjusted_position is not None and original_length > 0:
                for applied_start, applied_end in applied_spans:
                    if self._check_overlap(adjusted_position, original_length, applied_start, applied_end - applied_start):
                        # Overlap detected - skip this correction
                        has_overlap = True
                        break
            
            if has_overlap:
                self.corrections.append(Correction(
                    issue=issue, 
                    applied=False,
                    supervisor_decision="skipped",
                    supervisor_reason="Chevauchement avec une autre correction"
                ))
                continue
            
            # Supervisor validation (if enabled)
            text_to_apply = issue.suggested_text
            supervisor_action = None
            supervisor_reason = None
            modified_by_supervisor = False
            
            if self.use_supervisor and self.supervisor and self.supervisor.is_available():
                decision = self.supervisor.review_correction(
                    full_content=self.original_content,
                    position=issue.position if issue.position is not None else 0,
                    original=issue.original_text or "",
                    suggested=issue.suggested_text,
                    issue_type=issue.issue_type,
                    description=issue.description
                )
                
                supervisor_action = decision.action
                supervisor_reason = decision.reason
                
                if decision.action == "reject":
                    self.corrections.append(Correction(
                        issue=issue, 
                        applied=False,
                        supervisor_decision="reject",
                        supervisor_reason=decision.reason
                    ))
                    continue
                elif decision.action == "modify" and decision.modified_text:
                    text_to_apply = decision.modified_text
                    new_length = len(text_to_apply)
                    offset_delta = new_length - original_length
                    modified_by_supervisor = True
                elif decision.action == "approve":
                    # Explicit approval from supervisor
                    pass
                else:
                    # Default approval (timeout, error, limit reached)
                    supervisor_action = "default"
            
            # Apply the correction at the adjusted position
            if adjusted_position is not None and adjusted_position >= 0:
                start = adjusted_position
                end = start + original_length
                
                if end <= len(self.current_content):
                    if not issue.original_text or self.current_content[start:end] == issue.original_text:
                        self.current_content = (
                            self.current_content[:start] + 
                            text_to_apply + 
                            self.current_content[end:]
                        )
                        self.corrections.append(Correction(
                            issue=issue, 
                            applied=True,
                            supervisor_decision=supervisor_action or "auto",
                            supervisor_reason=supervisor_reason,
                            modified_by_supervisor=modified_by_supervisor
                        ))
                        cumulative_offset += offset_delta
                        if original_length > 0:
                            applied_spans.append((start, start + new_length))
                    else:
                        self.corrections.append(Correction(
                            issue=issue, 
                            applied=False,
                            supervisor_decision="error",
                            supervisor_reason="Texte original non trouvé à la position attendue"
                        ))
                else:
                    self.corrections.append(Correction(
                        issue=issue, 
                        applied=False,
                        supervisor_decision="error",
                        supervisor_reason="Position hors limites"
                    ))
            else:
                # Fallback to string replacement
                if issue.original_text and issue.original_text in self.current_content:
                    self.current_content = self.current_content.replace(
                        issue.original_text, 
                        text_to_apply, 
                        1
                    )
                    self.corrections.append(Correction(
                        issue=issue, 
                        applied=True,
                        supervisor_decision=supervisor_action or "auto",
                        supervisor_reason=supervisor_reason,
                        modified_by_supervisor=modified_by_supervisor
                    ))
                else:
                    self.corrections.append(Correction(
                        issue=issue, 
                        applied=False,
                        supervisor_decision="error",
                        supervisor_reason="Texte original non trouvé"
                    ))
        
        return self.current_content
    
    def get_diff(self) -> str:
        """Generate unified diff between original and corrected content.
        
        Returns:
            Unified diff string
        """
        original_lines = self.original_content.splitlines(keepends=True)
        corrected_lines = self.current_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            corrected_lines,
            fromfile='original',
            tofile='corrected',
            lineterm=''
        )
        
        return ''.join(diff)
    
    def get_html_diff(self) -> str:
        """Generate HTML diff with color coding (red for deletions, green for additions).
        
        Returns:
            HTML diff string
        """
        original_lines = self.original_content.splitlines(keepends=True)
        corrected_lines = self.current_content.splitlines(keepends=True)
        
        differ = difflib.HtmlDiff(wrapcolumn=80)
        html_diff = differ.make_table(
            original_lines,
            corrected_lines,
            fromdesc='Original',
            todesc='Corrigé',
            context=True,
            numlines=3
        )
        
        # Replace default colors with custom colors (red for deletions, green for additions)
        # HtmlDiff uses: .diff_sub for deletions, .diff_add for additions
        html_diff = html_diff.replace(
            'class="diff_sub"',
            'class="diff_sub" style="background-color: #ffe6e6; color: #cc0000;"'
        )
        html_diff = html_diff.replace(
            'class="diff_add"',
            'class="diff_add" style="background-color: #e6ffe6; color: #006600;"'
        )
        html_diff = html_diff.replace(
            'class="diff_chg"',
            'class="diff_chg" style="background-color: #fff4e6; color: #cc6600;"'
        )
        
        return html_diff
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of corrections applied.
        
        Returns:
            Dictionary with correction statistics
        """
        total = len(self.corrections)
        applied = sum(1 for c in self.corrections if c.applied)
        failed = total - applied
        
        # Count by issue type
        by_type = {}
        for correction in self.corrections:
            issue_type = correction.issue.issue_type
            if issue_type not in by_type:
                by_type[issue_type] = {'applied': 0, 'failed': 0}
            if correction.applied:
                by_type[issue_type]['applied'] += 1
            else:
                by_type[issue_type]['failed'] += 1
        
        return {
            'total_corrections': total,
            'applied': applied,
            'failed': failed,
            'by_type': by_type
        }
    
    def reset(self):
        """Reset to original content."""
        self.current_content = self.original_content
        self.corrections = []
    
    def get_corrected_content(self) -> str:
        """Get current corrected content.
        
        Returns:
            Corrected wikicode
        """
        return self.current_content

    # ------------------------------------------------------------------
    # Advanced correction methods for wikification
    # ------------------------------------------------------------------

    def merge_duplicate_refs(self, content: str, duplicate_groups: List[tuple]) -> str:
        """
        Merge duplicate references using <ref name="x"> syntax.
        
        Args:
            content: Wikicode content
            duplicate_groups: List of (normalized_ref, positions) tuples from find_duplicate_refs
            
        Returns:
            Content with merged references
        """
        if not duplicate_groups:
            return content
        
        # For each group, assign a name to the first occurrence
        # and use <ref name="x"/> for subsequent occurrences
        result = content
        offset = 0
        
        for i, (normalized, positions) in enumerate(duplicate_groups):
            if len(positions) < 2:
                continue
            
            # Generate a reference name
            ref_name = f"ref{i+1}"
            
            # Find the actual reference text at each position
            ref_pattern = re.compile(r'<ref[^>]*>(.*?)</ref>', re.IGNORECASE | re.DOTALL)
            
            for j, pos in enumerate(positions):
                # Find the reference at this position
                for match in ref_pattern.finditer(content):
                    if match.start() == pos:
                        ref_text = match.group(0)
                        
                        if j == 0:
                            # First occurrence: add name attribute
                            if '<ref name=' not in ref_text:
                                new_ref = ref_text.replace('<ref', f'<ref name="{ref_name}"', 1)
                                result = result[:pos + offset] + new_ref + result[pos + offset + len(ref_text):]
                                offset += len(new_ref) - len(ref_text)
                        else:
                            # Subsequent occurrences: use named reference
                            new_ref = f'<ref name="{ref_name}" />'
                            result = result[:pos + offset] + new_ref + result[pos + offset + len(ref_text):]
                            offset += len(new_ref) - len(ref_text)
                        break
        
        return result

    def convert_to_wikitable(self, content: str, list_start: int, list_end: int, 
                            headers: List[str]) -> str:
        """
        Convert a list-based works list (filmography/discography) to a wikitable.
        
        Args:
            content: Wikicode content
            list_start: Start position of the list
            list_end: End position of the list
            headers: List of column headers for the table
            
        Returns:
            Content with wikitable instead of list
        """
        # Extract the list content
        list_content = content[list_start:list_end]
        
        # Parse list items (assuming * format)
        lines = list_content.split('\n')
        items = [line.strip().lstrip('*').strip() for line in lines if line.strip().startswith('*')]
        
        # Build wikitable
        table_lines = ['{| class="wikitable"']
        table_lines.append(f"! {' !! '.join(headers)}")
        table_lines.append('|-')
        
        for item in items:
            # Split by common separators (dash, pipe, etc.)
            parts = re.split(r'\s*[-–|]\s*', item)
            table_lines.append(f"| {' | '.join(parts)}")
            table_lines.append('|-')
        
        table_lines.append('|}')
        
        table_text = '\n'.join(table_lines)
        
        # Replace list with table
        result = content[:list_start] + table_text + content[list_end:]
        
        return result

    def format_social_media(self, content: str) -> str:
        """
        Format social media URLs in external links section.
        Groups them and adds appropriate labels.
        
        Args:
            content: Wikicode content
            
        Returns:
            Content with formatted social media links
        """
        # Find external links section
        external_section_match = re.search(r'==\s*[Ll]iens externes\s*==', content)
        if not external_section_match:
            return content
        
        section_start = external_section_match.end()
        next_heading = re.search(r'\n==', content[section_start:])
        section_end = section_start + next_heading.start() if next_heading else len(content)
        
        section_content = content[section_start:section_end]
        
        # Extract social media URLs
        social_domains = {'twitter.com', 'x.com', 'facebook.com', 'instagram.com', 
                        'tiktok.com', 'linkedin.com', 'youtube.com', 'threads.net'}
        
        url_pattern = re.compile(r'\*\s*(https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+[^\s.,])', re.IGNORECASE)
        social_urls = []
        other_urls = []
        
        for match in url_pattern.finditer(section_content):
            url = match.group(1)
            parsed = urlparse(url)
            if parsed.netloc.lower() in social_domains:
                social_urls.append(url)
            else:
                other_urls.append(url)
        
        # Rebuild section with grouped social media
        new_section = []
        
        if social_urls:
            new_section.append("=== Réseaux sociaux ===")
            for url in social_urls:
                new_section.append(f"* {url}")
            new_section.append("")
        
        if other_urls:
            new_section.append("=== Autres liens ===")
            for url in other_urls:
                new_section.append(f"* {url}")
        
        new_section_text = '\n'.join(new_section)
        
        # Replace section
        result = content[:section_start] + new_section_text + content[section_end:]
        
        return result

    def group_authority_ids(self, content: str) -> str:
        """
        Group scattered authority control IDs into a single {{Autorité}} template.
        
        Args:
            content: Wikicode content
            
        Returns:
            Content with grouped authority IDs
        """
        # Find authority ID patterns
        authority_patterns = {
            'ISNI': r'\bISNI\s*[:=]\s*(\d{4}\s?\d{4}\s?\d{4}\s?\d{3}[0-9Xx])',
            'VIAF': r'\bVIAF\s*[:=]\s*(\d{8,})',
            'BNF': r'\bBNF\s*[:=]\s*(\d{8,})',
            'GND': r'\bGND\s*[:=]\s*(\d{8,})',
            'LCCN': r'\bLCCN\s*[:=]\s*([nN]\d{8,})',
        }
        
        found_ids = {}
        for authority, pattern in authority_patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                found_ids[authority] = matches
        
        if not found_ids:
            return content
        
        # Build {{Autorité}} template
        params = []
        for authority, values in found_ids.items():
            for value in values:
                params.append(f"{authority}={value}")
        
        autorité_template = f"{{{{Autorité|{'|'.join(params)}}}}}"
        
        # Find where to place the template (typically at the end before categories)
        # Remove scattered IDs and place template
        result = content
        
        # Remove scattered authority IDs
        for authority, pattern in authority_patterns.items():
            result = re.sub(pattern, '', result)
        
        # Add template at the end (before categories)
        category_match = re.search(r'\[\[(?:Catégorie|Category):', result, re.IGNORECASE)
        if category_match:
            insert_pos = category_match.start()
            result = result[:insert_pos] + '\n' + autorité_template + '\n' + result[insert_pos:]
        else:
            result = result + '\n' + autorité_template + '\n'
        
        return result

    def move_social_media_to_external(self, content: str) -> str:
        """
        Move social media URLs from references to external links section.
        
        Args:
            content: Wikicode content
            
        Returns:
            Content with social media moved to external links
        """
        social_domains = {'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
                        'tiktok.com', 'linkedin.com', 'youtube.com', 'threads.net'}
        
        # Find social media URLs in references
        ref_pattern = re.compile(r'<ref[^>]*>(.*?)</ref>', re.IGNORECASE | re.DOTALL)
        social_urls_in_refs = []
        
        for match in ref_pattern.finditer(content):
            ref_content = match.group(1)
            url_pattern = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+', re.IGNORECASE)
            for url_match in url_pattern.finditer(ref_content):
                url = url_match.group()
                parsed = urlparse(url)
                if parsed.netloc.lower() in social_domains:
                    social_urls_in_refs.append((match.start(), match.end(), url))
        
        if not social_urls_in_refs:
            return content
        
        # Remove social media from references
        result = content
        offset = 0
        
        for start, end, url in social_urls_in_refs:
            # Remove the reference containing the social media URL
            result = result[:start + offset] + result[end + offset:]
            offset -= (end - start)
        
        # Add to external links section
        external_section_match = re.search(r'==\s*[Ll]iens externes\s*==', result)
        if external_section_match:
            section_start = external_section_match.end()
            # Add social media URLs
            social_links = '\n'.join([f"* {url}" for _, _, url in social_urls_in_refs])
            result = result[:section_start] + '\n' + social_links + '\n' + result[section_start:]
        else:
            # Create external links section
            social_links = '\n'.join([f"* {url}" for _, _, url in social_urls_in_refs])
            result = result + '\n== Liens externes ==\n' + social_links + '\n'
        
        return result

    def fix_portal_placement(self, content: str) -> str:
        """
        Move portal templates to be autonomous before categories.
        
        Args:
            content: Wikicode content
            
        Returns:
            Content with portals correctly placed
        """
        # Find all portal templates
        portal_pattern = re.compile(r'\{\{[Pp]ortail\|[^}]+\}\}')
        portals = list(portal_pattern.finditer(content))
        
        if not portals:
            return content
        
        # Find categories
        category_pattern = re.compile(r'\[\[(?:Catégorie|Category):[^\]]+\]\]', re.IGNORECASE)
        categories = list(category_pattern.finditer(content))
        
        if not categories:
            return content
        
        # Remove portals from current positions
        result = content
        offset = 0
        
        for portal in portals:
            result = result[:portal.start() + offset] + result[portal.end() + offset:]
            offset -= (portal.end() - portal.start())
        
        # Insert portals before first category
        first_cat_pos = categories[0].start() + offset
        portal_text = '\n'.join([p.group() for p in portals])
        result = result[:first_cat_pos] + '\n' + portal_text + '\n' + result[first_cat_pos:]
        
        return result

    def restructure_voir_aussi(self, content: str, subsections: List[str]) -> str:
        """
        Restructure "Voir aussi" subsections into a single section.
        
        Args:
            content: Wikicode content
            subsections: List of subsection titles to merge
            
        Returns:
            Content with restructured "Voir aussi"
        """
        # Find "Voir aussi" section
        voir_aussi_match = re.search(r'==\s*[Vv]oir aussi\s*==', content)
        if not voir_aussi_match:
            return content
        
        section_start = voir_aussi_match.end()
        next_heading = re.search(r'\n==', content[section_start:])
        section_end = section_start + next_heading.start() if next_heading else len(content)
        
        section_content = content[section_start:section_end]
        
        # Find subsections to merge
        subsection_pattern = re.compile(r'===\s*([^=]+)\s*===')
        subsection_matches = list(subsection_pattern.finditer(section_content))
        
        if not subsection_matches:
            return content
        
        # Extract content from each subsection
        merged_content = []
        for match in subsection_matches:
            subsection_title = match.group(1).strip()
            subsection_start = match.end()
            
            # Find next subsection or end
            next_subsection = subsection_pattern.search(section_content[subsection_start:])
            subsection_end = subsection_start + next_subsection.start() if next_subsection else len(section_content)
            
            subsection_text = section_content[subsection_start:subsection_end].strip()
            merged_content.append(subsection_text)
        
        # Rebuild section without subsections
        new_section = '\n'.join(merged_content)
        result = content[:section_start] + '\n' + new_section + '\n' + content[section_end:]
        
        return result

    def fix_heading_levels(self, content: str) -> str:
        """
        Fix heading level jumps to ensure consistent hierarchy.
        
        Args:
            content: Wikicode content
            
        Returns:
            Content with fixed heading levels
        """
        heading_pattern = re.compile(r'^(={1,6})\s*([^=]+?)\s*\1\s*$', re.MULTILINE)
        headings = list(heading_pattern.finditer(content))
        
        if len(headings) < 2:
            return content
        
        result = content
        offset = 0
        
        for i in range(len(headings) - 1):
            current = headings[i]
            next_heading = headings[i + 1]
            
            current_level = len(current.group(1))
            next_level = len(next_heading.group(1))
            
            # If next level jumps more than 1, fix it
            if next_level > current_level + 1:
                # Set next level to current_level + 1
                new_level = current_level + 1
                new_markers = '=' * new_level
                old_heading = next_heading.group(0)
                new_heading = f"{new_markers} {next_heading.group(2).strip()} {new_markers}"
                
                # Replace
                pos = next_heading.start() + offset
                result = result[:pos] + new_heading + result[pos + len(old_heading):]
                offset += len(new_heading) - len(old_heading)
        
        return result

    def merge_duplicate_sections(self, content: str, duplicate_titles: List[str]) -> str:
        """
        Merge duplicate sections by keeping the first occurrence and removing others.
        
        Args:
            content: Wikicode content
            duplicate_titles: List of section titles that are duplicated
            
        Returns:
            Content with duplicate sections removed
        """
        result = content
        offset = 0
        
        for title in duplicate_titles:
            # Find all occurrences of this section
            heading_pattern = re.compile(rf'^==\s*{re.escape(title)}\s*==', re.MULTILINE)
            matches = list(heading_pattern.finditer(content))
            
            if len(matches) > 1:
                # Keep first, remove others
                for match in matches[1:]:
                    section_start = match.start() + offset
                    # Find end of section (next heading or end)
                    next_heading = re.search(r'\n==', result[section_start:])
                    section_end = section_start + next_heading.start() if next_heading else len(result)
                    
                    result = result[:section_start] + result[section_end:]
                    offset -= (section_end - section_start)
        
        return result

    def replace_html_with_wikicode(self, content: str) -> str:
        """
        Replace HTML tags with equivalent wikicode where possible.
        
        Args:
            content: Wikicode content
            
        Returns:
            Content with HTML replaced by wikicode
        """
        # Common HTML to wikicode replacements
        replacements = {
            r'<b>([^<]+)</b>': r"'''\1'''",
            r'<i>([^<]+)</i>': r"''\1''",
            r'<strong>([^<]+)</strong>': r"'''\1'''",
            r'<em>([^<]+)</em>': r"''\1''",
            r'<br\s*/?>': '\n',
            r'<br\s*/?>': '\n',
        }
        
        result = content
        
        for html_pattern, wiki_replacement in replacements.items():
            result = re.sub(html_pattern, wiki_replacement, result, flags=re.IGNORECASE)
        
        return result
