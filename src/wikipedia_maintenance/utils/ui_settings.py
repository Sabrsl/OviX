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
    })
    
    # UI preferences
    compact_mode: bool = False
    auto_expand_groups: bool = True
    show_diff_by_default: bool = True
    
    # Analysis preferences
    min_severity_filter: str = "all"  # all, low, medium, high
    
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
            logger.info("Dead Linker mode: only DeadLinkAnalyzer enabled")
            self.db.set_setting("enabled_analyzers", json.dumps(enabled_analyzers))
            
            # Load UI preferences
            compact_mode = self.db.get_setting("compact_mode", "false") == "true"
            auto_expand_groups = self.db.get_setting("auto_expand_groups", "true") == "true"
            show_diff_by_default = self.db.get_setting("show_diff_by_default", "true") == "true"
            min_severity_filter = self.db.get_setting("min_severity_filter", "all")
            
            return UISettings(
                enabled_analyzers=enabled_analyzers,
                compact_mode=compact_mode,
                auto_expand_groups=auto_expand_groups,
                show_diff_by_default=show_diff_by_default,
                min_severity_filter=min_severity_filter
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
