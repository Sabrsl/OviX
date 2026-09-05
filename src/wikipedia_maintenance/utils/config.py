"""
Configuration management for Wikipedia Maintenance Tool.

Provides a hierarchical configuration system with support for:
    - YAML configuration files
    - Environment variable overrides (using WMT_ prefix)
    - Default values
    - Configuration validation
    - Multiple profiles (development, production)

All existing dataclasses and methods are preserved; new fields and methods
are added without breaking backward compatibility.
"""

import os
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Set
from dataclasses import dataclass, field, fields, asdict
from copy import deepcopy
from .typography_xml_analyzer_config import TypographyXMLAnalyzerConfig

logger = logging.getLogger(__name__)


def _load_timeout_from_config(key: str, default: float) -> float:
    """Load timeout value from config.yaml."""
    try:
        config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config and 'timeouts' in config and key in config['timeouts']:
                    return config['timeouts'][key]
    except Exception:
        pass
    return default


def _load_wikipedia_config_value(key: str, default: str) -> str:
    """Load Wikipedia configuration value from config.yaml."""
    try:
        config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config and 'wikipedia' in config and key in config['wikipedia']:
                    return config['wikipedia'][key]
    except Exception:
        pass
    return default


# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------

class ConfigError(Exception):
    """Raised for configuration errors."""
    pass


# ----------------------------------------------------------------------
# Configuration dataclasses (extended)
# ----------------------------------------------------------------------

@dataclass
class WikipediaConfig:
    """Wikipedia connection configuration."""
    lang: str = field(default_factory=lambda: _load_wikipedia_config_value('lang', 'fr'))
    family: str = field(default_factory=lambda: _load_wikipedia_config_value('family', 'wikipedia'))
    api_url: Optional[str] = None          # override base API URL if needed
    user_agent: Optional[str] = None       # custom user agent
    timeout: float = field(default_factory=lambda: _load_timeout_from_config('wikipedia_api', 30.0))

    def __post_init__(self):
        """Validate values."""
        if not self.lang or not self.lang.isalpha():
            raise ValueError(f"Invalid language code: {self.lang}")
        if not self.family or not self.family.isalpha():
            raise ValueError(f"Invalid family: {self.family}")
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    min_edit_delay: float = 1.0
    max_edits_per_minute: int = 10
    max_requests_per_second: float = 2.0
    burst: int = 5

    def __post_init__(self):
        if self.min_edit_delay < 0:
            raise ValueError("min_edit_delay must be >= 0")
        if self.max_edits_per_minute < 1:
            raise ValueError("max_edits_per_minute must be at least 1")
        if self.max_requests_per_second <= 0:
            raise ValueError("max_requests_per_second must be > 0")
        if self.burst < 1:
            raise ValueError("burst must be at least 1")


