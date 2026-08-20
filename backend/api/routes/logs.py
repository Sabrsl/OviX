"""
OVIX Backend API - Logs Routes

Handles log retrieval and streaming.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Models
# ============================================================================

class LogEntry(BaseModel):
    """Log entry."""
    timestamp: str
    level: str
    logger: str
    message: str


class LogsResponse(BaseModel):
    """Logs response."""
    success: bool
    logs: List[LogEntry]
    total: int


class LogStatsResponse(BaseModel):
    """Log statistics response."""
    success: bool
    stats: dict


# ============================================================================
# Routes
# ============================================================================

@router.get("/")
async def get_logs(
    limit: int = 100,
    level: Optional[str] = None,
    offset: int = 0
):
    """
    Get recent logs.
    
    Retrieves logs from the log file with optional filtering by level.
    """
    try:
        # Try multiple possible log file names
        log_file = Path("logs/app.log")
        if not log_file.exists():
            log_file = Path("logs/wikipedia_maintenance.log")
        
        if not log_file.exists():
            return LogsResponse(
                success=True,
                logs=[],
                count=0,
                message="No log file found"
            )
        
        # Read log file
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Normalize the requested filter once, outside the loop
        level_filter = level.upper() if level else None

        # Parse log lines
        log_entries = []
        for line in lines:
            try:
                # Log format parsing: timestamp - module - level - message
                parts = line.strip().split(" - ", 3)
                if len(parts) >= 4:
                    # Extract level from the third part (which contains the level)
                    level_part = parts[2].strip()
                    # The level is typically the first word in the third part.
                    # NOTE: this must NOT be named `level` — that would shadow
                    # the `level` function parameter (the requested filter) and
                    # silently turn the filter below into a no-op.
                    entry_level = level_part.split()[0] if level_part else "INFO"
                    
                    # Try to convert timestamp to ISO format for better frontend parsing
                    timestamp = parts[0]
                    try:
                        # Try to parse common log formats
                        # Format: "2026-08-17 10:13:49,558"
                        if ' ' in timestamp:
                            date_part, time_part = timestamp.split(' ', 1)
                            # Convert to ISO format: "2026-08-17T10:13:49.558"
                            timestamp = f"{date_part}T{time_part.replace(',', '.')}"
                    except:
                        pass  # Keep original timestamp if conversion fails
                    
                    entry = LogEntry(
                        timestamp=timestamp,
                        level=entry_level,
                        logger=parts[1],
                        message=parts[3]
                    )
                    
                    # Filter by level if specified
                    if level_filter is None or entry.level.upper() == level_filter:
                        log_entries.append(entry)
            except Exception as e:
                # Skip malformed lines
                continue
        
        # Reverse to get most recent first
        log_entries.reverse()
        
        # Apply pagination
        paginated_logs = log_entries[offset:offset + limit]
        
        return LogsResponse(
            success=True,
            logs=paginated_logs,
            total=len(log_entries)
        )
        
    except Exception as e:
        logger.error(f"Failed to get logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@router.get("/recent")
async def get_recent_logs(count: int = 50):
    """
    Get most recent logs.
    
    Convenience endpoint for getting the most recent log entries.
    """
    result = await get_logs(limit=count, offset=0)
    # Transform to match frontend expectation
    return {
        "success": result.success,
        "logs": [log.dict() for log in result.logs],
        "total": result.total
    }


@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats():
    """
    Get log statistics.
    
    Returns statistics about log levels and counts.
    """
    try:
        # Try multiple possible log file names
        log_file = Path("logs/app.log")
        if not log_file.exists():
            log_file = Path("logs/wikipedia_maintenance.log")
        
        if not log_file.exists():
            return LogStatsResponse(
                success=True,
                stats={
                    "total_lines": 0,
                    "by_level": {},
                    "file_size": 0
                }
            )
        
        # Read log file
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Count by level
        level_counts = {
            "DEBUG": 0,
            "INFO": 0,
            "WARNING": 0,
            "ERROR": 0,
            "CRITICAL": 0
        }
        
        for line in lines:
            try:
                parts = line.strip().split(" - ", 3)
                if len(parts) >= 3:
                    # Extract level from the third part
                    level_part = parts[2].strip()
                    entry_level = level_part.split()[0].upper() if level_part else "INFO"
                    if entry_level in level_counts:
                        level_counts[entry_level] += 1
            except Exception:
                continue
        
        stats = {
            "total_lines": len(lines),
            "by_level": level_counts,
            "file_size": log_file.stat().st_size,
            "file_path": str(log_file)
        }
        
        return LogStatsResponse(
            success=True,
            stats=stats
        )
        
    except Exception as e:
        logger.error(f"Failed to get log stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get log stats: {str(e)}")