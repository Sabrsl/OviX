"""
Configuration API endpoints.

Provides REST API endpoints for managing OVIX configuration from the UI.
All configuration changes are persisted to config.yaml.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Configuration"])

# Configuration file path
CONFIG_FILE = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
CONFIG_EXAMPLE = Path(__file__).parent.parent.parent.parent / "config" / "config.example.yaml"


# ----------------------------------------------------------------------
# Request/Response Models
# ----------------------------------------------------------------------


class ConfigUpdateRequest(BaseModel):
    """Request model for configuration updates."""
    section: str  # e.g., "wikipedia", "rate_limiting", "ui"
    key: str  # e.g., "lang", "timeout", "theme"
    value: Any  # The new value


class ConfigSectionUpdateRequest(BaseModel):
    """Request model for updating an entire configuration section."""
    section: str
    data: Dict[str, Any]


class ConfigResponse(BaseModel):
    """Response model for configuration data."""
    success: bool
    config: Dict[str, Any]
    source: str  # "file" or "defaults"


class ConfigValidationResponse(BaseModel):
    """Response model for configuration validation."""
    success: bool
    valid: bool
    errors: list
    warnings: list


# ----------------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------------


def _get_config_path() -> Path:
    """Get the configuration file path, creating from example if needed."""
    if CONFIG_FILE.exists():
        return CONFIG_FILE
    
    # If config.yaml doesn't exist, try to create from example
    if CONFIG_EXAMPLE.exists():
        logger.info(f"Creating config.yaml from example file")
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_EXAMPLE, 'r', encoding='utf-8') as src:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
        return CONFIG_FILE
    
    # If no example exists, create a minimal config
    logger.warning(f"No config.yaml or example found, creating minimal config")
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    minimal_config = {
        "wikipedia": {"lang": "fr", "family": "wikipedia", "timeout": 30.0},
        "rate_limiting": {"min_edit_delay": 1.0, "max_edits_per_minute": 10},
        "ui": {"theme": "dark"},
        "analysis": {"enabled_analyzers": ["DeadLinkAnalyzer"], "min_severity": "all"},
        "database": {"path": "data/wikipedia_maintenance.db"},
        "safety": {"dry_run_default": True, "require_confirmation": True},
        "logging": {"level": "INFO", "console": True}
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(minimal_config, f, default_flow_style=False, allow_unicode=True)
    
    return CONFIG_FILE


def _load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = _get_config_path()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load configuration: {str(e)}")


def _save_config(config: Dict[str, Any]) -> None:
    """Save configuration to YAML file."""
    config_path = _get_config_path()
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info(f"Saved configuration to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")


# ----------------------------------------------------------------------
# API Endpoints
# ----------------------------------------------------------------------


@router.get("/", response_model=ConfigResponse)
async def get_config():
    """
    Get the complete configuration.
    
    Returns all configuration sections with their current values.
    """
    try:
        config = _load_config()
        return ConfigResponse(
            success=True,
            config=config,
            source="file"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting configuration: {str(e)}")


@router.options("/")
async def options_config():
    """Handle OPTIONS request for CORS preflight."""
    return JSONResponse(
        status_code=200,
        content={"message": "OK"}
    )
async def get_config():
    """
    Get the complete configuration.
    
    Returns all configuration sections with their current values.
    """
    try:
        config = _load_config()
        return ConfigResponse(
            success=True,
            config=config,
            source="file"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting configuration: {str(e)}")


@router.get("/{section}", response_model=ConfigResponse)
async def get_config_section(section: str):
    """
    Get a specific configuration section.
    
    Args:
        section: Configuration section name (e.g., "wikipedia", "ui", "rate_limiting")
    """
    try:
        config = _load_config()
        
        if section not in config:
            raise HTTPException(status_code=404, detail=f"Configuration section '{section}' not found")
        
        return ConfigResponse(
            success=True,
            config={section: config[section]},
            source="file"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration section {section}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting configuration section: {str(e)}")


@router.options("/{section}")
async def options_config_section(section: str):
    """Handle OPTIONS request for CORS preflight."""
    return JSONResponse(
        status_code=200,
        content={"message": "OK"}
    )
async def get_config_section(section: str):
    """
    Get a specific configuration section.
    
    Args:
        section: Configuration section name (e.g., "wikipedia", "ui", "rate_limiting")
    """
    try:
        config = _load_config()
        
        if section not in config:
            raise HTTPException(status_code=404, detail=f"Configuration section '{section}' not found")
        
        return ConfigResponse(
            success=True,
            config={section: config[section]},
            source="file"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration section {section}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting configuration section: {str(e)}")


@router.put("/value", response_model=ConfigResponse)
async def update_config_value(request: ConfigUpdateRequest):
    """
    Update a single configuration value.
    
    Args:
        request: ConfigUpdateRequest with section, key, and new value
    """
    try:
        config = _load_config()
        
        # Ensure section exists
        if request.section not in config:
            config[request.section] = {}
        
        # Update the value
        config[request.section][request.key] = request.value
        
        # Save the updated configuration
        _save_config(config)
        
        logger.info(f"Updated config: {request.section}.{request.key} = {request.value}")
        
        return ConfigResponse(
            success=True,
            config={request.section: config[request.section]},
            source="file"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration value: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {str(e)}")


@router.options("/value")
async def options_config_value():
    """Handle OPTIONS request for CORS preflight."""
    return JSONResponse(
        status_code=200,
        content={"message": "OK"}
    )
async def update_config_value(request: ConfigUpdateRequest):
    """
    Update a single configuration value.
    
    Args:
        request: ConfigUpdateRequest with section, key, and new value
    """
    try:
        config = _load_config()
        
        # Ensure section exists
        if request.section not in config:
            config[request.section] = {}
        
        # Update the value
        config[request.section][request.key] = request.value
        
        # Save the updated configuration
        _save_config(config)
        
        logger.info(f"Updated config: {request.section}.{request.key} = {request.value}")
        
        return ConfigResponse(
            success=True,
            config={request.section: config[request.section]},
            source="file"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration value: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {str(e)}")


@router.put("/section", response_model=ConfigResponse)
async def update_config_section(request: ConfigSectionUpdateRequest):
    """
    Update an entire configuration section.
    
    Args:
        request: ConfigSectionUpdateRequest with section name and data
    """
    try:
        config = _load_config()
        
        # Update the entire section
        config[request.section] = request.data
        
        # Save the updated configuration
        _save_config(config)
        
        logger.info(f"Updated config section: {request.section}")
        
        return ConfigResponse(
            success=True,
            config={request.section: config[request.section]},
            source="file"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration section: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating configuration section: {str(e)}")


@router.options("/section")
async def options_config_section_update():
    """Handle OPTIONS request for CORS preflight."""
    return JSONResponse(
        status_code=200,
        content={"message": "OK"}
    )
async def update_config_section(request: ConfigSectionUpdateRequest):
    """
    Update an entire configuration section.
    
    Args:
        request: ConfigSectionUpdateRequest with section name and data
    """
    try:
        config = _load_config()
        
        # Update the entire section
        config[request.section] = request.data
        
        # Save the updated configuration
        _save_config(config)
        
        logger.info(f"Updated config section: {request.section}")
        
        return ConfigResponse(
            success=True,
            config={request.section: config[request.section]},
            source="file"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration section: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating configuration section: {str(e)}")


@router.post("/validate", response_model=ConfigValidationResponse)
async def validate_config(config_data: Optional[Dict[str, Any]] = None):
    """
    Validate configuration data.
    
    If config_data is provided, validates that data.
    Otherwise, validates the current configuration file.
    
    Args:
        config_data: Optional configuration data to validate
    """
    try:
        if config_data is None:
            config_data = _load_config()
        
        errors = []
        warnings = []
        
        # Validate wikipedia section
        if "wikipedia" in config_data:
            wiki = config_data["wikipedia"]
            if "lang" in wiki and not isinstance(wiki["lang"], str):
                errors.append("wikipedia.lang must be a string")
            if "timeout" in wiki and not isinstance(wiki["timeout"], (int, float)):
                errors.append("wikipedia.timeout must be a number")
            if "timeout" in wiki and wiki["timeout"] <= 0:
                errors.append("wikipedia.timeout must be positive")
        
        # Validate rate_limiting section
        if "rate_limiting" in config_data:
            rl = config_data["rate_limiting"]
            if "max_edits_per_minute" in rl and rl["max_edits_per_minute"] < 1:
                errors.append("rate_limiting.max_edits_per_minute must be at least 1")
            if "min_edit_delay" in rl and rl["min_edit_delay"] < 0:
                errors.append("rate_limiting.min_edit_delay must be >= 0")
        
        # Validate UI section
        if "ui" in config_data:
            ui = config_data["ui"]
            if "theme" in ui and ui["theme"] not in ["light", "dark", "auto"]:
                errors.append("ui.theme must be one of: light, dark, auto")
        
        # Validate safety section
        if "safety" in config_data:
            safety = config_data["safety"]
            if "max_article_batch_size" in safety and safety["max_article_batch_size"] < 1:
                errors.append("safety.max_article_batch_size must be at least 1")
            if "dry_run_default" in safety and not isinstance(safety["dry_run_default"], bool):
                errors.append("safety.dry_run_default must be a boolean")
        
        return ConfigValidationResponse(
            success=True,
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    except Exception as e:
        logger.error(f"Error validating configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error validating configuration: {str(e)}")


@router.options("/validate")
async def options_config_validate():
    """Handle OPTIONS request for CORS preflight."""
    return JSONResponse(
        status_code=200,
        content={"message": "OK"}
    )
async def validate_config(config_data: Optional[Dict[str, Any]] = None):
    """
    Validate configuration data.
    
    If config_data is provided, validates that data.
    Otherwise, validates the current configuration file.
    
    Args:
        config_data: Optional configuration data to validate
    """
    try:
        if config_data is None:
            config_data = _load_config()
        
        errors = []
        warnings = []
        
        # Validate wikipedia section
        if "wikipedia" in config_data:
            wiki = config_data["wikipedia"]
            if "lang" in wiki and not isinstance(wiki["lang"], str):
                errors.append("wikipedia.lang must be a string")
            if "timeout" in wiki and not isinstance(wiki["timeout"], (int, float)):
                errors.append("wikipedia.timeout must be a number")
            if "timeout" in wiki and wiki["timeout"] <= 0:
                errors.append("wikipedia.timeout must be positive")
        
        # Validate rate_limiting section
        if "rate_limiting" in config_data:
            rl = config_data["rate_limiting"]
            if "max_edits_per_minute" in rl and rl["max_edits_per_minute"] < 1:
                errors.append("rate_limiting.max_edits_per_minute must be at least 1")
            if "min_edit_delay" in rl and rl["min_edit_delay"] < 0:
                errors.append("rate_limiting.min_edit_delay must be >= 0")
        
        # Validate UI section
        if "ui" in config_data:
            ui = config_data["ui"]
            if "theme" in ui and ui["theme"] not in ["light", "dark", "auto"]:
                errors.append("ui.theme must be one of: light, dark, auto")
        
        # Validate safety section
        if "safety" in config_data:
            safety = config_data["safety"]
            if "max_article_batch_size" in safety and safety["max_article_batch_size"] < 1:
                errors.append("safety.max_article_batch_size must be at least 1")
            if "dry_run_default" in safety and not isinstance(safety["dry_run_default"], bool):
                errors.append("safety.dry_run_default must be a boolean")
        
        return ConfigValidationResponse(
            success=True,
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    except Exception as e:
        logger.error(f"Error validating configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error validating configuration: {str(e)}")


@router.post("/reset")
async def reset_config_to_defaults():
    """
    Reset configuration to default values by recreating from example.
    
    WARNING: This will overwrite all current configuration values.
    """
    try:
        # Remove existing config file
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            logger.info(f"Removed existing config file: {CONFIG_FILE}")
        
        # Force recreation from example
        _get_config_path()
        
        # Return the new default configuration
        config = _load_config()
        
        return ConfigResponse(
            success=True,
            config=config,
            source="file"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error resetting configuration: {str(e)}")


@router.options("/reset")
async def options_config_reset():
    """Handle OPTIONS request for CORS preflight."""
    return JSONResponse(
        status_code=200,
        content={"message": "OK"}
    )
