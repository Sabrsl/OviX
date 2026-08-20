"""
Sidebar UI module for Wikipedia Maintenance Tool.
Handles Wikipedia connection, AI mode, automation, and settings.
"""

import streamlit as st
import os
import yaml
import logging
from pathlib import Path
from typing import Optional

from .theme import COLORS, SPACING
from .components import info_box, spacer

logger = logging.getLogger(__name__)


def render_sidebar(
    connect_to_wikipedia_func,
    gemini_client_class,
    scheduler_config_class,
    scheduler_class,
    automation_orchestrator_class,
    orchestrator_instance_ref,
    scheduler_instance_ref
):
    """
    Render the complete sidebar with all sections.

    Args:
        connect_to_wikipedia_func: Function to connect to Wikipedia.
        gemini_client_class: GeminiClient class for AI initialization.
        scheduler_config_class: SchedulerConfig class.
        scheduler_class: Scheduler class.
        automation_orchestrator_class: AutomationOrchestrator class.
        orchestrator_instance_ref: Reference to global orchestrator instance.
        scheduler_instance_ref: Reference to global scheduler instance.
    """
    with st.sidebar:
        st.title("📝 Wikipedia Maintenance Tool")

        # Global status strip — quick glance state of the whole tool
        _render_status_strip()

        st.divider()

        # Connection section
        _render_connection_section(connect_to_wikipedia_func)

        # Dry-run mode
        _render_dry_run_section()

        # AI mode section
        _render_ai_mode_section(gemini_client_class)

        # Automation section
        _render_automation_section(
            scheduler_config_class,
            scheduler_class,
            automation_orchestrator_class,
            orchestrator_instance_ref,
            scheduler_instance_ref,
            gemini_client_class
        )

        # Settings section
        _render_settings_section()

        # Secrets configuration section
        _render_secrets_section()

        # Logs section
        _render_logs_section()


def _render_status_strip():
    """Render a compact at-a-glance status row (connection / IA / automation)."""
    connected = bool(st.session_state.site)
    ia_on = bool(st.session_state.lia_mode)
    running = bool(st.session_state.automation_running)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Wiki", "✅" if connected else "⚪", label_visibility="visible")
    with c2:
        st.metric("IA", "🤖" if ia_on else "⚪", label_visibility="visible")
    with c3:
        st.metric("Auto", "🟢" if running else "⚪", label_visibility="visible")

    if st.session_state.dry_run:
        st.caption("🧪 Mode test actif — aucune publication réelle en cours.")


def _render_connection_section(connect_to_wikipedia_func):
    """Render Wikipedia connection section."""
    with st.expander("🔌 Connexion Wikipédia", expanded=not st.session_state.site):
        # Load saved connection parameters from config file
        config_file = Path(__file__).parent.parent / "config" / "config.yaml"
        saved_config = {}
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and 'wikipedia' in config:
                        saved_config = config['wikipedia']
            except:
                pass

        # Use saved connection parameters as defaults
        default_lang_index = 0
        default_family_index = 0
        if saved_config.get('lang'):
            try:
                default_lang_index = ["fr", "en", "de", "es"].index(saved_config['lang'])
            except ValueError:
                pass
        if saved_config.get('family'):
            try:
                default_family_index = ["wikipedia", "wiktionary", "wikibooks"].index(saved_config['family'])
            except ValueError:
                pass

        col1, col2 = st.columns(2)
        with col1:
            lang = st.selectbox("Langue", ["fr", "en", "de", "es"], index=default_lang_index)
        with col2:
            family = st.selectbox("Famille", ["wikipedia", "wiktionary", "wikibooks"], index=default_family_index)

        st.divider()

        # Wikipedia credentials input
        if 'wp_username' not in st.session_state:
            st.session_state.wp_username = ''
        if 'wp_password' not in st.session_state:
            st.session_state.wp_password = ''
        if 'wp_remember' not in st.session_state:
            st.session_state.wp_remember = False

        wp_username = st.text_input(
            "Nom d'utilisateur Wikipedia",
            value=st.session_state.wp_username,
            help="Votre nom d'utilisateur Wikipedia",
            key="wp_username_input"
        )

        wp_password = st.text_input(
            "Mot de passe",
            value=st.session_state.wp_password,
            type="password",
            help="Votre mot de passe Wikipedia",
            key="wp_password_input"
        )

        wp_remember = st.checkbox(
            "Rester connecté",
            value=st.session_state.wp_remember,
            help="Sauvegarder vos identifiants localement (dans votre navigateur)"
        )

        # Update session state
        st.session_state.wp_username = wp_username
        st.session_state.wp_password = wp_password
        st.session_state.wp_remember = wp_remember

        st.caption("ℹ️ Les identifiants sont stockés localement dans votre navigateur si 'Rester connecté' est coché.")

        if st.button("Se connecter", width='stretch', type="primary"):
            with st.spinner(f"Connexion à {lang}.{family}.org..."):
                if connect_to_wikipedia_func(lang, family):
                    # Save connection parameters to config file
                    try:
                        if config_file.exists():
                            with open(config_file, 'r', encoding='utf-8') as f:
                                config = yaml.safe_load(f)
                        else:
                            config = {}

                        if 'wikipedia' not in config:
                            config['wikipedia'] = {}
                        config['wikipedia']['lang'] = lang
                        config['wikipedia']['family'] = family

                        with open(config_file, 'w', encoding='utf-8') as f:
                            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
                    except Exception as e:
                        st.warning(f"Impossible de sauvegarder la configuration : {e}")

                    st.success(f"Connecté à {lang}.{family}.org")
                else:
                    st.error("Échec de la connexion. Vérifiez vos identifiants pywikibot.")

        # Auto-connect on startup if saved config exists and not connected
        if saved_config and not st.session_state.site:
            saved_lang = saved_config.get('lang')
            saved_family = saved_config.get('family')
            if saved_lang and saved_family:
                with st.spinner("Reconnexion automatique..."):
                    if connect_to_wikipedia_func(saved_lang, saved_family):
                        st.success(f"Reconnexion automatique à {saved_lang}.{saved_family}.org")

        if st.session_state.site:
            st.success(f"✅ Connecté : {lang}.{family}.org", icon="✅")
        else:
            st.caption("⚪ Non connecté")


def _render_dry_run_section():
    """Render dry-run mode section."""
    st.session_state.dry_run = st.toggle(
        "🧪 Mode test (dry-run)",
        value=st.session_state.dry_run,
        help="Aucune modification n'est réellement publiée sur Wikipédia tant que cette case est cochée."
    )
    if st.session_state.publisher:
        st.session_state.publisher.set_dry_run(st.session_state.dry_run)


