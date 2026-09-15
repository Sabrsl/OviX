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

    Wikimedia's User-Agent policy (meta.wikimedia.org/wiki/User-Agent_policy)
    requires a descriptive User-Agent with contact information on every
    request, and explicitly treats a browser-copied User-Agent as evidence
    of malicious bot behavior — so the string below is always descriptive,
    regardless of bot-flag approval status. `use_bot_user_agent` only
    controls whether "bot" appears in the string, which the policy
    recommends once the account has bot-flag approval.
    """

    bot_name: str = "SynsOperatorBot"
    bot_version: str = "1.0"
    operator_name: str = "Sysoperator"
    operator_contact: str = "https://fr.wikipedia.org/wiki/Discussion_utilisateur:Sysoperator"
    bot_discussion: str = "https://fr.wikipedia.org/wiki/Discussion_utilisateur:SynsOperatorBot"
    repository: str = "https://github.com/Sabrsl/OviX"
    use_bot_user_agent: bool = False

    def get_user_agent(self, purpose: str = "") -> str:
        """
        Generate a Wikimedia API-compliant User-Agent string:
        `<name>/<version> (<contact>[; <purpose>])`.

        Args:
            purpose: Optional purpose description (e.g., "Archive Research", "Content Verification")

        Returns:
            Wikimedia API-compliant User-Agent string.
        """
        agent = f"{self.bot_name}/{self.bot_version}"

        if purpose:
            agent += f" ({self.operator_contact}; {purpose})"
        else:
            agent += f" ({self.operator_contact})"

        if self.use_bot_user_agent and "bot" not in agent.lower():
            agent += " bot"

        return agent


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
                "https://github.com/Sabrsl/OviX"
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