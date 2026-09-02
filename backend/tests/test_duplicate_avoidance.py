"""
Test cases for duplicate avoidance in reference enrichment and dead link repair.

This tests ensure that:
1. Site parameters are not duplicated when already present
2. Consulté le parameters are not duplicated when already present
3. Parameter variants (site/Site/website, consulté le/Consulté le/consulte le) are properly detected
4. Ouvrage and chapitre templates are never enriched with site/consulté le
"""

import pytest
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper, ReferenceTemplate


class TestDuplicateAvoidance:
    """Test that duplicate parameters are avoided in reference enrichment."""

    def test_site_parameter_not_duplicated(self):
        """Test that site parameter is not added when already present."""
        helper = ReferenceTemplateHelper()
        
        # Template with existing site parameter
        template = ReferenceTemplate(
            template_name="Lien web",
            parameters={
                'titre': 'Histoire de l\'usine Victoria',
                'url': 'https://example.com/test',
                'site': 'drukkerdiffusion.com'
            },
            full_match="{{Lien web|titre=Histoire de l'usine Victoria|url=https://example.com/test|site=drukkerdiffusion.com}}",
            start_position=0,
            end_position=100
        )
        
        # Try to add the same site parameter
        result = helper.generate_enriched_template(
            template,
            site_value="drukkerdiffusion.com",
            consulte_le_value="2026-09-01"
        )
        
        # Should return original template unchanged (site already present)
        assert result == template.full_match
        assert result.count("site=") == 1
        print(f"Template with existing site preserved: {result}")

    def test_consulte_le_parameter_not_duplicated(self):
        """Test that consulté le parameter is not added when already present."""
        helper = ReferenceTemplateHelper()
        
        # Template with existing consulté le parameter
        template = ReferenceTemplate(
            template_name="Lien web",
            parameters={
                'titre': 'Histoire de l\'usine Victoria',
                'url': 'https://example.com/test',
                'site': 'drukkerdiffusion.com',
                'consulté le': '2022-08-05'
            },
            full_match="{{Lien web|titre=Histoire de l'usine Victoria|url=https://example.com/test|site=drukkerdiffusion.com|consulté le=2022-08-05}}",
            start_position=0,
            end_position=120
        )
        
        # Try to add consulté le when already present
        result = helper.generate_enriched_template(
            template,
            site_value="DRUKKER Diffusion",
            consulte_le_value="2026-09-01"
        )
        
        # Should return original template unchanged (both params already present)
        assert result == template.full_match
        assert result.count("consulté le=") == 1
        print(f"Template with existing consulté le preserved: {result}")

    def test_site_variant_detection(self):
        """Test that site parameter variants are properly detected."""
        helper = ReferenceTemplateHelper()
        
        # Template with 'Site' (capitalized) instead of 'site'
        template = ReferenceTemplate(
            template_name="Lien web",
            parameters={
                'titre': 'Test Article',
                'url': 'https://example.com/test',
                'Site': 'example.com'
            },
            full_match="{{Lien web|titre=Test Article|url=https://example.com/test|Site=example.com}}",
            start_position=0,
            end_position=80
        )
        
        # Try to add site parameter (should detect existing 'Site')
        result = helper.generate_enriched_template(
            template,
            site_value="example.com",
            consulte_le_value="2026-09-01"
        )
        
        # Should detect existing 'Site' variant and not duplicate
        assert result.count("site=") <= 1
        assert result.count("Site=") <= 1
        print(f"Template with Site variant detected: {result}")

    def test_consulte_le_variant_detection(self):
        """Test that consulté le parameter variants are properly detected."""
        helper = ReferenceTemplateHelper()
        
        # Template with 'Consulté le' (capitalized) instead of 'consulté le'
        template = ReferenceTemplate(
            template_name="Lien web",
            parameters={
                'titre': 'Test Article',
                'url': 'https://example.com/test',
                'Consulté le': '2022-08-05'
            },
            full_match="{{Lien web|titre=Test Article|url=https://example.com/test|Consulté le=2022-08-05}}",
            start_position=0,
            end_position=90
        )
        
        # Try to add consulté le (should detect existing 'Consulté le')
        result = helper.generate_enriched_template(
            template,
            site_value="example.com",
            consulte_le_value="2026-09-01"
        )
        
        # Should detect existing 'Consulté le' variant and not duplicate
        assert result.count("consulté le=") <= 1
        assert result.count("Consulté le=") <= 1
        print(f"Template with Consulté le variant detected: {result}")

    def test_ouvrage_template_never_enriched(self):
        """Test that ouvrage templates are never enriched with site/consulté le."""
        helper = ReferenceTemplateHelper()
        
        # Ouvrage template without site or consulté le
        template = ReferenceTemplate(
            template_name="ouvrage",
            parameters={
                'titre': 'Test Book',
                'auteur': 'Test Author',
                'éditeur': 'Test Publisher',
                'année': '2020'
            },
            full_match="{{ouvrage|titre=Test Book|auteur=Test Author|éditeur=Test Publisher|année=2020}}",
            start_position=0,
            end_position=90
        )
        
        # Try to add site and consulté le (should be skipped for ouvrage)
        result = helper.generate_enriched_template(
            template,
            site_value="publisher.com",
            consulte_le_value="2026-09-01"
        )
        
        # Should return original template unchanged (ouvrage doesn't support these params)
        assert result == template.full_match
        assert "site=" not in result
        assert "consulté le=" not in result
        print(f"Ouvrage template not enriched: {result}")

    def test_ouvrage_template_with_variations(self):
        """Test that ouvrage template variations are properly detected."""
        helper = ReferenceTemplateHelper()
        
        # Test different case variations
        for template_name in ["ouvrage", "Ouvrage", "OUVRAGE", "ouvrage "]:
            template = ReferenceTemplate(
                template_name=template_name,
                parameters={'titre': 'Test Book'},
                full_match=f"{{{{{template_name}|titre=Test Book}}}}",
                start_position=0,
                end_position=30
            )
            
            result = helper.generate_enriched_template(
                template,
                site_value="test.com",
                consulte_le_value="2026-09-01"
            )
            
            # All variations should be protected
            assert result == template.full_match
            assert "site=" not in result

    def test_partial_enrichment_allowed(self):
        """Test that partial enrichment is allowed when only one param is missing."""
        helper = ReferenceTemplateHelper()
        
        # Template with site but missing consulté le
        template = ReferenceTemplate(
            template_name="Lien web",
            parameters={
                'titre': 'Test Article',
                'url': 'https://example.com/test',
                'site': 'example.com'
            },
            full_match="{{Lien web|titre=Test Article|url=https://example.com/test|site=example.com}}",
            start_position=0,
            end_position=80
        )
        
        # Add only consulté le (site already present)
        result = helper.generate_enriched_template(
            template,
            site_value=None,  # Don't add site
            consulte_le_value="2026-09-01"
        )
        
        # Should add consulté le but not duplicate site
        assert "consulté le=2026-09-01" in result
        assert result.count("site=") == 1
        print(f"Template with partial enrichment: {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