def _render_ai_mode_section(gemini_client_class):
    """Render AI mode section."""
    st.divider()
    with st.expander("🤖 Mode IA", expanded=st.session_state.lia_mode):
        st.session_state.lia_mode = st.toggle(
            "Activer le mode IA",
            value=st.session_state.lia_mode,
            help="Utilise Google Gemini pour corriger les articles au lieu des analyseurs regex (configuration via variables d'environnement)"
        )

        # Character limit for AI analysis
        if "lia_limit_value" not in st.session_state:
            st.session_state.lia_limit_value = st.session_state.lia_limite_caracteres
        
        gemini_limit = st.number_input(
            "Limite de caractères pour l'analyse IA",
            min_value=1000,
            max_value=100000,
            value=st.session_state.lia_limit_value,
            step=1000,
            help="Nombre maximum de caractères autorisé pour l'analyse par IA. Les articles dépassant cette limite seront exclus.",
            key="lia_limit_input"
        )
        
        st.session_state.lia_limit_value = gemini_limit
        st.session_state.lia_limite_caracteres = gemini_limit

        # Initialize Gemini client when IA mode is enabled
        if st.session_state.lia_mode and not st.session_state.lia_client:
            # Prioritize UI-provided credentials over environment variables
            gemini_api_key = st.session_state.get('gemini_api_key') or os.environ.get('GEMINI_API_KEY')
            
            # Load from config.yaml if not in environment or session state
            config_file = Path(__file__).parent.parent / "config" / "config.yaml"
            gemini_project_id = st.session_state.get('gemini_project_id') or os.environ.get('GEMINI_PROJECT_ID')
            gemini_model = st.session_state.get('gemini_model') or os.environ.get('GEMINI_MODEL')
            gemini_limit = st.session_state.get('gemini_limit') or os.environ.get('GEMINI_LIMIT')

            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        if config and 'ai' in config and 'gemini' in config['ai']:
                            gemini_project_id = gemini_project_id or config['ai']['gemini'].get('project_id')
                            gemini_model = gemini_model or config['ai']['gemini'].get('model', 'gemini-flash-lite-latest')
                            gemini_limit = gemini_limit or str(config['ai']['gemini'].get('limit', 10800))
                except:
                    pass

            gemini_project_id = gemini_project_id or None
            gemini_model = gemini_model or 'gemini-flash-lite-latest'
            # Use UI-provided limit for initialization
            gemini_limit = st.session_state.lia_limit_value

            if gemini_api_key:
                try:
                    with st.spinner("Initialisation du client Gemini..."):
                        client = gemini_client_class(
                            api_key=gemini_api_key,
                            project_id=gemini_project_id,
                            model=gemini_model,
                            limite_caracteres=gemini_limit
                        )
                        ok, error = client.tester_connexion()
                    if ok:
                        st.session_state.lia_client = client
                        st.session_state.ai_provider = "gemini"
                        st.session_state.lia_limite_caracteres = gemini_limit
                        st.success("✅ Client Gemini initialisé automatiquement")
                    else:
                        st.error(f"❌ Erreur de connexion Gemini : {error}")
                        st.session_state.lia_mode = False
                except Exception as e:
                    st.error(f"❌ Erreur d'initialisation Gemini : {e}")
                    st.session_state.lia_mode = False
            else:
                st.error("❌ Variable d'environnement GEMINI_API_KEY non définie")
                st.session_state.lia_mode = False

        if st.session_state.lia_mode and st.session_state.lia_client:
            st.caption(f"Modèle actif : `{os.environ.get('GEMINI_MODEL', 'gemini-flash-lite-latest')}`")
            st.caption(f"Limite de caractères : {st.session_state.lia_limite_caracteres}")
            
            # Button to update client with new limit if changed
            if st.session_state.lia_limite_caracteres != st.session_state.lia_limit_value:
                if st.button("🔄 Appliquer nouvelle limite", key="apply_new_limit"):
                    try:
                        gemini_limit = st.session_state.lia_limit_value
                        
                        # Update the existing client's limit directly
                        st.session_state.lia_client.update_limite_caracteres(gemini_limit)
                        st.session_state.lia_limite_caracteres = gemini_limit
                        st.success(f"✅ Limite mise à jour : {gemini_limit} caractères")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur de mise à jour de la limite : {e}")


