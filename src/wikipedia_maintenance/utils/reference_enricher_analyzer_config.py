"""
ReferenceEnricherAnalyzer Configuration Loader.

This module handles loading configuration for the ReferenceEnricherAnalyzer from YAML files.
It follows the same pattern as DeadLinkAnalyzerConfig to maintain consistency.

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

_CONFIG_SECTION_KEY: Final[str] = 'reference_enricher_analyzer'


class ReferenceEnricherConfig:
    """
    Configuration loader for ReferenceEnricherAnalyzer.

    Provides methods to load configuration from YAML files with sensible defaults
    and validation. Supports dependency injection of config path for testing.
    """

    # Default configuration values
    DEFAULT_TIMEOUT: Final[int] = 10
    DEFAULT_MAX_RETRIES: Final[int] = 3
    DEFAULT_MAX_CHECKS_PER_ARTICLE: Final[int] = 50
    DEFAULT_ENABLE_SITE_FILL: Final[bool] = True
    DEFAULT_ENABLE_CONSULTE_LE_FILL: Final[bool] = True

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "ReferenceEnricherConfig":
        """
        Load configuration from YAML file with fallback to defaults.

        Any error while locating, reading, parsing, or applying the config
        file (missing file, malformed YAML, wrong types, permission errors,
        etc.) results in falling back to defaults rather than raising -
        configuration loading must never crash analysis startup.

        Args:
            config_path: Path to config file. If None, uses default path.

        Returns:
            ReferenceEnricherConfig instance with loaded configuration
            (falls back to an all-defaults instance on any error).
        """
        if config_path is None:
            # Default path relative to this file
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"

        config_data: Dict[str, Any] = {
            'timeout': cls.DEFAULT_TIMEOUT,
            'max_retries': cls.DEFAULT_MAX_RETRIES,
            'max_checks_per_article': cls.DEFAULT_MAX_CHECKS_PER_ARTICLE,
            'enable_site_fill': cls.DEFAULT_ENABLE_SITE_FILL,
            'enable_consulte_le_fill': cls.DEFAULT_ENABLE_CONSULTE_LE_FILL,
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
                            f"Loaded ReferenceEnricherAnalyzer config: timeout={config_data['timeout']}s, "
                            f"max_retries={config_data['max_retries']}, "
                            f"max_checks={config_data['max_checks_per_article']}, "
                            f"enable_site_fill={config_data['enable_site_fill']}, "
                            f"enable_consulte_le_fill={config_data['enable_consulte_le_fill']}"
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

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_retries: int = DEFAULT_MAX_RETRIES,
                 max_checks_per_article: int = DEFAULT_MAX_CHECKS_PER_ARTICLE,
                 enable_site_fill: bool = DEFAULT_ENABLE_SITE_FILL,
                 enable_consulte_le_fill: bool = DEFAULT_ENABLE_CONSULTE_LE_FILL):
        """
        Initialize configuration with specific values.

        Args:
            timeout: Link check timeout in seconds
            max_retries: Maximum retry attempts for failed checks
            max_checks_per_article: Maximum URLs to check per article
            enable_site_fill: Whether to auto-fill |site= parameter
            enable_consulte_le_fill: Whether to auto-fill |consulté le= parameter
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_checks_per_article = max_checks_per_article
        self.enable_site_fill = enable_site_fill
        self.enable_consulte_le_fill = enable_consulte_le_fill

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'max_checks_per_article': self.max_checks_per_article,
            'enable_site_fill': self.enable_site_fill,
            'enable_consulte_le_fill': self.enable_consulte_le_fill,
        }

    def validate(self) -> bool:
        """
        Validate configuration values.

        Returns:
            True if configuration is valid, False otherwise.
        """
        try:
            if self.timeout <= 0:
                logger.error(f"Invalid timeout: {self.timeout} must be positive")
                return False

            if self.max_retries < 0:
                logger.error(f"Invalid max_retries: {self.max_retries} must be non-negative")
                return False

            if self.max_checks_per_article <= 0:
                logger.error(
                    f"Invalid max_checks_per_article: {self.max_checks_per_article} must be positive"
                )
                return False
        except TypeError as e:
            logger.error(f"Invalid configuration value type: {e}")
            return False

        return True

    def __repr__(self) -> str:
        return f"ReferenceEnricherConfig({self.to_dict()})"