@dataclass
class AnalysisConfig:
    """Analysis configuration."""
    # List of enabled analyzers (by class name)
    enabled_analyzers: List[str] = field(default_factory=lambda: [
        "DeadLinkAnalyzer"
    ])
    # Enable/disable specific analyzers (for UI convenience)
    enable_dead_link_analyzer: bool = True
    enable_http_links_analyzer: bool = False  # HttpLinksAnalyzer controlled by https_verification.enabled
    # Minimum severity to report (or 'all')
    min_severity: str = "all"  # Changed to "all" to show all corrections including minor ones
    # Disable specific issue types (globally)
    disabled_issue_types: List[str] = field(default_factory=list)
    # Issue-specific overrides (e.g., {'duplicate_link': {'severity': 'high'}})
    issue_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Whether to run analyzers in parallel (if supported)
    parallel: bool = False
    # Timeout per analyzer in seconds
    analyzer_timeout: float = field(default_factory=lambda: _load_timeout_from_config('analyzer', 60.0))
    # Enable case normalization for reference templates
    enable_case_normalization: bool = False
    # Enable NER-based title normalization (requires spaCy + fr_core_news_sm model)
    enable_ner_title_normalization: bool = False
    # Enable AI-assisted normalization using Gemini (only if enable_case_normalization is true)
    normalize_with_ai: bool = False

    _VALID_SEVERITIES = {"low", "medium", "high", "critical", "all"}

    def __post_init__(self):
        if self.min_severity.lower() not in self._VALID_SEVERITIES:
            raise ValueError(f"Invalid min_severity: {self.min_severity}")


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: str = "data/wikipedia_maintenance.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    max_backups: int = 7
    # SQLite pragmas
    pragmas: Dict[str, Any] = field(default_factory=lambda: {
        "journal_mode": "WAL",
        "synchronous": "NORMAL",
        "cache_size": -64000,  # 64MB
    })

    def __post_init__(self):
        # Convert relative path to absolute path
        if not Path(self.path).is_absolute():
            import os
            project_root = os.environ.get('PROJECT_ROOT')
            if project_root:
                self.path = str(Path(project_root) / self.path)
            else:
                self.path = str(Path.cwd() / self.path)
                
        if self.backup_interval_hours <= 0:
            raise ValueError("backup_interval_hours must be > 0")
        if self.max_backups < 1:
            raise ValueError("max_backups must be at least 1")


@dataclass
class UIConfig:
    """UI configuration."""
    theme: str = "light"
    max_issues_display: int = 100
    auto_expand_high_severity: bool = True
    show_diff_by_default: bool = True
    compact_view: bool = False
    # Available themes: light, dark, auto
    _VALID_THEMES = {"light", "dark", "auto"}

    def __post_init__(self):
        if self.theme.lower() not in self._VALID_THEMES:
            raise ValueError(f"Invalid theme: {self.theme}; must be one of {self._VALID_THEMES}")
        if self.max_issues_display < 1:
            raise ValueError("max_issues_display must be >= 1")


@dataclass
class SafetyConfig:
    """Safety configuration."""
    dry_run_default: bool = True
    require_confirmation: bool = True
    max_article_batch_size: int = 50
    max_edits_per_session: int = 100
    # Automatically skip edits that would affect more than N bytes
    max_change_bytes: int = 50000
    # Exclude certain namespaces from editing
    excluded_namespaces: List[int] = field(default_factory=lambda: [0, 4, 10])
    # Require edit summaries
    enforce_edit_summary: bool = True
    default_edit_summary: str = "Corrections automatiques ([[Projet:Maintenance]])"

    def __post_init__(self):
        if self.max_article_batch_size < 1:
            raise ValueError("max_article_batch_size must be >= 1")
        if self.max_edits_per_session < 1:
            raise ValueError("max_edits_per_session must be >= 1")
        if self.max_change_bytes < 0:
            raise ValueError("max_change_bytes must be >= 0")


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: str = "logs/wikipedia_maintenance.log"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    datefmt: str = "%Y-%m-%d %H:%M:%S"
    # Also log to console
    console: bool = True

    _VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    def __post_init__(self):
        if self.level.upper() not in self._VALID_LEVELS:
            raise ValueError(f"Invalid logging level: {self.level}")
        if self.max_size_mb < 1:
            raise ValueError("max_size_mb must be >= 1")
        if self.backup_count < 0:
            raise ValueError("backup_count must be >= 0")


# ----------------------------------------------------------------------
# New wikification-specific configuration dataclasses
# ----------------------------------------------------------------------


@dataclass
class TypographyConfig:
    """Typography analyzer configuration."""
    check_nbsp: bool = True
    max_issues: Optional[int] = None
    check_ordinal_abbreviations: bool = True
    check_percent_nbsp: bool = False
    check_double_spaces: bool = True
    check_simple_punctuation_spacing: bool = True
    check_abusive_formatting: bool = True
    check_all_caps: bool = True
    check_abbreviations: bool = True
    check_dates: bool = True
    check_centuries: bool = True
    check_units: bool = True
    check_section_titles: bool = True
    # XML-based analyzer configuration
    use_xml_rules: bool = False
    xml_rules_path: Optional[str] = None


