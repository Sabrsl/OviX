"""
Bot discussion page management for Wikipedia automation.

This module provides functionality to:
- Create and maintain a bot discussion page
- Log bot operations on the discussion page
- Enable community feedback
- Document bot activities for transparency
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of bot operations to log."""
    ARTICLE_ANALYSIS = "Analyse d'article"
    ARTICLE_CORRECTION = "Correction d'article"
    ARTICLE_PUBLICATION = "Publication d'article"
    CATEGORY_PROCESSING = "Traitement de catégorie"
    ERROR = "Erreur"
    MAINTENANCE = "Maintenance"
    CONFIGURATION_CHANGE = "Changement de configuration"


@dataclass
class BotOperation:
    """Record of a bot operation for discussion page logging."""
    operation_type: OperationType
    timestamp: datetime
    article_title: Optional[str] = None
    details: str = ""
    success: bool = True
    error_message: Optional[str] = None
    
    def format_for_discussion(self) -> str:
        """
        Format the operation for Wikipedia discussion page.
        
        Returns:
            Formatted wikitext string
        """
        timestamp_str = self.timestamp.strftime("%d %B %Y à %H:%M")
        status_icon = "✓" if self.success else "✗"
        
        if self.article_title:
            header = f"=== {self.operation_type.value} : {self.article_title} ==="
        else:
            header = f"=== {self.operation_type.value} ==="
        
        content = f"""
{header}
* '''Date''' : {timestamp_str}
* '''Statut''' : {status_icon} {'Succès' if self.success else 'Échec'}
"""
        
        if self.details:
            content += f"* '''Détails''' : {self.details}\n"
        
        if self.error_message:
            content += f"* '''Erreur''' : {self.error_message}\n"
        
        return content


