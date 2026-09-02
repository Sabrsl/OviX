"""
Configuration API endpoints.

Provides REST API endpoints for managing OVIX configuration from the UI.
All configuration changes are persisted to config.yaml.
"""

import os
import shutil
import tempfile
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Configuration"])

# Configuration file path
CONFIG_FILE = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
CONFIG_EXAMPLE = Path(__file__).parent.parent.parent.parent / "config" / "config.example.yaml"
CONFIG_BACKUP_SUFFIX = ".bak"

# Sections/keys allowed for partial updates (defense-in-depth against unexpected keys)
KNOWN_SECTIONS = {
    "wikipedia", "rate_limiting", "ui", "analysis", "database",
    "safety", "logging", "api_throttling", "api_urls",
    "dead_links_analyzer", "other", "publication_delays",
    "scheduler", "timeouts", "ai", "reference_enricher_analyzer",
}


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
        logger.info("Creating config.yaml from example file")
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(CONFIG_EXAMPLE, CONFIG_FILE)
        except OSError as e:
            logger.error(f"Failed to copy example config: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize configuration: {e}")
        return CONFIG_FILE

    # If no example exists, create a minimal config
    logger.warning("No config.yaml or example found, creating minimal config")
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    minimal_config = {
        "wikipedia": {"lang": "fr", "family": "wikipedia", "timeout": 30.0},
        "rate_limiting": {"min_edit_delay": 1.0, "max_edits_per_minute": 10},
        "ui": {"theme": "dark"},
        "analysis": {"enabled_analyzers": ["DeadLinkAnalyzer"], "min_severity": "all"},
        "database": {"path": "data/wikipedia_maintenance.db"},
        "safety": {"dry_run_default": True, "require_confirmation": True},
        "logging": {"level": "INFO", "console": True},
    }
    try:
        _write_yaml_atomic(CONFIG_FILE, minimal_config)
    except OSError as e:
        logger.error(f"Failed to write minimal config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize configuration: {e}")

    return CONFIG_FILE