def _render_automation_section(
    scheduler_config_class,
    scheduler_class,
    automation_orchestrator_class,
    orchestrator_instance_ref,
    scheduler_instance_ref,
    gemini_client_class
):
    """Render automation section."""
    st.divider()
    st.subheader("🚀 Automatisation")

    # Display automation status - check if scheduler is actually running
    scheduler_running = False
    
    # Method 1: Check via scheduler object (if available in session)
    if st.session_state.automation_scheduler:
        try:
            scheduler_running = st.session_state.automation_scheduler.is_running()
        except:
            pass
    
    # Method 2: Check via state file (persistent across reruns)
    if not scheduler_running:
        try:
            import json
            from pathlib import Path
            state_file = Path("data/scheduler_state.json")
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state_data = json.load(f)
                    if state_data.get('is_active', False):
                        scheduler_running = True
        except:
            pass
    
    # Sync session state with actual scheduler state
    if scheduler_running:
        st.session_state.automation_running = True
        st.success("🟢 Automatisation en cours")
    else:
        st.session_state.automation_running = False
        st.info("⚪ Automatisation arrêtée")

    max_articles = st.session_state.get("automation_max_articles", 5)
    daily_limit = 100
    automation_lia_mode = False

    # Automation configuration
    if not st.session_state.automation_running:
        with st.expander("⚙️ Configuration de l'automatisation", expanded=True):
            # Number of articles to retrieve
            if "automation_max_articles" not in st.session_state:
                st.session_state.automation_max_articles = 5
            max_articles = st.number_input(
                "Nombre d'articles à récupérer",
                min_value=1,
                max_value=100,
                value=st.session_state.automation_max_articles,
                help="Nombre d'articles à récupérer depuis la catégorie",
                key="automation_max_articles_input"
            )
            st.session_state.automation_max_articles = max_articles

            # Daily publication limit
            daily_limit = st.number_input(
                "Limite de publication par jour",
                min_value=1,
                max_value=500,
                value=100,
                help="Nombre maximum d'articles à publier par jour"
            )

            # AI mode choice for automation
            automation_lia_mode = st.checkbox(
                "Utiliser l'analyse IA pour l'automatisation",
                value=False,
                help="Si activé, utilise Google Gemini pour corriger les articles au lieu des analyseurs regex"
            )

            # Character limit for AI analysis
            if "automation_lia_limit" not in st.session_state:
                st.session_state.automation_lia_limit = 10800
            automation_lia_limit = st.number_input(
                "Limite de caractères pour l'analyse IA",
                min_value=1000,
                max_value=100000,
                value=st.session_state.automation_lia_limit,
                step=1000,
                help="Nombre maximum de caractères autorisé pour l'analyse par IA. Les articles dépassant cette limite seront exclus.",
                key="automation_lia_limit_input"
            )
            st.session_state.automation_lia_limit = automation_lia_limit

            # Include already analyzed articles
            include_analyzed = st.checkbox(
                "Inclure les articles déjà analysés",
                value=False,
                help="Si coché, inclut également les articles qui ont déjà été analysés dans le nombre demandé"
            )

            # Initialize Gemini client for automation if needed
            if automation_lia_mode and not st.session_state.lia_client:
                # Prioritize UI-provided credentials over environment variables
                gemini_api_key = st.session_state.get('gemini_api_key') or os.environ.get('GEMINI_API_KEY')
                
                # Load from config.yaml if not in environment or session state
                config_file = Path(__file__).parent.parent / "config" / "config.yaml"
                gemini_project_id = st.session_state.get('gemini_project_id') or os.environ.get('GEMINI_PROJECT_ID')
                gemini_model = st.session_state.get('gemini_model') or os.environ.get('GEMINI_MODEL')
                gemini_limit = st.session_state.get('gemini_limit') or os.environ.get('GEMINI_LIMIT')
                
                # Prioritize UI Ollama settings
                ollama_url = st.session_state.get('ollama_url') or os.environ.get('OLLAMA_URL')
                ollama_model = st.session_state.get('ollama_model') or os.environ.get('OLLAMA_MODEL')
                ollama_fallback = st.session_state.get('ollama_fallback') or os.environ.get('OLLAMA_FALLBACK')
                
                if config_file.exists():
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = yaml.safe_load(f)
                            if config and 'ai' in config and 'gemini' in config['ai']:
                                gemini_project_id = gemini_project_id or config['ai']['gemini'].get('project_id')
                                gemini_model = gemini_model or config['ai']['gemini'].get('model', 'gemini-flash-lite-latest')
                                gemini_limit = gemini_limit or str(config['ai']['gemini'].get('limit', 10800))
                    except:
                        pass

                gemini_project_id = gemini_project_id or None
                gemini_model = gemini_model or 'gemini-flash-lite-latest'
                gemini_limit = int(gemini_limit or '10800')

                if gemini_api_key:
                    try:
                        with st.spinner("Initialisation du client Gemini..."):
                            client = gemini_client_class(
                                api_key=gemini_api_key,
                                project_id=gemini_project_id,
                                model=gemini_model,
                                limite_caracteres=automation_lia_limit  # Use UI-configured limit
                            )
                            ok, error = client.tester_connexion()
                        if ok:
                            st.session_state.lia_client = client
                            st.session_state.ai_provider = "gemini"
                            st.session_state.lia_limite_caracteres = automation_lia_limit  # Use UI-configured limit
                            st.success("✅ Client Gemini initialisé pour l'automatisation")
                        else:
                            st.error(f"❌ Erreur de connexion Gemini : {error}")
                            automation_lia_mode = False
                    except Exception as e:
                        st.error(f"❌ Erreur d'initialisation Gemini : {e}")
                        automation_lia_mode = False
                else:
                    st.error("❌ Variable d'environnement GEMINI_API_KEY non définie")
                    automation_lia_mode = False

    # Start / Stop buttons side by side
    col_start, col_stop = st.columns(2)
    with col_start:
        start_clicked = st.button(
            "▶️ Démarrer",
            disabled=st.session_state.automation_running,
            width='stretch',
            type="primary"
        )
    with col_stop:
        stop_clicked = st.button(
            "🛑 Arrêt d'urgence",
            disabled=not st.session_state.automation_running,
            width='stretch'
        )

    if start_clicked:
        if not st.session_state.site:
            st.error("Veuillez d'abord vous connecter à Wikipédia")
        elif not st.session_state.publisher:
            st.error("Publisher non initialisé")
        elif st.session_state.automation_running:
            st.warning("⚠️ Une automatisation est déjà en cours. Arrêtez-la d'abord avant d'en démarrer une nouvelle.")
        else:
            # Use the chosen mode for automation
            if automation_lia_mode:
                # Check if Gemini client is initialized
                if not st.session_state.lia_client:
                    st.error("Client IA non initialisé. Veuillez activer le mode IA dans les paramètres.")
                    return
                st.info("Mode IA activé pour l'automatisation")
            else:
                st.info("Mode regex activé pour l'automatisation")

            with st.spinner("Démarrage de l'automatisation..."):
                # Reuse existing orchestrator if it exists and is not running
                if orchestrator_instance_ref[0] is None:
                    # Create automation orchestrator with full workflow, reusing existing components
                    orchestrator_instance_ref[0] = automation_orchestrator_class(
                        lang=st.session_state.connected_lang,
                        family=st.session_state.connected_family,
                        category_name="Article à wikifier/Liste complète",
                        max_articles=max_articles,
                        dry_run=st.session_state.dry_run,
                        lia_mode=automation_lia_mode,
                        include_analyzed=include_analyzed,
                        ai_provider="gemini",
                        gemini_api_key=st.session_state.get('gemini_api_key') or os.environ.get('GEMINI_API_KEY'),
                        gemini_project_id=st.session_state.get('gemini_project_id') or os.environ.get('GEMINI_PROJECT_ID'),
                        gemini_model=st.session_state.get('gemini_model') or os.environ.get('GEMINI_MODEL', 'gemini-flash-lite-latest'),
                        lia_limit=automation_lia_limit,
                        telegram_bot_token=None,
                        telegram_admin_ids=[],
                        # Reuse existing components to avoid re-authentication
                        publisher=st.session_state.publisher,
                        published_tracker=st.session_state.get('published_tracker'),
                        analyzed_tracker=st.session_state.get('analyzed_tracker')
                    )

                # Start automation in background
                import asyncio
                import threading

                def run_automation():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(orchestrator_instance_ref[0].startup())
                        # Keep the event loop running so the scheduler continues
                        # The scheduler runs in a background task within this loop
                        try:
                            loop.run_forever()
                        except KeyboardInterrupt:
                            pass
                    finally:
                        # Update running status when automation completes
                        st.session_state.automation_running = False
                        loop.close()

                thread = threading.Thread(target=run_automation, daemon=True)
                thread.start()

                # Set running to True immediately when thread starts
                st.session_state.automation_running = True

                # Use the orchestrator's scheduler for monitoring
                import time
                time.sleep(3)  # Increased wait time to ensure scheduler is initialized

                if orchestrator_instance_ref[0] and hasattr(orchestrator_instance_ref[0], 'scheduler') and orchestrator_instance_ref[0].scheduler:
                    scheduler_instance_ref[0] = orchestrator_instance_ref[0].scheduler
                    st.session_state.automation_scheduler = scheduler_instance_ref[0]
                    logger.info(f"Scheduler attached from orchestrator: {scheduler_instance_ref[0]}")
                else:
                    # Fallback: create separate scheduler for monitoring
                    logger.warning("Orchestrator scheduler not available, creating separate scheduler for monitoring")
                    config = scheduler_config_class(
                        state_file="data/scheduler_state.json",
                        daily_limit=daily_limit,
                        dry_run=st.session_state.dry_run,
                        site=st.session_state.site
                    )
                    scheduler_instance_ref[0] = scheduler_class(config, st.session_state.publisher)
                    st.session_state.automation_scheduler = scheduler_instance_ref[0]
            st.success("✅ Automatisation démarrée : récupération → analyse → corrections → publication")
            st.rerun()

    if stop_clicked:
        if orchestrator_instance_ref[0]:
            with st.spinner("Arrêt en cours..."):
                import asyncio
                import threading

                def stop_automation():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(orchestrator_instance_ref[0].shutdown())
                    finally:
                        loop.close()

                thread = threading.Thread(target=stop_automation, daemon=True)
                thread.start()
                thread.join(timeout=5.0)  # Wait for shutdown to complete

                # Stop scheduler if running
                if scheduler_instance_ref[0]:
                    def stop_scheduler():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(scheduler_instance_ref[0].stop())
                        finally:
                            loop.close()

                    thread2 = threading.Thread(target=stop_scheduler, daemon=True)
                    thread2.start()
                    thread2.join(timeout=5.0)

                # Reset orchestrator instance to None to allow fresh start
                orchestrator_instance_ref[0] = None
                st.session_state.automation_running = False
                st.session_state.automation_scheduler = None
                scheduler_instance_ref[0] = None

            st.warning("⚠️ Arrêt d'urgence déclenché")
            st.rerun()

    # Display scheduler status if running
    if st.session_state.automation_running and st.session_state.automation_scheduler:
        # Check if scheduler is still actually running
        if not st.session_state.automation_scheduler.is_running():
            st.session_state.automation_running = False
            st.rerun()
        
        # Also check orchestrator state if available
        if orchestrator_instance_ref[0] and hasattr(orchestrator_instance_ref[0], 'state_manager'):
            from wikipedia_maintenance.utils.automation_state import SessionStatus
            state = orchestrator_instance_ref[0].state_manager.get_state()
            if state and state.status in [SessionStatus.COMPLETED.value, SessionStatus.FAILED.value, SessionStatus.INTERRUPTED.value]:
                st.session_state.automation_running = False
                st.rerun()
        
        status = st.session_state.automation_scheduler.get_status()
        st.divider()
        st.caption("📊 État de la file d'attente")
        m1, m2, m3 = st.columns(3)
        m1.metric("File", status['queue_size'])
        m2.metric(
            "Publié aujourd'hui",
            status['daily_published'],
            delta=f"/{status['daily_limit']}",
            delta_color="off"
        )
        m3.metric("Total publié", status['total_published'])
        
        # Auto-refresh every 5 seconds when automation is running
        import time
        if 'last_auto_refresh' not in st.session_state:
            st.session_state.last_auto_refresh = 0
        if time.time() - st.session_state.last_auto_refresh > 5:
            st.session_state.last_auto_refresh = time.time()
            st.rerun()

        progress_ratio = 0.0
        if status['daily_limit']:
            progress_ratio = min(status['daily_published'] / status['daily_limit'], 1.0)
        st.progress(progress_ratio, text=f"{status['daily_published']}/{status['daily_limit']} publications aujourd'hui")

        if status['is_within_working_hours']:
            st.caption("🕒 Dans les heures de travail")
        else:
            st.caption("🌙 Hors des heures de travail — en pause")