@dataclass
class ReferencesConfig:
    """Reference analyzer configuration."""
    check_bare_refs: bool = True
    check_duplicate_refs: bool = True
    check_uppercase_refs: bool = True
    check_isbn_format: bool = True
    check_template_type: bool = True
    check_broken_links: bool = False
    use_wayback_api: bool = False
    link_check_timeout: float = field(default_factory=lambda: _load_timeout_from_config('link_check', 5.0))


@dataclass
class HttpsVerificationConfig:
    """HTTPS verification configuration for HTTP links analyzer."""
    enabled: bool = False  # Whether to verify HTTPS availability before suggesting conversion
    timeout: float = field(default_factory=lambda: _load_timeout_from_config('https_verification', 10.0))
    ttl_available: int = 30  # TTL for HTTPS_AVAILABLE status (days)
    ttl_unavailable: int = 7  # TTL for HTTPS_UNAVAILABLE status (days)
    ttl_failed: int = 1  # TTL for CHECK_FAILED status (days)
    
    def __post_init__(self):
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.ttl_available < 1:
            raise ValueError("ttl_available must be at least 1 day")
        if self.ttl_unavailable < 1:
            raise ValueError("ttl_unavailable must be at least 1 day")
        if self.ttl_failed < 1:
            raise ValueError("ttl_failed must be at least 1 day")


@dataclass
class ReferenceEnricherAnalyzerConfig:
    """Reference enricher analyzer configuration."""
    enabled: bool = False  # Whether to enable the reference enricher analyzer
    timeout: float = 10.0  # Link check timeout in seconds
    max_retries: int = 3  # Maximum retry attempts
    max_checks_per_article: int = 50  # Maximum URLs to check per article
    enable_site_fill: bool = True  # Whether to auto-fill |site= parameter
    enable_consulte_le_fill: bool = True  # Whether to auto-fill |consulté le= parameter
    
    def __post_init__(self):
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.max_checks_per_article < 1:
            raise ValueError("max_checks_per_article must be at least 1")


@dataclass
class WorksListConfig:
    """Works list analyzer configuration."""
    filmography_threshold: int = 3
    discography_threshold: int = 3
    check_awards: bool = True
    check_italics: bool = True
    check_lang_template: bool = True
    check_sort_order: bool = True


@dataclass
class StructureConfig:
    """Structure analyzer configuration."""
    check_heading_levels: bool = True
    check_duplicate_sections: bool = True
    check_voir_aussi_algorithm: bool = True
    check_portal_placement: bool = True
    check_section_order: bool = True
    check_empty_sections: bool = True


# ----------------------------------------------------------------------
# Main configuration container
# ----------------------------------------------------------------------

