"""
Main automation orchestrator for Wikipedia maintenance.

Implements the complete startup workflow:
1. Retrieve up to 100 articles from "Article à wikifier/Liste complète"
2. Exclude already treated articles
3. Launch full analysis
4. Generate and apply all corrections
5. Feed publication queue
6. Start progressive publication
"""

import logging
import asyncio
import random
import yaml
from datetime import datetime
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Tuple
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

if TYPE_CHECKING:
    import pywikibot

from wikipedia_maintenance.retrievers import CategoryRetriever, Article
from wikipedia_maintenance.utils.analyzed_tracker import AnalyzedTracker, AnalysisStatus, AnalysisRecord, get_analyzed_tracker
from wikipedia_maintenance.utils.ui_settings import get_settings_manager
from wikipedia_maintenance.analyzers import DeadLinkAnalyzer, HttpLinksAnalyzer, XMLTypographyAnalyzer
from wikipedia_maintenance.utils.publisher import Publisher, Corrector
from wikipedia_maintenance.utils.published_tracker import PublishedTracker
from wikipedia_maintenance.utils.database import DatabaseManager
from wikipedia_maintenance.utils.automation_report import get_report_generator, AutomationReport
from wikipedia_maintenance.utils.automation_state_sqlite import (
    SQLiteAutomationStateManager, SessionStatus, ArticleProcessingStatus, ArticleState
)
from wikipedia_maintenance.utils import get_wikipedia_retry_handler, get_gemini_retry_handler
from wikipedia_maintenance.utils.connection_checker import get_connection_checker
from wikipedia_maintenance.utils.event_manager import get_event_manager, EventType
from .scheduler import Scheduler, SchedulerConfig

logger = logging.getLogger(__name__)


