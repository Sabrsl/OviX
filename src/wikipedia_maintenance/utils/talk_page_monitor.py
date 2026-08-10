"""
Talk Page Monitor for emergency bot control via Wikipedia discussion page.

This module provides:
- Deterministic command detection (no AI interpretation)
- Comment format: <!-- BOT-CONTROL: STOP --> or <!-- BOT-CONTROL: RESUME -->
- Integration with centralized kill switch
- Safe command parsing
"""

import logging
import re
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Deterministic command markers (NO natural language interpretation)
# Accept both HTML comments and MediaWiki templates for user-friendliness
COMMAND_PATTERN = re.compile(r'(?:<!--\s*BOT-CONTROL:\s*(STOP|RESUME)\s*-->|{{!\s*BOT-CONTROL:\s*(STOP|RESUME)\s*}})', re.IGNORECASE)


@dataclass
class TalkPageCommand:
    """Detected command from talk page."""
    command: str  # "STOP" or "RESUME"
    marker: str  # The exact marker found
    position: int  # Position in page content
    context: str  # Surrounding context for logging


class TalkPageMonitor:
    """
    Monitor bot's talk page for emergency control commands.
    
    ONLY processes deterministic markers:
    - <!-- BOT-CONTROL: STOP -->
    - <!-- BOT-CONTROL: RESUME -->
    
    NO natural language interpretation for safety.
    """
    
    def __init__(self, bot_username: str):
        """
        Initialize the talk page monitor.
        
        Args:
            bot_username: Wikipedia username of the bot
        """
        self.bot_username = bot_username
        self.talk_page_title = f"Discussion utilisateur:{bot_username}"
        logger.info(f"Talk Page Monitor initialized for {self.talk_page_title}")
    
    def parse_commands(self, page_content: str) -> list[TalkPageCommand]:
        """
        Parse deterministic commands from talk page content.
        
        Args:
            page_content: Raw wikitext content of talk page
            
        Returns:
            List of detected commands (most recent first)
        """
        commands = []
        
        for match in COMMAND_PATTERN.finditer(page_content):
            command = match.group(1).upper()
            marker = match.group(0)
            position = match.start()
            
            # Get context (100 chars before and after)
            start_context = max(0, position - 100)
            end_context = min(len(page_content), position + len(marker) + 100)
            context = page_content[start_context:end_context]
            
            cmd = TalkPageCommand(
                command=command,
                marker=marker,
                position=position,
                context=context
            )
            
            commands.append(cmd)
            logger.info(f"Detected command: {command} at position {position}")
        
        # Return most recent command first
        commands.reverse()
        return commands
    
    def get_latest_command(self, page_content: str) -> Optional[TalkPageCommand]:
        """
        Get the most recent command from talk page.
        
        Args:
            page_content: Raw wikitext content of talk page
            
        Returns:
            Most recent command or None
        """
        commands = self.parse_commands(page_content)
        return commands[0] if commands else None
    
    def should_stop(self, page_content: str) -> Tuple[bool, Optional[str]]:
        """
        Check if the bot should stop based on talk page commands.
        
        Args:
            page_content: Raw wikitext content of talk page
            
        Returns:
            (should_stop, reason) tuple
        """
        latest_command = self.get_latest_command(page_content)
        
        if latest_command is None:
            return False, None
        
        if latest_command.command == "STOP":
            reason = f"Emergency stop requested from talk page via marker: {latest_command.marker}"
            logger.warning(f"🛑 {reason}")
            return True, reason
        
        if latest_command.command == "RESUME":
            logger.info("✅ Resume command detected from talk page")
            return False, "Resume command detected"
        
        return False, None
    
    def validate_command_marker(self, marker: str) -> bool:
        """
        Validate that a marker is a legitimate command.
        
        Args:
            marker: Marker string to validate
            
        Returns:
            True if marker is a valid command
        """
        return bool(COMMAND_PATTERN.fullmatch(marker))


class TalkPageCommandHandler:
    """
    Handler for processing talk page commands and updating kill switch.
    
    This integrates TalkPageMonitor with KillSwitchManager.
    """
    
    def __init__(self, bot_username: str, kill_switch_manager):
        """
        Initialize the command handler.
        
        Args:
            bot_username: Wikipedia username of the bot
            kill_switch_manager: Kill switch manager instance
        """
        self.monitor = TalkPageMonitor(bot_username)
        self.kill_switch_manager = kill_switch_manager
        self.bot_username = bot_username
    
    def process_talk_page(self, page_content: str, user: str = "unknown") -> None:
        """
        Process talk page content and update kill switch accordingly.
        
        Args:
            page_content: Raw wikitext content of talk page
            user: User who made the edit (if known)
        """
        try:
            should_stop, reason = self.monitor.should_stop(page_content)
            
            if should_stop:
                # Enable kill switch
                from .kill_switch_manager import KillSwitchTrigger
                self.kill_switch_manager.enable(
                    reason=reason,
                    trigger_source=KillSwitchTrigger.TALK_PAGE,
                    requested_by=user
                )
                logger.warning(f"🛑 Kill switch enabled via talk page by {user}")
            else:
                # Only disable if there's an explicit RESUME command
                latest_command = self.monitor.get_latest_command(page_content)
                if latest_command and latest_command.command == "RESUME":
                    self.kill_switch_manager.disable(
                        reason="Resume command from talk page",
                        requested_by=user
                    )
                    logger.info(f"✅ Kill switch disabled via talk page by {user}")
        
        except Exception as e:
            logger.error(f"Failed to process talk page commands: {e}")