"""
XMLTypographyAnalyzer Configuration Loader.

This module handles loading configuration for the XMLTypographyAnalyzer from YAML files.
It follows the same pattern as DeadLinkAnalyzerConfig and ReferenceEnricherConfig to maintain consistency.

Responsibilities:
- Load configuration from YAML files
- Provide default values when configuration is missing
- Validate configuration values
- Support dependency injection for testing

Design Principles:
- Injectable config path for testing
- Sensible defaults for all values
- Clear error handling for missing/invalid config
"""

import logging
from typing import Any, Dict, Final, Optional
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

_CONFIG_SECTION_KEY: Final[str] = 'typography_xml_analyzer'


class TypographyXMLAnalyzerConfig:
    """
    Configuration loader for XMLTypographyAnalyzer.

    Provides methods to load configuration from YAML files with sensible defaults
    and validation. Supports dependency injection of config path for testing.
    """

    # Default configuration values
    DEFAULT_ENABLED: Final[bool] = False
    DEFAULT_XML_RULES_PATH: Final[Optional[str]] = None
    DEFAULT_MAX_CORRECTIONS_PER_ARTICLE: Final[int] = 100
    DEFAULT_IGNORE_PROTECTED_AREAS: Final[bool] = True
    DEFAULT_CASE_SENSITIVE: Final[bool] = False

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "TypographyXMLAnalyzerConfig":
        """
        Load configuration from YAML file with fallback to defaults.

        Any error while locating, reading, parsing, or applying the config
        file (missing file, malformed YAML, wrong types, permission errors,
        etc.) results in falling back to defaults rather than raising -
        configuration loading must never crash analysis startup.

        Args:
            config_path: Path to config file. If None, uses default path.

        Returns:
            TypographyXMLAnalyzerConfig instance with loaded configuration
            (falls back to an all-defaults instance on any error).
        """
        if config_path is None:
            # Default path relative to this file
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"

        config_data: Dict[str, Any] = {
            'enabled': cls.DEFAULT_ENABLED,
            'xml_rules_path': cls.DEFAULT_XML_RULES_PATH,
            'max_corrections_per_article': cls.DEFAULT_MAX_CORRECTIONS_PER_ARTICLE,
            'ignore_protected_areas': cls.DEFAULT_IGNORE_PROTECTED_AREAS,
            'case_sensitive': cls.DEFAULT_CASE_SENSITIVE,
        }

        try:
            config_exists = config_path.exists()
        except OSError as e:
            logger.warning(f"Failed to check config path {config_path}: {e}. Using defaults.")
            config_exists = False

        if config_exists:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f)

                if yaml_config and isinstance(yaml_config, dict) and _CONFIG_SECTION_KEY in yaml_config:
                    analyzer_config = yaml_config[_CONFIG_SECTION_KEY]

                    if isinstance(analyzer_config, dict):
                        for key in config_data:
                            if key in analyzer_config:
                                config_data[key] = analyzer_config[key]

                        logger.info(
                            f"Loaded XMLTypographyAnalyzer config: enabled={config_data['enabled']}, "
                            f"max_corrections={config_data['max_corrections_per_article']}, "
                            f"ignore_protected={config_data['ignore_protected_areas']}, "
                            f"case_sensitive={config_data['case_sensitive']}"
                        )
                    else:
                        logger.warning(
                            f"Config section '{_CONFIG_SECTION_KEY}' is not a mapping in {config_path}. "
                            f"Using defaults."
                        )
            except (yaml.YAMLError, OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to load config from {config_path}: {e}. Using defaults.")
        else:
            logger.info(f"Config file not found at {config_path}. Using defaults.")

        instance = cls(**config_data)

        if not instance.validate():
            logger.warning(
                f"Loaded configuration failed validation ({instance.to_dict()}); "
                f"falling back to defaults."
            )
            instance = cls()

        return instance

    def __init__(self, enabled: bool = DEFAULT_ENABLED,
                 xml_rules_path: Optional[str] = DEFAULT_XML_RULES_PATH,
                 max_corrections_per_article: int = DEFAULT_MAX_CORRECTIONS_PER_ARTICLE,
                 ignore_protected_areas: bool = DEFAULT_IGNORE_PROTECTED_AREAS,
                 case_sensitive: bool = DEFAULT_CASE_SENSITIVE):
        """
        Initialize configuration with specific values.

        Args:
            enabled: Whether the XML typography analyzer is enabled
            xml_rules_path: Custom path to the XML rules file (None for default)
            max_corrections_per_article: Maximum corrections to apply per article
            ignore_protected_areas: Whether to ignore protected areas (nowiki, comments, etc.)
            case_sensitive: Whether regex matching should be case-sensitive
        """
        self.enabled = enabled
        self.xml_rules_path = xml_rules_path
        self.max_corrections_per_article = max_corrections_per_article
        self.ignore_protected_areas = ignore_protected_areas
        self.case_sensitive = case_sensitive

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'enabled': self.enabled,
            'xml_rules_path': self.xml_rules_path,
            'max_corrections_per_article': self.max_corrections_per_article,
            'ignore_protected_areas': self.ignore_protected_areas,
            'case_sensitive': self.case_sensitive,
        }

    def validate(self) -> bool:
        """
        Validate configuration values.

        Returns:
            True if configuration is valid, False otherwise.
        """
        try:
            if self.max_corrections_per_article <= 0:
                logger.error(f"Invalid max_corrections_per_article: {self.max_corrections_per_article} must be positive")
                return False

            if self.xml_rules_path is not None:
                # Validate that the path is a string
                if not isinstance(self.xml_rules_path, str):
                    logger.error(f"Invalid xml_rules_path: must be a string or None")
                    return False

        except TypeError as e:
            logger.error(f"Invalid configuration value type: {e}")
            return False

        return True

    def __repr__(self) -> str:
        return f"TypographyXMLAnalyzerConfig({self.to_dict()})"