def _render_settings_section():
    """Render settings section."""
    st.divider()

    # Reset button at top of settings
    st.button("🔄 Rétablir les paramètres par défaut", key="reset_defaults_top", on_click=_reset_to_defaults)

    # Cache management section
    with st.expander("💾 Cache API Wikipédia", expanded=False):
        st.caption("Optimisation des appels à l'API Wikipédia")
        
        from wikipedia_maintenance.utils.api_cache import get_cache
        cache = get_cache()
        stats = cache.get_stats()
        
        # Display cache statistics
        c1, c2 = st.columns(2)
        c1.metric("Requêtes totales", stats['total_requests'])
        c2.metric("Taux de réussite", f"{stats['hit_rate_percent']}%")
        
        st.caption(f"⏱️ Temps économisé : {stats['time_saved_seconds']}s")
        st.caption(f"📉 Appels évités : {stats['api_calls_avoided']}")
        
        # Cache controls
        col_clear, col_reset = st.columns(2)
        with col_clear:
            if st.button("🗑️ Vider le cache", width='stretch'):
                cache.clear()
                st.toast("Cache vidé", icon="🗑️")
                st.rerun()
        with col_reset:
            if st.button("🔄 Réinitialiser stats", width='stretch'):
                cache.reset_stats()
                st.toast("Statistiques réinitialisées", icon="🔄")
                st.rerun()

    st.divider()

    # Rate limiting settings
    with st.expander("🚦 Rate Limiting", expanded=False):
        st.caption("Limitation du taux d'éditions Wikipedia")
        
        if 'max_edits_per_minute' not in st.session_state:
            st.session_state.max_edits_per_minute = 10
        if 'min_edit_delay' not in st.session_state:
            st.session_state.min_edit_delay = 1.0
        if 'scheduler_daily_limit' not in st.session_state:
            st.session_state.scheduler_daily_limit = 50
        
        max_edits = st.number_input(
            "Max éditions/minute",
            min_value=1,
            max_value=100,
            value=st.session_state.max_edits_per_minute,
            help="Nombre maximum d'éditions Wikipedia par minute",
            key="settings_max_edits"
        )
        
        min_delay = st.number_input(
            "Délai minimum entre éditions (secondes)",
            min_value=0.0,
            max_value=60.0,
            value=st.session_state.min_edit_delay,
            step=0.1,
            help="Délai minimum entre deux éditions",
            key="settings_min_delay"
        )
        
        daily_limit = st.number_input(
            "Limite journalière d'éditions",
            min_value=1,
            max_value=500,
            value=st.session_state.scheduler_daily_limit,
            help="Nombre maximum d'éditions par jour",
            key="settings_daily_limit"
        )
        
        if max_edits != st.session_state.max_edits_per_minute:
            st.session_state.max_edits_per_minute = max_edits
            _save_ui_config_to_yaml()
            st.success("✅ Limite d'éditions mise à jour")
    
    st.divider()
    
    # API throttling settings
    with st.expander("⏱️ API Throttling", expanded=False):
        st.caption("Paramètres de limitation des appels API")
        
        # Clear stale widget state to avoid type conflicts
        for k in ("settings_api_max_requests", "settings_api_max_requests_min", "settings_api_max_requests_max", 
                  "settings_api_min_delay_min", "settings_api_min_delay_max", "settings_pub_delay_min", "settings_pub_delay_max"):
            if k in st.session_state and not isinstance(st.session_state[k], float):
                del st.session_state[k]
        
        if 'api_max_requests_per_minute' not in st.session_state:
            st.session_state.api_max_requests_per_minute = 10.0
        else:
            st.session_state.api_max_requests_per_minute = float(st.session_state.api_max_requests_per_minute)
        if 'api_max_requests_per_minute_min' not in st.session_state:
            st.session_state.api_max_requests_per_minute_min = 10.0
        else:
            st.session_state.api_max_requests_per_minute_min = float(st.session_state.api_max_requests_per_minute_min)
        if 'api_max_requests_per_minute_max' not in st.session_state:
            st.session_state.api_max_requests_per_minute_max = 15.0
        else:
            st.session_state.api_max_requests_per_minute_max = float(st.session_state.api_max_requests_per_minute_max)
        if 'api_min_delay_min' not in st.session_state:
            st.session_state.api_min_delay_min = 8.0
        if 'api_min_delay_max' not in st.session_state:
            st.session_state.api_min_delay_max = 15.0
        if 'api_random_delay' not in st.session_state:
            st.session_state.api_random_delay = True
        
        api_max_requests = st.number_input(
            "Max requêtes API/minute",
            min_value=10.0,
            max_value=15.0,
            value=float(st.session_state.api_max_requests_per_minute),
            step=1.0,
            help="Nombre maximum de requêtes API par minute (10-15 recommandé)",
            key="settings_api_max_requests"
        )
        
        api_max_requests_min = st.number_input(
            "Min requêtes API/minute",
            min_value=10.0,
            max_value=15.0,
            value=float(st.session_state.api_max_requests_per_minute_min),
            step=1.0,
            help="Minimum de requêtes API par minute (10-15)",
            key="settings_api_max_requests_min"
        )
        
        api_max_requests_max = st.number_input(
            "Max requêtes API/minute (limite)",
            min_value=10.0,
            max_value=15.0,
            value=float(st.session_state.api_max_requests_per_minute_max),
            step=1.0,
            help="Maximum de requêtes API par minute (10-15)",
            key="settings_api_max_requests_max"
        )
        
        api_min_delay_min = st.number_input(
            "Délai API minimum (secondes)",
            min_value=1.0,
            max_value=30.0,
            value=float(st.session_state.api_min_delay_min),
            step=0.5,
            help="Délai minimum entre deux analyses API (8-15s recommandé)",
            key="settings_api_min_delay_min"
        )
        
        api_min_delay_max = st.number_input(
            "Délai API maximum (secondes)",
            min_value=1.0,
            max_value=60.0,
            value=float(st.session_state.api_min_delay_max),
            step=0.5,
            help="Délai maximum entre deux analyses API (8-15s recommandé)",
            key="settings_api_min_delay_max"
        )
        
        api_random_delay = st.checkbox(
            "Délai aléatoire API",
            value=st.session_state.api_random_delay,
            help="Activer les délais aléatoires entre les requêtes API",
            key="settings_api_random_delay"
        )
        
        if int(api_max_requests) != st.session_state.api_max_requests_per_minute:
            st.session_state.api_max_requests_per_minute = int(api_max_requests)
            _save_ui_config_to_yaml()
            st.success("✅ Limite requêtes API mise à jour")
        
        if int(api_max_requests_min) != st.session_state.api_max_requests_per_minute_min:
            st.session_state.api_max_requests_per_minute_min = int(api_max_requests_min)
            _save_ui_config_to_yaml()
            st.success("✅ Limite minimale requêtes API mise à jour")
        
        if int(api_max_requests_max) != st.session_state.api_max_requests_per_minute_max:
            st.session_state.api_max_requests_per_minute_max = int(api_max_requests_max)
            _save_ui_config_to_yaml()
            st.success("✅ Limite maximale requêtes API mise à jour")
        
        if api_min_delay_min != st.session_state.api_min_delay_min:
            st.session_state.api_min_delay_min = api_min_delay_min
            _save_ui_config_to_yaml()
            st.success("✅ Délai API minimum mis à jour")
        
        if api_min_delay_max != st.session_state.api_min_delay_max:
            st.session_state.api_min_delay_max = api_min_delay_max
            _save_ui_config_to_yaml()
            st.success("✅ Délai API maximum mis à jour")
        
        if api_random_delay != st.session_state.api_random_delay:
            st.session_state.api_random_delay = api_random_delay
            _save_ui_config_to_yaml()
            st.success("✅ Délai aléatoire API mis à jour")
    
    st.divider()
    
    # Publication delay settings
    with st.expander("📅 Publication Delays", expanded=False):
        st.caption("Délais entre les publications")
        
        if 'pub_delay_min' not in st.session_state:
            st.session_state.pub_delay_min = 4.0
        else:
            st.session_state.pub_delay_min = float(st.session_state.pub_delay_min)
        if 'pub_delay_max' not in st.session_state:
            st.session_state.pub_delay_max = 7.0
        else:
            st.session_state.pub_delay_max = float(st.session_state.pub_delay_max)
        
        pub_delay_min = st.number_input(
            "Délai publication minimum (minutes)",
            min_value=1.0,
            max_value=30.0,
            value=float(st.session_state.pub_delay_min),
            step=0.5,
            help="Délai minimum entre deux publications (4-7 min recommandé)",
            key="settings_pub_delay_min"
        )
        
        pub_delay_max = st.number_input(
            "Délai publication maximum (minutes)",
            min_value=1.0,
            max_value=60.0,
            value=float(st.session_state.pub_delay_max),
            step=0.5,
            help="Délai maximum entre deux publications (4-7 min recommandé)",
            key="settings_pub_delay_max"
        )
        
        if pub_delay_min != st.session_state.pub_delay_min:
            st.session_state.pub_delay_min = pub_delay_min
            _save_ui_config_to_yaml()
            st.success("✅ Délai publication minimum mis à jour")
        
        if pub_delay_max != st.session_state.pub_delay_max:
            st.session_state.pub_delay_max = pub_delay_max
            _save_ui_config_to_yaml()
            st.success("✅ Délai publication maximum mis à jour")
        
        if min_delay != st.session_state.min_edit_delay:
            st.session_state.min_edit_delay = min_delay
            _save_ui_config_to_yaml()
            st.success("✅ Délai minimum mis à jour")
        
        if daily_limit != st.session_state.scheduler_daily_limit:
            st.session_state.scheduler_daily_limit = daily_limit
            _save_ui_config_to_yaml()
            st.success("✅ Limite journalière mise à jour")

    st.divider()

    # Initialize settings manager in session state if not present
    if 'settings_manager' not in st.session_state:
        from wikipedia_maintenance.utils.ui_settings import get_settings_manager
        st.session_state.settings_manager = get_settings_manager()

    settings = st.session_state.settings_manager.get_settings()

    with st.expander("⚙️ Analyseurs actifs", expanded=False):
        st.caption("Activez ou désactivez les analyseurs de problèmes")

        analyzer_descriptions = {
            "DeadLinkAnalyzer": "Liens morts et brisés (détection et réparation)"
        }

        enabled_count = sum(
            1 for name in settings.enabled_analyzers.keys()
            if settings.is_analyzer_enabled(name)
        )
        total_count = len(settings.enabled_analyzers)
        st.caption(f"{enabled_count}/{total_count} analyseurs actifs")

        col_all, col_none = st.columns(2)
        with col_all:
            if st.button("Tout activer", width='stretch', key="analyzers_enable_all"):
                for analyzer_name in settings.enabled_analyzers.keys():
                    settings.set_analyzer_enabled(analyzer_name, True)
                st.session_state.settings_manager.save_settings()
                st.rerun()
        with col_none:
            if st.button("Tout désactiver", width='stretch', key="analyzers_disable_all"):
                for analyzer_name in settings.enabled_analyzers.keys():
                    settings.set_analyzer_enabled(analyzer_name, False)
                st.session_state.settings_manager.save_settings()
                st.rerun()

        st.divider()

        for analyzer_name in settings.enabled_analyzers.keys():
            is_enabled = settings.is_analyzer_enabled(analyzer_name)
            description = analyzer_descriptions.get(analyzer_name, "")

            if description:
                label = f"{analyzer_name}"
                help_text = description
            else:
                label = analyzer_name
                help_text = ""

            new_value = st.checkbox(
                label,
                value=is_enabled,
                key=f"analyzer_toggle_{analyzer_name}",
                help=help_text
            )

            if new_value != is_enabled:
                settings.set_analyzer_enabled(analyzer_name, new_value)
                st.session_state.settings_manager.save_settings()