@dataclass
class Config:
    """Main configuration class."""
    wikipedia: WikipediaConfig = field(default_factory=WikipediaConfig)
    rate_limiting: RateLimitConfig = field(default_factory=RateLimitConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    # Wikification-specific configurations
    typography: TypographyConfig = field(default_factory=TypographyConfig)
    references: ReferencesConfig = field(default_factory=ReferencesConfig)
    https_verification: HttpsVerificationConfig = field(default_factory=HttpsVerificationConfig)
    reference_enricher_analyzer: ReferenceEnricherAnalyzerConfig = field(default_factory=ReferenceEnricherAnalyzerConfig)
    typography_xml_analyzer: 'TypographyXMLAnalyzerConfig' = field(default_factory=lambda: TypographyXMLAnalyzerConfig())
    works_list: WorksListConfig = field(default_factory=WorksListConfig)
    structure: StructureConfig = field(default_factory=StructureConfig)
    # Profile name (optional)
    profile: str = "default"

    # ------------------------------------------------------------------
    # YAML serialization (preserved and enhanced)
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, config_path: str) -> "Config":
        """Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Config object

        Raises:
            FileNotFoundError: if file does not exist
            ConfigError: if YAML is malformed or invalid
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {config_path}: {e}")

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Build Config from a dictionary, validating sub‑configs."""
        # Get profile if present
        profile = data.get("profile", "default")

        # Build sub‑configs using their own dataclass constructors
        # We use the dataclass field names; unknown keys are ignored.
        kwargs = {}
        for subfield in fields(cls):
            if subfield.name == "profile":
                continue
            sub_data = data.get(subfield.name, {})
            try:
                sub_class = subfield.type
                # If the field type is a dataclass, instantiate it
                if hasattr(sub_class, "__dataclass_fields__"):
                    kwargs[subfield.name] = sub_class(**sub_data)
                else:
                    # fallback (should not happen)
                    kwargs[subfield.name] = sub_data
            except Exception as e:
                raise ConfigError(f"Error building {subfield.name}: {e}")

        return cls(profile=profile, **kwargs)

    def to_yaml(self, config_path: str) -> None:
        """Save configuration to YAML file.

        Args:
            config_path: Path to save YAML configuration file
        """
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = asdict(self)
        # Ensure all values are serializable
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # ------------------------------------------------------------------
    # Environment variable loading
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls, prefix: str = "WMT_") -> "Config":
        """
        Load configuration from environment variables with the given prefix.

        Variables are expected in the form:
            WMT_WIKIPEDIA_LANG=fr
            WMT_RATE_LIMITING_MIN_EDIT_DELAY=0.5
            WMT_ANALYSIS_ENABLED_ANALYZERS='["DeadLinkAnalyzer"]'   # JSON array
            WMT_UI_THEME=dark

        Nested structures are supported using double underscore (not used here,
        but we can support: WMT_WIKIPEDIA__LANG=fr). We'll use simple dot notation
        as per the prefix and field names.

        For lists and dicts, we expect JSON‑encoded strings.
        """
        # Build a nested dict from environment variables
        data = {}
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            # Remove prefix and split by underscore
            rest = key[len(prefix):]
            parts = rest.lower().split("_")
            if len(parts) < 2:
                continue  # at least section and field

            section = parts[0]
            field_name = "_".join(parts[1:])
            # Try to parse via YAML to handle booleans, numbers, lists, dicts
            try:
                parsed = yaml.safe_load(value)
                # Use parsed value if it's not a string (handles bool, int, float, list, dict)
                if not isinstance(parsed, str):
                    value = parsed
            except Exception:
                pass  # keep as string

            # Store in nested dict
            data.setdefault(section, {})[field_name] = value

        # If no environment variables found, return None to avoid overriding file config with defaults
        if not data:
            return None
        
        # Merge with defaults (from_env takes precedence over defaults, but not over file)
        # We'll create a base config from defaults and update with env values
        base = cls()
        # Update recursively
        for section, fields_dict in data.items():
            if hasattr(base, section):
                sub = getattr(base, section)
                if isinstance(sub, object) and hasattr(sub, "__dataclass_fields__"):
                    for fname, fvalue in fields_dict.items():
                        if hasattr(sub, fname):
                            setattr(sub, fname, fvalue)
        return base

    # ------------------------------------------------------------------
    # Merging
    # ------------------------------------------------------------------

    def merge(self, other: "Config", override: bool = True) -> "Config":
        """
        Merge another configuration into this one.

        Args:
            other: Config to merge.
            override: If True, values from other override existing ones;
                      if False, only missing fields are filled.

        Returns:
            A new Config object (shallow copy of values, but deep for subconfigs).
        """
        # Deep copy self
        merged = deepcopy(self)

        for subfield in fields(merged):
            subname = subfield.name
            other_sub = getattr(other, subname, None)
            if other_sub is None:
                continue
            current_sub = getattr(merged, subname)
            # If both are dataclasses, merge recursively
            if hasattr(current_sub, "__dataclass_fields__") and hasattr(other_sub, "__dataclass_fields__"):
                # Merge by updating current with other
                for f in fields(current_sub):
                    fname = f.name
                    other_val = getattr(other_sub, fname)
                    current_val = getattr(current_sub, fname)
                    # Override if explicitly requested, or if current value is None/empty
                    # For booleans, we need explicit override since False is a valid value
                    should_override = override or current_val is None or (isinstance(current_val, (list, dict)) and not current_val)
                    if should_override:
                        setattr(current_sub, fname, other_val)
            else:
                # Simple assignment if override or current is None/empty
                if override or current_sub is None:
                    setattr(merged, subname, other_sub)

        return merged

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """
        Perform comprehensive validation of all configuration values.

        Raises:
            ConfigError: if any validation fails.
        """
        # Each subconfig already validates in __post_init__.
        # Additional cross‑section validation can be added here.
        # For example: ensure analysis.min_severity is a valid severity.
        pass

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def get_issue_severity(self, issue_type: str) -> str:
        """
        Get the effective severity for a given issue type, considering overrides.

        Returns:
            The severity string ('low', 'medium', 'high', 'critical')
            or 'all' if not overridden.
        """
        override = self.analysis.issue_overrides.get(issue_type, {})
        return override.get("severity", self.analysis.min_severity)

    def is_issue_enabled(self, issue_type: str) -> bool:
        """Check if a given issue type is enabled (not disabled globally)."""
        return issue_type not in self.analysis.disabled_issue_types

    def is_analyzer_enabled(self, analyzer_name: str) -> bool:
        """Check if a given analyzer is enabled."""
        return analyzer_name in self.analysis.enabled_analyzers


