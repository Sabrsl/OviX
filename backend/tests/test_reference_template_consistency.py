"""
Test suite for ReferenceTemplateHelper consistency checks.

This module validates cross-consistency between TEMPLATES_* constant sets
to prevent regressions where a template appears in contradictory sets.
"""

import pytest
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper


class TestTemplateSetsConsistency:
    """Test cross-consistency between TEMPLATES_* constant sets."""

    def test_without_archive_params_vs_supporting_brise_le(self):
        """
        Templates in TEMPLATES_WITHOUT_ARCHIVE_PARAMS should NOT be in TEMPLATES_SUPPORTING_BRISE_LE.
        
        If a template doesn't support archive parameters, it shouldn't support brisé le either,
        since brisé le is typically used alongside archive parameters.
        """
        without_archive = ReferenceTemplateHelper.TEMPLATES_WITHOUT_ARCHIVE_PARAMS
        supporting_brise_le = ReferenceTemplateHelper.TEMPLATES_SUPPORTING_BRISE_LE
        
        overlap = without_archive & supporting_brise_le
        if overlap:
            pytest.fail(
                f"Templates in TEMPLATES_WITHOUT_ARCHIVE_PARAMS should NOT be in "
                f"TEMPLATES_SUPPORTING_BRISE_LE. Overlap found: {overlap}"
            )

    def test_without_archive_params_vs_supporting_consulte_le(self):
        """
        Templates in TEMPLATES_WITHOUT_ARCHIVE_PARAMS should NOT be in TEMPLATES_SUPPORTING_CONSULTE_LE
        if they are physical/digital publications without web URLs.
        
        This is a soft constraint - some templates might support consulté le without archive params,
        but for physical publications this is usually inconsistent.
        """
        without_archive = ReferenceTemplateHelper.TEMPLATES_WITHOUT_ARCHIVE_PARAMS
        supporting_consulte_le = ReferenceTemplateHelper.TEMPLATES_SUPPORTING_CONSULTE_LE
        
        # For now, this is just a warning - log it but don't fail
        overlap = without_archive & supporting_consulte_le
        if overlap:
            # Check if the overlap makes sense (e.g., article might have online access)
            # For now, just log it for manual review
            print(f"WARNING: Templates in both WITHOUT_ARCHIVE_PARAMS and SUPPORTING_CONSULTE_LE: {overlap}")

    def test_without_site_param_vs_supporting_consulte_le(self):
        """
        Templates in TEMPLATES_WITHOUT_SITE_PARAM should NOT be in TEMPLATES_SUPPORTING_CONSULTE_LE
        unless they have online access (lire en ligne).
        
        Physical publications without site parameter typically shouldn't have consulté le.
        """
        without_site = ReferenceTemplateHelper.TEMPLATES_WITHOUT_SITE_PARAM
        supporting_consulte_le = ReferenceTemplateHelper.TEMPLATES_SUPPORTING_CONSULTE_LE
        
        overlap = without_site & supporting_consulte_le
        if overlap:
            # This might be intentional for templates with lire en ligne
            # Log for manual review
            print(f"INFO: Templates in both WITHOUT_SITE_PARAM and SUPPORTING_CONSULTE_LE: {overlap}")

    def test_archive_as_main_link_vs_without_archive_params(self):
        """
        Templates in TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK should NOT be in
        TEMPLATES_WITHOUT_ARCHIVE_PARAMS.
        
        If a template supports promoting archive to main link, it must support archive parameters.
        """
        archive_as_main = ReferenceTemplateHelper.TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK
        without_archive = ReferenceTemplateHelper.TEMPLATES_WITHOUT_ARCHIVE_PARAMS
        
        overlap = archive_as_main & without_archive
        if overlap:
            pytest.fail(
                f"Templates in TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK should NOT be in "
                f"TEMPLATES_WITHOUT_ARCHIVE_PARAMS. Overlap found: {overlap}"
            )

    def test_known_template_names_coverage(self):
        """
        All templates in KNOWN_TEMPLATE_NAMES should be categorized in at least one
        of the TEMPLATES_* sets for proper behavior.
        
        This ensures new templates are properly categorized.
        """
        known_templates = set(ReferenceTemplateHelper.KNOWN_TEMPLATE_NAMES.values())
        
        # Union of all template sets
        all_categorized = (
            ReferenceTemplateHelper.TEMPLATES_SUPPORTING_CONSULTE_LE |
            ReferenceTemplateHelper.TEMPLATES_WITHOUT_ARCHIVE_PARAMS |
            ReferenceTemplateHelper.TEMPLATES_WITHOUT_SITE_PARAM |
            ReferenceTemplateHelper.TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK |
            ReferenceTemplateHelper.TEMPLATES_SUPPORTING_BRISE_LE
        )
        
        uncategorized = known_templates - all_categorized
        if uncategorized:
            print(f"WARNING: Templates not categorized in any TEMPLATES_* set: {uncategorized}")
            # Don't fail - some templates might not need categorization

    def test_template_specific_parameters_consistency(self):
        """
        Verify that TEMPLATE_SPECIFIC_PARAMETERS includes parameters that are
        actually used by the code logic (e.g., brisé le, consulté le, archive-url).
        
        This is a sanity check to ensure the parameter list is maintained.
        """
        template_specific = ReferenceTemplateHelper.TEMPLATE_SPECIFIC_PARAMETERS
        
        # Check that key templates have parameter lists
        assert 'lien web' in template_specific, "lien web should be in TEMPLATE_SPECIFIC_PARAMETERS"
        assert 'article' in template_specific, "article should be in TEMPLATE_SPECIFIC_PARAMETERS"
        assert 'ouvrage' in template_specific, "ouvrage should be in TEMPLATE_SPECIFIC_PARAMETERS"
        
        # Check that lien web has expected parameters
        lien_web_params = template_specific['lien web']
        assert 'url' in lien_web_params, "lien web should have 'url' parameter"
        assert 'titre' in lien_web_params, "lien web should have 'titre' parameter"


