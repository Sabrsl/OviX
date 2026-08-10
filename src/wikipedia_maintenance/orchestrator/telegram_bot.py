"""
Telegram bot integration for Wikipedia maintenance scheduler.

Provides remote administration via Telegram commands:
- STOP: Stop the scheduler
- START: Start the scheduler
- STATUS: Get current status
- STATS: Get statistics
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from telegram import Update, Bot
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Telegram integration disabled.")


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str
    admin_ids: List[int]


class TelegramBot:
    """
    Telegram bot for remote scheduler administration.
    """
    
    def __init__(self, config: TelegramConfig, state_manager, timing_manager):
        """
        Initialize Telegram bot.
        
        Args:
            config: TelegramConfig with bot token and admin IDs.
            state_manager: StateManager instance for accessing scheduler state.
            timing_manager: TimingManager instance for timing information.
        """
        if not TELEGRAM_AVAILABLE:
            logger.error("Cannot initialize Telegram bot: python-telegram-bot not installed")
            return
        
        self.config = config
        self.state_manager = state_manager
        self.timing_manager = timing_manager
        self.application: Optional[Application] = None
        self._running = False
        
        logger.info(f"Telegram bot initialized for admins: {config.admin_ids}")
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is an admin."""
        return user_id in self.config.admin_ids
    
    async def _handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle STOP command."""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Accès refusé. Vous n'êtes pas administrateur.")
            return
        
        state = self.state_manager.get_state()
        if not state.is_active:
            await update.message.reply_text("⚠️ Le scheduler est déjà arrêté.")
            return
        
        self.state_manager.set_active(False)
        await update.message.reply_text(
            "✅ Scheduler arrêté.\n"
            "• Arrêt immédiat du scheduler\n"
            "• Opération en cours terminée proprement\n"
            "• Aucune nouvelle publication\n"
            "• État sauvegardé"
        )
        logger.info(f"STOP command received from admin {update.effective_user.id}")
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle START command."""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Accès refusé. Vous n'êtes pas administrateur.")
            return
        
        state = self.state_manager.get_state()
        if state.is_active:
            await update.message.reply_text("⚠️ Le scheduler est déjà actif.")
            return
        
        self.state_manager.set_active(True)
        await update.message.reply_text(
            "✅ Scheduler démarré.\n"
            "• Reprise de la file d'attente\n"
            "• Publication progressive reprise\n"
            "• État sauvegardé"
        )
        logger.info(f"START command received from admin {update.effective_user.id}")
    
    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle STATUS command."""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Accès refusé. Vous n'êtes pas administrateur.")
            return
        
        state = self.state_manager.get_state()
        current_time = datetime.now()
        
        # Build status message
        status_emoji = "🟢" if state.is_active else "🔴"
        status_text = "ACTIF" if state.is_active else "ARRÊTÉ"
        
        message = (
            f"📊 *STATUT DU SCHEDULER*\n\n"
            f"{status_emoji} État: {status_text}\n"
            f"📝 File d'attente: {len(state.queue)} articles\n"
            f"📈 Publiés aujourd'hui: {state.daily_published_count}/100\n"
            f"📦 Total analysés: {state.statistics['total_analyzed']}\n"
            f"✅ Total publiés: {state.statistics['total_published']}\n"
            f"❌ Total erreurs: {state.statistics['total_errors']}\n"
            f"⏭️ Total ignorés: {state.statistics['total_ignored']}\n"
        )
        
        # Next publication time
        if state.next_publish_time:
            next_pub = datetime.fromisoformat(state.next_publish_time)
            if next_pub > current_time:
                time_until = next_pub - current_time
                message += f"\n⏰ Prochaine publication: dans {self._format_timedelta(time_until)}"
        
        # Next pause
        if state.next_pause_start:
            next_pause = datetime.fromisoformat(state.next_pause_start)
            if next_pause > current_time:
                time_until = next_pause - current_time
                message += f"\n⏸️ Prochaine pause: dans {self._format_timedelta(time_until)}"
        
        # Working hours
        is_working = self.timing_manager.is_within_working_hours(current_time)
        working_status = "🟢 Ouvert" if is_working else "🔴 Fermé"
        message += f"\n🕐 Fenêtre de fonctionnement: {working_status}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"STATUS command received from admin {update.effective_user.id}")
    
    async def _handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle STATS command."""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Accès refusé. Vous n'êtes pas administrateur.")
            return
        
        state = self.state_manager.get_state()
        stats = state.statistics
        
        message = (
            f"📈 *STATISTIQUES GLOBALES*\n\n"
            f"✅ Total publié: {stats['total_published']}\n"
            f"📦 Total analysé: {stats['total_analyzed']}\n"
            f"⏭️ Total ignoré: {stats['total_ignored']}\n"
            f"❌ Total erreurs: {stats['total_errors']}\n"
        )
        
        # Average times
        if stats['avg_publish_delay'] > 0:
            message += f"\n⏱️ Temps moyen entre publications: {stats['avg_publish_delay']:.1f} min"
        if stats['avg_processing_time'] > 0:
            message += f"\n⚙️ Temps moyen de traitement: {stats['avg_processing_time']:.1f} s"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"STATS command received from admin {update.effective_user.id}")
    
    def _format_timedelta(self, td) -> str:
        """Format timedelta as human-readable string."""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}min {seconds}s"
        elif minutes > 0:
            return f"{minutes}min {seconds}s"
        else:
            return f"{seconds}s"
    
    async def start(self) -> None:
        """Start the Telegram bot."""
        if not TELEGRAM_AVAILABLE:
            logger.error("Cannot start Telegram bot: python-telegram-bot not installed")
            return
        
        if self._running:
            logger.warning("Telegram bot already running")
            return
        
        try:
            self.application = Application.builder().token(self.config.bot_token).build()
            
            # Register command handlers
            self.application.add_handler(CommandHandler("STOP", self._handle_stop))
            self.application.add_handler(CommandHandler("START", self._handle_start))
            self.application.add_handler(CommandHandler("STATUS", self._handle_status))
            self.application.add_handler(CommandHandler("STATS", self._handle_stats))
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            self._running = True
            logger.info("Telegram bot started successfully")
        except Exception as e:
            logger.error(f"Error starting Telegram bot: {e}")
    
    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if not self._running:
            return
        
        try:
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            self._running = False
            logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")
    
    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._running


def create_telegram_bot(bot_token: str, admin_ids: List[int], 
                       state_manager, timing_manager) -> Optional[TelegramBot]:
    """
    Factory function to create Telegram bot.
    
    Args:
        bot_token: Telegram bot token.
        admin_ids: List of admin user IDs.
        state_manager: StateManager instance.
        timing_manager: TimingManager instance.
        
    Returns:
        TelegramBot instance or None if Telegram not available.
    """
    if not TELEGRAM_AVAILABLE:
        logger.warning("Cannot create Telegram bot: python-telegram-bot not installed")
        return None
    
    config = TelegramConfig(bot_token=bot_token, admin_ids=admin_ids)
    return TelegramBot(config, state_manager, timing_manager)
