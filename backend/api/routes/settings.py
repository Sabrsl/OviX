"""
OVIX Backend API - Settings Routes

Handles configuration settings.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Models
# ============================================================================

class ThrottlingSettings(BaseModel):
    """Throttling settings."""
    max_requests_per_minute: float
    max_requests_per_minute_min: float
    max_requests_per_minute_max: float
    min_delay: float
    min_delay_min: float
    min_delay_max: float
    random_delay: bool


class AnalysisSettings(BaseModel):
    """Analysis settings."""
    enabled_analyzers: list
    min_severity: str
    timeout: float


class PublicationSettings(BaseModel):
    """Publication settings."""
    max_delay_minutes: float
    min_delay_minutes: float
    dry_run_default: bool


class SchedulerSettings(BaseModel):
    """Scheduler settings."""
    daily_limit: int
    working_hours_start: int
    working_hours_end: int


class AllSettings(BaseModel):
    """All settings."""
    throttling: ThrottlingSettings
    analysis: AnalysisSettings
    publication: PublicationSettings
    scheduler: SchedulerSettings


class SettingsResponse(BaseModel):
    """Settings response."""
    success: bool
    settings: AllSettings


# ============================================================================
# Dependencies
# ============================================================================

def get_config():
    """Get configuration."""
    from backend.api.main import get_config
    return get_config()


# ============================================================================
# Routes
# ============================================================================

@router.get("/", response_model=SettingsResponse)
async def get_settings(config = Depends(get_config)):
    """
    Get current settings.
    
    Returns the current configuration settings from config.yaml.
    """
    try:
        config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
        
        if not config_file.exists():
            raise HTTPException(status_code=404, detail="Config file not found")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # Extract relevant settings
        settings = AllSettings(
            throttling=ThrottlingSettings(
                max_requests_per_minute=config_data.get("api_throttling", {}).get("max_requests_per_minute", 10.0),
                max_requests_per_minute_min=config_data.get("api_throttling", {}).get("max_requests_per_minute_min", 10.0),
                max_requests_per_minute_max=config_data.get("api_throttling", {}).get("max_requests_per_minute_max", 15.0),
                min_delay=config_data.get("api_throttling", {}).get("min_delay", 11.0),
                min_delay_min=config_data.get("api_throttling", {}).get("min_delay_min", 8.0),
                min_delay_max=config_data.get("api_throttling", {}).get("min_delay_max", 15.0),
                random_delay=config_data.get("api_throttling", {}).get("random_delay", True)
            ),
            analysis=AnalysisSettings(
                enabled_analyzers=config_data.get("analysis", {}).get("enabled_analyzers", ["DeadLinkAnalyzer"]),
                min_severity=config_data.get("analysis", {}).get("min_severity", "all"),
                timeout=config_data.get("timeouts", {}).get("analyzer", 60.0)
            ),
            publication=PublicationSettings(
                max_delay_minutes=config_data.get("publication_delays", {}).get("max_delay_minutes", 7.0),
                min_delay_minutes=config_data.get("publication_delays", {}).get("min_delay_minutes", 4.0),
                dry_run_default=config_data.get("safety", {}).get("dry_run_default", True)
            ),
            scheduler=SchedulerSettings(
                daily_limit=config_data.get("scheduler", {}).get("daily_limit", 30),
                working_hours_start=config_data.get("scheduler", {}).get("working_hours_start", 0),
                working_hours_end=config_data.get("scheduler", {}).get("working_hours_end", 23)
            )
        )
        
        return SettingsResponse(
            success=True,
            settings=settings
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.put("/")
async def update_settings(
    settings: AllSettings,
    config = Depends(get_config)
):
    """
    Update settings.
    
    Updates the configuration settings in config.yaml.
    Note: This is a simplified implementation that updates the file directly.
    """
    try:
        config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
        
        if not config_file.exists():
            raise HTTPException(status_code=404, detail="Config file not found")
        
        # Read existing config
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # Update throttling settings
        if "api_throttling" not in config_data:
            config_data["api_throttling"] = {}
        config_data["api_throttling"].update({
            "max_requests_per_minute": settings.throttling.max_requests_per_minute,
            "max_requests_per_minute_min": settings.throttling.max_requests_per_minute_min,
            "max_requests_per_minute_max": settings.throttling.max_requests_per_minute_max,
            "min_delay": settings.throttling.min_delay,
            "min_delay_min": settings.throttling.min_delay_min,
            "min_delay_max": settings.throttling.min_delay_max,
            "random_delay": settings.throttling.random_delay
        })
        
        # Update analysis settings
        if "analysis" not in config_data:
            config_data["analysis"] = {}
        config_data["analysis"].update({
            "enabled_analyzers": settings.analysis.enabled_analyzers,
            "min_severity": settings.analysis.min_severity
        })
        
        # Update publication settings
        if "publication_delays" not in config_data:
            config_data["publication_delays"] = {}
        config_data["publication_delays"].update({
            "max_delay_minutes": settings.publication.max_delay_minutes,
            "min_delay_minutes": settings.publication.min_delay_minutes
        })
        
        if "safety" not in config_data:
            config_data["safety"] = {}
        config_data["safety"].update({
            "dry_run_default": settings.publication.dry_run_default
        })
        
        # Update scheduler settings
        if "scheduler" not in config_data:
            config_data["scheduler"] = {}
        config_data["scheduler"].update({
            "daily_limit": settings.scheduler.daily_limit,
            "working_hours_start": settings.scheduler.working_hours_start,
            "working_hours_end": settings.scheduler.working_hours_end
        })
        
        # Write updated config
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        logger.info("Settings updated successfully")
        
        return {"success": True, "message": "Settings updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")