def _save_ui_config_to_yaml():
    """Save UI configuration values to config.yaml for persistence."""
    try:
        config_file = Path(__file__).parent.parent / "config" / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        else:
            config = {}
        
        if not config:
            config = {}
        
        # Save rate limiting settings
        if 'rate_limiting' not in config:
            config['rate_limiting'] = {}
        if 'max_edits_per_minute' in st.session_state:
            config['rate_limiting']['max_edits_per_minute'] = st.session_state.max_edits_per_minute
        if 'min_edit_delay' in st.session_state:
            config['rate_limiting']['min_edit_delay'] = st.session_state.min_edit_delay
        if 'scheduler_daily_limit' in st.session_state:
            config['rate_limiting']['daily_limit'] = st.session_state.scheduler_daily_limit
        
        # Save API throttling settings
        if 'api_throttling' not in config:
            config['api_throttling'] = {}
        if 'api_max_requests_per_minute' in st.session_state:
            config['api_throttling']['max_requests_per_minute'] = float(st.session_state.api_max_requests_per_minute)
        if 'api_max_requests_per_minute_min' in st.session_state:
            config['api_throttling']['max_requests_per_minute_min'] = float(st.session_state.api_max_requests_per_minute_min)
        if 'api_max_requests_per_minute_max' in st.session_state:
            config['api_throttling']['max_requests_per_minute_max'] = float(st.session_state.api_max_requests_per_minute_max)
        if 'api_min_delay_min' in st.session_state:
            config['api_throttling']['min_delay_min'] = st.session_state.api_min_delay_min
        if 'api_min_delay_max' in st.session_state:
            config['api_throttling']['min_delay_max'] = st.session_state.api_min_delay_max
        if 'api_random_delay' in st.session_state:
            config['api_throttling']['random_delay'] = st.session_state.api_random_delay
        # Set default min_delay to the midpoint of min/max
        if 'api_min_delay_min' in st.session_state and 'api_min_delay_max' in st.session_state:
            config['api_throttling']['min_delay'] = (st.session_state.api_min_delay_min + st.session_state.api_min_delay_max) / 2
        
        # Save publication delay settings
        if 'publication_delays' not in config:
            config['publication_delays'] = {}
        if 'pub_delay_min' in st.session_state:
            config['publication_delays']['min_delay_minutes'] = st.session_state.pub_delay_min
        if 'pub_delay_max' in st.session_state:
            config['publication_delays']['max_delay_minutes'] = st.session_state.pub_delay_max
        
        # Save scheduler settings
        if 'scheduler' not in config:
            config['scheduler'] = {}
        if 'scheduler_working_hours_start' in st.session_state:
            config['scheduler']['working_hours_start'] = st.session_state.scheduler_working_hours_start
        if 'scheduler_working_hours_end' in st.session_state:
            config['scheduler']['working_hours_end'] = st.session_state.scheduler_working_hours_end
        
        # Save Ollama settings
        if 'ai' not in config:
            config['ai'] = {}
        if 'ollama' not in config['ai']:
            config['ai']['ollama'] = {}
        if 'ollama_url' in st.session_state and st.session_state.ollama_url:
            config['ai']['ollama']['url'] = st.session_state.ollama_url
        if 'ollama_model' in st.session_state and st.session_state.ollama_model:
            config['ai']['ollama']['model'] = st.session_state.ollama_model
        if 'ollama_fallback' in st.session_state and st.session_state.ollama_fallback:
            config['ai']['ollama']['fallback'] = st.session_state.ollama_fallback
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        pass  # Silently fail to avoid UI disruption


