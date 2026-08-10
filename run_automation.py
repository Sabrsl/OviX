#!/usr/bin/env python3
"""
Main entry point for Wikipedia maintenance automation.

Usage:
    python run_automation.py [--dry-run] [--lia-mode] [--no-telegram]

Environment variables:
    TELEGRAM_BOT_TOKEN: Telegram bot token (optional)
    TELEGRAM_ADMIN_IDS: Comma-separated list of admin Telegram IDs (optional)
    GEMINI_API_KEY: Google Gemini API key (optional)
"""

import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root))

from wikipedia_maintenance.orchestrator.automation_orchestrator import AutomationOrchestrator


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/automation.log', encoding='utf-8')
        ]
    )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Wikipedia Maintenance Automation Bot'
    )
    
    parser.add_argument(
        '--lang',
        default='fr',
        help='Wikipedia language code (default: fr)'
    )
    
    parser.add_argument(
        '--family',
        default='wikipedia',
        help='Wikipedia family (default: wikipedia)'
    )
    
    parser.add_argument(
        '--category',
        default=None,
        help='Category to retrieve articles from (default: from config.yaml or "Article à wikifier/Liste complète")'
    )
    
    parser.add_argument(
        '--max-articles',
        type=int,
        default=100,
        help='Maximum articles to retrieve (default: 100)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (no actual publishing)'
    )
    
    parser.add_argument(
        '--lia-mode',
        action='store_true',
        help='Use AI for corrections instead of regex analyzers'
    )
    
    parser.add_argument(
        '--ai-provider',
        default='gemini',
        choices=['gemini', 'ollama'],
        help='AI provider to use for LIA mode (default: gemini)'
    )
    
    parser.add_argument(
        '--ollama-url',
        default=None,
        help='Ollama server URL (default: from config.yaml or http://localhost:11434)'
    )
    
    parser.add_argument(
        '--ollama-model',
        default=None,
        help='Main Ollama model (default: from config.yaml or mistral:instruct)'
    )
    
    parser.add_argument(
        '--ollama-fallback',
        default=None,
        help='Fallback Ollama model (default: from config.yaml or llama3:instruct)'
    )
    
    parser.add_argument(
        '--gemini-api-key',
        help='Google Gemini API key (can also be set via GEMINI_API_KEY env var)'
    )
    
    parser.add_argument(
        '--gemini-project-id',
        default=None,
        help='Google Cloud project ID (default: from config.yaml or 804175778135)'
    )
    
    parser.add_argument(
        '--gemini-model',
        default=None,
        help='Gemini model to use (default: from config.yaml or gemini-flash-lite-latest)'
    )
    
    parser.add_argument(
        '--lia-limit',
        type=int,
        default=None,
        help='Character limit for AI mode (default: from config.yaml or 10800)'
    )
    
    parser.add_argument(
        '--no-telegram',
        action='store_true',
        help='Disable Telegram bot integration'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Parse arguments
    args = parse_args()
    
    # Load config.yaml for defaults
    config_defaults = {}
    try:
        with open('config/config.yaml', 'r', encoding='utf-8') as f:
            config_yaml = yaml.safe_load(f)
            if config_yaml:
                if 'ai' in config_yaml:
                    ai_config = config_yaml['ai']
                    if 'gemini' in ai_config:
                        config_defaults['gemini_project_id'] = ai_config['gemini'].get('project_id', '804175778135')
                        config_defaults['gemini_model'] = ai_config['gemini'].get('model', 'gemini-flash-lite-latest')
                        config_defaults['gemini_limit'] = ai_config['gemini'].get('limit', 10800)
                    if 'ollama' in ai_config:
                        config_defaults['ollama_url'] = ai_config['ollama'].get('url', 'http://localhost:11434')
                        config_defaults['ollama_model'] = ai_config['ollama'].get('model', 'mistral:instruct')
                        config_defaults['ollama_fallback'] = ai_config['ollama'].get('fallback', 'llama3:instruct')
                if 'other' in config_yaml:
                    config_defaults['default_category'] = config_yaml['other'].get('default_category', 'Article à wikifier/Liste complète')
    except Exception as e:
        logger.warning(f"Could not load config.yaml: {e}")
    
    # Get Telegram config from environment
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_admin_ids = []
    
    if not args.no_telegram and telegram_bot_token:
        admin_ids_str = os.environ.get('TELEGRAM_ADMIN_IDS', '')
        if admin_ids_str:
            try:
                telegram_admin_ids = [int(id.strip()) for id in admin_ids_str.split(',')]
            except ValueError:
                logger.error("Invalid TELEGRAM_ADMIN_IDS format. Use comma-separated integers.")
                sys.exit(1)
        else:
            logger.warning("TELEGRAM_BOT_TOKEN set but TELEGRAM_ADMIN_IDS not set. Telegram disabled.")
            telegram_bot_token = None
    
    # Get Gemini API key from argument or environment
    gemini_api_key = args.gemini_api_key or os.environ.get('GEMINI_API_KEY')
    
    # Create orchestrator
    orchestrator = AutomationOrchestrator(
        lang=args.lang,
        family=args.family,
        category_name=args.category or config_defaults.get('default_category'),
        max_articles=args.max_articles,
        dry_run=args.dry_run,
        telegram_bot_token=telegram_bot_token,
        telegram_admin_ids=telegram_admin_ids,
        lia_mode=args.lia_mode,
        ai_provider=args.ai_provider,
        ollama_url=args.ollama_url or config_defaults.get('ollama_url'),
        ollama_model=args.ollama_model or config_defaults.get('ollama_model'),
        ollama_fallback=args.ollama_fallback or config_defaults.get('ollama_fallback'),
        gemini_api_key=gemini_api_key,
        gemini_project_id=args.gemini_project_id or config_defaults.get('gemini_project_id'),
        gemini_model=args.gemini_model or config_defaults.get('gemini_model'),
        lia_limit=args.lia_limit or config_defaults.get('gemini_limit')
    )
    
    # Run orchestrator
    try:
        asyncio.run(orchestrator.run_forever())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        asyncio.run(orchestrator.shutdown())
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