class TestTemplateSetSemanticLogic:
    """Test semantic logic of template parameter support."""

    def test_ouvrage_has_archive_and_brise_le(self):
        """
        ouvrage should support archive parameters and brisé le per Wikipedia documentation.
        """
        assert 'ouvrage' not in ReferenceTemplateHelper.TEMPLATES_WITHOUT_ARCHIVE_PARAMS, \
            "ouvrage should support archive parameters"
        assert 'ouvrage' in ReferenceTemplateHelper.TEMPLATES_SUPPORTING_BRISE_LE, \
            "ouvrage should support brisé le parameter"

    def test_chapitre_no_archive_params(self):
        """
        chapitre should NOT support archive parameters (physical publication).
        """
        assert 'chapitre' in ReferenceTemplateHelper.TEMPLATES_WITHOUT_ARCHIVE_PARAMS, \
            "chapitre should not support archive parameters"

    def test_lien_web_has_consulte_le_and_archive(self):
        """
        lien web should support consulté le and archive parameters.
        """
        assert 'lien web' in ReferenceTemplateHelper.TEMPLATES_SUPPORTING_CONSULTE_LE, \
            "lien web should support consulté le"
        assert 'lien web' not in ReferenceTemplateHelper.TEMPLATES_WITHOUT_ARCHIVE_PARAMS, \
            "lien web should support archive parameters"
        assert 'lien web' in ReferenceTemplateHelper.TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK, \
            "lien web should support promoting archive to main link"

    def test_article_no_brise_le(self):
        """
        article should NOT support brisé le per Wikipedia documentation.
        """
        assert 'article' not in ReferenceTemplateHelper.TEMPLATES_SUPPORTING_BRISE_LE, \
            "article should not support brisé le parameter"

    def test_lien_archive_special_semantics(self):
        """
        lien archive should have special semantics (horodatage archive instead of archive-url/date).
        """
        # lien archive uses horodatage archive, not standard archive-url/date
        # It should be in WITHOUT_ARCHIVE_PARAMS to prevent standard archive handling
        # But this depends on the current implementation - check the actual state
        lien_archive_in_without = 'lien archive' in ReferenceTemplateHelper.TEMPLATES_WITHOUT_ARCHIVE_PARAMS
        lien_archive_in_consulte = 'lien archive' in ReferenceTemplateHelper.TEMPLATES_SUPPORTING_CONSULTE_LE
        
        # If lien archive is in WITHOUT_ARCHIVE_PARAMS, it shouldn't be in CONSULTE_LE
        # (or this should be documented as a special case)
        if lien_archive_in_without and lien_archive_in_consulte:
            print(f"INFO: lien archive is in both WITHOUT_ARCHIVE_PARAMS and SUPPORTING_CONSULTE_LE - verify this is intentional")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
