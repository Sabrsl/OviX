"""
Streamlit web interface for Wikipedia Maintenance Tool.
"""

import difflib
import html
import streamlit as st
from streamlit_option_menu import option_menu
import sys
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure PYWIKIBOT_DIR BEFORE importing pywikibot
project_root = Path(__file__).parent
os.environ['PYWIKIBOT_DIR'] = str(project_root)
sys.path.insert(0, str(project_root))

# Configure logging to show in Streamlit terminal and write to file
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Import logging configuration
sys.path.insert(0, str(Path(__file__).parent))
from utils.logging_config import setup_logging, get_log_capture

# Setup logging
setup_logging()

logger = logging.getLogger(__name__)

# Add src to path FIRST (before importing wikipedia_maintenance)
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Import categories config and published tracker
sys.path.insert(0, str(Path(__file__).parent))
from categories_config import get_predefined_categories

# Now import wikipedia_maintenance modules
from wikipedia_maintenance.utils.published_tracker import PublishedTracker

from wikipedia_maintenance.retrievers import (
    CategoryRetriever, ManualRetriever, UserContribsRetriever,
    PetScanRetriever, FileRetriever, Article
)
from wikipedia_maintenance.analyzers import (
    LinkAnalyzer, WhitespaceAnalyzer, TypographyAnalyzer,
    TemplateAnalyzer, CategoryAnalyzer, HTMLAnalyzer,
    ReferenceAnalyzer, StructureAnalyzer, WorksListAnalyzer,
    HttpLinksAnalyzer, DeadLinkAnalyzer
)
from wikipedia_maintenance.utils import DatabaseManager
from wikipedia_maintenance.utils.ui_settings import get_settings_manager
from wikipedia_maintenance.utils.publisher import Publisher, Corrector
from wikipedia_maintenance.utils.lia_client import LIAOllamaClient
from wikipedia_maintenance.utils.gemini_client import GeminiClient
from wikipedia_maintenance.utils.analyzed_tracker import get_analyzed_tracker, AnalysisStatus
from wikipedia_maintenance.orchestrator import Scheduler, SchedulerConfig, AutomationOrchestrator

# Thread-safe scheduler storage (module-level)
_scheduler_instance = None
_automation_orchestrator_instance = None