class AutomationOrchestrator:
    """
    Main orchestrator for Wikipedia maintenance automation.
    
    Coordinates:
    - Article retrieval
    - Analysis and correction
    - Queue feeding
    - Scheduler startup
    """
    
    def __init__(
        self,
        lang: str = 'fr',
        family: str = 'wikipedia',
        category_name: str = "Article à wikifier/Liste complète",
        max_articles: int = 100,
        dry_run: bool = True,
        telegram_bot_token: Optional[str] = None,
        telegram_admin_ids: Optional[List[int]] = None,
        lia_mode: bool = False,
        include_analyzed: bool = False,
        ai_provider: str = "gemini",  # "gemini" or "ollama"
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "mistral:instruct",
        ollama_fallback: str = "llama3:instruct",
        gemini_api_key: Optional[str] = None,
        gemini_project_id: Optional[str] = None,
        gemini_model: str = "gemini-flash-lite-latest",
        lia_limit: int = 10800,
        # Optional pre-initialized components to avoid recreation
        publisher: Optional[Publisher] = None,
        published_tracker: Optional[PublishedTracker] = None,
        analyzed_tracker: Optional[AnalyzedTracker] = None,
        database: Optional[Any] = None,  # Database manager for SQLite integration
        kill_switch_manager: Optional[Any] = None  # Kill switch manager for emergency stop
    ):
        """
        Initialize automation orchestrator.
        
        Args:
            lang: Wikipedia language code.
            family: Wikipedia family.
            category_name: Category to retrieve articles from.
            max_articles: Maximum articles to retrieve.
            dry_run: If True, don't actually publish.
            telegram_bot_token: Telegram bot token for remote control.
            telegram_admin_ids: List of admin Telegram IDs.
            lia_mode: If True, use AI for corrections.
            ai_provider: AI provider to use ("gemini" or "ollama").
            ollama_url: Ollama server URL.
            ollama_model: Main Ollama model.
            ollama_fallback: Fallback Ollama model.
            gemini_api_key: Google Gemini API key.
            gemini_project_id: Google Cloud project ID.
            gemini_model: Gemini model to use.
            lia_limit: Character limit for AI mode.
        """
        # Use provided parameters or fallback to config
        if lang is None or lang == '':
            try:
                from wikipedia_maintenance.utils.config import load_config
                config = load_config()
                self.lang = config.wikipedia.lang
            except Exception:
                self.lang = 'fr'  # Ultimate fallback
        else:
            self.lang = lang
            
        if family is None or family == '':
            try:
                from wikipedia_maintenance.utils.config import load_config
                config = load_config()
                self.family = config.wikipedia.family
            except Exception:
                self.family = 'wikipedia'  # Ultimate fallback
        else:
            self.family = family
        self.category_name = category_name
        self.max_articles = max_articles
        self.dry_run = dry_run
        self.lia_mode = lia_mode
        self.include_analyzed = include_analyzed
        self.ai_provider = ai_provider
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.ollama_fallback = ollama_fallback
        self.gemini_api_key = gemini_api_key
        self.gemini_project_id = gemini_project_id
        self.gemini_model = gemini_model
        self.lia_limit = lia_limit

        # Validate Gemini credentials if AI provider is gemini
        if self.ai_provider == "gemini" and not self.gemini_api_key:
            logger.warning("Gemini API key not provided for AI provider 'gemini'")
        if self.ai_provider == "gemini" and not self.gemini_project_id:
            logger.warning("Gemini project ID not provided for AI provider 'gemini'")

        # Initialize components (use pre-initialized ones if provided)
        self.site: Optional[pywikibot.Site] = None
        self.publisher = publisher  # Use provided publisher or None
        self.published_tracker = published_tracker  # Use provided tracker or None
        self.analyzed_tracker = analyzed_tracker  # Use provided tracker or None
        self.database = database  # Use provided database manager for SQLite integration
        self.kill_switch_manager = kill_switch_manager  # Use provided kill switch manager or None
        self.report_generator = get_report_generator()
        self.scheduler: Optional[Scheduler] = None
        self.lia_client: Optional[Any] = None
        
        # State management and retry handlers - SQLite as single source of truth
        if self.database:
            self.state_manager = SQLiteAutomationStateManager(self.database)
        else:
            # Fallback to JSON if database not provided (should not happen in production)
            from wikipedia_maintenance.utils.automation_state import AutomationStateManager
            self.state_manager = AutomationStateManager()
            logger.warning("Using JSON-based state manager - SQLite database not provided")
        self.wikipedia_retry_handler = get_wikipedia_retry_handler()
        self.gemini_retry_handler = get_gemini_retry_handler()
        self.connection_checker = get_connection_checker()
        self.event_manager = get_event_manager()
        
        # API throttler for rate limiting
        from wikipedia_maintenance.utils.api_throttler import get_global_throttler
        self.api_throttler = get_global_throttler()
        
        # Initialize analyzers once (reused across articles to avoid repeated config loading)
        self._analyzers_cache = None
        self._settings_manager = None
        
        self.category_name = category_name
        self.max_articles = max_articles
        self.dry_run = dry_run
        self.lia_mode = lia_mode
        self.include_analyzed = include_analyzed
        self.ai_provider = ai_provider
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.ollama_fallback = ollama_fallback
        self.gemini_api_key = gemini_api_key
        self.gemini_project_id = gemini_project_id
        self.gemini_model = gemini_model
        self.lia_limit = lia_limit
        
        # Track statistics for reporting
        self.start_time: Optional[datetime] = None
        self.stats = {
            'articles_retrieved': 0,
            'articles_excluded_published': 0,
            'articles_excluded_analyzed': 0,
            'articles_excluded_length': 0,
            'articles_excluded_duplicates': 0,
            'articles_analyzed': 0,
            'articles_published': 0,
            'articles_rejected': 0,
            'articles_ignored': 0,
            'articles_error': 0,
            'errors': []
        }
        
        # Telegram config
        self.telegram_bot_token = telegram_bot_token
        self.telegram_admin_ids = telegram_admin_ids or []
        
        # Control flags for pause/stop
        self._paused = False
        self._stopped = False
        
        logger.info(f"AutomationOrchestrator initialized (lang={lang}, category={category_name})")
    
    def _check_kill_switch(self) -> bool:
        """
        Check if kill switch is enabled and update article states to prevent stale status.
        
        Returns:
            True if kill switch is enabled and automation should stop, False otherwise.
        """
        if self.kill_switch_manager:
            try:
                state = self.kill_switch_manager.get_state()
                if state and state.enabled:
                    logger.warning(f"Kill Switch is ENABLED - stopping automation. Reason: {state.reason}")
                    self.state_manager.update_status(SessionStatus.INTERRUPTED)
                    self.state_manager.record_interruption(f"Kill Switch activated: {state.reason}")
                    
                    # Update article states to prevent stale 'analyzing' status
                    current_state = self.state_manager.get_state()
                    if current_state and current_state.article_states:
                        for article_state in current_state.article_states:
                            if article_state.get('status') in ['analyzing', 'retrieving', 'correcting']:
                                article_state['status'] = 'interrupted'
                                article_state['completed_at'] = datetime.now().isoformat()
                                article_state['error_message'] = f'Kill Switch activated: {state.reason}'
                        self.state_manager.save_state()
                        logger.info(f"Updated {len([s for s in current_state.article_states if s.get('status') == 'interrupted'])} article states to 'interrupted' due to kill switch")
                    
                    return True
            except Exception as e:
                logger.error(f"Error checking kill switch: {e}")
        return False
    
    async def _check_control_flags(self) -> bool:
        """
        Check if automation should pause or stop based on control flags.
        
        Returns:
            True if automation should stop, False if it should continue (or pause).
        """
        # Check stop flag first
        if self._stopped:
            logger.warning("Stop flag is set - stopping automation")
            self.state_manager.update_status(SessionStatus.FAILED)
            self.state_manager.record_interruption("Stop requested by user")
            
            # Update article states to prevent stale 'analyzing' status
            state = self.state_manager.get_state()
            if state and state.article_states:
                for article_state in state.article_states:
                    if article_state.get('status') in ['analyzing', 'retrieving', 'correcting']:
                        article_state['status'] = 'interrupted'
                        article_state['completed_at'] = datetime.now().isoformat()
                        article_state['error_message'] = 'Automation stopped by user'
                self.state_manager.save_state()
                logger.info(f"Updated {len([s for s in state.article_states if s.get('status') == 'interrupted'])} article states to 'interrupted' due to stop request")
            
            return True
        
        # Check pause flag
        if self._paused:
            logger.info("Pause flag is set - pausing automation")
            self.state_manager.update_status(SessionStatus.PAUSED)
            self.state_manager.record_interruption("Pause requested by user")
            # Wait until pause is lifted
            while self._paused and not self._stopped:
                import asyncio
                await asyncio.sleep(1)
            # If stopped while paused
            if self._stopped:
                logger.warning("Stop requested while paused - stopping automation")
                self.state_manager.update_status(SessionStatus.FAILED)
                self.state_manager.record_interruption("Stop requested while paused")
                return True
            # Resume
            logger.info("Resuming automation")
            self.state_manager.update_status(SessionStatus.RUNNING)
            self.state_manager.resolve_interruption(self.state_manager.get_interruption_summary()['unresolved_count'] > 0 and 
                                                      self.state_manager.get_state().interruptions[-1] if 
                                                      self.state_manager.get_state() and 
                                                      self.state_manager.get_state().interruptions else None)
        
        return False
    
    def pause(self) -> bool:
        """
        Pause the automation.
        
        Returns:
            True if pause command was sent successfully.
        """
        if not self._paused:
            self._paused = True
            logger.info("Automation pause requested")
            return True
        return False
    
    async def resume(self) -> bool:
        """
        Resume the automation or session.
        
        P2-1 FIX: Now properly calls _resume_session() to restore interrupted sessions.
        
        Returns:
            True if resume command was sent successfully.
        """
        # Check if there's a paused session to resume
        state = self.state_manager.get_state()
        if state and state.status == SessionStatus.PAUSED.value:
            logger.info("Resuming paused session...")
            result = await self._resume_session()
            if result:
                self._paused = False
                return True
            return False
        
        # Simple flag-based resume for in-progress automation
        if self._paused:
            self._paused = False
            logger.info("Automation resume requested (flag-based)")
            return True
        
        logger.warning("Automation is not paused, cannot resume")
        return False
    
    def stop(self) -> bool:
        """
        Stop the automation and update article states to prevent stale status.
        
        Returns:
            True if stop command was sent successfully.
        """
        if not self._stopped:
            self._stopped = True
            self._paused = False  # Clear pause flag when stopping
            logger.info("Automation stop requested")
            
            # Update article states to prevent stale 'analyzing' status
            state = self.state_manager.get_state()
            if state and state.article_states:
                for article_state in state.article_states:
                    if article_state.get('status') in ['analyzing', 'retrieving', 'correcting']:
                        article_state['status'] = 'interrupted'
                        article_state['completed_at'] = datetime.now().isoformat()
                        article_state['error_message'] = 'Automation stopped by user'
                self.state_manager.save_state()
                logger.info(f"Updated {len([s for s in state.article_states if s.get('status') == 'interrupted'])} article states to 'interrupted'")
            
            return True
        return False
    
    async def startup(self) -> bool:
        """
        Execute the complete startup workflow.
        
        Returns:
            True if startup successful.
        """
        logger.info("=" * 60)
        logger.info("STARTING AUTOMATION ORCHESTRATOR")
        logger.info("=" * 60)
        
        # Émettre l'événement AUTOMATION_STARTED
        await self.event_manager.emit(
            EventType.AUTOMATION_STARTED,
            {
                "category": self.category_name,
                "max_articles": self.max_articles,
                "include_analyzed": self.include_analyzed,
                "lia_mode": self.lia_mode
            },
            session_id=self.session_id
        )
        
        # P1 CRITICAL FIX: Check if automation is already running to prevent double launch
        current_state = self.state_manager.get_state()
        if current_state and current_state.status in ['running', 'paused']:
            logger.warning(f"Automation already active with status: {current_state.status}, session: {current_state.session_id}")
            logger.warning("Rejecting duplicate automation launch attempt")
            return False
        
        # P1 CRITICAL FIX: Clean up stale article states from previous crashes/interruptions with timeout mechanism
        if current_state and current_state.article_states:
            stale_count = 0
            timeout_threshold_minutes = 30  # Articles stuck > 30 min are considered stale
            current_time = datetime.now()
            
            for article_state in current_state.article_states:
                status = article_state.get('status')
                
                # Check for stale states (analyzing, retrieving, correcting) with timeout
                if status in ['analyzing', 'retrieving', 'correcting']:
                    started_at = article_state.get('started_at')
                    
                    # If we have a timestamp, check if it's stale
                    if started_at:
                        try:
                            start_time = datetime.fromisoformat(started_at)
                            time_diff = (current_time - start_time).total_seconds() / 60  # Convert to minutes
                            
                            if time_diff > timeout_threshold_minutes:
                                article_state['status'] = 'interrupted'
                                article_state['completed_at'] = current_time.isoformat()
                                article_state['error_message'] = f'Automation interrupted (stale for {time_diff:.1f} minutes - timeout threshold: {timeout_threshold_minutes} min)'
                                stale_count += 1
                                logger.warning(f"Marked article as stale: {article_state.get('title', 'unknown')} stuck in '{status}' for {time_diff:.1f} minutes")
                        except Exception as e:
                            logger.warning(f"Could not parse timestamp for article state: {e}")
                            # Fallback: mark as interrupted if we can't parse the timestamp
                            article_state['status'] = 'interrupted'
                            article_state['completed_at'] = current_time.isoformat()
                            article_state['error_message'] = 'Automation interrupted (invalid timestamp)'
                            stale_count += 1
                    else:
                        # No timestamp - assume stale (safer to interrupt than leave hanging)
                        article_state['status'] = 'interrupted'
                        article_state['completed_at'] = current_time.isoformat()
                        article_state['error_message'] = 'Automation interrupted (no timestamp - assumed stale)'
                        stale_count += 1
                        logger.warning(f"Marked article as stale (no timestamp): {article_state.get('title', 'unknown')} stuck in '{status}'")
            
            if stale_count > 0:
                self.state_manager.save_state()
                logger.warning(f"Cleaned up {stale_count} stale article states from previous interrupted session (timeout threshold: {timeout_threshold_minutes} minutes)")
        
        # Check for resumable session
        if self.state_manager.can_resume():
            logger.info("Found resumable session, will attempt recovery")
            return await self._resume_session()
        
        # Clear any old state before creating new session
        self.state_manager.clear_state()
        
        # Create new session
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        mode = "IA" if self.lia_mode else "regex"
        self.state_manager.create_session(
            session_id=session_id,
            category_name=self.category_name,
            max_articles=self.max_articles,
            mode=mode
        )
        self.state_manager.update_status(SessionStatus.RUNNING)
        
        # Reset statistics and record start time
        self.start_time = datetime.now()
        self.stats = {
            'articles_retrieved': 0,
            'articles_excluded_published': 0,
            'articles_excluded_analyzed': 0,
            'articles_excluded_length': 0,
            'articles_excluded_duplicates': 0,
            'articles_analyzed': 0,
            'articles_published': 0,
            'articles_rejected': 0,
            'articles_ignored': 0,
            'articles_error': 0,
            'errors': []
        }
        
        try:
            # Step 1/10: Connect to Wikipedia
            self.state_manager.update_step("1/10 - Connecting to Wikipedia")
            if self._check_kill_switch() or await self._check_control_flags():
                return False
            if not await self._connect_to_wikipedia():
                self.state_manager.update_status(SessionStatus.FAILED)
                return False
            
            # Step 2/10: Initialize scheduler (but don't start yet)
            self.state_manager.update_step("2/10 - Initializing scheduler")
            if self._check_kill_switch() or await self._check_control_flags():
                return False
            await self._initialize_scheduler()
            
            # Step 3/10: Get already analyzed but unpublished articles (ONLY if include_analyzed is True)
            self.state_manager.update_step("3/10 - Reusing analyzed articles")
            if self._check_kill_switch() or await self._check_control_flags():
                return False
            existing_analyzed = []
            if self.include_analyzed:
                existing_analyzed = await self._get_analyzed_pending_articles()
                # Limit to max_articles to prevent overwhelming the queue
                existing_analyzed = existing_analyzed[:self.max_articles]
                logger.info(f"Limited existing analyzed articles to {len(existing_analyzed)} (max: {self.max_articles})")
            else:
                logger.info("include_analyzed is False, skipping reuse of analyzed articles")
            
            # Step 4/10: Calculate how many new articles to retrieve
            needed_articles = self.max_articles - len(existing_analyzed)
            logger.info(f"Target: {self.max_articles} articles, Already analyzed: {len(existing_analyzed)}, Need to retrieve: {needed_articles}")
            
            # Step 5/10: Retrieve new articles if needed
            new_articles = []
            if needed_articles > 0:
                self.state_manager.update_step("5/10 - Retrieving articles")
                if self._check_kill_switch() or await self._check_control_flags():
                    return False
                new_articles = await self._retrieve_articles(max_articles=needed_articles)
                
                # Émettre ARTICLE_DISCOVERED pour chaque article
                for article in new_articles:
                    await self.event_manager.emit(
                        EventType.ARTICLE_DISCOVERED,
                        {
                            "title": article.title,
                            "page_id": article.page_id
                        },
                        session_id=self.session_id
                    )
                if not new_articles:
                    logger.warning(f"No new articles retrieved, will use only existing analyzed articles ({len(existing_analyzed)})")
            
            # Step 6/10: Analyze and correct new articles only
            corrected_new_articles = []
            if new_articles:
                self.state_manager.update_step("6/10 - Analyzing articles")
                if self._check_kill_switch() or await self._check_control_flags():
                    return False
                corrected_new_articles = await self._analyze_and_correct_articles(new_articles)
            
            # Step 7/10: Combine existing analyzed and newly corrected articles
            self.state_manager.update_step("7/10 - Combining articles")
            if self._check_kill_switch() or await self._check_control_flags():
                return False
            all_corrected = existing_analyzed + corrected_new_articles
            logger.info(f"Total articles ready for publication: {len(all_corrected)} (existing: {len(existing_analyzed)}, new: {len(corrected_new_articles)})")
            
            if not all_corrected:
                logger.warning("No articles ready for publication, stopping")
                self.state_manager.update_status(SessionStatus.FAILED)
                return False
            
            # Step 8/10: Feed publication queue BEFORE starting scheduler
            self.state_manager.update_step("8/10 - Feeding publication queue")
            if self._check_kill_switch() or await self._check_control_flags():
                return False
            await self._feed_queue(all_corrected)
            
            # Émettre ARTICLE_QUEUED pour chaque article mis en file
            for article in all_corrected:
                await self.event_manager.emit(
                    EventType.ARTICLE_QUEUED,
                    {
                        "title": article.get('title', article.get('article_title', 'unknown')),
                        "changes_count": article.get('changes_count', 0)
                    },
                    session_id=self.session_id
                )
            
            # Step 9/10: Start scheduler AFTER queue is fed
            self.state_manager.update_step("9/10 - Starting scheduler")
            if self._check_kill_switch() or await self._check_control_flags():
                return False
            await self._start_scheduler()
            
            # Step 10/10: Generate and save report
            self.state_manager.update_step("10/10 - Generating report")
            await self._generate_and_save_report()
            
            self.state_manager.update_status(SessionStatus.COMPLETED)
            
            # Émettre AUTOMATION_STOPPED (complété avec succès)
            await self.event_manager.emit(
                EventType.AUTOMATION_STOPPED,
                {
                    "status": "completed",
                    "articles_processed": len(all_corrected)
                },
                session_id=self.session_id
            )
            logger.info("=" * 60)
            logger.info("AUTOMATION ORCHESTRATOR STARTUP COMPLETE")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Startup failed: {e}", exc_info=True)
            self.state_manager.update_status(SessionStatus.FAILED)
            return False
    
    async def _resume_session(self) -> bool:
        """
        Resume an interrupted automation session.
        
        Returns:
            True if resumption successful.
        """
        state = self.state_manager.get_state()
        if not state:
            logger.error("No state to resume")
            return False
        
        logger.info(f"Resuming session {state.session_id} from step: {state.current_step}")
        
        # Restore statistics from state
        self.start_time = datetime.fromisoformat(state.started_at) if state.started_at else datetime.now()
        self.stats = {
            'articles_retrieved': state.articles_processed,
            'articles_excluded_published': 0,
            'articles_excluded_analyzed': 0,
            'articles_excluded_length': 0,
            'articles_excluded_duplicates': 0,
            'articles_analyzed': state.articles_processed,
            'articles_published': state.articles_published,
            'articles_rejected': 0,
            'articles_ignored': 0,
            'articles_error': state.articles_error,
            'errors': []
        }
        
        self.state_manager.update_status(SessionStatus.RUNNING)
        
        try:
            # Step 1: Connect to Wikipedia
            self.state_manager.update_step("connecting_to_wikipedia")
            if not await self._connect_to_wikipedia():
                self.state_manager.update_status(SessionStatus.FAILED)
                return False
            
            # Step 2: Retrieve articles (skip already processed)
            self.state_manager.update_step("retrieving_articles")
            articles = await self._retrieve_articles()
            if not articles:
                logger.warning("No articles retrieved, stopping")
                self.state_manager.update_status(SessionStatus.FAILED)
                return False
            
            # Step 3: Initialize scheduler
            self.state_manager.update_step("initializing_scheduler")
            await self._initialize_scheduler()
            
            # Step 4: Analyze and correct articles (skip already processed)
            self.state_manager.update_step("analyzing_articles")
            corrected_articles = await self._analyze_and_correct_articles(articles)
            if not corrected_articles:
                logger.warning("No articles successfully corrected, stopping")
                self.state_manager.update_status(SessionStatus.FAILED)
                return False
            
            # Step 5: Feed publication queue
            await self._feed_queue(corrected_articles)
            
            # Step 6: Start scheduler
            await self._start_scheduler()
            
            # Step 7: Generate and save report
            await self._generate_and_save_report()
            
            self.state_manager.update_status(SessionStatus.COMPLETED)
            logger.info("=" * 60)
            logger.info("AUTOMATION SESSION RESUMED AND COMPLETED")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Session resumption failed: {e}", exc_info=True)
            self.state_manager.update_status(SessionStatus.FAILED)
            return False
    
    async def _connect_to_wikipedia(self) -> bool:
        """Connect to Wikipedia and initialize components."""
        logger.info("Step 1: Connecting to Wikipedia...")

        # Check connection first
        if not self.connection_checker.is_connected():
            logger.warning("Connection check failed, waiting for connection...")
            interruption = self.state_manager.record_interruption("Network connection unavailable")
            await self.connection_checker.wait_for_connection(check_interval=10.0, max_wait=300.0)
            self.state_manager.resolve_interruption(interruption)

        try:
            # Set PYWIKIBOT_DIR
            import os
            from pathlib import Path
            local_project_root = Path(__file__).parent.parent.parent.parent
            os.environ['PYWIKIBOT_DIR'] = str(local_project_root)
            
            # Create pywikibot site with retry logic and rate limiting
            import pywikibot
            def create_site():
                site = pywikibot.Site(self.lang, self.family)
                # Configure pywikibot rate limiting to match our settings
                pywikibot.config.put_throttle = 0  # Disable default throttling, we manage it ourselves
                pywikibot.config.maxlag = 5  # Maximum server lag in seconds
                
                # Override the API request method to use our throttler
                try:
                    original_request = site._simple_request
                except AttributeError:
                    # For newer pywikibot versions, we can't override internal methods
                    # Use the site's built-in rate limiting instead
                    logger.info("Using pywikibot built-in rate limiting")
                    original_request = None
                
                if original_request:
                    def throttled_request(**kwargs):
                        self.api_throttler.wait_if_needed()
                        try:
                            result = original_request(**kwargs)
                            self.api_throttler.report_success()
                            return result
                        except Exception as e:
                            if '429' in str(e) or 'Too Many Requests' in str(e):
                                self.api_throttler.report_429()
                            raise
                    
                    site._simple_request = throttled_request
                
                return site
            
            self.site = self.wikipedia_retry_handler.execute_with_retry(
                create_site
            )
            logger.info(f"Connected to {self.lang}.{self.family}")
            
            # Initialize publisher with credentials from environment (only if not already provided)
            if not self.publisher:
                import os
                username = os.environ.get('WIKIPEDIA_USERNAME')
                password = os.environ.get('WIKIPEDIA_PASSWORD')
                self.publisher = Publisher(username=username, password=password, dry_run=self.dry_run, lang=self.lang)
                authenticated = self.publisher.authenticate()

                if not authenticated:
                    logger.error("Publisher authentication failed")
                    return False

                logger.info("Publisher authenticated successfully")
            else:
                logger.info("Using existing publisher instance (skipping authentication)")

            # Initialize published tracker (only if not already provided)
            if not self.published_tracker:
                self.published_tracker = PublishedTracker()
            else:
                logger.info("Using existing published tracker instance")

            # Initialize analyzed tracker (only if not already provided)
            if not self.analyzed_tracker:
                self.analyzed_tracker = get_analyzed_tracker()
            else:
                logger.info("Using existing analyzed tracker instance")

            # Initialize database manager if not provided (for SQLite integration)
            if not self.database:
                try:
                    from wikipedia_maintenance.utils.database import DatabaseManager
                    import os
                    project_root = Path(__file__).parent.parent.parent.parent
                    db_path = str(project_root / "data" / "wikipedia_maintenance.db")
                    self.database = DatabaseManager(db_path)
                    logger.info("Database manager initialized for automation")
                except Exception as e:
                    logger.warning(f"Could not initialize database manager: {e}")
                    self.database = None
            else:
                logger.info("Using existing database manager instance")
            
            # Initialize AI client if in LIA mode
            if self.lia_mode:
                if self.ai_provider == "gemini":
                    if not self.gemini_api_key:
                        logger.error("Gemini API key not provided")
                        return False
                    from wikipedia_maintenance.utils.gemini_client import GeminiClient
                    self.lia_client = GeminiClient(
                        api_key=self.gemini_api_key,
                        project_id=self.gemini_project_id,
                        model=self.gemini_model,
                        limite_caracteres=self.lia_limit
                    )
                    provider_name = "Gemini"
                else:  # ollama
                    from wikipedia_maintenance.utils.lia_client import LIAOllamaClient
                    self.lia_client = LIAOllamaClient(
                        base_url=self.ollama_url,
                        model=self.ollama_model,
                        fallback_model=self.ollama_fallback,
                        limite_caracteres=self.lia_limit
                    )
                    provider_name = "Ollama"
                
                ok, error = self.lia_client.tester_connexion()
                if not ok:
                    logger.error(f"{provider_name} connection failed: {error}")
                    return False
                logger.info(f"{provider_name} client connected successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Wikipedia: {e}", exc_info=True)
            return False
    
    def _get_cached_analyzers(self):
        """Get or create cached analyzers to avoid repeated initialization."""
        if self._analyzers_cache is not None:
            return self._analyzers_cache
        
        # Read enabled analyzers from config.yaml (same source as UI settings)
        enabled_analyzer_names = self._get_enabled_analyzers_from_config()
        logger.info(f"Enabled analyzers from config.yaml: {enabled_analyzer_names}")
        
        # Map analyzer names to their classes
        analyzer_classes = {
            "DeadLinkAnalyzer": DeadLinkAnalyzer,
            "HttpLinksAnalyzer": HttpLinksAnalyzer,
            "XMLTypographyAnalyzer": XMLTypographyAnalyzer
        }
        
        # Initialize only enabled analyzers once
        analyzers = []
        for analyzer_name in enabled_analyzer_names:
            if analyzer_name in analyzer_classes:
                logger.info(f"Initializing analyzer: {analyzer_name}")
                if analyzer_name == "XMLTypographyAnalyzer":
                    # Initialize XML analyzer with config
                    from wikipedia_maintenance.utils.typography_xml_analyzer_config import TypographyXMLAnalyzerConfig
                    config = TypographyXMLAnalyzerConfig.load()
                    analyzers.append(XMLTypographyAnalyzer.from_config(config))
                else:
                    analyzers.append(analyzer_classes[analyzer_name]())
        
        self._analyzers_cache = analyzers
        logger.info(f"Cached {len(analyzers)} analyzers for reuse across articles")
        return analyzers
    
    def _get_enabled_analyzers_from_config(self) -> List[str]:
        """
        Get the list of enabled analyzers from config.yaml.
        
        This unifies the configuration source between UI and automation.
        The UI saves to config.yaml via the /api/config/section endpoint,
        and automation reads from the same file.
        
        Returns:
            List[str]: List of enabled analyzer names
        """
        try:
            from wikipedia_maintenance.utils.config import load_config
            config = load_config()
            
            # Check if analysis section exists
            if not hasattr(config, 'analysis'):
                logger.debug("analysis section not found in config, defaulting to DeadLinkAnalyzer")
                return ["DeadLinkAnalyzer"]
            
            # Build enabled analyzers list
            enabled_list = []
            
            # Always check DeadLinkAnalyzer
            if hasattr(config.analysis, 'enable_dead_link_analyzer'):
                if config.analysis.enable_dead_link_analyzer:
                    enabled_list.append("DeadLinkAnalyzer")
                    logger.info("DeadLinkAnalyzer enabled via enable_dead_link_analyzer setting")
                else:
                    logger.info("DeadLinkAnalyzer disabled via enable_dead_link_analyzer setting")
            else:
                # Default to enabled if not specified
                enabled_list.append("DeadLinkAnalyzer")
                logger.info("DeadLinkAnalyzer enabled by default")
            
            # Check if https_verification is enabled for HttpLinksAnalyzer
            if hasattr(config, 'https_verification') and hasattr(config.https_verification, 'enabled'):
                if config.https_verification.enabled:
                    enabled_list.append("HttpLinksAnalyzer")
                    logger.info("HttpLinksAnalyzer enabled via https_verification.enabled setting")
                else:
                    logger.info("HttpLinksAnalyzer disabled via https_verification.enabled setting")
            
            # Also check analysis.enable_http_links_analyzer as fallback/supplement
            if hasattr(config.analysis, 'enable_http_links_analyzer'):
                if config.analysis.enable_http_links_analyzer and "HttpLinksAnalyzer" not in enabled_list:
                    enabled_list.append("HttpLinksAnalyzer")
                    logger.info("HttpLinksAnalyzer enabled via enable_http_links_analyzer setting")
            
            # Check if XML typography analyzer is enabled
            if hasattr(config, 'typography_xml_analyzer') and hasattr(config.typography_xml_analyzer, 'enabled'):
                if config.typography_xml_analyzer.enabled:
                    enabled_list.append("XMLTypographyAnalyzer")
                    logger.info("XMLTypographyAnalyzer enabled via typography_xml_analyzer.enabled setting")
                else:
                    logger.info("XMLTypographyAnalyzer disabled via typography_xml_analyzer.enabled setting")
            
            return enabled_list if enabled_list else ["DeadLinkAnalyzer"]
            
            # Fallback to enabled_analyzers list if the boolean is not available
            if hasattr(config.analysis, 'enabled_analyzers'):
                return config.analysis.enabled_analyzers
            
            # Fallback to DeadLinkAnalyzer only if not configured
            logger.debug("enabled_analyzers not found in config, defaulting to DeadLinkAnalyzer")
            return ["DeadLinkAnalyzer"]
        except Exception as e:
            logger.warning(f"Failed to load enabled_analyzers from config: {e}, defaulting to DeadLinkAnalyzer")
            return ["DeadLinkAnalyzer"]
    
    def _get_case_normalization_setting(self) -> Tuple[bool, bool, bool]:
        """
        Get the case normalization settings from config.yaml.
        
        This unifies the configuration source between UI and automation.
        The UI saves to config.yaml via the /api/config/section endpoint,
        and automation reads from the same file.
        
        Returns:
            Tuple[bool, bool, bool]: (enable_case_normalization, enable_ner_title_normalization, normalize_with_ai)
        """
        try:
            from wikipedia_maintenance.utils.config import load_config
            config = load_config()
            
            # Check if analysis section exists and has enable_case_normalization
            enable_case = False
            enable_ner = False
            normalize_with_ai = False
            
            if hasattr(config, 'analysis'):
                if hasattr(config.analysis, 'enable_case_normalization'):
                    enable_case = config.analysis.enable_case_normalization
                if hasattr(config.analysis, 'enable_ner_title_normalization'):
                    enable_ner = config.analysis.enable_ner_title_normalization
                if hasattr(config.analysis, 'normalize_with_ai'):
                    normalize_with_ai = config.analysis.normalize_with_ai
            
            # normalize_with_ai only takes effect if enable_case_normalization is true
            if not enable_case:
                normalize_with_ai = False
            
            # Fallback to False if not configured
            if not enable_case and not enable_ner:
                logger.debug("enable_case_normalization not found in config, defaulting to False")
            
            return enable_case, enable_ner, normalize_with_ai
        except Exception as e:
            logger.warning(f"Failed to load case normalization settings from config: {e}, defaulting to False")
            return False, False, False
    
    async def _get_analyzed_pending_articles(self) -> List[Dict[str, Any]]:
        """Get already analyzed but unpublished articles from AnalyzedTracker."""
        logger.info("Retrieving already analyzed but unpublished articles...")
        
        if not self.analyzed_tracker:
            logger.warning("AnalyzedTracker not initialized, no existing articles to reuse")
            return []
        
        try:
            # Get all pending articles (analyzed but not published)
            pending_records = self.analyzed_tracker.get_records_by_status(AnalysisStatus.PENDING)
            logger.info(f"Found {len(pending_records)} pending analyzed articles")
            
            # Convert to corrected article format for queue
            corrected_articles = []
            for record in pending_records:
                # Skip if article has been published since analysis
                if self.published_tracker.is_recently_published(record.title, months=6):
                    logger.info(f"Skipping {record.title} - already published since analysis")
                    continue
                
                # Only include articles that match current mode (IA if lia_mode, regex otherwise)
                if self.lia_mode and record.mode != "IA":
                    continue
                if not self.lia_mode and record.mode == "IA":
                    continue
                
                # Get the corrected content from the article
                try:
                    article = Article(
                        title=record.title,
                        page_id=record.page_id,
                        revision_id=record.revision_id,
                        url=f"https://{self.lang}.{self.family}/wiki/{record.title.replace(' ', '_')}"
                    )
                    corrected_content = await self._get_corrected_content_from_record(record, article)
                    
                    if corrected_content:
                        corrected_articles.append({
                            'title': record.title,
                            'corrected_content': corrected_content,
                            'summary': record.summary or 'Wikification',
                            'changes_count': record.changes_count or 0,
                            'mode': record.mode,
                            'page_id': record.page_id,
                            'revision_id': record.revision_id
                        })
                        logger.info(f"Reusing analyzed article: {record.title}")
                except Exception as e:
                    logger.warning(f"Failed to retrieve content for {record.title}: {e}")
                    continue
            
            logger.info(f"Successfully retrieved {len(corrected_articles)} reusable analyzed articles")
            return corrected_articles
            
        except Exception as e:
            logger.error(f"Error retrieving analyzed pending articles: {e}", exc_info=True)
            return []
    
    async def _get_corrected_content_from_record(self, record: AnalysisRecord, article: Article) -> Optional[str]:
        """Get corrected content from an analysis record."""
        # Use the stored corrected content if available
        if record.corrected_content:
            logger.info(f"Using stored corrected content for {record.title}")
            return record.corrected_content
        
        # Fallback: fetch current page content from pywikibot if no stored content
        logger.warning(f"No stored corrected content for {record.title}, fetching from Wikipedia")
        try:
            page = pywikibot.Page(self.site, record.title)
            if page.exists():
                content = page.get()
                return content
            else:
                logger.error(f"Article {record.title} does not exist")
                return None
        except Exception as e:
            logger.error(f"Failed to get content for {record.title}: {e}")
            return None
    
    async def _retrieve_articles(self, max_articles: int = None) -> List[Article]:
        """Retrieve articles from category, excluding already treated ones."""
        target = max_articles if max_articles is not None else self.max_articles
        logger.info(f"Step 2: Retrieving articles from '{self.category_name}' (target: {target} eligible articles)...")
        
        try:
            # Use CategoryRetriever with cache disabled for automation to avoid pagination issues
            retriever = CategoryRetriever(self.site, use_cache=False)
            
            # Keep retrieving until we have enough eligible articles
            all_articles = []
            batch_size = 50  # Retrieve in batches to avoid too many API calls
            total_retrieved = 0
            total_filtered_published = 0
            total_filtered_analyzed = 0
            total_filtered_length = 0
            total_filtered_duplicates = 0
            
            # Track consecutive low-yield batches to avoid premature termination
            consecutive_low_yield_batches = 0
            MIN_BATCHES_BEFORE_ABORT = 5  # Allow several attempts before aborting
            
            # Use random offset for varied retrieval - cover entire category
            import random
            offset = random.randint(0, 10500)  # Cover full category range (11k articles)
            
            while len(all_articles) < target:
                # Retrieve a batch of articles with offset to progress through category
                articles = retriever.retrieve(
                    category_name=self.category_name,
                    max_articles=batch_size,
                    recursive=False,
                    offset=offset
                )
                
                if not articles:
                    logger.info("No more articles available in category")
                    break
                
                total_retrieved += len(articles)
                logger.info(f"Retrieved {len(articles)} articles (total retrieved: {total_retrieved}, eligible so far: {len(all_articles)})")
                
                # Increment offset for next batch to progress through category
                offset += batch_size
                
                # Filter out already treated articles
                article_titles = [article.title for article in articles]
                filtered_titles = self.published_tracker.filter_recently_published(article_titles, months=6)
                new_articles = [article for article in articles if article.title in filtered_titles]
                filtered_published = len(articles) - len(new_articles)
                total_filtered_published += filtered_published
                if filtered_published > 0:
                    logger.info(f"Filtered {filtered_published} recently published articles")
                
                # Filter out already analyzed articles (with same revision)
                if self.analyzed_tracker and not self.include_analyzed:
                    before_analyzed = len(new_articles)
                    new_articles = self.analyzed_tracker.filter_analyzed_articles(new_articles)
                    filtered_analyzed = before_analyzed - len(new_articles)
                    total_filtered_analyzed += filtered_analyzed
                    logger.info(f"Filtered {filtered_analyzed} already analyzed articles (remaining: {len(new_articles)})")
                
                # Filter by character limit if in LIA mode
                if self.lia_mode:
                    from wikipedia_maintenance.utils.verif_longueur import verifier
                    from wikipedia_maintenance.utils.api_throttler import get_global_throttler
                    import pywikibot
                    length_filtered_articles = []
                    logger.info(f"LIA mode active, filtering articles by character limit ({self.lia_limit})")
                    
                    # Use throttler for batch requests (one wait per batch, not per article)
                    throttler = get_global_throttler()
                    
                    # Use batch API call to get page lengths (more efficient)
                    batch_size = 50
                    for batch_start in range(0, len(new_articles), batch_size):
                        batch = new_articles[batch_start:batch_start + batch_size]
                        titles = [article.title for article in batch]
                        
                        # Apply throttling once per batch
                        throttler.wait_if_needed()
                        
                        try:
                            # Use MediaWiki API to get page info including length
                            params = {
                                'action': 'query',
                                'titles': '|'.join(titles),
                                'prop': 'info',
                                'inprop': 'length',
                                'format': 'json',
                                'formatversion': 2,
                            }
                            
                            api_url = self.site.base_url('api')
                            response = self.site._simple_request(**params)
                            data = response.submit()
                            
                            title_to_length = {}
                            if 'query' in data and 'pages' in data['query']:
                                for page_data in data['query']['pages']:
                                    title = page_data.get('title')
                                    length = page_data.get('length', 0)
                                    if title:
                                        title_to_length[title] = length
                            
                            # Filter articles based on length
                            for article in batch:
                                length = title_to_length.get(article.title, 0)
                                if length <= self.lia_limit:
                                    length_filtered_articles.append(article)
                        except Exception as e:
                            logger.warning(f"Batch API call failed: {e}, falling back to individual checks")
                            # Fallback to individual checks for this batch
                            for article in batch:
                                try:
                                    throttler.wait_if_needed()
                                    page = pywikibot.Page(self.site, article.title)
                                    if page.exists():
                                        content = page.get()
                                        ok, nb_caracteres = verifier(content, self.lia_limit)
                                        if ok:
                                            length_filtered_articles.append(article)
                                except Exception as e2:
                                    logger.warning(f"Failed to check length for '{article.title}': {e2}")
                    
                    new_articles = length_filtered_articles
                    logger.info(f"After length filtering: {len(new_articles)} articles remaining")
                
                # Add new articles to our list (avoid duplicates)
                before_add = len(all_articles)
                for article in new_articles:
                    if article.title not in [a.title for a in all_articles]:
                        all_articles.append(article)
                filtered_duplicates = len(new_articles) - (len(all_articles) - before_add)
                total_filtered_duplicates += filtered_duplicates
                
                added_count = len(all_articles) - before_add
                logger.info(f"Added {added_count} new articles (duplicates: {filtered_duplicates})")
                
                # Track consecutive low-yield batches
                if added_count == 0:
                    consecutive_low_yield_batches += 1
                    logger.warning(f"Low-yield batch: {consecutive_low_yield_batches}/{MIN_BATCHES_BEFORE_ABORT} consecutive batches with 0 eligible articles")
                else:
                    consecutive_low_yield_batches = 0  # Reset counter when we get articles
                
                # Update statistics
                self.stats['articles_retrieved'] = total_retrieved
                self.stats['articles_excluded_published'] = total_filtered_published
                self.stats['articles_excluded_analyzed'] = total_filtered_analyzed
                self.stats['articles_excluded_length'] = total_filtered_length
                self.stats['articles_excluded_duplicates'] = total_filtered_duplicates
                
                # Stop if we have enough articles
                if len(all_articles) >= target:
                    logger.info(f"Reached target of {target} eligible articles")
                    break
                
                # Abort after consecutive low-yield batches (allows exploration of multiple offsets)
                if consecutive_low_yield_batches >= MIN_BATCHES_BEFORE_ABORT:
                    logger.error(f"CRITICAL: {consecutive_low_yield_batches} consecutive batches with 0 eligible articles")
                    logger.error(f"Retrieved {total_retrieved} articles but only {len(all_articles)} are eligible")
                    logger.error(f"Filters: published={total_filtered_published}, analyzed={total_filtered_analyzed}, length={total_filtered_length}, duplicates={total_filtered_duplicates}")
                    if self.lia_mode and total_filtered_length > total_filtered_published + total_filtered_analyzed:
                        logger.error(f"LENGTH FILTER is the main bottleneck: {total_filtered_length} articles filtered for being too long")
                        logger.error(f"Recommendation: Increase character limit from {self.lia_limit} or disable LIA mode")
                    break
                
                # Stop if we retrieved a lot but still don't have enough (avoid infinite loop)
                if total_retrieved > target * 20:
                    logger.warning(f"Retrieved {total_retrieved} articles but only {len(all_articles)} are eligible, stopping")
                    logger.warning(f"Filters: published={total_filtered_published}, analyzed={total_filtered_analyzed}, length={total_filtered_length}, duplicates={total_filtered_duplicates}")
                    if self.lia_mode and total_filtered_length > total_filtered_published + total_filtered_analyzed:
                        logger.warning(f"LENGTH FILTER is the main bottleneck: {total_filtered_length} articles filtered for being too long")
                        logger.warning(f"Recommendation: Increase character limit from {self.lia_limit} or disable LIA mode")
                    break
            
            # Trim to exact count
            final_articles = all_articles[:target]
            
            logger.info(f"Final article count: {len(final_articles)} (requested: {target}, total retrieved: {total_retrieved})")
            logger.info(f"Filter summary: published={total_filtered_published}, analyzed={total_filtered_analyzed}, length={total_filtered_length}, duplicates={total_filtered_duplicates}")
            
            return final_articles
            
        except Exception as e:
            logger.error(f"Failed to retrieve articles: {e}", exc_info=True)
            return []
    
    async def _analyze_and_correct_articles(self, articles: List[Article]) -> List[Dict[str, Any]]:
        """Analyze and correct all articles, skipping already processed ones."""
        logger.info(f"Step 3: Analyzing and correcting {len(articles)} articles...")
        
        # Check for already processed articles from state
        state = self.state_manager.get_state()
        processed_titles = set()
        if state and state.article_states:
            for state_dict in state.article_states:
                status = state_dict.get('status')
                if status in [
                    ArticleProcessingStatus.QUEUED.value,
                    ArticleProcessingStatus.PUBLISHED.value,
                    ArticleProcessingStatus.REJECTED.value
                ]:
                    processed_titles.add(state_dict.get('title'))
        
        if processed_titles:
            logger.info(f"Skipping {len(processed_titles)} already processed articles: {', '.join(list(processed_titles)[:5])}{'...' if len(processed_titles) > 5 else ''}")
        
        corrected_articles = []
        stats = {
            'total': len(articles),
            'analyzed': 0,
            'errors': 0,
            'ignored': 0,
            'skipped': len(processed_titles)
        }
        
        for i, article in enumerate(articles, 1):
            # Skip already processed articles
            if article.title in processed_titles:
                logger.info(f"Skipping already processed article: {article.title}")
                # Restore already processed article from state if available
                article_state = self.state_manager.get_article_state(article.title)
                if article_state and article_state.status == ArticleProcessingStatus.QUEUED.value:
                    # Re-queue already corrected articles
                    corrected_articles.append({
                        'title': article.title,
                        'corrected_content': '',  # Will be refetched if needed
                        'summary': article_state.summary or '',
                        'changes_count': article_state.changes_count or 0,
                        'mode': state.mode if state else 'regex',
                        'page_id': article_state.page_id or article.page_id,
                        'revision_id': article_state.revision_id or article.revision_id
                    })
                    stats['analyzed'] += 1
                continue
            
            logger.info(f"Processing article {i}/{len(articles)}: {article.title}")
            
            # Track article state
            article_state = ArticleState(
                title=article.title,
                page_id=article.page_id,
                revision_id=article.revision_id,
                status=ArticleProcessingStatus.ANALYZING.value,
                started_at=datetime.now().isoformat()
            )
            self.state_manager.add_article_state(article_state)
            
            try:
                if self.lia_mode:
                    result = await self._analyze_with_lia(article)
                    # Add delay between LIA analyses to avoid API rate limiting
                    if i < len(articles):  # Don't delay after the last article
                        self.api_throttler.wait_if_needed()
                        logger.info("Throttling before next article analysis...")
                else:
                    result = await self._analyze_with_analyzers(article)
                    # Add delay between regex analyses to avoid API rate limiting
                    if i < len(articles):  # Don't delay after the last article
                        self.api_throttler.wait_if_needed()
                        logger.info("Throttling before next article analysis...")
                
                if result:
                    corrected_articles.append(result)
                    stats['analyzed'] += 1
                    article_state.status = ArticleProcessingStatus.QUEUED.value
                    article_state.completed_at = datetime.now().isoformat()
                    article_state.changes_count = result.get('changes_count')
                    article_state.summary = result.get('summary')
                else:
                    stats['ignored'] += 1
                    article_state.status = ArticleProcessingStatus.REJECTED.value
                    article_state.completed_at = datetime.now().isoformat()
                
                self.state_manager.add_article_state(article_state)
                    
            except Exception as e:
                logger.error(f"Error processing {article.title}: {e}", exc_info=True)
                stats['errors'] += 1
                self.stats['errors'].append(f"{article.title}: {str(e)}")
                article_state.status = ArticleProcessingStatus.ERROR.value
                article_state.error_message = str(e)
                article_state.completed_at = datetime.now().isoformat()
                self.state_manager.add_article_state(article_state)
            
            # Update progress in state
            self.state_manager.update_progress(
                current_index=i,
                articles_processed=stats['analyzed'] + stats['ignored'] + stats['errors'] + stats['skipped'],
                articles_published=self.stats['articles_published'],
                articles_error=stats['errors']
            )
        
        logger.info(f"Analysis complete: {stats['analyzed']} analyzed, {stats['errors']} errors, {stats['ignored']} ignored")
        
        # Update statistics
        self.stats['articles_analyzed'] = stats['analyzed']
        self.stats['articles_error'] = stats['errors']
        self.stats['articles_ignored'] = stats['ignored']
        
        # Update statistics in state
        if self.scheduler:
            state = self.scheduler.state_manager.get_state()
            state.statistics['total_analyzed'] += stats['analyzed']
            state.statistics['total_errors'] += stats['errors']
            state.statistics['total_ignored'] += stats['ignored']
            self.scheduler.state_manager.update_state(statistics=state.statistics)
        
        return corrected_articles
    
    async def _analyze_with_lia(self, article: Article) -> Optional[Dict[str, Any]]:
        """Analyze article using LIA/Ollama."""
        import pywikibot
        try:
            # Get page content
            page = pywikibot.Page(self.site, article.title)
            if not page.exists():
                logger.warning(f"Article {article.title} does not exist")
                return None
            
            content = page.get()
            
            # Apply case normalization if enabled (BEFORE LIA analysis)
            # Read from config.yaml (same source as UI settings)
            enable_case_normalization, enable_ner, normalize_with_ai = self._get_case_normalization_setting()
            logger.info(f"Case normalization setting for {article.title} (LIA mode): enable={enable_case_normalization}, ner={enable_ner}, ai={normalize_with_ai}")
            
            case_normalization_changes = 0
            if enable_case_normalization:
                from wikipedia_maintenance.utils.case_normalizer import CaseNormalizer
                # normalize_with_ai only takes effect if enable_case_normalization is true
                if not enable_case_normalization:
                    normalize_with_ai = False
                normalizer = CaseNormalizer(
                    enabled=enable_case_normalization,
                    enable_ner_title_normalization=enable_ner,
                    normalize_with_ai=normalize_with_ai
                )
                normalization_result = normalizer.normalize_text(content)
                
                if normalization_result.total_changes > 0:
                    logger.info(f"Case normalization applied to {article.title} (LIA mode): {normalization_result.total_changes} changes, {normalization_result.total_ignored} ignored")
                    content = normalization_result.normalized_text
                    case_normalization_changes = normalization_result.total_changes
                    
                    # Log normalization details for debugging
                    for report in normalization_result.reports:
                        logger.debug(f"Template '{report.template_name}': {len(report.parameter_changes)} changes, {len(report.ignored_occurrences)} ignored")
                        for param, (before, after) in report.parameter_changes.items():
                            logger.debug(f"  {param}: '{before}' -> '{after}'")
                        for param, reason in report.ignored_occurrences:
                            logger.debug(f"  {param}: ignored ({reason})")
                else:
                    logger.info(f"Case normalization: no changes needed for {article.title} (LIA mode)")
            else:
                logger.info(f"Case normalization disabled in config.yaml for {article.title} (LIA mode)")
            
            # Check length limit
            from wikipedia_maintenance.utils.verif_longueur import verifier
            ok, nb_caracteres = verifier(content, self.lia_limit)
            if not ok:
                logger.warning(f"Article {article.title} too long ({nb_caracteres} characters), skipping")
                return None
            
            # Correct with LIA with retry logic
            def correct_with_lia():
                return self.lia_client.corriger_article(content)
            
            succes, article_corrige, erreur = self.gemini_retry_handler.execute_with_retry(
                correct_with_lia,
                operation_name=f"LIA correction for {article.title}"
            )
            if not succes:
                logger.error(f"LIA correction failed for {article.title}: {erreur}")
                return None
            
            # Calculate link statistics BEFORE generating summary
            dead_links_count = 0
            corrected_links_count = 0
            http_links_count = 0
            if all_issues:
                dead_links_count = len([issue for issue in all_issues if issue.get('type') == 'dead_link'])
                corrected_links_count = len([issue for issue in all_issues if issue.get('corrected')])
                http_links_count = len([issue for issue in all_issues if issue.get('type') == 'http_link'])
            logger.info(f"LIA link statistics: {dead_links_count} dead links, {corrected_links_count} corrected, {http_links_count} HTTP links")

            # Generate summary using Publisher's configured comments only (enforce Publisher comments)
            # For LIA mode, use the publisher's method to ensure consistent comments
            # Determine correction type based on what was actually changed
            correction_types = []
            if case_normalization_changes > 0:
                correction_types.extend(['case_normalization'] * case_normalization_changes)
            # Only add dead_link and http_link if they were actually corrected
            if corrected_links_count > 0:
                correction_types.extend(['dead_link'] * corrected_links_count)
            if http_links_count > 0:
                correction_types.extend(['http_link'] * http_links_count)
            # Always add lia_correction if LIA was used
            correction_types.append('lia_correction')
            summary = self.publisher.generate_edit_summary(len(correction_types), correction_types)

            # Estimate changes count for LIA (simplified)
            changes_count = len(article_corrige) - len(content) if article_corrige else 0

            # Record analysis in tracker
            if self.analyzed_tracker:
                self.analyzed_tracker.record_analysis(
                    title=article.title,
                    page_id=article.page_id,
                    revision_id=article.revision_id,
                    status=AnalysisStatus.PENDING,  # Will be updated after publication
                    mode='IA',
                    changes_count=max(0, changes_count),
                    summary=summary,
                    corrected_content=article_corrige,
                    character_count=len(content) if content else 0,
                    total_links=len(all_issues) if all_issues else 0,
                    dead_links_count=dead_links_count,
                    corrected_links_count=corrected_links_count
                )

            # Record analysis in database for history display
            if self.database:
                try:
                    import uuid
                    from datetime import datetime
                    result_id = str(uuid.uuid4())
                    job_id = f"automation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                    self.database.create_analysis_result(
                        result_id=result_id,
                        job_id=job_id,
                        article_title=article.title,
                        page_id=article.page_id,
                        revision_id=article.revision_id,
                        status='analyzed',
                        mode='IA',
                        changes_count=max(0, changes_count),
                        summary=summary,
                        original_content=content,
                        corrected_content=article_corrige,
                        character_count=len(content) if content else 0,
                        total_links=len(all_issues) if all_issues else 0,
                        dead_links_count=dead_links_count,
                        corrected_links_count=corrected_links_count,
                        human_verified=False,
                        manual_review_urls=None,
                        issues_json=None,
                        analysis_date=datetime.now().isoformat()
                    )
                    logger.info(f"Analysis result saved to database for {article.title}")
                except Exception as e:
                    logger.error(f"Failed to save analysis result to database for {article.title}: {e}")
            
            return {
                'title': article.title,
                'corrected_content': article_corrige,
                'summary': summary,
                'original_content': content,
                'changes_count': max(0, changes_count),  # Ensure non-negative
                'mode': 'IA',  # Mark as AI-corrected
                'page_id': article.page_id,
                'revision_id': article.revision_id
            }
            
        except Exception as e:
            logger.error(f"LIA analysis error for {article.title}: {e}", exc_info=True)
            return None
    
    async def _analyze_with_analyzers(self, article: Article) -> Optional[Dict[str, Any]]:
        """Analyze article using regex analyzers."""
        import pywikibot
        try:
            # Get page content
            page = pywikibot.Page(self.site, article.title)
            if not page.exists():
                logger.warning(f"Article {article.title} does not exist")
                return None
            
            content = page.get()
            
            # Apply case normalization if enabled (BEFORE dead link analysis)
            # Read from config.yaml (same source as UI settings)
            enable_case_normalization, enable_ner, normalize_with_ai = self._get_case_normalization_setting()
            logger.info(f"Case normalization setting for {article.title} (regex mode): enable={enable_case_normalization}, ner={enable_ner}, ai={normalize_with_ai}")
            
            case_normalization_changes = 0
            if enable_case_normalization:
                from wikipedia_maintenance.utils.case_normalizer import CaseNormalizer
                # normalize_with_ai only takes effect if enable_case_normalization is true
                if not enable_case_normalization:
                    normalize_with_ai = False
                normalizer = CaseNormalizer(
                    enabled=enable_case_normalization,
                    enable_ner_title_normalization=enable_ner,
                    normalize_with_ai=normalize_with_ai
                )
                normalization_result = normalizer.normalize_text(content)
                
                if normalization_result.total_changes > 0:
                    logger.info(f"Case normalization applied to {article.title}: {normalization_result.total_changes} changes, {normalization_result.total_ignored} ignored")
                    content = normalization_result.normalized_text
                    case_normalization_changes = normalization_result.total_changes
                    
                    # Log normalization details for debugging
                    for report in normalization_result.reports:
                        logger.debug(f"Template '{report.template_name}': {len(report.parameter_changes)} changes, {len(report.ignored_occurrences)} ignored")
                        for param, (before, after) in report.parameter_changes.items():
                            logger.debug(f"  {param}: '{before}' -> '{after}'")
                        for param, reason in report.ignored_occurrences:
                            logger.debug(f"  {param}: ignored ({reason})")
                else:
                    logger.info(f"Case normalization: no changes needed for {article.title}")
            else:
                logger.info(f"Case normalization disabled in config.yaml for {article.title} (regex mode)")
            
            # Use cached analyzers to avoid repeated initialization
            analyzers = self._get_cached_analyzers()
            
            if not analyzers:
                logger.warning(f"No analyzers enabled, skipping analysis of {article.title}")
                return None
            
            # Run enabled analyzers
            all_issues = []
            analyzer_failed = False
            failed_analyzer_name = None
            
            for analyzer in analyzers:
                try:
                    logger.info(f"Running {analyzer.__class__.__name__} on {article.title} with content length: {len(content)}")
                    issues = analyzer.analyze(content)
                    logger.info(f"{analyzer.__class__.__name__} found {len(issues)} issues in {article.title}")
                    all_issues.extend(issues)
                    
                    # Check if analyzer has repaired content and update content accordingly
                    if hasattr(analyzer, 'repaired_content') and analyzer.repaired_content:
                        content = analyzer.repaired_content
                        logger.info(f"Updated content with repairs from {analyzer.__class__.__name__}")
                except Exception as e:
                    logger.error(f"{analyzer.__class__.__name__} failed: {e}", exc_info=True)
                    analyzer_failed = True
                    failed_analyzer_name = analyzer.__class__.__name__
                    break  # Stop processing if analyzer fails
            
            # If an analyzer failed, return None to indicate analysis failure
            if analyzer_failed:
                logger.error(f"Analysis failed for {article.title}: {failed_analyzer_name} raised exception")
                return None
            
            logger.info(f"Total issues found in {article.title}: {len(all_issues)}")
            
            # Extract link statistics from issues
            dead_links_count = len([i for i in all_issues if i.issue_type == 'dead_link'])
            corrected_links_count = len([i for i in all_issues if i.suggested_text is not None and i.extra.get('repair_status') in ['REPAIR_APPLIED', 'SAFE_REPLACEMENT']])
            logger.info(f"Link statistics: {dead_links_count} dead links, {corrected_links_count} corrected")
            
            if not all_issues:
                # No issues found, record as analyzed with no changes to avoid re-analysis
                if self.analyzed_tracker:
                    self.analyzed_tracker.record_analysis(
                        title=article.title,
                        page_id=article.page_id,
                        revision_id=article.revision_id,
                        status=AnalysisStatus.IGNORED,  # Mark as ignored since no issues
                        mode='regex',
                        changes_count=0,
                        summary="No issues found",
                        corrected_content=content,
                        character_count=len(content) if content else 0
                    )
                logger.info(f"No issues found in {article.title}, marked as analyzed")
                return None
            
            # Apply corrections using the same robust method as frontend
            corrector = Corrector(content)
            corrected_content = corrector.apply_corrections(all_issues)

            # Calculate link statistics for summary
            dead_links_count = len([issue for issue in all_issues if issue.issue_type == 'dead_link'])
            http_links_count = len([issue for issue in all_issues if issue.issue_type == 'http_link'])
            corrected_links_count = len([issue for issue in all_issues if issue.suggested_text is not None and issue.issue_type == 'dead_link'])
            logger.info(f"Regex mode statistics: {dead_links_count} dead links, {corrected_links_count} corrected, {http_links_count} HTTP links")

            # Generate summary - only count issues with suggested corrections (actually applied)
            correction_types = [issue.issue_type for issue in all_issues if issue.suggested_text is not None]
            # Add case_normalization to correction_types if it was applied
            if case_normalization_changes > 0:
                correction_types.extend(['case_normalization'] * case_normalization_changes)
            from collections import Counter
            type_counts = Counter(correction_types)
            logger.info(f"Résumé: {dict(type_counts)}, total={len(correction_types)}")
            summary = self.publisher.generate_edit_summary(len(correction_types), correction_types)
            
            # Record analysis in tracker
            if self.analyzed_tracker:
                self.analyzed_tracker.record_analysis(
                    title=article.title,
                    page_id=article.page_id,
                    revision_id=article.revision_id,
                    status=AnalysisStatus.PENDING,  # Will be updated after publication
                    mode='regex',
                    changes_count=len(correction_types),  # Only count issues with suggested corrections (same as manual)
                    summary=summary,
                    corrected_content=corrected_content,
                    character_count=len(content) if content else 0,
                    total_links=len(all_issues) if all_issues else 0,
                    dead_links_count=dead_links_count,
                    corrected_links_count=corrected_links_count
                )

            # Record analysis in database for history display
            if self.database:
                try:
                    import uuid
                    from datetime import datetime
                    result_id = str(uuid.uuid4())
                    job_id = f"automation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                    self.database.create_analysis_result(
                        result_id=result_id,
                        job_id=job_id,
                        article_title=article.title,
                        page_id=article.page_id,
                        revision_id=article.revision_id,
                        status='analyzed',
                        mode='regex',
                        changes_count=len(correction_types),
                        summary=summary,
                        original_content=content,
                        corrected_content=corrected_content,
                        character_count=len(content) if content else 0,
                        total_links=len(all_issues),  # Total issues found
                        dead_links_count=dead_links_count,
                        corrected_links_count=corrected_links_count,
                        human_verified=False,
                        manual_review_urls=None,
                        issues_json=None,
                        analysis_date=datetime.now().isoformat()
                    )
                    logger.info(f"Analysis result saved to database for {article.title}")
                except Exception as e:
                    logger.error(f"Failed to save analysis result to database for {article.title}: {e}")
            
            return {
                'title': article.title,
                'corrected_content': corrected_content,
                'summary': summary,
                'original_content': content,
                'changes_count': len(correction_types),  # Only count issues with suggested corrections (same as manual)
                'mode': 'regex',  # Mark as regex-corrected
                'page_id': article.page_id,
                'revision_id': article.revision_id
            }
            
        except Exception as e:
            logger.error(f"Analyzer error for {article.title}: {e}", exc_info=True)
            return None
    
    async def _feed_queue(self, corrected_articles: List[Dict[str, Any]]) -> None:
        """Feed the publication queue with corrected articles, preventing duplicates."""
        logger.info(f"Step 5: Feeding queue with {len(corrected_articles)} articles...")
        
        # Small delay to ensure scheduler is fully initialized
        await asyncio.sleep(0.5)
        
        if not self.scheduler:
            logger.error("Scheduler not initialized, cannot feed queue")
            return
        
        # Track titles to prevent duplicates
        seen_titles = set()
        duplicates_prevented = 0
        
        for article_data in corrected_articles:
            title = article_data['title']
            
            # Check for duplicates
            if title in seen_titles:
                logger.warning(f"Skipping duplicate article: {title}")
                duplicates_prevented += 1
                continue
            
            # Check if already published
            if self.published_tracker and self.published_tracker.is_recently_published(title):
                logger.info(f"Skipping already published article: {title}")
                duplicates_prevented += 1
                continue
            
            # Check if already in queue (by checking scheduler state)
            state = self.scheduler.state_manager.get_state()
            if any(qa.get('title') == title for qa in state.queue):
                logger.info(f"Skipping article already in queue: {title}")
                duplicates_prevented += 1
                continue
            
            # Check if article has any changes (skip if no changes)
            changes_count = article_data.get('changes_count', 0)
            if changes_count == 0:
                logger.info(f"Skipping article with no changes: {title}")
                self.stats['articles_ignored'] += 1
                continue
            
            seen_titles.add(title)
            self.scheduler.add_article_to_queue(
                title=article_data['title'],
                corrected_content=article_data['corrected_content'],
                summary=article_data['summary'],
                changes_count=article_data.get('changes_count', 0),
                mode=article_data.get('mode', 'regex'),
                page_id=article_data.get('page_id', 0),
                revision_id=article_data.get('revision_id', 0)
            )
        
        logger.info(f"Queue fed successfully (duplicates prevented: {duplicates_prevented})")
    
    async def _initialize_scheduler(self) -> None:
        """Initialize the scheduler object without starting it."""
        logger.info("Step 3: Initializing scheduler object...")
        
        try:
            # Check if scheduler is already running - if so, reuse it
            import os
            state_file = "data/scheduler_state.json"
            scheduler_already_running = False
            
            if os.path.exists(state_file):
                try:
                    import json
                    with open(state_file, 'r') as f:
                        state_data = json.load(f)
                        if state_data.get('is_active', False):
                            scheduler_already_running = True
                            logger.info("Scheduler is already running, will reuse existing instance")
                except:
                    pass
            
            if scheduler_already_running:
                # Try to get existing scheduler from global state if available
                # For now, we'll just create a new one but won't delete the state file
                logger.info("Not deleting state file - scheduler may be running")
            else:
                # Only delete state file if scheduler is not running
                if os.path.exists(state_file):
                    os.remove(state_file)
                    logger.info(f"Deleted existing state file: {state_file}")
            
            config = SchedulerConfig(
                state_file="data/scheduler_state.json",
                telegram_bot_token=self.telegram_bot_token,
                telegram_admin_ids=self.telegram_admin_ids,
                dry_run=self.dry_run,
                daily_limit=None,  # P0 FIX: Load from config via TimingManager, not hardcoded
                site=self.site,  # Pass the site object
                category=self.category_name,  # Store category for manual runs
                articles_to_process=self.max_articles  # Store max articles for manual runs
            )
            
            self.scheduler = Scheduler(config, self.publisher, self.published_tracker, self.analyzed_tracker, self.kill_switch_manager, self.database)
            logger.info(f"Scheduler object created: {self.scheduler is not None}")
            logger.info("Scheduler initialized successfully (not started yet)")
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}", exc_info=True)
            raise
    
    async def _start_scheduler(self) -> None:
        """Start the already-initialized scheduler."""
        logger.info("Step 6: Starting scheduler...")
        
        try:
            # Start scheduler directly (await to ensure it starts)
            logger.info("Calling scheduler.start()...")
            await self.scheduler.start()
            logger.info("Scheduler started successfully")
            
            # Verify scheduler is actually running
            import asyncio
            await asyncio.sleep(0.5)  # Small delay to let state persist
            state = self.scheduler.state_manager.get_state()
            logger.info(f"Scheduler verification: is_running={self.scheduler.is_running()}, is_active={state.is_active}")
            
            # Also verify state file directly
            import json
            from pathlib import Path
            state_file = Path("data/scheduler_state.json")
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    file_state = json.load(f)
                    logger.info(f"State file verification: is_active={file_state.get('is_active')}")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}", exc_info=True)
            raise
    
    async def _generate_and_save_report(self) -> None:
        """Generate and save automation report."""
        logger.info("Step 7: Generating automation report...")
        
        try:
            end_time = datetime.now()
            
            # Get published count from scheduler if available
            published_count = 0
            if self.scheduler:
                state = self.scheduler.state_manager.get_state()
                published_count = state.daily_published_count
                self.stats['articles_published'] = published_count
            
            # Get interruption statistics from state manager
            interruption_summary = self.state_manager.get_interruption_summary()
            
            # Check if session was resumed
            state = self.state_manager.get_state()
            was_resumed = state and state.started_at != self.start_time.isoformat() if state else False
            
            # Create report
            report = self.report_generator.create_report(
                start_time=self.start_time,
                end_time=end_time,
                articles_retrieved=self.stats['articles_retrieved'],
                articles_excluded_published=self.stats['articles_excluded_published'],
                articles_excluded_analyzed=self.stats['articles_excluded_analyzed'],
                articles_excluded_length=self.stats['articles_excluded_length'],
                articles_excluded_duplicates=self.stats['articles_excluded_duplicates'],
                articles_analyzed=self.stats['articles_analyzed'],
                articles_published=self.stats['articles_published'],
                articles_rejected=self.stats['articles_rejected'],
                articles_ignored=self.stats['articles_ignored'],
                articles_error=self.stats['articles_error'],
                mode='IA' if self.lia_mode else 'regex',
                max_articles_requested=self.max_articles,
                character_limit=self.lia_limit if self.lia_mode else 0,
                errors=self.stats['errors'],
                total_interruptions=interruption_summary['total_interruptions'],
                total_interruption_duration_seconds=interruption_summary['total_duration_seconds'],
                resolved_interruptions=interruption_summary['resolved_count'],
                unresolved_interruptions=interruption_summary['unresolved_count'],
                was_resumed=was_resumed
            )
            
            # Save report
            self.report_generator.save_report(report)
            
            logger.info(f"Report generated: {report.report_id}")
            logger.info(f"Duration: {report.duration_seconds:.1f}s")
            logger.info(f"Articles: retrieved={report.articles_retrieved}, analyzed={report.articles_analyzed}, published={report.articles_published}")
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}", exc_info=True)
    
    async def shutdown(self) -> None:
        """Shutdown the orchestrator gracefully."""
        logger.info("Shutting down orchestrator...")
        
        if self.scheduler:
            await self.scheduler.stop()
        
        logger.info("Orchestrator shutdown complete")
    
    async def run_forever(self) -> None:
        """Run the orchestrator indefinitely."""
        if await self.startup():
            logger.info("Orchestrator running, press Ctrl+C to stop")
            try:
                # Keep running until interrupted
                while self.scheduler and self.scheduler.is_running():
                    await asyncio.sleep(60)
            except asyncio.CancelledError:
                logger.info("Orchestrator cancelled")
            finally:
                await self.shutdown()
