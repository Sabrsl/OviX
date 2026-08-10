"""
Structured JSON logging for better observability and security.

This module provides a centralized logging system that outputs structured JSON logs
with consistent field names, proper masking of sensitive data, and improved
searchability for log analysis tools.
"""

import logging
import json
import time
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path
import os


class StructuredJSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs log records as structured JSON.
    
    This provides:
    - Consistent field names across all log entries
    - Automatic masking of sensitive data
    - Structured format for log analysis tools
    - Better observability and debugging capabilities
    """
    
    # Fields that should never be logged in clear text
    SENSITIVE_FIELDS = {
        'password', 'pwd', 'passwd', 'secret', 'token', 'api_key', 'apikey',
        'credential', 'auth', 'authorization', 'bearer', 'session'
    }
    
    def __init__(self, service_name: str = "wikipedia_maintenance"):
        """
        Initialize the structured JSON formatter.
        
        Args:
            service_name: Name of the service for consistent log identification
        """
        super().__init__()
        self.service_name = service_name
        
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as structured JSON.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON-formatted log entry as string
        """
        # Create base log entry
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'service': self.service_name,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(self._sanitize_extra_fields(record.extra_fields))
        
        # Add context-specific fields from record
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'created', 'filename', 'lineno', 'funcName',
                'levelname', 'levelno', 'pathname', 'module', 'exc_info', 'exc_text',
                'stack_info', 'message', 'asctime', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'extra_fields'
            }:
                # Check if this is a sensitive field
                if any(sensitive in key.lower() for sensitive in self.SENSITIVE_FIELDS):
                    log_entry[key] = self._mask_value(value)
                else:
                    log_entry[key] = value
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)
    
    def _sanitize_extra_fields(self, extra_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize extra fields to remove sensitive data.
        
        Args:
            extra_fields: Dictionary of extra fields from the log record
            
        Returns:
            Sanitized dictionary with sensitive values masked
        """
        sanitized = {}
        for key, value in extra_fields.items():
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_FIELDS):
                sanitized[key] = self._mask_value(value)
            else:
                sanitized[key] = value
        return sanitized
    
    def _mask_value(self, value: Any) -> str:
        """
        Mask a sensitive value for logging.
        
        Args:
            value: The sensitive value to mask
            
        Returns:
            Masked value string
        """
        if value is None:
            return "null"
        
        value_str = str(value)
        if len(value_str) <= 4:
            return "*" * len(value_str)
        return "*" * (len(value_str) - 4) + value_str[-4:]


class StructuredLogger:
    """
    Centralized structured logging manager.
    
    Provides consistent logging across the application with:
    - JSON formatting for machine readability
    - Automatic sensitive data masking
    - Context-aware logging
    - Performance metrics tracking
    """
    
    def __init__(self, service_name: str = "wikipedia_maintenance", log_level: str = "INFO"):
        """
        Initialize the structured logger.
        
        Args:
            service_name: Name of the service for log identification
            log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.service_name = service_name
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self._setup_logging()
        
    def _setup_logging(self) -> None:
        """Configure the root logger with structured JSON formatting."""
        # Remove existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create JSON formatter
        json_formatter = StructuredJSONFormatter(self.service_name)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(json_formatter)
        console_handler.setLevel(self.log_level)
        
        # File handler (if log directory exists)
        log_dir = Path("logs")
        if log_dir.exists():
            file_handler = logging.FileHandler(log_dir / "structured.log")
            file_handler.setFormatter(json_formatter)
            file_handler.setLevel(self.log_level)
            root_logger.addHandler(file_handler)
        
        # Add console handler
        root_logger.addHandler(console_handler)
        root_logger.setLevel(self.log_level)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance with structured formatting.
        
        Args:
            name: Name of the logger (typically __name__)
            
        Returns:
            Logger instance configured for structured logging
        """
        return logging.getLogger(name)
    
    def log_performance(self, operation: str, duration_ms: float, extra: Optional[Dict[str, Any]] = None) -> None:
        """
        Log performance metrics for an operation.
        
        Args:
            operation: Name of the operation performed
            duration_ms: Duration in milliseconds
            extra: Additional context fields
        """
        logger = self.get_logger("performance")
        log_data = {
            'operation': operation,
            'duration_ms': duration_ms,
            'performance': True
        }
        if extra:
            log_data.update(extra)
        
        logger.info(f"Performance: {operation}", extra={'extra_fields': log_data})


# Global structured logger instance
_structured_logger: Optional[StructuredLogger] = None


def setup_structured_logging(service_name: str = "wikipedia_maintenance", log_level: str = "INFO") -> StructuredLogger:
    """
    Setup structured logging for the application.
    
    Args:
        service_name: Name of the service for log identification
        log_level: Minimum log level
        
    Returns:
        StructuredLogger instance
    """
    global _structured_logger
    
    if _structured_logger is None:
        _structured_logger = StructuredLogger(service_name, log_level)
    
    return _structured_logger


def get_structured_logger() -> Optional[StructuredLogger]:
    """
    Get the global structured logger instance.
    
    Returns:
        StructuredLogger instance or None if not initialized
    """
    return _structured_logger


class PerformanceTimer:
    """
    Context manager for timing operations and logging performance.
    
    Usage:
        with PerformanceTimer("article_analysis"):
            analyze_article()
    """
    
    def __init__(self, operation_name: str, extra: Optional[Dict[str, Any]] = None):
        """
        Initialize the performance timer.
        
        Args:
            operation_name: Name of the operation being timed
            extra: Additional context fields
        """
        self.operation_name = operation_name
        self.extra = extra or {}
        self.start_time = None
        self.logger = get_structured_logger()
        
    def __enter__(self):
        """Start the timer."""
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer and log performance."""
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            if self.logger:
                self.logger.log_performance(self.operation_name, duration_ms, self.extra)
        return False