def _load_ui_config_from_yaml():
    """Load UI configuration values from config.yaml."""
    try:
        config_file = Path(__file__).parent.parent / "config" / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config:
                    # Load rate limiting
                    if 'rate_limiting' in config:
                        if 'max_edits_per_minute' in config['rate_limiting']:
                            st.session_state.max_edits_per_minute = config['rate_limiting']['max_edits_per_minute']
                        if 'min_edit_delay' in config['rate_limiting']:
                            st.session_state.min_edit_delay = config['rate_limiting']['min_edit_delay']
                        if 'daily_limit' in config['rate_limiting']:
                            st.session_state.scheduler_daily_limit = config['rate_limiting']['daily_limit']
                    
                    # Load API throttling
                    if 'api_throttling' in config:
                        if 'max_requests_per_minute' in config['api_throttling']:
                            st.session_state.api_max_requests_per_minute = float(config['api_throttling']['max_requests_per_minute'])
                        if 'max_requests_per_minute_min' in config['api_throttling']:
                            st.session_state.api_max_requests_per_minute_min = float(config['api_throttling']['max_requests_per_minute_min'])
                        if 'max_requests_per_minute_max' in config['api_throttling']:
                            st.session_state.api_max_requests_per_minute_max = float(config['api_throttling']['max_requests_per_minute_max'])
                        if 'min_delay_min' in config['api_throttling']:
                            st.session_state.api_min_delay_min = float(config['api_throttling']['min_delay_min'])
                        if 'min_delay_max' in config['api_throttling']:
                            st.session_state.api_min_delay_max = float(config['api_throttling']['min_delay_max'])
                        if 'random_delay' in config['api_throttling']:
                            st.session_state.api_random_delay = config['api_throttling']['random_delay']
                    
                    # Load publication delays
                    if 'publication_delays' in config:
                        if 'min_delay_minutes' in config['publication_delays']:
                            st.session_state.pub_delay_min = float(config['publication_delays']['min_delay_minutes'])
                        if 'max_delay_minutes' in config['publication_delays']:
                            st.session_state.pub_delay_max = float(config['publication_delays']['max_delay_minutes'])
                    
                    # Load scheduler
                    if 'scheduler' in config:
                        if 'working_hours_start' in config['scheduler']:
                            st.session_state.scheduler_working_hours_start = config['scheduler']['working_hours_start']
                        if 'working_hours_end' in config['scheduler']:
                            st.session_state.scheduler_working_hours_end = config['scheduler']['working_hours_end']
                    
                    # Load Ollama
                    if 'ai' in config and 'ollama' in config['ai']:
                        if 'url' in config['ai']['ollama']:
                            st.session_state.ollama_url = config['ai']['ollama']['url']
                        if 'model' in config['ai']['ollama']:
                            st.session_state.ollama_model = config['ai']['ollama']['model']
                        if 'fallback' in config['ai']['ollama']:
                            st.session_state.ollama_fallback = config['ai']['ollama']['fallback']
    except Exception:
        pass


