"""
Utility modules for Wikipedia Maintenance Tool.
"""

from .database import DatabaseManager
from .corrector import Corrector, Correction
# from .publisher import Publisher  # Disabled
from .config import Config, load_config
from .wikipedia_api import get_wikipedia_client, WikipediaAPIClient
from .secure_credentials import get_credential_manager, SecureCredentialManager
from .structured_logging import setup_structured_logging, get_structured_logger, PerformanceTimer
from .retry_handler import RetryHandler, RetryConfig, RetryStrategy, retry_with_config, get_retry_handler, RateLimitError, get_wikipedia_retry_handler, get_gemini_retry_handler
from .bot_identity import BotIdentity, BotIdentityManager, get_bot_identity_manager, get_user_agent
from .bot_discussion import BotDiscussionManager, OperationType, get_bot_discussion_manager, log_bot_operation
from .performance_optimizer import (
    PerformanceMonitor, PerformanceMetrics, ControlledParallelism, 
    PayloadOptimizer, get_performance_monitor, monitor_performance, BatchProcessor
)
from .kill_switch_manager import KillSwitchManager, KillSwitchState, KillSwitchTrigger, get_kill_switch_manager
from .talk_page_monitor import TalkPageMonitor, TalkPageCommand, TalkPageCommandHandler
from .kill_switch_templates import get_discussion_page_template, get_emergency_stop_instructions

__all__ = [
    'DatabaseManager',
    'Corrector',
    'Correction',
    # 'Publisher',  # Disabled
    'Config',
    'load_config',
    'get_wikipedia_client',
    'WikipediaAPIClient',
    'get_credential_manager',
    'SecureCredentialManager',
    'setup_structured_logging',
    'get_structured_logger',
    'PerformanceTimer',
    'RetryHandler',
    'RetryConfig',
    'RetryStrategy',
    'retry_with_config',
    'get_retry_handler',
    'RateLimitError',
    'get_wikipedia_retry_handler',
    'get_gemini_retry_handler',
    'BotIdentity',
    'BotIdentityManager',
    'get_bot_identity_manager',
    'get_user_agent',
    'BotDiscussionManager',
    'OperationType',
    'get_bot_discussion_manager',
    'log_bot_operation',
    'PerformanceMonitor',
    'PerformanceMetrics',
    'ControlledParallelism',
    'PayloadOptimizer',
    'get_performance_monitor',
    'monitor_performance',
    'BatchProcessor',
    'KillSwitchManager',
    'KillSwitchState',
    'KillSwitchTrigger',
    'get_kill_switch_manager',
    'TalkPageMonitor',
    'TalkPageCommand',
    'TalkPageCommandHandler',
    'get_discussion_page_template',
    'get_emergency_stop_instructions'
]