def _write_yaml_atomic(path: Path, data: Dict[str, Any]) -> None:
    """
    Write YAML data to `path` atomically.

    Writes to a temp file in the same directory first, then renames it into
    place. This avoids leaving a truncated/corrupted config file if the
    process crashes or the disk fills up mid-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic on POSIX and Windows
    except Exception:
        # Clean up the temp file if something went wrong before the rename
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = _get_config_path()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        if not isinstance(config, dict):
            logger.error(f"Config file did not contain a mapping at top level: {config_path}")
            raise HTTPException(
                status_code=500,
                detail="Configuration file is malformed (expected a YAML mapping at the top level)",
            )
        logger.info(f"Loaded configuration from {config_path}")
        return config
    except HTTPException:
        raise
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse configuration YAML: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse configuration: {e}")
    except OSError as e:
        logger.error(f"Failed to read configuration file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load configuration: {e}")


def _save_config(config: Dict[str, Any]) -> None:
    """Save configuration to YAML file atomically."""
    config_path = _get_config_path()

    try:
        _write_yaml_atomic(config_path, config)
        logger.info(f"Saved configuration to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {e}")


def _validate_config_data(config_data: Dict[str, Any]) -> tuple[list, list]:
    """
    Run all configuration validation rules against `config_data`.

    Returns:
        (errors, warnings) lists of human-readable strings.
    """
    errors: list = []
    warnings: list = []

    # Validate wikipedia section
    wiki = config_data.get("wikipedia")
    if isinstance(wiki, dict):
        if "lang" in wiki and not isinstance(wiki["lang"], str):
            errors.append("wikipedia.lang must be a string")
        if "timeout" in wiki:
            if not isinstance(wiki["timeout"], (int, float)) or isinstance(wiki["timeout"], bool):
                errors.append("wikipedia.timeout must be a number")
            elif wiki["timeout"] <= 0:
                errors.append("wikipedia.timeout must be positive")
    elif "wikipedia" in config_data:
        errors.append("wikipedia section must be a mapping")

    # Validate rate_limiting section
    rl = config_data.get("rate_limiting")
    if isinstance(rl, dict):
        if "max_edits_per_minute" in rl and rl["max_edits_per_minute"] < 1:
            errors.append("rate_limiting.max_edits_per_minute must be at least 1")
        if "min_edit_delay" in rl and rl["min_edit_delay"] < 0:
            errors.append("rate_limiting.min_edit_delay must be >= 0")
    elif "rate_limiting" in config_data:
        errors.append("rate_limiting section must be a mapping")

    # Validate UI section
    ui = config_data.get("ui")
    if isinstance(ui, dict):
        if "theme" in ui and ui["theme"] not in ("light", "dark", "auto"):
            errors.append("ui.theme must be one of: light, dark, auto")
    elif "ui" in config_data:
        errors.append("ui section must be a mapping")

    # Validate safety section
    safety = config_data.get("safety")
    if isinstance(safety, dict):
        if "max_article_batch_size" in safety and safety["max_article_batch_size"] < 1:
            errors.append("safety.max_article_batch_size must be at least 1")
        if "dry_run_default" in safety and not isinstance(safety["dry_run_default"], bool):
            errors.append("safety.dry_run_default must be a boolean")
    elif "safety" in config_data:
        errors.append("safety section must be a mapping")

    # Validate ai section
    ai = config_data.get("ai")
    if isinstance(ai, dict):
        gemini = ai.get("gemini")
        if isinstance(gemini, dict):
            if "api_key" in gemini and not isinstance(gemini["api_key"], str):
                errors.append("ai.gemini.api_key must be a string")
            if "project_id" in gemini and not isinstance(gemini["project_id"], str):
                errors.append("ai.gemini.project_id must be a string")
            if "model" in gemini and not isinstance(gemini["model"], str):
                errors.append("ai.gemini.model must be a string")
            if "limit" in gemini:
                if not isinstance(gemini["limit"], (int, float)) or isinstance(gemini["limit"], bool):
                    errors.append("ai.gemini.limit must be a number")
                elif gemini["limit"] <= 0:
                    errors.append("ai.gemini.limit must be positive")
        elif "gemini" in ai:
            errors.append("ai.gemini section must be a mapping")
    elif "ai" in config_data:
        errors.append("ai section must be a mapping")

    # Validate analysis section
    analysis = config_data.get("analysis")
    if isinstance(analysis, dict):
        if "enable_dead_link_analyzer" in analysis and not isinstance(
            analysis["enable_dead_link_analyzer"], bool
        ):
            errors.append("analysis.enable_dead_link_analyzer must be a boolean")
        if "enable_case_normalization" in analysis and not isinstance(
            analysis["enable_case_normalization"], bool
        ):
            errors.append("analysis.enable_case_normalization must be a boolean")
        if "normalize_with_ai" in analysis and not isinstance(
            analysis["normalize_with_ai"], bool
        ):
            errors.append("analysis.normalize_with_ai must be a boolean")
        if "parallel" in analysis and not isinstance(analysis["parallel"], bool):
            errors.append("analysis.parallel must be a boolean")
        if "analyzer_timeout" in analysis:
            if not isinstance(analysis["analyzer_timeout"], (int, float)) or isinstance(
                analysis["analyzer_timeout"], bool
            ):
                errors.append("analysis.analyzer_timeout must be a number")
            elif analysis["analyzer_timeout"] <= 0:
                errors.append("analysis.analyzer_timeout must be positive")
    elif "analysis" in config_data:
        errors.append("analysis section must be a mapping")

    # Validate reference_enricher_analyzer section
    ref_enricher = config_data.get("reference_enricher_analyzer")
    if isinstance(ref_enricher, dict):
        if "enabled" in ref_enricher and not isinstance(ref_enricher["enabled"], bool):
            errors.append("reference_enricher_analyzer.enabled must be a boolean")
        if "timeout" in ref_enricher:
            if not isinstance(ref_enricher["timeout"], (int, float)) or isinstance(
                ref_enricher["timeout"], bool
            ):
                errors.append("reference_enricher_analyzer.timeout must be a number")
            elif ref_enricher["timeout"] <= 0:
                errors.append("reference_enricher_analyzer.timeout must be positive")
        if "max_retries" in ref_enricher:
            if not isinstance(ref_enricher["max_retries"], int) or isinstance(
                ref_enricher["max_retries"], bool
            ):
                errors.append("reference_enricher_analyzer.max_retries must be an integer")
            elif ref_enricher["max_retries"] < 0:
                errors.append("reference_enricher_analyzer.max_retries must be >= 0")
        if "max_checks_per_article" in ref_enricher:
            if not isinstance(ref_enricher["max_checks_per_article"], int) or isinstance(
                ref_enricher["max_checks_per_article"], bool
            ):
                errors.append("reference_enricher_analyzer.max_checks_per_article must be an integer")
            elif ref_enricher["max_checks_per_article"] < 1:
                errors.append("reference_enricher_analyzer.max_checks_per_article must be at least 1")
        if "enable_site_fill" in ref_enricher and not isinstance(ref_enricher["enable_site_fill"], bool):
            errors.append("reference_enricher_analyzer.enable_site_fill must be a boolean")
        if "enable_consulte_le_fill" in ref_enricher and not isinstance(ref_enricher["enable_consulte_le_fill"], bool):
            errors.append("reference_enricher_analyzer.enable_consulte_le_fill must be a boolean")
    elif "reference_enricher_analyzer" in config_data:
        errors.append("reference_enricher_analyzer section must be a mapping")

    # Non-blocking heads-up for unknown top-level sections (helps catch typos in the UI)
    unknown_sections = set(config_data.keys()) - KNOWN_SECTIONS
    for section in sorted(unknown_sections):
        warnings.append(f"Unrecognized configuration section: '{section}'")

    return errors, warnings


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
        return ConfigResponse(success=True, config=config, source="file")
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

        return ConfigResponse(success=True, config={section: config[section]}, source="file")
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
    if not request.section.strip():
        raise HTTPException(status_code=400, detail="section must not be empty")
    if not request.key.strip():
        raise HTTPException(status_code=400, detail="key must not be empty")

    try:
        config = _load_config()

        # Ensure section exists and is a mapping (don't silently clobber a non-dict section)
        existing_section = config.get(request.section)
        if existing_section is None:
            config[request.section] = {}
        elif not isinstance(existing_section, dict):
            raise HTTPException(
                status_code=409,
                detail=f"Configuration section '{request.section}' is not a mapping; cannot set a key on it",
            )

        # Update the value
        config[request.section][request.key] = request.value

        # Validate before persisting so a bad value can't be written to disk
        errors, _warnings = _validate_config_data(config)
        if errors:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid configuration after update: {'; '.join(errors)}",
            )

        # Save the updated configuration
        _save_config(config)

        logger.info(f"Updated config: {request.section}.{request.key} = {request.value}")

        return ConfigResponse(success=True, config={request.section: config[request.section]}, source="file")
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
    if not request.section.strip():
        raise HTTPException(status_code=400, detail="section must not be empty")

    try:
        config = _load_config()

        # Apply the change to a copy first so validation failures never touch the loaded config
        candidate = dict(config)
        candidate[request.section] = request.data

        errors, _warnings = _validate_config_data(candidate)
        if errors:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid configuration for section '{request.section}': {'; '.join(errors)}",
            )

        # Save the updated configuration
        _save_config(candidate)

        logger.info(f"Updated config section: {request.section}")

        return ConfigResponse(success=True, config={request.section: candidate[request.section]}, source="file")
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

        errors, warnings = _validate_config_data(config_data)

        return ConfigValidationResponse(success=True, valid=len(errors) == 0, errors=errors, warnings=warnings)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error validating configuration: {str(e)}")


@router.post("/reset")
async def reset_config_to_defaults():
    """
    Reset configuration to default values by recreating from example.

    WARNING: This will overwrite all current configuration values.
    A timestamped backup of the previous config is kept alongside it
    (config.yaml.bak) so the last configuration is not silently lost.
    """
    try:
        if CONFIG_FILE.exists():
            backup_path = CONFIG_FILE.with_suffix(CONFIG_FILE.suffix + CONFIG_BACKUP_SUFFIX)
            try:
                shutil.copyfile(CONFIG_FILE, backup_path)
                logger.info(f"Backed up existing config to {backup_path}")
            except OSError as e:
                # Don't proceed with a destructive reset if we couldn't back it up
                logger.error(f"Failed to back up existing config before reset: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Reset aborted: could not back up existing configuration: {e}",
                )

            CONFIG_FILE.unlink()
            logger.info(f"Removed existing config file: {CONFIG_FILE}")

        # Force recreation from example
        _get_config_path()

        # Return the new default configuration
        config = _load_config()

        return ConfigResponse(success=True, config=config, source="file")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error resetting configuration: {str(e)}")