def _reset_to_defaults():
    """Reset all UI settings to config.yaml defaults."""
    try:
        config_file = Path(__file__).parent.parent / "config" / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config:
                    # Reset rate limiting
                    if 'rate_limiting' in config:
                        st.session_state.max_edits_per_minute = config['rate_limiting'].get('max_edits_per_minute', 10)
                        st.session_state.min_edit_delay = config['rate_limiting'].get('min_edit_delay', 1.0)
                        st.session_state.scheduler_daily_limit = config['rate_limiting'].get('daily_limit', 50)
                    else:
                        st.session_state.max_edits_per_minute = 10
                        st.session_state.min_edit_delay = 1.0
                        st.session_state.scheduler_daily_limit = 50
                    
                    # Reset API throttling
                    if 'api_throttling' in config:
                        st.session_state.api_max_requests_per_minute = float(config['api_throttling'].get('max_requests_per_minute', 10))
                        st.session_state.api_max_requests_per_minute_min = float(config['api_throttling'].get('max_requests_per_minute_min', 10))
                        st.session_state.api_max_requests_per_minute_max = float(config['api_throttling'].get('max_requests_per_minute_max', 15))
                        st.session_state.api_min_delay_min = config['api_throttling'].get('min_delay_min', 8.0)
                        st.session_state.api_min_delay_max = config['api_throttling'].get('min_delay_max', 15.0)
                        st.session_state.api_random_delay = config['api_throttling'].get('random_delay', True)
                    else:
                        st.session_state.api_max_requests_per_minute = 10.0
                        st.session_state.api_max_requests_per_minute_min = 10.0
                        st.session_state.api_max_requests_per_minute_max = 15.0
                        st.session_state.api_min_delay_min = 8.0
                        st.session_state.api_min_delay_max = 15.0
                        st.session_state.api_random_delay = True
                    
                    # Reset publication delays
                    if 'publication_delays' in config:
                        st.session_state.pub_delay_min = config['publication_delays'].get('min_delay_minutes', 2)
                        st.session_state.pub_delay_max = config['publication_delays'].get('max_delay_minutes', 4)
                    else:
                        st.session_state.pub_delay_min = 2
                        st.session_state.pub_delay_max = 4
                    
                    # Reset scheduler
                    if 'scheduler' in config:
                        st.session_state.scheduler_working_hours_start = config['scheduler'].get('working_hours_start', 9)
                        st.session_state.scheduler_working_hours_end = config['scheduler'].get('working_hours_end', 18)
                    else:
                        st.session_state.scheduler_working_hours_start = 9
                        st.session_state.scheduler_working_hours_end = 18
                    
                    # Reset Ollama
                    if 'ai' in config and 'ollama' in config['ai']:
                        st.session_state.ollama_url = config['ai']['ollama'].get('url', '')
                        st.session_state.ollama_model = config['ai']['ollama'].get('model', '')
                        st.session_state.ollama_fallback = config['ai']['ollama'].get('fallback', '')
                    else:
                        st.session_state.ollama_url = ''
                        st.session_state.ollama_model = ''
                        st.session_state.ollama_fallback = ''
                    
                    st.success("✅ Paramètres réinitialisés aux valeurs par défaut")
                    st.rerun()
        else:
            st.error("❌ Fichier config.yaml introuvable")
    except Exception as e:
        st.error(f"❌ Erreur lors de la réinitialisation : {e}")


