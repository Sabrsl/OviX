"""
UI Settings Manager for Wikipedia Maintenance Tool.

Provides persistent storage for user preferences and feature toggles.
Settings are stored in the SQLite database.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class UISettings:
    """User interface settings with persistence."""
    
    # Analyzer toggles
    enabled_analyzers: Dict[str, bool] = field(default_factory=lambda: {
        "DeadLinkAnalyzer": True,
        "HttpLinksAnalyzer": False,  # Controlled by https_verification.enabled in config
        "ReferenceEnricherAnalyzer": False,  # Controlled by reference_enricher_analyzer.enabled in config
    })
    
    # UI preferences
    compact_mode: bool = False
    auto_expand_groups: bool = True
    show_diff_by_default: bool = True
    
    # Analysis preferences
    min_severity_filter: str = "all"  # all, low, medium, high
    
    # Reference processing preferences
    enable_case_normalization: bool = False  # Normalisation des majuscules dans les références
    
    def get_enabled_analyzers(self) -> List[str]:
        """Get list of enabled analyzer names."""
        return [name for name, enabled in self.enabled_analyzers.items() if enabled]
    
    def set_analyzer_enabled(self, analyzer_name: str, enabled: bool) -> None:
        """Enable or disable a specific analyzer."""
        if analyzer_name in self.enabled_analyzers:
            self.enabled_analyzers[analyzer_name] = enabled
        else:
            logger.warning(f"Unknown analyzer: {analyzer_name}")
    
    def is_analyzer_enabled(self, analyzer_name: str) -> bool:
        """Check if a specific analyzer is enabled."""
        return self.enabled_analyzers.get(analyzer_name, False)


class UISettingsManager:
    """Manager for UI settings with database persistence."""
    
    def __init__(self, db_manager=None):
        """
        Initialize the settings manager.
        
        Args:
            db_manager: DatabaseManager instance. If None, creates a new one.
        """
        if db_manager is None:
            from .database import DatabaseManager
            self.db = DatabaseManager()
        else:
            self.db = db_manager
        
        self.settings = self._load_settings()
    
    def _load_settings(self) -> UISettings:
        """Load settings from database or create defaults."""
        try:
            # Dead Linker Project - Force DeadLinkAnalyzer only
            # Ignore any old database settings
            enabled_analyzers = {
                "DeadLinkAnalyzer": True,
            }
            
            # Check if https_verification is enabled for HttpLinksAnalyzer
            try:
                from .config import load_config
                config = load_config()
                if hasattr(config, 'https_verification') and hasattr(config.https_verification, 'enabled'):
                    if config.https_verification.enabled:
                        enabled_analyzers["HttpLinksAnalyzer"] = True
                        logger.info("HttpLinksAnalyzer enabled via https_verification.enabled")
                    else:
                        enabled_analyzers["HttpLinksAnalyzer"] = False
                        logger.info("HttpLinksAnalyzer disabled via https_verification.enabled")
                else:
                    enabled_analyzers["HttpLinksAnalyzer"] = False
                    logger.info("HttpsVerification config not found, HttpLinksAnalyzer disabled")
            except Exception as e:
                logger.warning(f"Failed to load https_verification config: {e}")
                enabled_analyzers["HttpLinksAnalyzer"] = False
            
            # Check if reference_enricher_analyzer is enabled
            try:
                from .config import load_config
                config = load_config()
                if hasattr(config, 'reference_enricher_analyzer') and hasattr(config.reference_enricher_analyzer, 'enabled'):
                    if config.reference_enricher_analyzer.enabled:
                        enabled_analyzers["ReferenceEnricherAnalyzer"] = True
                        logger.info("ReferenceEnricherAnalyzer enabled via reference_enricher_analyzer.enabled")
                    else:
                        enabled_analyzers["ReferenceEnricherAnalyzer"] = False
                        logger.info("ReferenceEnricherAnalyzer disabled via reference_enricher_analyzer.enabled")
                else:
                    enabled_analyzers["ReferenceEnricherAnalyzer"] = False
                    logger.info("ReferenceEnricherAnalyzer config not found, disabled")
            except Exception as e:
                logger.warning(f"Failed to load reference_enricher_analyzer config: {e}")
                enabled_analyzers["ReferenceEnricherAnalyzer"] = False
            
            logger.info(f"Dead Linker mode: enabled analyzers = {list(enabled_analyzers.keys())}")
            self.db.set_setting("enabled_analyzers", json.dumps(enabled_analyzers))
            
            # Load UI preferences
            compact_mode = self.db.get_setting("compact_mode", "false") == "true"
            auto_expand_groups = self.db.get_setting("auto_expand_groups", "true") == "true"
            show_diff_by_default = self.db.get_setting("show_diff_by_default", "true") == "true"
            min_severity_filter = self.db.get_setting("min_severity_filter", "all")
            enable_case_normalization = self.db.get_setting("enable_case_normalization", "false") == "true"
            
            return UISettings(
                enabled_analyzers=enabled_analyzers,
                compact_mode=compact_mode,
                auto_expand_groups=auto_expand_groups,
                show_diff_by_default=show_diff_by_default,
                min_severity_filter=min_severity_filter,
                enable_case_normalization=enable_case_normalization
            )
        except Exception as e:
            logger.warning(f"Failed to load settings from database: {e}")
            logger.info("Creating default settings")
            return UISettings()
    
    def save_settings(self) -> None:
        """Save current settings to database."""
        try:
            # Save enabled_analyzers as JSON
            self.db.set_setting("enabled_analyzers", json.dumps(self.settings.enabled_analyzers))
            
            # Save UI preferences
            self.db.set_setting("compact_mode", str(self.settings.compact_mode).lower())
            self.db.set_setting("auto_expand_groups", str(self.settings.auto_expand_groups).lower())
            self.db.set_setting("show_diff_by_default", str(self.settings.show_diff_by_default).lower())
            self.db.set_setting("min_severity_filter", self.settings.min_severity_filter)
            self.db.set_setting("enable_case_normalization", str(self.settings.enable_case_normalization).lower())
            
            logger.debug("Settings saved to database")
        except Exception as e:
            logger.error(f"Failed to save settings to database: {e}")
    
    def get_settings(self) -> UISettings:
        """Get current settings."""
        return self.settings
    
    def update_settings(self, **kwargs) -> None:
        """
        Update settings with provided keyword arguments.
        
        Args:
            **kwargs: Settings to update (e.g., compact_mode=True)
        """
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
            else:
                logger.warning(f"Unknown setting: {key}")
        self.save_settings()
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to default values."""
        # Clear database setting to force new defaults
        self.db.set_setting("enabled_analyzers", None)
        self.settings = UISettings()
        self.save_settings()
        logger.info("Settings reset to defaults")


# Global instance for use in Streamlit
_global_settings_manager: Optional[UISettingsManager] = None


def get_settings_manager() -> UISettingsManager:
    """Get or create the global settings manager instance."""
    global _global_settings_manager
    if _global_settings_manager is None:
        _global_settings_manager = UISettingsManager()
    return _global_settings_manager