class BotDiscussionManager:
    """
    Manager for bot discussion page operations.
    
    Provides functionality to maintain a transparent record of bot operations
    on Wikipedia following bot guidelines and best practices.
    """
    
    def __init__(self, bot_username: str, discussion_page_title: Optional[str] = None):
        """
        Initialize the bot discussion manager.
        
        Args:
            bot_username: Wikipedia username of the bot
            discussion_page_title: Full title of the discussion page (default: Discussion utilisateur:BotUsername)
        """
        self.bot_username = bot_username
        self.discussion_page_title = discussion_page_title or f"Discussion utilisateur:{bot_username}"
        self.operation_log: List[BotOperation] = []
        self._enabled = True
    
    def log_operation(
        self,
        operation_type: OperationType,
        article_title: Optional[str] = None,
        details: str = "",
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log a bot operation.
        
        Args:
            operation_type: Type of operation
            article_title: Related article title (if applicable)
            details: Additional details about the operation
            success: Whether the operation succeeded
            error_message: Error message if operation failed
        """
        operation = BotOperation(
            operation_type=operation_type,
            timestamp=datetime.now(),
            article_title=article_title,
            details=details,
            success=success,
            error_message=error_message
        )
        
        self.operation_log.append(operation)
        logger.info(f"Logged operation: {operation_type.value} for {article_title or 'system'}")
    
    def generate_discussion_page_content(self, max_operations: int = 50) -> str:
        """
        Generate content for the bot discussion page.
        
        Args:
            max_operations: Maximum number of recent operations to include
            
        Returns:
            Wikitext content for the discussion page
        """
        # Get recent operations
        recent_operations = self.operation_log[-max_operations:]
        
        # Generate page header
        content = "{{Bot maintenance page\n\n"
        content += f"This page documents the operations and activities of the {self.bot_username} bot.\n\n"
        
        content += "== Bot Information ==\n"
        content += f"* '''Bot Name''' : {self.bot_username}\n"
        content += "* '''Operator''' : [[User:Sysoperator|Sysoperator]]\n"
        content += "* '''Purpose''' : Automated Wikipedia maintenance and corrections\n"
        content += "* '''Approval Status''' : [[Wikipedia:Bot requests|Pending approval]]\n\n"
        
        content += "== Recent Operations ==\n"
        content += "The following table shows the most recent bot operations:\n\n"
        
        content += "{| class=\"wikitable\"\n"
        content += "|-\n"
        content += "! Date\n"
        content += "! Operation\n"
        content += "! Article\n"
        content += "! Status\n"
        content += "! Details\n"
        
        # Add operation rows
        for operation in reversed(recent_operations):
            date_str = operation.timestamp.strftime("%Y-%m-%d %H:%M")
            operation_name = operation.operation_type.value
            article = f"[[{operation.article_title}]]" if operation.article_title else "N/A"
            status = "✓" if operation.success else "✗"
            details = operation.details[:50] + "..." if len(operation.details) > 50 else operation.details
            
            content += "|-\n"
            content += f"| {date_str}\n"
            content += f"| {operation_name}\n"
            content += f"| {article}\n"
            content += f"| {status}\n"
            content += f"| {details}\n"
        
        content += "|}\n"
        
        # Add statistics
        total_operations = len(self.operation_log)
        successful_operations = sum(1 for op in self.operation_log if op.success)
        failed_operations = total_operations - successful_operations
        
        content += "\n== Statistics ==\n"
        content += f"* '''Total Operations''' : {total_operations}\n"
        if total_operations > 0:
            success_rate = successful_operations/total_operations*100
            content += f"* '''Successful''' : {successful_operations} ({success_rate:.1f}%)\n"
            content += f"* '''Failed''' : {failed_operations} ({100-success_rate:.1f}%)\n\n"
        else:
            content += "* '''Successful''' : 0 (0.0%)\n"
            content += "* '''Failed''' : 0 (0.0%)\n\n"
        
        content += "== Feedback and Issues ==\n"
        content += "Community members can report issues or provide feedback here:\n"
        content += "* Use the section below to report problems\n"
        content += "* Include the article title and description of the issue\n"
        content += "* The bot operator will review all reports\n\n"
        
        content += "=== Issue Reports ===\n"
        content += "<!-- Add new issue reports below this line -->\n\n"
        
        content += "== Contact ==\n"
        content += "* '''Bot Operator''' : [[User talk:Sysoperator|Contact the operator]]\n"
        content += f"* '''Bot Discussion''' : [[{self.discussion_page_title}|This page]]\n"
        content += "* '''Repository''' : https://github.com/yourusername/syns_operator_bot\n\n"
        
        content += "----\n"
        content += f"''Last updated: {datetime.now().strftime('%d %B %Y %H:%M')}''\n"
        
        return content
    
    def enable_logging(self) -> None:
        """Enable operation logging."""
        self._enabled = True
        logger.info("Bot discussion logging enabled")
    
    def disable_logging(self) -> None:
        """Disable operation logging."""
        self._enabled = False
        logger.info("Bot discussion logging disabled")
    
    def is_enabled(self) -> bool:
        """Check if logging is enabled."""
        return self._enabled
    
    def get_operation_count(self) -> int:
        """Get total number of logged operations."""
        return len(self.operation_log)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get operation statistics.
        
        Returns:
            Dictionary with operation statistics
        """
        if not self.operation_log:
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0
            }
        
        total = len(self.operation_log)
        successful = sum(1 for op in self.operation_log if op.success)
        failed = total - successful
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total * 100
        }


# Global instance
_bot_discussion_manager: Optional[BotDiscussionManager] = None


def get_bot_discussion_manager(bot_username: str = "SynsOperatorBot") -> BotDiscussionManager:
    """
    Get the global bot discussion manager instance.
    
    Args:
        bot_username: Wikipedia username of the bot
        
    Returns:
        BotDiscussionManager instance
    """
    global _bot_discussion_manager
    
    if _bot_discussion_manager is None:
        _bot_discussion_manager = BotDiscussionManager(bot_username)
    
    return _bot_discussion_manager


def log_bot_operation(
    operation_type: OperationType,
    article_title: Optional[str] = None,
    details: str = "",
    success: bool = True,
    error_message: Optional[str] = None
) -> None:
    """
    Convenience function to log a bot operation.
    
    Args:
        operation_type: Type of operation
        article_title: Related article title (if applicable)
        details: Additional details about the operation
        success: Whether the operation succeeded
        error_message: Error message if operation failed
    """
    manager = get_bot_discussion_manager()
    manager.log_operation(operation_type, article_title, details, success, error_message)