def _render_secrets_section():
    """Render secrets configuration section."""
    st.divider()
    
    # Load persisted values on first render
    _load_ui_config_from_yaml()
    
    with st.expander("🔑 Configuration des Secrets", expanded=False):
        st.caption("⚠️ Les secrets sont stockés localement dans votre navigateur et ne sont jamais envoyés au serveur.")
        
        # Gemini API Key
        if 'gemini_api_key' not in st.session_state:
            st.session_state.gemini_api_key = os.environ.get('GEMINI_API_KEY', '')
        
        gemini_api_key = st.text_input(
            "Gemini API Key",
            value=st.session_state.gemini_api_key,
            type="password",
            help="Clé API Google Gemini pour l'analyse IA. Obtenable depuis Google Cloud Console.",
            key="secrets_gemini_api_key"
        )
        
        if gemini_api_key != st.session_state.gemini_api_key:
            st.session_state.gemini_api_key = gemini_api_key
            os.environ['GEMINI_API_KEY'] = gemini_api_key
            st.success("✅ Clé API Gemini mise à jour")
        
        # Gemini Project ID
        if 'gemini_project_id' not in st.session_state:
            st.session_state.gemini_project_id = os.environ.get('GEMINI_PROJECT_ID', '')
        
        gemini_project_id = st.text_input(
            "Gemini Project ID",
            value=st.session_state.gemini_project_id,
            help="ID du projet Google Cloud. Optionnel si configuré dans config.yaml.",
            key="secrets_gemini_project_id"
        )
        
        if gemini_project_id != st.session_state.gemini_project_id:
            st.session_state.gemini_project_id = gemini_project_id
            os.environ['GEMINI_PROJECT_ID'] = gemini_project_id
            st.success("✅ Project ID Gemini mis à jour")
        
        # Telegram Bot Token
        if 'telegram_bot_token' not in st.session_state:
            st.session_state.telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        
        telegram_bot_token = st.text_input(
            "Telegram Bot Token",
            value=st.session_state.telegram_bot_token,
            type="password",
            help="Token du bot Telegram pour contrôle à distance. Optionnel.",
            key="secrets_telegram_bot_token"
        )
        
        if telegram_bot_token != st.session_state.telegram_bot_token:
            st.session_state.telegram_bot_token = telegram_bot_token
            os.environ['TELEGRAM_BOT_TOKEN'] = telegram_bot_token
            st.success("✅ Token Telegram mis à jour")
        
        # Telegram Admin IDs
        if 'telegram_admin_ids' not in st.session_state:
            st.session_state.telegram_admin_ids = os.environ.get('TELEGRAM_ADMIN_IDS', '')
        
        telegram_admin_ids = st.text_input(
            "Telegram Admin IDs",
            value=st.session_state.telegram_admin_ids,
            help="IDs des administrateurs Telegram (séparés par des virgules). Optionnel.",
            key="secrets_telegram_admin_ids"
        )
        
        if telegram_admin_ids != st.session_state.telegram_admin_ids:
            st.session_state.telegram_admin_ids = telegram_admin_ids
            os.environ['TELEGRAM_ADMIN_IDS'] = telegram_admin_ids
            st.success("✅ Admin IDs Telegram mis à jour")
        
        st.divider()
        
        # Ollama Configuration
        st.subheader("🤖 Configuration Ollama (Local AI)")
        
        if 'ollama_url' not in st.session_state:
            st.session_state.ollama_url = ''
        if 'ollama_model' not in st.session_state:
            st.session_state.ollama_model = ''
        if 'ollama_fallback' not in st.session_state:
            st.session_state.ollama_fallback = ''
        
        ollama_url = st.text_input(
            "Ollama Server URL",
            value=st.session_state.ollama_url,
            help="URL du serveur Ollama local (ex: http://localhost:11434)",
            key="secrets_ollama_url"
        )
        
        ollama_model = st.text_input(
            "Ollama Model",
            value=st.session_state.ollama_model,
            help="Modèle Ollama principal (ex: mistral:instruct)",
            key="secrets_ollama_model"
        )
        
        ollama_fallback = st.text_input(
            "Ollama Fallback Model",
            value=st.session_state.ollama_fallback,
            help="Modèle Ollama de fallback (ex: llama3:instruct)",
            key="secrets_ollama_fallback"
        )
        
        if ollama_url != st.session_state.ollama_url:
            st.session_state.ollama_url = ollama_url
            os.environ['OLLAMA_URL'] = ollama_url
            _save_ui_config_to_yaml()
            st.success("✅ URL Ollama mise à jour")
        
        if ollama_model != st.session_state.ollama_model:
            st.session_state.ollama_model = ollama_model
            os.environ['OLLAMA_MODEL'] = ollama_model
            _save_ui_config_to_yaml()
            st.success("✅ Modèle Ollama mis à jour")
        
        if ollama_fallback != st.session_state.ollama_fallback:
            st.session_state.ollama_fallback = ollama_fallback
            os.environ['OLLAMA_FALLBACK'] = ollama_fallback
            _save_ui_config_to_yaml()
            st.success("✅ Modèle fallback mis à jour")
        
        st.divider()
        st.caption("ℹ️ Pour une configuration permanente, utilisez un fichier .env ou configurez les variables d'environnement système.")
        st.caption("📖 Voir .env.example pour la liste complète des variables disponibles.")
        
        # Scheduler configuration
        st.divider()
        st.subheader("📅 Configuration Scheduler (Horaires)")
        
        if 'scheduler_working_hours_start' not in st.session_state:
            st.session_state.scheduler_working_hours_start = 9
        if 'scheduler_working_hours_end' not in st.session_state:
            st.session_state.scheduler_working_hours_end = 18
        
        col1, col2 = st.columns(2)
        with col1:
            working_start = st.number_input(
                "Heure début (0-23)",
                min_value=0,
                max_value=23,
                value=st.session_state.scheduler_working_hours_start,
                help="Heure de début des heures de travail",
                key="scheduler_start"
            )
        with col2:
            working_end = st.number_input(
                "Heure fin (0-23)",
                min_value=0,
                max_value=23,
                value=st.session_state.scheduler_working_hours_end,
                help="Heure de fin des heures de travail",
                key="scheduler_end"
            )
        
        if working_start != st.session_state.scheduler_working_hours_start:
            st.session_state.scheduler_working_hours_start = working_start
            _save_ui_config_to_yaml()
            st.success("✅ Heure début mise à jour")
        
        if working_end != st.session_state.scheduler_working_hours_end:
            st.session_state.scheduler_working_hours_end = working_end
            _save_ui_config_to_yaml()
            st.success("✅ Heures de travail mises à jour")


def _render_logs_section():
    """Render logs display section."""
    st.divider()
    st.subheader("📋 Logs en temps réel")
    
    # Importer le captureur de logs depuis le module partagé
    import sys
    from pathlib import Path
    # Ajouter le répertoire parent au path pour importer le module logging
    app_dir = Path(__file__).parent.parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    
    try:
        from utils.logging_config import get_log_capture
        
        # Obtenir les logs récents depuis le captureur en mémoire
        log_capture = get_log_capture()
        recent_logs = log_capture.get_recent_logs(100)
        
        if not recent_logs:
            st.info("Aucun log disponible")
            return
        
        # Afficher les logs
        st.text_area(
            "Logs récents",
            value='\n'.join(recent_logs),
            height=300,
            key="logs_display"
        )
        
        # Auto-refresh option
        if st.checkbox("🔄 Auto-rafraîchir (5s)", key="auto_refresh_logs"):
            st.rerun()
            
    except ImportError:
        # Fallback: lire le fichier de logs si le captureur n'est pas disponible
        log_file = Path("logs/app.log")
        
        if not log_file.exists():
            st.info("Aucun fichier de logs trouvé")
            return
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            log_lines = log_content.split('\n')
            recent_logs = log_lines[-100:] if len(log_lines) > 100 else log_lines
            
            st.text_area(
                "Logs récents",
                value='\n'.join(recent_logs),
                height=300,
                key="logs_display"
            )
            
            if st.checkbox("🔄 Auto-rafraîchir (5s)", key="auto_refresh_logs"):
                st.rerun()
                
        except Exception as e:
            st.error(f"Erreur lors de la lecture des logs: {e}")