# Page configuration
st.set_page_config(
    page_title="Wikipedia Maintenance Tool",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Apply UI theme
# ---------------------------------------------------------------------------
from ui.theme import apply_theme
apply_theme()

# Initialize session state
if 'site' not in st.session_state:
    st.session_state.site = None
if 'connected_lang' not in st.session_state:
    st.session_state.connected_lang = None
if 'connected_family' not in st.session_state:
    st.session_state.connected_family = None
if 'articles' not in st.session_state:
    st.session_state.articles = []
if 'current_article_index' not in st.session_state:
    st.session_state.current_article_index = 0
if 'issues' not in st.session_state:
    st.session_state.issues = {}
if 'corrected_content' not in st.session_state:
    st.session_state.corrected_content = {}
if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()
if 'publisher' not in st.session_state:
    st.session_state.publisher = None  # Publisher disabled
if 'dry_run' not in st.session_state:
    st.session_state.dry_run = True
if 'article_status' not in st.session_state:
    # title -> "pending" | "analyzed" | "approved" | "ignored" | "error"
    st.session_state.article_status = {}
if 'manual_edit_mode' not in st.session_state:
    st.session_state.manual_edit_mode = False
if 'confirm_publish' not in st.session_state:
    st.session_state.confirm_publish = False
if 'lia_client' not in st.session_state:
    st.session_state.lia_client = None
if 'lia_mode' not in st.session_state:
    st.session_state.lia_mode = False  # False = regex mode, True = LIA mode
if 'lia_corrected_content' not in st.session_state:
    st.session_state.lia_corrected_content = {}
if 'lia_limite_caracteres' not in st.session_state:
    st.session_state.lia_limite_caracteres = 10800
if 'ai_provider' not in st.session_state:
    st.session_state.ai_provider = "gemini"  # "gemini" or "ollama"
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = os.environ.get('GEMINI_API_KEY', "")
if 'gemini_project_id' not in st.session_state:
    st.session_state.gemini_project_id = os.environ.get('GEMINI_PROJECT_ID', "804175778135")
if 'automation_scheduler' not in st.session_state:
    st.session_state.automation_scheduler = None
if 'automation_running' not in st.session_state:
    st.session_state.automation_running = False
if 'analyzed_tracker' not in st.session_state:
    st.session_state.analyzed_tracker = None
# Initialize API throttling parameters
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
# Initialize publication delay parameters
if 'pub_delay_min' not in st.session_state:
    st.session_state.pub_delay_min = 4.0
else:
    st.session_state.pub_delay_min = float(st.session_state.pub_delay_min)
if 'pub_delay_max' not in st.session_state:
    st.session_state.pub_delay_max = 7.0
else:
    st.session_state.pub_delay_max = float(st.session_state.pub_delay_max)


# ---------------------------------------------------------------------------
# Cached resource initialization
# ---------------------------------------------------------------------------

@st.cache_resource
def get_cached_published_tracker():
    """Cached PublishedTracker instance to avoid reloading on each rerun."""
    from wikipedia_maintenance.utils.published_tracker import PublishedTracker
    return PublishedTracker()

@st.cache_resource
def get_cached_analyzed_tracker():
    """Cached AnalyzedTracker instance to avoid reloading on each rerun."""
    try:
        return get_analyzed_tracker()
    except Exception as e:
        logger.warning(f"Failed to initialize analyzed tracker: {e}")
        return None

# ---------------------------------------------------------------------------
# Diff / display helpers
# ---------------------------------------------------------------------------

SEVERITY_STYLE = {
    "high":   {"color": "#b30000", "bg": "#b30000", "icon": "🔴", "label": "Critique"},
    "medium": {"color": "#946200", "bg": "#c9781a", "icon": "🟠", "label": "Moyen"},
    "low":    {"color": "#1a6b1a", "bg": "#1f8a1f", "icon": "🟢", "label": "Mineur"},
}

STATUS_STYLE = {
    "pending":  {"color": "#9e9e9e", "label": "En attente"},
    "analyzed": {"color": "#1976d2", "label": "Analysé"},
    "approved": {"color": "#2e7d32", "label": "Publié"},
    "published": {"color": "#2e7d32", "label": "Publié"},
    "ignored":  {"color": "#9e9e9e", "label": "Ignoré"},
    "error":    {"color": "#b30000", "label": "Erreur"},
}


def severity_badge(severity: str) -> str:
    """Badge HTML coloré (fond plein + texte blanc : lisible en clair et sombre)."""
    s = SEVERITY_STYLE.get(severity, SEVERITY_STYLE["low"])
    return (
        f'<span style="background-color:{s["bg"]};color:#ffffff;'
        f'padding:2px 10px;border-radius:12px;font-size:0.85em;font-weight:600;'
        f'white-space:nowrap;">{s["icon"]} {s["label"]}</span>'
    )


def status_dot(title: str) -> str:
    status = st.session_state.article_status.get(title, "pending")
    s = STATUS_STYLE.get(status, STATUS_STYLE["pending"])
    return f'<span class="status-dot" style="background-color:{s["color"]};"></span>{s["label"]}'


def render_word_diff(original: str, corrected: str) -> str:
    """Génère un diff HTML qui préserve la structure wikicode (sauts de ligne, sections)."""
    orig_lines = original.split('\n')
    corr_lines = corrected.split('\n')

    matcher = difflib.SequenceMatcher(None, orig_lines, corr_lines)

    out_lines = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in orig_lines[i1:i2]:
                out_lines.append(html.escape(line))
        elif tag == "delete":
            for line in orig_lines[i1:i2]:
                out_lines.append(f'<span class="wm-diff-del">{html.escape(line)}</span>')
        elif tag == "insert":
            for line in corr_lines[j1:j2]:
                out_lines.append(f'<span class="wm-diff-ins">{html.escape(line)}</span>')
        elif tag == "replace":
            for orig_line, corr_line in zip(orig_lines[i1:i2], corr_lines[j1:j2]):
                out_lines.append(_diff_line(orig_line, corr_line))

    return '<br>'.join(out_lines)


def _diff_line(original: str, corrected: str) -> str:
    """Diff mot-à-mot pour une seule ligne."""
    orig_words = original.split()
    corr_words = corrected.split()
    matcher = difflib.SequenceMatcher(None, orig_words, corr_words)

    out = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            out.append(html.escape(" ".join(orig_words[i1:i2])))
        elif tag == "delete":
            out.append(f'<span class="wm-diff-del">{html.escape(" ".join(orig_words[i1:i2]))}</span>')
        elif tag == "insert":
            out.append(f'<span class="wm-diff-ins">{html.escape(" ".join(corr_words[j1:j2]))}</span>')
        elif tag == "replace":
            out.append(
                f'<span class="wm-diff-del">{html.escape(" ".join(orig_words[i1:i2]))}</span> '
                f'<span class="wm-diff-ins">{html.escape(" ".join(corr_words[j1:j2]))}</span>'
            )
    return " ".join(out)


def connect_to_wikipedia(lang: str, family: str):
    """Connect to Wikipedia using MediaWiki API for publishing, but keep pywikibot for retrieval."""
    try:
        import pywikibot
        import os
        import sys
        from pathlib import Path

        # Check if already connected with same parameters
        if (st.session_state.site and 
            st.session_state.connected_lang == lang and 
            st.session_state.connected_family == family and
            st.session_state.publisher):
            logger.info("Already connected to Wikipedia, reusing existing connection")
            st.success(f"✅ Déjà connecté à Wikipédia ({lang}.{family})")
            return True

        # Set PYWIKIBOT_DIR to project root
        project_root = Path(__file__).parent
        os.environ['PYWIKIBOT_DIR'] = str(project_root)
        sys.path.insert(0, str(project_root))

        # Create pywikibot site for retrieval (no login needed)
        import pywikibot
        site = pywikibot.Site(lang, family)
        # Configure pywikibot rate limiting to match our settings
        pywikibot.config.put_throttle = 0  # Disable default throttling, we manage it ourselves
        pywikibot.config.maxlag = 5  # Maximum server lag in seconds
        
        # Override the API request method to use our throttler
        from wikipedia_maintenance.utils.api_throttler import get_global_throttler
        api_throttler = get_global_throttler()
        original_request = site._simple_request
        def throttled_request(**kwargs):
            api_throttler.wait_if_needed()
            try:
                result = original_request(**kwargs)
                api_throttler.report_success()
                return result
            except Exception as e:
                if '429' in str(e) or 'Too Many Requests' in str(e):
                    api_throttler.report_429()
                raise
        
        site._simple_request = throttled_request

        # Get credentials from session state if provided
        username = st.session_state.get('wp_username', None)
        password = st.session_state.get('wp_password', None)

        # Create Publisher with MediaWiki API for publishing
        if username and password:
            st.session_state.publisher = Publisher(
                username=username,
                password=password,
                dry_run=st.session_state.dry_run,
                lang=lang
            )
        else:
            st.session_state.publisher = Publisher(
                dry_run=st.session_state.dry_run,
                lang=lang
            )

        authenticated = st.session_state.publisher.authenticate()

        if authenticated:
            st.session_state.site = site  # Keep pywikibot site for retrieval
            st.session_state.connected_lang = lang  # Save connection parameters
            st.session_state.connected_family = family
            
            # Clear password from session state if not remembering
            if not st.session_state.get('wp_remember', False):
                st.session_state.wp_password = ''
            
            st.success(f"✅ Connecté à Wikipédia ({lang}.{family})")
            return True
        else:
            st.error("Échec de l'authentification")
            return False
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        return False


def retrieve_articles(source_type: str, **kwargs):
    """Retrieve articles based on source type."""
    if not st.session_state.site:
        st.error("Veuillez d'abord vous connecter à Wikipédia")
        return

    retriever = None
    max_articles = kwargs.get('max_articles', 100)
    
    # Get tracker for analyzed articles
    tracker = None
    try:
        tracker = get_analyzed_tracker()
    except Exception as e:
        logger.warning(f"Failed to get analyzed tracker: {e}")
    
    # Check if we should include already analyzed articles (default: False for manual retrieval, True for automation)
    include_analyzed = kwargs.get('include_analyzed', False)
    
    # First, try to get analyzed but not published articles (priority) - ONLY if include_analyzed is True
    priority_articles = []
    if tracker and include_analyzed:
        try:
            analyzed_records = tracker.get_analyzed_but_not_published(max_count=max_articles)
            
            for record in analyzed_records:
                try:
                    import pywikibot
                    page = pywikibot.Page(st.session_state.site, record.title)
                    if page.exists():
                        # Check if revision is still the same
                        if page.latest_revision_id == record.revision_id:
                            article = Article(
                                title=record.title,
                                page_id=record.page_id,
                                revision_id=record.revision_id,
                                url=page.full_url()
                            )
                            # Restore corrected content if available
                            if record.corrected_content:
                                article.content = record.corrected_content
                            priority_articles.append(article)
                        else:
                            logger.info(f"Article '{record.title}' has been modified, skipping from priority")
                except Exception as e:
                    logger.warning(f"Failed to load priority article '{record.title}': {e}")
        except Exception as e:
            logger.warning(f"Failed to get analyzed articles: {e}")
    
    if priority_articles:
        st.info(f"📋 {len(priority_articles)} article(s) analysé(s) mais non publié(s) récupéré(s) en priorité")
    elif not include_analyzed:
        st.info("📋 Filtrage des articles déjà analysés activé")
    
    try:
        with st.spinner("Récupération des articles en cours..."):
            # Calculate how many new articles we need
            needed = max_articles - len(priority_articles)
            
            if needed > 0:
                if source_type == "category":
                    retriever = CategoryRetriever(st.session_state.site, use_cache=False)  # Disable cache for pagination
                    new_articles = []
                    offset = 0
                    batch_size = needed * 2  # Fetch in batches to account for filtering
                    max_iterations = 10  # Prevent infinite loops
                    iteration = 0
                    consecutive_empty_batches = 0  # Track consecutive empty batches to detect end of category
                    
                    while len(new_articles) < needed and iteration < max_iterations:
                        iteration += 1
                        logger.info(f"Fetching batch {iteration} with offset {offset}, target: {needed}, current: {len(new_articles)}")
                        
                        batch_articles = retriever.retrieve(
                            category_name=kwargs.get('category_name'),
                            max_articles=batch_size,
                            recursive=kwargs.get('recursive', False),
                            exclude_published=False,  # Don't filter here, let app.py handle it
                            offset=offset
                        )
                        
                        if not batch_articles:
                            logger.info(f"No more articles available in category, stopping with {len(new_articles)} articles")
                            break
                        
                        # Filter out recently published articles if requested
                        if kwargs.get('exclude_published', True):
                            article_titles = [article.title for article in batch_articles]
                            filtered_titles = st.session_state.published_tracker.filter_recently_published(article_titles, months=6)
                            batch_articles = [article for article in batch_articles if article.title in filtered_titles]
                        
                        # Filter out already analyzed articles (unless include_analyzed is True)
                        if tracker and not include_analyzed:
                            batch_articles = tracker.filter_analyzed_articles(batch_articles)
                        
                        if len(batch_articles) == 0:
                            consecutive_empty_batches += 1
                            logger.info(f"Batch {iteration} fully filtered out ({consecutive_empty_batches} consecutive empty batches)")
                            if consecutive_empty_batches >= 3:  # Stop after 3 consecutive empty batches
                                logger.info(f"Too many consecutive empty batches, stopping with {len(new_articles)} articles")
                                break
                        else:
                            consecutive_empty_batches = 0  # Reset counter when we get articles
                        
                        new_articles.extend(batch_articles)
                        offset += batch_size
                    
                    # Take only what we need
                    new_articles = new_articles[:needed]
                    
                    if iteration > 1:
                        st.info(f"📊 Récupération en {iteration} lots pour obtenir {len(new_articles)} articles après filtrage")
                    
                elif source_type == "manual":
                    retriever = ManualRetriever(st.session_state.site)
                    titles = [t.strip() for t in kwargs.get('titles', '').split('\n') if t.strip()]
                    if not titles:
                        st.warning("Veuillez saisir au moins un titre d'article")
                        return
                    new_articles = retriever.retrieve(titles=titles)
                    
                    # Filter out already analyzed articles (unless include_analyzed is True)
                    if tracker and not include_analyzed:
                        new_articles = tracker.filter_analyzed_articles(new_articles)
                    
                elif source_type == "user_contribs":
                    retriever = UserContribsRetriever(st.session_state.site)
                    new_articles = []
                    iteration = 0
                    max_iterations = 10
                    consecutive_empty_batches = 0
                    
                    while len(new_articles) < needed and iteration < max_iterations:
                        iteration += 1
                        batch_size = needed * 2
                        logger.info(f"Fetching user contributions batch {iteration}, target: {needed}, current: {len(new_articles)}")
                        
                        batch_articles = retriever.retrieve(
                            username=kwargs.get('username'),
                            max_articles=batch_size,
                            exclude_published=False  # Don't filter here, let app.py handle it
                        )
                        
                        if not batch_articles:
                            break
                        
                        # Filter out recently published articles if requested
                        if kwargs.get('exclude_published', True):
                            article_titles = [article.title for article in batch_articles]
                            filtered_titles = st.session_state.published_tracker.filter_recently_published(article_titles, months=6)
                            batch_articles = [article for article in batch_articles if article.title in filtered_titles]
                        
                        # Filter out already analyzed articles (unless include_analyzed is True)
                        if tracker and not include_analyzed:
                            batch_articles = tracker.filter_analyzed_articles(batch_articles)
                        
                        if len(batch_articles) == 0:
                            consecutive_empty_batches += 1
                            logger.info(f"Batch {iteration} fully filtered out ({consecutive_empty_batches} consecutive empty batches)")
                            if consecutive_empty_batches >= 3:
                                logger.info(f"Too many consecutive empty batches, stopping with {len(new_articles)} articles")
                                break
                        else:
                            consecutive_empty_batches = 0
                        
                        new_articles.extend(batch_articles)
                        
                        # If we got fewer articles than requested, we've reached the end
                        if len(batch_articles) < batch_size:
                            break
                    
                    # Take only what we need
                    new_articles = new_articles[:needed]
                    
                    if iteration > 1:
                        st.info(f"📊 Récupération en {iteration} lots pour obtenir {len(new_articles)} articles après filtrage")
                    
                elif source_type == "petscan":
                    retriever = PetScanRetriever()
                    psid = kwargs.get('psid', '').strip()
                    if not psid:
                        st.error("PetScan ID requis")
                        return
                    if not psid.isdigit():
                        st.error("Le PetScan ID doit être un nombre entier")
                        return
                    
                    # PetScan doesn't support pagination, fetch more to account for filtering
                    batch_articles = retriever.retrieve(psid=int(psid), max_articles=needed * 10, exclude_published=False)
                    
                    # Filter out recently published articles if requested
                    if kwargs.get('exclude_published', True):
                        article_titles = [article.title for article in batch_articles]
                        filtered_titles = st.session_state.published_tracker.filter_recently_published(article_titles, months=6)
                        batch_articles = [article for article in batch_articles if article.title in filtered_titles]
                    
                    # Filter out already analyzed articles (unless include_analyzed is True)
                    if tracker and not include_analyzed:
                        batch_articles = tracker.filter_analyzed_articles(batch_articles)
                    
                    new_articles = batch_articles[:needed]
                    
                    # Take only what we need
                    new_articles = new_articles[:needed]
                    
                elif source_type == "file":
                    retriever = FileRetriever()
                    new_articles = retriever.retrieve(file_path=kwargs.get('file_path'))
                    missing = 0
                    for article in new_articles:
                        try:
                            import pywikibot
                            page = pywikibot.Page(st.session_state.site, article.title)
                            if page.exists():
                                article.page_id = page.pageid
                                article.revision_id = page.latest_revision_id
                                article.url = page.full_url()
                            else:
                                missing += 1
                        except Exception:
                            missing += 1
                    if missing:
                        st.warning(f"{missing} article(s) introuvable(s) sur le wiki et ignoré(s)")
                    
                    # Filter out already analyzed articles (unless include_analyzed is True)
                    if tracker and not include_analyzed:
                        new_articles = tracker.filter_analyzed_articles(new_articles)
                    
                    # Take only what we need
                    new_articles = new_articles[:needed]
                else:
                    st.error("Type de source non reconnu")
                    return
            else:
                new_articles = []
                
        # Combine priority articles with new articles
        articles = priority_articles + new_articles
        
        # Store priority titles for later reference
        st.session_state.priority_article_titles = [a.title for a in priority_articles]
    except Exception as e:
        st.error(f"Échec de la récupération des articles : {e}")
        return

    if not articles:
        st.warning("Aucun article trouvé pour ces critères")
        return

    # Filter by character limit if in IA mode (both manual and automatic)
    if st.session_state.lia_mode:
        from wikipedia_maintenance.utils.verif_longueur import verifier
        lia_limit = st.session_state.lia_limite_caracteres
        filtered_articles = []
        filtered_count = 0
        
        # Use batch API call to get page lengths (more efficient than fetching full content)
        try:
            # Fetch page metadata in batches of 50 to avoid rate limiting
            batch_size = 50
            title_to_length = {}
            
            for i in range(0, len(articles), batch_size):
                batch = articles[i:i + batch_size]
                titles = [article.title for article in batch]
                
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
                    
                    # Use the site's API directly
                    api_url = st.session_state.site.base_url('api')
                    response = st.session_state.site._simple_request(**params)
                    data = response.submit()
                    result = data
                    
                    if 'query' in result and 'pages' in result['query']:
                        for page_data in result['query']['pages']:
                            title = page_data.get('title')
                            length = page_data.get('length', 0)
                            if title:
                                title_to_length[title] = length
                    
                    # Small delay between batches to avoid rate limiting
                    if i + batch_size < len(articles):
                        import time
                        time.sleep(0.5)
                        
                except Exception as e:
                    logger.warning(f"Batch API call failed: {e}, falling back to individual checks")
                    # Fall back to individual checks for this batch
                    for article in batch:
                        try:
                            import pywikibot
                            if not article.content:
                                page = pywikibot.Page(st.session_state.site, article.title)
                                if page.exists():
                                    article.content = page.get()
                            
                            if article.content:
                                title_to_length[article.title] = len(article.content)
                            else:
                                title_to_length[article.title] = 0
                        except Exception as e2:
                            logger.warning(f"Failed to get length for '{article.title}': {e2}")
                            title_to_length[article.title] = 0
            
            # Filter articles based on length
            for article in articles:
                length = title_to_length.get(article.title, 0)
                if length <= lia_limit:
                    filtered_articles.append(article)
                else:
                    filtered_count += 1
                    logger.info(f"Article '{article.title}' filtered: {length} chars exceeds limit {lia_limit}")
                    
        except Exception as e:
            logger.warning(f"Batch length filtering failed: {e}, using fallback method")
            # Fallback to original method if batch approach fails
            for article in articles:
                try:
                    import pywikibot
                    if not article.content:
                        page = pywikibot.Page(st.session_state.site, article.title)
                        if page.exists():
                            article.content = page.get()
                    
                    if article.content:
                        ok, nb_caracteres = verifier(article.content, lia_limit)
                        if ok:
                            filtered_articles.append(article)
                        else:
                            filtered_count += 1
                            logger.info(f"Article '{article.title}' filtered: {nb_caracteres} chars exceeds limit {lia_limit}")
                    else:
                        filtered_articles.append(article)
                except Exception as e2:
                    logger.warning(f"Failed to check length for '{article.title}': {e2}")
                    filtered_articles.append(article)
        
        articles = filtered_articles
        if filtered_count > 0:
            st.info(f"📊 {filtered_count} articles filtrés (dépassent la limite de {lia_limit} caractères)")

    st.session_state.articles = articles
    st.session_state.current_article_index = 0
    st.session_state.issues = {}
    st.session_state.corrected_content = {}
    
    # Set status for articles - priority articles should be "approved" since they're already analyzed
    st.session_state.article_status = {}
    priority_titles = st.session_state.get('priority_article_titles', [])
    for article in articles:
        if article.content and article.title in priority_titles:
            # Already analyzed with corrected content
            st.session_state.corrected_content[article.title] = article.content
            st.session_state.article_status[article.title] = "approved"
        else:
            st.session_state.article_status[article.title] = "pending"

    # Store in database
    st.session_state.db.start_session(source_type)
    for article in articles:
        st.session_state.db.add_article(
            title=article.title,
            page_id=article.page_id,
            source_type=source_type
        )

    st.success(f"{len(articles)} article(s) récupéré(s)")


def analyze_article_with_lia(article: Article, silent: bool = False):
    """Analyze an article using LIA/Ollama. Returns True on success."""
    logger.info(f"=== LIA ANALYSIS START === Article: {article.title}")

    if not st.session_state.lia_client:
        logger.error("Client LIA non configuré")
        if not silent:
            st.error("Client LIA non configuré")
        return False

    import pywikibot
    try:
        logger.info(f"Récupération de la page: {article.title}")
        page = pywikibot.Page(st.session_state.site, article.title)
        if not page.exists():
            logger.error(f"L'article « {article.title} » n'existe pas")
            if not silent:
                st.error(f"L'article « {article.title} » n'existe pas")
            st.session_state.article_status[article.title] = "error"
            return False
        content = page.get()
        logger.info(f"Contenu récupéré, longueur: {len(content)} caractères")
    except pywikibot.exceptions.IsRedirectPageError:
        logger.error(f"« {article.title} » est une redirection")
        if not silent:
            st.error(f"« {article.title} » est une redirection, article ignoré")
        st.session_state.article_status[article.title] = "error"
        return False
    except Exception as e:
        logger.error(f"Exception lors de la récupération de « {article.title} » : {e}", exc_info=True)
        if not silent:
            st.error(f"Impossible de récupérer « {article.title} » : {e}")
        st.session_state.article_status[article.title] = "error"
        return False

    article.content = content

    # Vérifier la longueur de l'article avec la limite configurée
    from wikipedia_maintenance.utils.verif_longueur import verifier
    ok, nb_caracteres = verifier(content, st.session_state.lia_limite_caracteres)
    logger.info(f"Vérification longueur: {nb_caracteres} caractères, limite: {st.session_state.lia_limite_caracteres}, OK: {ok}")
    if not ok:
        logger.error(f"Article trop long ({nb_caracteres} caractères)")
        if not silent:
            st.error(f"Article trop long ({nb_caracteres} caractères, limite = {st.session_state.lia_limite_caracteres})")
        st.session_state.article_status[article.title] = "error"
        return False

    # Envoyer à LIA/Ollama ou Gemini selon le provider
    provider = st.session_state.ai_provider
    logger.info(f"Envoi à {provider.upper()} avec modèle: {st.session_state.lia_client.model}")
    from wikipedia_maintenance.utils.lia_logger import log_lia_operation
    log_lia_operation(article.title, "envoi_lia", {"provider": provider, "model": st.session_state.lia_client.model, "caracteres": len(content)})
    
    provider_name = "Gemini" if provider == "gemini" else "LIA/Ollama"
    if not silent:
        with st.spinner(f"Correction de « {article.title} » par {provider_name} en cours..."):
            succes, article_corrige, erreur = st.session_state.lia_client.corriger_article(content)
    else:
        succes, article_corrige, erreur = st.session_state.lia_client.corriger_article(content)

    logger.info(f"Résultat {provider_name}: succes={succes}, erreur={erreur}")
    if not succes:
        logger.error(f"Erreur lors de la correction {provider_name} : {erreur}")
        if not silent:
            st.error(f"Erreur lors de la correction {provider_name} : {erreur}")
        st.session_state.article_status[article.title] = "error"
        return False

    # Stocker le contenu corrigé
    logger.info(f"Stockage du contenu corrigé, longueur: {len(article_corrige)} caractères")
    st.session_state.lia_corrected_content[article.title] = article_corrige
    st.session_state.corrected_content[article.title] = content  # Original content
    st.session_state.issues[article.title] = []  # Empty list for LIA mode (no individual issues)
    st.session_state.article_status[article.title] = "analyzed"
    
    # Store correction type for auto-generated summary - use proper description
    st.session_state[f"{article.title}_correction_types"] = ["correction typographique"]

    # Record analysis in tracker for filtering future retrievals
    try:
        tracker = get_analyzed_tracker()
        if tracker:
            summary = "Correction typographique par IA"
            if st.session_state.publisher:
                summary = st.session_state.publisher.generate_edit_summary(1, ['lia_correction'])
            
            tracker.record_analysis(
                title=article.title,
                page_id=article.page_id,
                revision_id=article.revision_id,
                status=AnalysisStatus.PENDING,
                mode='IA',
                changes_count=1,
                summary=summary,
                corrected_content=article_corrige
            )
            logger.info(f"Article '{article.title}' (LIA) recorded in analyzed tracker")
    except Exception as e:
        logger.warning(f"Failed to record LIA analysis in tracker: {e}")

    log_lia_operation(article.title, "correction_complete", {"provider": provider, "caracteres_sortie": len(article_corrige)})
    logger.info(f"=== {provider_name.upper()} ANALYSIS SUCCESS === Article: {article.title}")
    return True


def analyze_article(article: Article, silent: bool = False):
    """Analyze an article for issues. Returns True on success."""
    logger.info(f"=== ANALYSIS START === Article: {article.title}, Mode: {'LIA' if st.session_state.lia_mode else 'Regex'}")

    if not st.session_state.site:
        logger.error("Non connecté à Wikipédia")
        if not silent:
            st.error("Non connecté à Wikipédia")
        return False

    # Use LIA mode if enabled
    if st.session_state.lia_mode:
        return analyze_article_with_lia(article, silent)

    try:
        import pywikibot
        logger.info(f"Récupération de la page (mode regex): {article.title}")
        page = pywikibot.Page(st.session_state.site, article.title)
        if not page.exists():
            logger.error(f"L'article « {article.title} » n'existe pas")
            if not silent:
                st.error(f"L'article « {article.title} » n'existe pas")
            st.session_state.article_status[article.title] = "error"
            return False
        content = page.get()
        logger.info(f"Contenu récupéré, longueur: {len(content)} caractères")
    except pywikibot.exceptions.IsRedirectPageError:
        logger.error(f"« {article.title} » est une redirection")
        if not silent:
            st.error(f"« {article.title} » est une redirection, article ignoré")
        st.session_state.article_status[article.title] = "error"
        return False
    except Exception as e:
        logger.error(f"Exception lors de la récupération de « {article.title} » : {e}", exc_info=True)
        if not silent:
            st.error(f"Impossible de récupérer « {article.title} » : {e}")
        st.session_state.article_status[article.title] = "error"
        return False

    article.content = content

    # Get enabled analyzers from settings
    if 'settings_manager' not in st.session_state:
        st.session_state.settings_manager = get_settings_manager()

    settings = st.session_state.settings_manager.get_settings()
    enabled_analyzer_names = settings.get_enabled_analyzers()

    logger.info(f"Analyseurs activés: {enabled_analyzer_names}")

    # Map analyzer names to their classes
    analyzer_classes = {
        "LinkAnalyzer": LinkAnalyzer,
        "WhitespaceAnalyzer": WhitespaceAnalyzer,
        "TypographyAnalyzer": TypographyAnalyzer,
        "TemplateAnalyzer": TemplateAnalyzer,
        "CategoryAnalyzer": CategoryAnalyzer,
        "HTMLAnalyzer": HTMLAnalyzer,
        "ReferenceAnalyzer": ReferenceAnalyzer,
        "StructureAnalyzer": StructureAnalyzer,
        "WorksListAnalyzer": WorksListAnalyzer,
        "HttpLinksAnalyzer": HttpLinksAnalyzer,
        "DeadLinkAnalyzer": DeadLinkAnalyzer
    }

    # Instantiate only enabled analyzers
    analyzers = []
    
    # Initialize HTTPS verification service if HttpLinksAnalyzer is enabled
    https_service = None
    if "HttpLinksAnalyzer" in enabled_analyzer_names:
        # Always enable HTTPS verification when HttpLinksAnalyzer is active
        from wikipedia_maintenance.utils.database import DatabaseManager
        from wikipedia_maintenance.utils.https_verification_cache import HttpsVerificationCache
        from wikipedia_maintenance.utils.https_verification_service import HttpsVerificationService
        
        db_manager = DatabaseManager()
        cache = HttpsVerificationCache(db_manager)
        https_service = HttpsVerificationService(
            cache,
            timeout=settings.https_check_timeout
        )
    
    for analyzer_name in enabled_analyzer_names:
        if analyzer_name in analyzer_classes:
            if analyzer_name == "HttpLinksAnalyzer":
                # Always enable HTTPS verification when HttpLinksAnalyzer is active
                analyzers.append(analyzer_classes[analyzer_name](
                    enable_https_verification=True,  # Force enable
                    https_verification_service=https_service,
                    max_https_checks=settings.max_https_checks,
                    https_check_timeout=settings.https_check_timeout
                ))
            elif analyzer_name in ["LinkAnalyzer", "WhitespaceAnalyzer", "ReferenceAnalyzer", "StructureAnalyzer", "WorksListAnalyzer"]:
                analyzers.append(analyzer_classes[analyzer_name](language=language))
            else:
                analyzers.append(analyzer_classes[analyzer_name]())

    logger.info(f"Analyseurs instanciés: {[a.__class__.__name__ for a in analyzers]}")

    all_issues = []
    analyzer_failed = False
    failed_analyzer_name = None
    
    for analyzer in analyzers:
        try:
            logger.info(f"Exécution de {analyzer.__class__.__name__}")
            issues = analyzer.analyze(content)
            logger.info(f"{analyzer.__class__.__name__} a trouvé {len(issues)} problèmes")
            all_issues.extend(issues)
        except Exception as e:
            logger.error(f"{analyzer.__class__.__name__} a échoué sur « {article.title} » : {e}", exc_info=True)
            analyzer_failed = True
            failed_analyzer_name = analyzer.__class__.__name__
            if not silent:
                st.warning(f"{analyzer.__class__.__name__} a échoué sur « {article.title} » : {e}")
            # Break early if analyzer fails to prevent partial analysis
            break

    # If an analyzer failed, mark article as error and return
    if analyzer_failed:
        logger.error(f"Analyse incomplète pour « {article.title} » : échec de {failed_analyzer_name}")
        st.session_state.article_status[article.title] = "error"
        return False

    logger.info(f"Total des problèmes détectés: {len(all_issues)}")

    article_data = st.session_state.db.get_article(article.title)
    if article_data:
        for issue in all_issues:
            st.session_state.db.add_issue(
                article_id=article_data['id'],
                issue_type=issue.issue_type,
                description=issue.description,
                position=issue.position,
                original_text=issue.original_text,
                suggested_text=issue.suggested_text,
                severity=issue.severity
            )

    st.session_state.issues[article.title] = all_issues

    # Apply corrections to get the corrected content
    from wikipedia_maintenance.utils.publisher import Corrector
    corrector = Corrector(content)
    corrected = corrector.apply_corrections(all_issues)
    
    # If no corrections were actually applied, still use the corrected content
    # (Corrector might return unchanged content if no valid corrections)
    if not corrected or corrected == content:
        logger.warning("No corrections applied, using content with issues shown")
        corrected = content
    
    # Log the difference for debugging
    logger.info(f"Original length: {len(content)}, Corrected length: {len(corrected)}, Changed: {content != corrected}")
    
    # Store the corrected content
    st.session_state.corrected_content[article.title] = corrected
    st.session_state.article_status[article.title] = "analyzed"
    
    # Store correction types for UI publication summary (only issues with suggested corrections)
    correction_types = [issue.issue_type for issue in all_issues if issue.suggested_text is not None]
    st.session_state[f"{article.title}_correction_types"] = correction_types

    # Record analysis in tracker for filtering future retrievals
    # Only record if analysis was successful (no analyzer failures)
    try:
        tracker = get_analyzed_tracker()
        if tracker and not analyzer_failed:  # Only record if no analyzer failed
            # Generate summary - only count issues with suggested corrections
            correction_types = [issue.issue_type for issue in all_issues if issue.suggested_text is not None]
            http_count = correction_types.count("http_link")
            typo_count = len([t for t in correction_types if t != "http_link"])
            logger.info(f"Résumé: http_link={http_count}, typo={typo_count}, total={len(correction_types)}")
            summary = "Correction typographique" if st.session_state.publisher else "Corrections typographiques"
            if st.session_state.publisher:
                summary = st.session_state.publisher.generate_edit_summary(len(correction_types), correction_types)
            
            tracker.record_analysis(
                title=article.title,
                page_id=article.page_id,
                revision_id=article.revision_id,
                status=AnalysisStatus.PENDING,
                mode='regex',
                changes_count=len(all_issues),
                summary=summary,
                corrected_content=corrected
            )
            logger.info(f"Article '{article.title}' recorded in analyzed tracker")
        elif analyzer_failed:
            logger.warning(f"Skipping tracker recording for '{article.title}' due to analyzer failure")
    except Exception as e:
        import traceback
        logger.warning(f"Failed to record analysis in tracker: {e}")
        logger.warning(f"Traceback: {traceback.format_exc()}")

    logger.info(f"=== ANALYSIS SUCCESS === Article: {article.title}, Issues: {len(all_issues)}")
    return True


def main():
    """Main application."""
    
    global _scheduler_instance
    global _automation_orchestrator_instance

    # Initialize published tracker in session state (using cached version)
    if 'published_tracker' not in st.session_state:
        st.session_state.published_tracker = get_cached_published_tracker()
    
    # Initialize analyzed tracker in session state (using cached version)
    if 'analyzed_tracker' not in st.session_state or st.session_state.analyzed_tracker is None:
        st.session_state.analyzed_tracker = get_cached_analyzed_tracker()

    # Sidebar
    from ui.sidebar import render_sidebar
    render_sidebar(
        connect_to_wikipedia_func=connect_to_wikipedia,
        gemini_client_class=GeminiClient,
        scheduler_config_class=SchedulerConfig,
        scheduler_class=Scheduler,
        automation_orchestrator_class=AutomationOrchestrator,
        orchestrator_instance_ref=[_automation_orchestrator_instance],
        scheduler_instance_ref=[_scheduler_instance]
    )
    
    # Article retrieval section (still in sidebar for now)
    _render_article_retrieval_section()
    
    # Overview / navigation
    _render_overview_section()
    
    # AI Analysis History section
    _render_ai_analysis_history()
    
    # Dashboard statistics section
    _render_dashboard_statistics()


def _render_article_retrieval_section():
    """Render article retrieval section in sidebar."""
    st.divider()
    st.subheader("Récupération d'articles")
    
    source_type = option_menu(
        None,
        ["Catégorie", "Manuel", "Contributions", "PetScan", "Fichier"],
        icons=["folder", "list", "user", "search", "file"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal"
    )
    
    lang = st.session_state.connected_lang if st.session_state.connected_lang else "fr"
    
    if source_type == "Catégorie":
        # Use predefined categories
        predefined_categories = get_predefined_categories(lang)
        category_options = list(predefined_categories.values())
        category_options.insert(0, "Autre (personnalisé)")

        # Set default to "Article à wikifier/Liste complète" if available
        default_category = "Article à wikifier/Liste complète"
        default_index = 0
        if default_category in category_options:
            default_index = category_options.index(default_category)

        selected_category = st.selectbox(
            "Catégorie prédéfinie",
            category_options,
            index=default_index,
            help="Sélectionnez une catégorie prédéfinie ou choisissez 'Autre' pour entrer un nom personnalisé"
        )

        if selected_category == "Autre (personnalisé)":
            category_name = st.text_input("Nom de la catégorie personnalisée")
        else:
            category_name = selected_category

        max_articles = st.number_input("Max articles", min_value=1, max_value=1000, value=100, step=1)
        recursive = st.checkbox("Inclure sous-catégories")
        exclude_published = st.checkbox(
            "Exclure les articles publiés récemment (6 mois)",
            value=True,
            help="Évite de récupérer les articles qui ont été publiés depuis moins de 6 mois"
        )
        include_analyzed = st.checkbox(
            "Inclure les articles déjà analysés",
            value=False,
            help="Si coché, inclut également les articles qui ont déjà été analysés (utile pour revoir ou corriger)"
        )

        if st.button("Récupérer", disabled=not category_name):
            retrieve_articles(
                "category",
                category_name=category_name,
                max_articles=int(max_articles),
                recursive=recursive,
                exclude_published=exclude_published,
                include_analyzed=include_analyzed
            )

    elif source_type == "Manuel":
        titles = st.text_area("Titres (un par ligne)", height=150)
        include_analyzed = st.checkbox(
            "Inclure les articles déjà analysés",
            value=False,
            help="Si coché, inclut également les articles qui ont déjà été analysés"
        )
        if st.button("Récupérer"):
            retrieve_articles("manual", titles=titles, include_analyzed=include_analyzed)

    elif source_type == "Contributions":
        username = st.text_input("Nom d'utilisateur")
        max_articles = st.number_input("Max articles", min_value=1, max_value=1000, value=100, step=1)
        include_analyzed = st.checkbox(
            "Inclure les articles déjà analysés",
            value=False,
            help="Si coché, inclut également les articles qui ont déjà été analysés"
        )
        if st.button("Récupérer", disabled=not username):
            retrieve_articles("user_contribs", username=username, max_articles=int(max_articles), include_analyzed=include_analyzed)

    elif source_type == "PetScan":
        psid = st.text_input("PetScan ID")
        include_analyzed = st.checkbox(
            "Inclure les articles déjà analysés",
            value=False,
            help="Si coché, inclut également les articles qui ont déjà été analysés"
        )
        if st.button("Récupérer"):
            retrieve_articles("petscan", psid=psid, include_analyzed=include_analyzed)

    elif source_type == "Fichier":
        file_path = st.text_input("Chemin du fichier")
        include_analyzed = st.checkbox(
            "Inclure les articles déjà analysés",
            value=False,
            help="Si coché, inclut également les articles qui ont déjà été analysés"
        )
        if st.button("Récupérer", disabled=not file_path):
            retrieve_articles("file", file_path=file_path, include_analyzed=include_analyzed)


def _render_overview_section():
    """Render overview and navigation section in sidebar."""
    from ui.issue_groups import STATUS_STYLE
    
    st.divider()
    
    # Overview / navigation
    if st.session_state.articles:
        st.subheader("Vue d'ensemble")
        total = len(st.session_state.articles)
        current_idx = st.session_state.current_article_index

        c1, c2 = st.columns(2)
        c1.metric("Articles chargés", total)
        c2.metric("Position", f"{current_idx + 1}/{total}")
        st.progress((current_idx + 1) / total)

        counts = {}
        for t in st.session_state.articles:
            s = st.session_state.article_status.get(t.title, "pending")
            counts[s] = counts.get(s, 0) + 1
        summary = " · ".join(
            f"{STATUS_STYLE[k]['label']} : {v}" for k, v in counts.items()
        )
        st.caption(summary)


def _render_ai_analysis_history():
    """Render AI analysis history section with filters and search."""
    st.divider()
    st.subheader("📊 Articles analysés par l'IA")
    
    # Initialize analyzed tracker
    try:
        tracker = get_analyzed_tracker()
        all_records = tracker.get_all_records()
        
        if not all_records:
            st.info("Aucun article analysé par l'IA pour le moment.")
            return
        
        # Filters
        with st.expander("🔍 Filtres et recherche", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                status_filter = st.selectbox(
                    "Statut",
                    ["Tous", "Publié", "Refusé", "Ignoré", "En attente", "Erreur"],
                    index=0
                )
            
            with col2:
                mode_filter = st.selectbox(
                    "Mode",
                    ["Tous", "IA", "Regex"],
                    index=0
                )
            
            search_query = st.text_input("Rechercher par titre", placeholder="Entrez un titre d'article...")
            
            date_filter = st.selectbox(
                "Période",
                ["Toutes", "Dernières 24h", "Derniers 7 jours", "Derniers 30 jours"],
                index=0
            )
        
        # Apply filters
        filtered_records = []
        from datetime import datetime, timedelta
        
        now = datetime.now()
        date_cutoff = None
        if date_filter == "Dernières 24h":
            date_cutoff = now - timedelta(days=1)
        elif date_filter == "Derniers 7 jours":
            date_cutoff = now - timedelta(days=7)
        elif date_filter == "Derniers 30 jours":
            date_cutoff = now - timedelta(days=30)
        
        for record in all_records:
            # Status filter
            if status_filter != "Tous":
                status_map = {
                    "Publié": "published",
                    "Refusé": "rejected",
                    "Ignoré": "ignored",
                    "En attente": "pending",
                    "Erreur": "error"
                }
                if record.status != status_map.get(status_filter):
                    continue
            
            # Mode filter
            if mode_filter != "Tous":
                if mode_filter == "IA" and record.mode != "IA":
                    continue
                if mode_filter == "Regex" and record.mode != "regex":
                    continue
            
            # Search filter
            if search_query and search_query.lower() not in record.title.lower():
                continue
            
            # Date filter
            if date_cutoff:
                record_date = datetime.fromisoformat(record.analysis_date)
                if record_date < date_cutoff:
                    continue
            
            filtered_records.append(record)
        
        # Display results
        st.caption(f"Affichage de {len(filtered_records)} / {len(all_records)} articles")
        
        if not filtered_records:
            st.warning("Aucun article ne correspond aux filtres.")
            return
        
        # Create dataframe for display
        import pandas as pd
        
        data = []
        for record in filtered_records:
            analysis_date = datetime.fromisoformat(record.analysis_date)
            data.append({
                "Titre": record.title,
                "Date": analysis_date.strftime("%Y-%m-%d %H:%M"),
                "Mode": record.mode.upper(),
                "Statut": record.status,
                "Décision": record.decision or "-",
                "Changements": record.changes_count or 0,
                "Révision": record.revision_id
            })
        
        df = pd.DataFrame(data)
        
        # Status styling
        def style_status(val):
            color_map = {
                "published": "🟢",
                "rejected": "🔴",
                "ignored": "⏭️",
                "pending": "⏳",
                "error": "❌"
            }
            return f"{color_map.get(val, '')} {val}"
        
        df["Statut"] = df["Statut"].apply(style_status)
        
        st.dataframe(df, width='stretch', hide_index=True)
        
        # Detailed view on click
        selected_title = st.selectbox(
            "Voir les détails d'un article",
            options=[r.title for r in filtered_records],
            format_func=lambda x: x,
            key="ai_history_select"
        )
        
        if selected_title:
            record = next(r for r in filtered_records if r.title == selected_title)
            
            st.divider()
            st.subheader(f"Détails : {record.title}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Page ID", record.page_id)
            with col2:
                st.metric("Révision ID", record.revision_id)
            with col3:
                st.metric("Mode", record.mode.upper())
            
            st.write(f"**Date d'analyse :** {record.analysis_date}")
            st.write(f"**Statut :** {record.status}")
            st.write(f"**Décision :** {record.decision or 'N/A'}")
            st.write(f"**Nombre de changements :** {record.changes_count or 0}")
            st.write(f"**Résumé :** {record.summary or 'N/A'}")
            if record.score:
                st.write(f"**Score IA :** {record.score}")
    
    except Exception as e:
        st.error(f"Erreur lors du chargement de l'historique : {e}")
        logger.error(f"Error loading AI analysis history: {e}", exc_info=True)


def _render_dashboard_statistics():
    """Render dashboard statistics view."""
    st.divider()
    st.subheader("📈 Tableau de bord")
    
    try:
        # Get statistics from analyzed tracker
        tracker = get_analyzed_tracker()
        analyzed_stats = tracker.get_statistics()
        
        # Get statistics from report generator
        from wikipedia_maintenance.utils.automation_report import get_report_generator
        report_gen = get_report_generator()
        report_summary = report_gen.get_reports_summary()
        
        # Display overall metrics
        st.subheader("Statistiques globales")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Articles analysés", analyzed_stats['total'])
        with col2:
            st.metric("Articles publiés", analyzed_stats['published'])
        with col3:
            st.metric("Taux de publication", f"{(analyzed_stats['published'] / analyzed_stats['total'] * 100) if analyzed_stats['total'] > 0 else 0:.1f}%")
        with col4:
            st.metric("Articles rejetés", analyzed_stats['rejected'])
        
        st.divider()
        
        # Display scheduler statistics if available
        st.subheader("Statistiques du scheduler")
        
        # Get scheduler statistics if available
        scheduler_stats = {
            'queue_size': 0,
            'published_today': 0,
            'total_published': 0
        }
        
        # Try to get scheduler from sidebar reference
        if 'scheduler_instance_ref' in st.session_state and st.session_state.scheduler_instance_ref:
            scheduler = st.session_state.scheduler_instance_ref[0]
            if scheduler and hasattr(scheduler, 'state_manager'):
                state = scheduler.state_manager.get_state()
                scheduler_stats['queue_size'] = len(state.queue)
                scheduler_stats['published_today'] = state.daily_published_count
                scheduler_stats['total_published'] = state.statistics.get('total_published', 0)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File d'attente", scheduler_stats['queue_size'])
        with col2:
            st.metric("Publiés aujourd'hui", scheduler_stats['published_today'])
        with col3:
            st.metric("Total publié", scheduler_stats['total_published'])
        
        st.divider()
        
        # Display automation reports summary
        st.subheader("Rapports d'automatisation")
        
        if report_summary['total_reports'] > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total rapports", report_summary['total_reports'])
            with col2:
                st.metric("Total articles analysés (tous rapports)", report_summary['total_articles_analyzed'])
            with col3:
                st.metric("Total articles publiés (tous rapports)", report_summary['total_articles_published'])
            
            if report_summary['total_gemini_cost'] > 0:
                st.metric("Coût total Gemini", f"${report_summary['total_gemini_cost']:.4f}")
            
            # Show latest reports
            with st.expander("📋 Historique des rapports", expanded=False):
                reports = report_gen.get_all_reports()
                if reports:
                    import pandas as pd
                    report_data = []
                    for report in reports[:10]:  # Show last 10 reports
                        from datetime import datetime
                        start = datetime.fromisoformat(report.start_time)
                        report_data.append({
                            "ID": report.report_id,
                            "Date": start.strftime("%Y-%m-%d %H:%M"),
                            "Durée": f"{report.duration_seconds:.1f}s",
                            "Mode": report.mode,
                            "Analysés": report.articles_analyzed,
                            "Publiés": report.articles_published,
                            "Erreurs": report.articles_error
                        })
                    
                    df = pd.DataFrame(report_data)
                    st.dataframe(df, width='stretch', hide_index=True)
        else:
            st.info("Aucun rapport d'automatisation disponible.")
        
        st.divider()
        
        # Display savings metrics
        st.subheader("Économies réalisées")
        
        # Calculate savings from analyzed tracker
        analyzed_savings = analyzed_stats['total'] - analyzed_stats['published'] - analyzed_stats['rejected'] - analyzed_stats['ignored']
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Appels Gemini évités", analyzed_savings)
        with col2:
            st.metric("Articles déjà analysés (réutilisés)", analyzed_stats['pending'])
        
        # Display detailed breakdown
        st.divider()
        st.subheader("Répartition par statut")
        
        status_data = {
            "Publié": analyzed_stats['published'],
            "Rejeté": analyzed_stats['rejected'],
            "Ignoré": analyzed_stats['ignored'],
            "En attente": analyzed_stats['pending'],
            "Erreur": analyzed_stats['error']
        }
        
        # Filter out zero values
        status_data = {k: v for k, v in status_data.items() if v > 0}
        
        if status_data:
            import pandas as pd
            df_status = pd.DataFrame(list(status_data.items()), columns=["Statut", "Nombre"])
            st.bar_chart(df_status.set_index("Statut"))
        else:
            st.info("Aucune donnée disponible.")
    
    except Exception as e:
        st.error(f"Erreur lors du chargement des statistiques : {e}")
        logger.error(f"Error loading dashboard statistics: {e}", exc_info=True)


def _render_overview_section():
    """Render overview and navigation section in sidebar."""
    from ui.issue_groups import STATUS_STYLE
    
    st.divider()
    
    # Overview / navigation
    if st.session_state.articles:
        st.subheader("Vue d'ensemble")
        total = len(st.session_state.articles)
        current_idx = st.session_state.current_article_index

        c1, c2 = st.columns(2)
        c1.metric("Articles chargés", total)
        c2.metric("Position", f"{current_idx + 1}/{total}")
        st.progress((current_idx + 1) / total)

        counts = {}
        for t in st.session_state.articles:
            s = st.session_state.article_status.get(t.title, "pending")
            counts[s] = counts.get(s, 0) + 1
        summary = " · ".join(
            f"{STATUS_STYLE[k]['label']} : {v}" for k, v in counts.items()
        )
        st.caption(summary)

        with st.expander("📋 Liste des articles"):
            titles = [a.title for a in st.session_state.articles]
            
            # Use a unique key to avoid session state conflicts
            selected_index = st.selectbox(
                "Aller à l'article", 
                options=range(total),
                format_func=lambda i: titles[i],
                index=st.session_state.current_article_index,
                key=f"article_select_{total}"
            )
            
            # Update and rerun if selection changed
            if selected_index != st.session_state.current_article_index:
                st.session_state.current_article_index = selected_index
                st.rerun()
            
            st.divider()
            for i, a in enumerate(st.session_state.articles):
                prefix = "➡️ " if i == st.session_state.current_article_index else "　　"
                st.text(f"{prefix} {a.title}")

        if st.button("⚡ Analyser tous les articles non traités"):
            to_process = [a for a in st.session_state.articles if a.title not in st.session_state.issues]
            if not to_process:
                st.info("Tous les articles ont déjà été analysés")
            else:
                progress = st.progress(0.0)
                status_text = st.empty()
                failed = []
                for i, a in enumerate(to_process):
                    status_text.text(f"Analyse de « {a.title} » ({i + 1}/{len(to_process)})...")
                    ok = analyze_article(a, silent=True)
                    if not ok:
                        failed.append(a.title)
                    progress.progress((i + 1) / len(to_process))
                status_text.empty()
                if failed:
                    st.warning(f"{len(failed)} article(s) en erreur : {', '.join(failed)}")
                st.success("Analyse en masse terminée")
                st.rerun()


def main():
    """Main application."""
    
    global _scheduler_instance
    global _automation_orchestrator_instance

    # Initialize published tracker in session state (using cached version)
    if 'published_tracker' not in st.session_state:
        st.session_state.published_tracker = get_cached_published_tracker()
    
    # Initialize analyzed tracker in session state (using cached version)
    if 'analyzed_tracker' not in st.session_state or st.session_state.analyzed_tracker is None:
        st.session_state.analyzed_tracker = get_cached_analyzed_tracker()

    # Sidebar
    from ui.sidebar import render_sidebar
    render_sidebar(
        connect_to_wikipedia_func=connect_to_wikipedia,
        gemini_client_class=GeminiClient,
        scheduler_config_class=SchedulerConfig,
        scheduler_class=Scheduler,
        automation_orchestrator_class=AutomationOrchestrator,
        orchestrator_instance_ref=[_automation_orchestrator_instance],
        scheduler_instance_ref=[_scheduler_instance]
    )
    
    # Article retrieval section (still in sidebar for now)
    _render_article_retrieval_section()
    
    # Overview / navigation
    _render_overview_section()
    
    # Article view (in sidebar, just below "analyser tous les articles")
    if st.session_state.articles:
        article = st.session_state.articles[st.session_state.current_article_index]
        from ui.article_view import render_article_view
        render_article_view(
            article=article,
            analyze_article_func=analyze_article,
            render_word_diff_func=render_word_diff
        )
    
    # AI Analysis History section
    _render_ai_analysis_history()
    
    # Dashboard statistics section
    _render_dashboard_statistics()

    # Main content area
    if not st.session_state.articles:
        st.info("👈 Récupérez des articles depuis le menu latéral pour commencer")
        return


if __name__ == "__main__":
    main()