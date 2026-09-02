"""
Template Replacement Validator.

This module provides validation logic for template replacements to ensure
that modifications are minimal and well-formed. This is a generic safeguard
useful for any analyzer doing template replacement, not just dead link repair.

Responsibilities:
- Validate that template replacement is safe and minimal
- Check that content before/after template is unchanged
- Verify template structure validity
- Provide clear error messages for validation failures

Design Principles:
- Pure validation logic (no side effects)
- Generic and reusable across analyzers
- Clear error reporting
"""

import difflib
import logging
from typing import Final, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_MAX_SIGNIFICANT_CHANGES: Final[int] = 10
_DEFAULT_MAX_GROWTH_FACTOR: Final[float] = 2.0


class TemplateReplacementValidator:
    """
    Validator for template replacement operations.

    Ensures that template replacements are minimal and well-formed,
    providing a generic safeguard for any analyzer doing template replacement.
    """

    @staticmethod
    def validate(old_content: str, new_content: str,
                 old_template_start: int, old_template_end: int,
                 new_template: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that template replacement is safe and minimal.

        Args:
            old_content: Original content.
            new_content: New content after replacement.
            old_template_start: Start position of old template.
            old_template_end: End position of old template.
            new_template: New template string.

        Returns:
            Tuple of (is_valid, error_message). error_message is None when
            is_valid is True.
        """
        if old_content is None or new_content is None or new_template is None:
            error_msg = "Template validation failed: missing content or template"
            logger.warning(error_msg)
            return False, error_msg

        if old_template_start < 0 or old_template_end < old_template_start:
            error_msg = "Template validation failed: invalid template position range"
            logger.warning(error_msg)
            return False, error_msg

        if old_template_end > len(old_content):
            error_msg = "Template validation failed: template range exceeds old content length"
            logger.warning(error_msg)
            return False, error_msg

        # Check that content before template is unchanged
        if old_content[:old_template_start] != new_content[:old_template_start]:
            error_msg = "Template validation failed: content before template changed"
            logger.warning(error_msg)
            return False, error_msg

        # Check that content after template is unchanged
        old_after = old_content[old_template_end:]
        new_after = new_content[old_template_start + len(new_template):]

        if old_after != new_after:
            error_msg = "Template validation failed: content after template changed"
            logger.warning(error_msg)
            return False, error_msg

        # Check that template structure is valid
        # Accept all reference template types: {{article}}, {{ouvrage}}, {{Lien web}}, etc.
        is_valid_structure, structure_error = TemplateReplacementValidator.validate_template_structure(new_template)
        if not is_valid_structure:
            error_msg = f"Template validation failed: invalid template structure ({structure_error})"
            logger.warning(error_msg)
            return False, error_msg

        logger.info("Template replacement validated successfully")
        return True, None

    @staticmethod
    def validate_template_structure(template: str) -> Tuple[bool, Optional[str]]:
        """
        Validate template structure without content context.

        Args:
            template: Template string to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not template or not isinstance(template, str):
            return False, "Template must be a non-empty string"

        if not template.startswith('{{') or not template.endswith('}}'):
            return False, "Template must start with {{ and end with }}"

        # CHANGED: was a raw count comparison (template.count('{{') !=
        # template.count('}}')), which only catches a mismatched total
        # count — not actual nesting problems. A malformed template like
        # "{{Lien web|titre={{date|2020}}" (one opened pair never closed,
        # plus one nested pair that IS balanced) has count('{{')=2 and
        # count('}}')=1, so the old check *would* catch that particular
        # case — but a template with an accidentally-matching total count
        # despite broken nesting (e.g. a stray '}}' inside a parameter
        # value compensating for a missing one elsewhere) would slip
        # through undetected. Proper brace-balanced scanning, matching
        # the rigor already used in ReferenceTemplateHelper's own
        # _match_balanced_braces, catches both cases and is the correct
        # fix rather than a stricter count-based heuristic.
        if not TemplateReplacementValidator._is_brace_balanced(template):
            return False, "Template has unbalanced braces"

        return True, None

    @staticmethod
    def _is_brace_balanced(template: str) -> bool:
        """
        Verify that {{ }} pairs in `template` are properly nested and
        balanced (not just equal in count), and that the string as a
        whole forms exactly one top-level {{...}} block with nothing
        left over.

        Mirrors ReferenceTemplateHelper._match_balanced_braces's
        depth-tracking approach so both modules apply the same standard
        of "well-formed template" — a raw '{{' vs '}}' count comparison
        cannot distinguish valid nesting from coincidentally-matching
        stray braces.
        """
        depth = 0
        i = 0
        length = len(template)
        closed_at = None
        while i < length - 1:
            two = template[i:i + 2]
            if two == '{{':
                depth += 1
                i += 2
                continue
            if two == '}}':
                depth -= 1
                if depth < 0:
                    # A '}}' with no matching '{{' before it.
                    return False
                i += 2
                if depth == 0 and closed_at is None:
                    closed_at = i
                continue
            i += 1

        if depth != 0:
            # Unclosed '{{' somewhere.
            return False

        if closed_at is None:
            # No top-level pair ever closed at all (shouldn't happen given
            # the startswith/endswith checks above, but stay defensive).
            return False

        # Nothing may follow the outermost template's closing '}}' other
        # than the '}}' itself already consumed — i.e. the top-level pair
        # must close exactly at the end of the string.
        return closed_at == length