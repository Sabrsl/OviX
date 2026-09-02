"""
Tests for ReferenceEnricherAnalyzer configuration loader.

Tests the configuration loading functionality which follows the same pattern as DeadLinkAnalyzerConfig.
"""

import sys
from pathlib import Path
import tempfile
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from wikipedia_maintenance.utils.reference_enricher_analyzer_config import ReferenceEnricherConfig


class TestReferenceEnricherConfig:
    """Test configuration loading and validation."""
    
    def test_default_configuration(self):
        """Test that default configuration values are set correctly."""
        config = ReferenceEnricherConfig()
        
        assert config.timeout == ReferenceEnricherConfig.DEFAULT_TIMEOUT
        assert config.max_retries == ReferenceEnricherConfig.DEFAULT_MAX_RETRIES
        assert config.max_checks_per_article == ReferenceEnricherConfig.DEFAULT_MAX_CHECKS_PER_ARTICLE
        assert config.enable_site_fill == ReferenceEnricherConfig.DEFAULT_ENABLE_SITE_FILL
        assert config.enable_consulte_le_fill == ReferenceEnricherConfig.DEFAULT_ENABLE_CONSULTE_LE_FILL
    
    def test_load_with_missing_file(self):
        """Test loading configuration when file doesn't exist (uses defaults)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            non_existent_path = Path(tmpdir) / "non_existent_config.yaml"
            config = ReferenceEnricherConfig.load(non_existent_path)
            
            # Should use defaults
            assert config.timeout == ReferenceEnricherConfig.DEFAULT_TIMEOUT
            assert config.max_retries == ReferenceEnricherConfig.DEFAULT_MAX_RETRIES
    
    def test_load_with_valid_config(self):
        """Test loading configuration from a valid YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_content = {
                'reference_enricher_analyzer': {
                    'timeout': 15,
                    'max_retries': 5,
                    'max_checks_per_article': 100,
                    'enable_site_fill': False,
                    'enable_consulte_le_fill': False
                }
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(config_content, f)
            
            config = ReferenceEnricherConfig.load(config_path)
            
            assert config.timeout == 15
            assert config.max_retries == 5
            assert config.max_checks_per_article == 100
            assert config.enable_site_fill is False
            assert config.enable_consulte_le_fill is False
    
    def test_load_with_partial_config(self):
        """Test loading configuration with only some values specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_content = {
                'reference_enricher_analyzer': {
                    'timeout': 20,
                    # Other values omitted
                }
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(config_content, f)
            
            config = ReferenceEnricherConfig.load(config_path)
            
            assert config.timeout == 20  # From config
            assert config.max_retries == ReferenceEnricherConfig.DEFAULT_MAX_RETRIES  # Default
            assert config.max_checks_per_article == ReferenceEnricherConfig.DEFAULT_MAX_CHECKS_PER_ARTICLE  # Default
    
    def test_load_with_invalid_yaml(self):
        """Test loading configuration with invalid YAML (uses defaults)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            
            with open(config_path, 'w') as f:
                f.write("invalid: yaml: content: [unclosed")
            
            config = ReferenceEnricherConfig.load(config_path)
            
            # Should use defaults when YAML is invalid
            assert config.timeout == ReferenceEnricherConfig.DEFAULT_TIMEOUT
    
    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        config = ReferenceEnricherConfig(timeout=10, max_retries=3, max_checks_per_article=50)
        assert config.validate() is True
    
    def test_validate_invalid_timeout(self):
        """Test validation rejects invalid timeout."""
        config = ReferenceEnricherConfig(timeout=-1)
        assert config.validate() is False
    
    def test_validate_invalid_max_retries(self):
        """Test validation rejects invalid max_retries."""
        config = ReferenceEnricherConfig(max_retries=-1)
        assert config.validate() is False
    
    def test_validate_invalid_max_checks(self):
        """Test validation rejects invalid max_checks_per_article."""
        config = ReferenceEnricherConfig(max_checks_per_article=0)
        assert config.validate() is False
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = ReferenceEnricherConfig(timeout=15, max_retries=5)
        config_dict = config.to_dict()
        
        assert config_dict['timeout'] == 15
        assert config_dict['max_retries'] == 5
        assert 'enable_site_fill' in config_dict
        assert 'enable_consulte_le_fill' in config_dict
        assert 'max_checks_per_article' in config_dict
    
    def test_custom_config_path(self):
        """Test loading configuration from custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "custom_config.yaml"
            config_content = {
                'reference_enricher_analyzer': {
                    'timeout': 25
                }
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(config_content, f)
            
            config = ReferenceEnricherConfig.load(config_path)
            assert config.timeout == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