# ----------------------------------------------------------------------
# Public loader functions (preserved and enhanced)
# ----------------------------------------------------------------------

def load_config(
    config_path: Optional[str] = None,
    profile: Optional[str] = None,
    use_env: bool = True,
) -> Config:
    """
    Load configuration from file, environment, and defaults.

    Priority (highest to lowest):
        1. Environment variables (if use_env=True)
        2. YAML file (if config_path provided or default locations)
        3. Default values

    Args:
        config_path: Path to configuration file (optional). If not provided,
                     looks for config.yaml in standard locations.
        profile: Profile name (e.g., 'production'). Currently not used but reserved.
        use_env: Whether to apply environment variable overrides.

    Returns:
        Config object.
    """
    # Start with defaults
    config = Config()

    # Try to load from file FIRST (file has highest priority)
    if config_path is None:
        # Try default locations
        default_paths = [
            "config/config.yaml",
            "../config/config.yaml",
            "../../config/config.yaml",
            "./wikipedia_maintenance.yaml",
        ]
        for path in default_paths:
            if Path(path).exists():
                config_path = path
                break

    if config_path:
        try:
            file_config = Config.from_yaml(config_path)
            config = config.merge(file_config, override=True)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")

    # Apply environment overrides SECOND (only if variables are actually defined)
    # Environment variables override file config
    if use_env:
        env_config = Config.from_env()
        if env_config is not None:
            config = config.merge(env_config, override=True)

    # If profile is specified, we might load profile-specific config here
    # For now, just set the profile attribute
    if profile:
        config.profile = profile

    # Validate final config
    try:
        config.validate()
    except ConfigError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise

    return config


# ----------------------------------------------------------------------
# Convenience function to get a specific config value
# ----------------------------------------------------------------------

def get_config_value(config: Config, path: str, default: Any = None) -> Any:
    """
    Get a nested configuration value using dot notation.

    Example: get_config_value(config, "wikipedia.lang") -> "fr"

    Args:
        config: Config object.
        path: Dot‑separated path (e.g., "wikipedia.lang").
        default: Value to return if path does not exist.

    Returns:
        The configuration value, or default.
    """
    parts = path.split(".")
    current = config
    for part in parts:
        if hasattr(current, part):
            current = getattr(current, part)
        else:
            return default
    return current