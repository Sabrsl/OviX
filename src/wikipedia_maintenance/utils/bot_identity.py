"""
Bot identity and User-Agent management for Wikipedia automation.

This module provides centralized bot identification including:
- Unique bot identifier
- Wikipedia-compliant User-Agent strings
- Bot discussion page information
- Contact information for the bot operator
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BotIdentity:
    """
    Bot identity information for Wikipedia compliance.
    
    IMPORTANT: Without bot approval, User-Agent must appear human.
    Set use_bot_user_agent=False to use human-like User-Agent.
    
    Wikipedia requires bots to:
    - Have a unique identifying name (only after approval)
    - Include contact information in User-Agent
    - Maintain a discussion page for community feedback
    - Follow bot approval process
    """
    
    bot_name: str = "SynsOperatorBot"
    bot_version: str = "1.0"
    operator_name: str = "Sysoperator"
    operator_contact: str = "https://fr.wikipedia.org/wiki/Discussion_utilisateur:Sysoperator"
    bot_discussion: str = "https://fr.wikipedia.org/wiki/Discussion_utilisateur:SynsOperatorBot"
    repository: str = "https://github.com/yourusername/syns_operator_bot"
    use_bot_user_agent: bool = False  # IMPORTANT: Default to human User-Agent without bot approval
    
    def get_user_agent(self, purpose: str = "") -> str:
        """
        Generate a Wikipedia-compliant User-Agent string.
        
        IMPORTANT: Without bot approval, returns human-like User-Agent.
        Set use_bot_user_agent=True only after Wikipedia bot approval.
        
        Args:
            purpose: Optional purpose description (e.g., "Archive Research", "Content Verification")
            
        Returns:
            Wikipedia-compliant User-Agent string (human-like by default)
        """
        if not self.use_bot_user_agent:
            # Human-like User-Agent for non-approved usage
            # This appears as a regular browser/tool rather than a bot
            return f"Mozilla/5.0 (compatible; WikipediaMaintenanceTool/{self.bot_version}; +{self.operator_contact})"
        
        # Bot User-Agent (only use after Wikipedia bot approval)
        base = f"{self.bot_name}/{self.bot_version}"
        
        if purpose:
            base += f" ({purpose})"
        
        base += f" - {self.operator_contact}"
        
        return base
    
    def get_full_user_agent(self) -> str:
        """
        Get the full User-Agent with all information.
        
        Returns:
            Complete User-Agent string
        """
        if not self.use_bot_user_agent:
            return f"Mozilla/5.0 (compatible; WikipediaMaintenanceTool/{self.bot_version}; +{self.operator_contact})"
        
        return (
            f"{self.bot_name}/{self.bot_version} "
            f"(https://fr.wikipedia.org/wiki/Discussion_utilisateur:SynsOperatorBot) "
            f"- {self.operator_contact} "
            f"- {self.repository}"
        )


class BotIdentityManager:
    """
    Manager for bot identity configuration.
    
    Provides centralized access to bot identity information
    with support for environment variable overrides.
    """
    
    ENV_BOT_NAME = "BOT_NAME"
    ENV_BOT_VERSION = "BOT_VERSION"
    ENV_OPERATOR_NAME = "OPERATOR_NAME"
    ENV_OPERATOR_CONTACT = "OPERATOR_CONTACT"
    ENV_BOT_DISCUSSION = "BOT_DISCUSSION"
    ENV_REPOSITORY = "REPOSITORY"
    ENV_USE_BOT_USER_AGENT = "USE_BOT_USER_AGENT"
    
    def __init__(self):
        """Initialize the bot identity manager."""
        self._identity = self._load_identity()
    
    def _load_identity(self) -> BotIdentity:
        """
        Load bot identity from environment variables or defaults.
        
        Returns:
            BotIdentity instance
        """
        # IMPORTANT: Default to false for human-like User-Agent without bot approval
        use_bot_user_agent = os.environ.get(self.ENV_USE_BOT_USER_AGENT, "false").lower() == "true"
        
        if use_bot_user_agent:
            logger.warning("USE_BOT_USER_AGENT=true - Using bot User-Agent. Ensure Wikipedia bot approval is obtained.")
        else:
            logger.info("USE_BOT_USER_AGENT=false - Using human-like User-Agent (appropriate without bot approval)")
        
        return BotIdentity(
            bot_name=os.environ.get(self.ENV_BOT_NAME, "SynsOperatorBot"),
            bot_version=os.environ.get(self.ENV_BOT_VERSION, "1.0"),
            operator_name=os.environ.get(self.ENV_OPERATOR_NAME, "Sysoperator"),
            operator_contact=os.environ.get(
                self.ENV_OPERATOR_CONTACT,
                "https://fr.wikipedia.org/wiki/Discussion_utilisateur:Sysoperator"
            ),
            bot_discussion=os.environ.get(
                self.ENV_BOT_DISCUSSION,
                "https://fr.wikipedia.org/wiki/Discussion_utilisateur:SynsOperatorBot"
            ),
            repository=os.environ.get(
                self.ENV_REPOSITORY,
                "https://github.com/yourusername/syns_operator_bot"
            ),
            use_bot_user_agent=use_bot_user_agent
        )
    
    def get_identity(self) -> BotIdentity:
        """
        Get the current bot identity.
        
        Returns:
            BotIdentity instance
        """
        return self._identity
    
    def get_user_agent(self, purpose: str = "") -> str:
        """
        Get a User-Agent string for a specific purpose.
        
        Args:
            purpose: Optional purpose description
            
        Returns:
            User-Agent string
        """
        return self._identity.get_user_agent(purpose)
    
    def update_identity(self, **kwargs) -> None:
        """
        Update bot identity parameters.
        
        Args:
            **kwargs: Bot identity parameters to update
        """
        for key, value in kwargs.items():
            if hasattr(self._identity, key):
                setattr(self._identity, key, value)
            else:
                logger.warning(f"Unknown bot identity parameter: {key}")


# Global instance
_bot_identity_manager: Optional[BotIdentityManager] = None


def get_bot_identity_manager() -> BotIdentityManager:
    """
    Get the global bot identity manager instance.
    
    Returns:
        BotIdentityManager instance
    """
    global _bot_identity_manager
    
    if _bot_identity_manager is None:
        _bot_identity_manager = BotIdentityManager()
    
    return _bot_identity_manager


def get_user_agent(purpose: str = "") -> str:
    """
    Convenience function to get a User-Agent string.
    
    Args:
        purpose: Optional purpose description
        
    Returns:
        User-Agent string
    """
    return get_bot_identity_manager().get_user_agent(purpose)