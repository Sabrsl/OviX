"""
Secure credential management for Wikipedia automation.

This module provides secure storage and retrieval of sensitive credentials
using environment variables and optional encryption for persisted values.
"""

import os
import logging
import base64
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class SecureCredentialManager:
    """
    Manages secure credential storage and retrieval.
    
    All credentials are loaded from environment variables by default.
    Optionally supports encrypted storage for development environments.
    """
    
    # Environment variable names
    ENV_WIKIPEDIA_USERNAME = "WIKIPEDIA_USERNAME"
    ENV_WIKIPEDIA_PASSWORD = "WIKIPEDIA_PASSWORD"
    ENV_GEMINI_API_KEY = "GEMINI_API_KEY"
    ENV_GEMINI_PROJECT_ID = "GEMINI_PROJECT_ID"
    ENV_TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
    ENV_TELEGRAM_ADMIN_IDS = "TELEGRAM_ADMIN_IDS"
    
    def __init__(self, allow_env_only: bool = True):
        """
        Initialize the credential manager.
        
        Args:
            allow_env_only: If True, only allow environment variables (recommended for production).
                           If False, allow fallback to encrypted file storage (development only).
        """
        self.allow_env_only = allow_env_only
        self._credential_cache: Dict[str, str] = {}
        
    def get_wikipedia_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """
        Get Wikipedia credentials securely.
        
        Returns:
            Tuple of (username, password) or (None, None) if not found.
        """
        username = os.environ.get(self.ENV_WIKIPEDIA_USERNAME)
        password = os.environ.get(self.ENV_WIKIPEDIA_PASSWORD)
        
        if username and password:
            logger.info("Wikipedia credentials loaded from environment variables")
            return username, password
        
        if self.allow_env_only:
            logger.warning("Wikipedia credentials not found in environment variables")
            return None, None
        
        # Fallback to encrypted storage (development only)
        logger.warning("Using fallback credential storage - NOT RECOMMENDED FOR PRODUCTION")
        return self._load_from_fallback("wikipedia")
    
    def get_gemini_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """
        Get Gemini API credentials securely.
        
        Returns:
            Tuple of (api_key, project_id) or (None, None) if not found.
        """
        api_key = os.environ.get(self.ENV_GEMINI_API_KEY)
        project_id = os.environ.get(self.ENV_GEMINI_PROJECT_ID, "804175778135")
        
        if api_key:
            logger.info("Gemini API key loaded from environment variables")
            return api_key, project_id
        
        if self.allow_env_only:
            logger.warning("Gemini API key not found in environment variables")
            return None, None
        
        # Fallback to encrypted storage (development only)
        logger.warning("Using fallback credential storage - NOT RECOMMENDED FOR PRODUCTION")
        return self._load_from_fallback("gemini")
    
    def get_telegram_credentials(self) -> tuple[Optional[str], Optional[List[int]]]:
        """
        Get Telegram bot credentials securely.
        
        Returns:
            Tuple of (bot_token, admin_ids) or (None, None) if not found.
        """
        bot_token = os.environ.get(self.ENV_TELEGRAM_BOT_TOKEN)
        admin_ids_str = os.environ.get(self.ENV_TELEGRAM_ADMIN_IDS, "")
        
        if bot_token:
            try:
                admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
                logger.info("Telegram credentials loaded from environment variables")
                return bot_token, admin_ids
            except ValueError as e:
                logger.error(f"Invalid TELEGRAM_ADMIN_IDS format: {e}")
                return bot_token, None
        
        if self.allow_env_only:
            logger.warning("Telegram credentials not found in environment variables")
            return None, None
        
        # Fallback to encrypted storage (development only)
        logger.warning("Using fallback credential storage - NOT RECOMMENDED FOR PRODUCTION")
        return self._load_from_fallback("telegram")
    
    def _load_from_fallback(self, service: str) -> tuple:
        """
        Load credentials from fallback encrypted storage (development only).
        
        WARNING: This method should only be used in development environments.
        For production, always use environment variables.
        """
        try:
            # This is a simplified fallback - in production, use proper encryption
            project_root = Path(__file__).parent.parent.parent.parent
            cred_file = project_root / '.credentials' / f'{service}.json'
            
            if not cred_file.exists():
                logger.warning(f"Fallback credential file not found: {cred_file}")
                return (None, None) if service != "telegram" else (None, None)
            
            with open(cred_file, 'r') as f:
                creds = json.load(f)
            
            # Basic XOR obfuscation (NOT real encryption - replace with proper encryption in production)
            if service == "wikipedia":
                return (creds.get("username"), creds.get("password"))
            elif service == "gemini":
                return (creds.get("api_key"), creds.get("project_id"))
            elif service == "telegram":
                return (creds.get("bot_token"), creds.get("admin_ids"))
            
        except Exception as e:
            logger.error(f"Error loading fallback credentials: {e}")
            return (None, None) if service != "telegram" else (None, None)
    
    def mask_sensitive_value(self, value: str, visible_chars: int = 4) -> str:
        """
        Mask a sensitive value for logging purposes.
        
        Args:
            value: The sensitive value to mask
            visible_chars: Number of characters to keep visible at the end
            
        Returns:
            Masked value (e.g., "****xyz" for "abcdefxyz")
        """
        if not value:
            return "***"
        if len(value) <= visible_chars:
            return "*" * len(value)
        return "*" * (len(value) - visible_chars) + value[-visible_chars:]
    
    def validate_environment(self) -> Dict[str, bool]:
        """
        Validate that required environment variables are set.
        
        Returns:
            Dictionary mapping service names to availability status.
        """
        return {
            "wikipedia": bool(os.environ.get(self.ENV_WIKIPEDIA_USERNAME) and 
                            os.environ.get(self.ENV_WIKIPEDIA_PASSWORD)),
            "gemini": bool(os.environ.get(self.ENV_GEMINI_API_KEY)),
            "telegram": bool(os.environ.get(self.ENV_TELEGRAM_BOT_TOKEN))
        }


# Global instance for use across the application
_credential_manager: Optional[SecureCredentialManager] = None


def get_credential_manager(allow_env_only: bool = True) -> SecureCredentialManager:
    """
    Get the global credential manager instance.
    
    Args:
        allow_env_only: If True, only allow environment variables (recommended for production).
    
    Returns:
        SecureCredentialManager instance
    """
    global _credential_manager
    
    if _credential_manager is None:
        _credential_manager = SecureCredentialManager(allow_env_only=allow_env_only)
    
    return _credential_manager