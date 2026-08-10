"""
Article view UI module for Wikipedia Maintenance Tool.
Handles article display, navigation, diff rendering, and publication.
"""

import streamlit as st
from typing import Optional, Dict, Any, List

from .theme import COLORS, SPACING
from .components import article_header, status_pill, divider, spacer


def render_article_view(
    article,
    analyze_article_func,
    render_word_diff_func
):
    """
    Render the main article view with navigation, analysis, and diff.

    Args:
        article: Current article object.
        analyze_article_func: Function to analyze article.
        render_word_diff_func: Function to render word diff.
    """
    # Article navigation
    _render_article_navigation(article)

    # Check if article is already analyzed with corrected content
    is_already_analyzed = article.title in st.session_state.corrected_content
    
    # If already analyzed, show corrected content directly
    if is_already_analyzed:
        _render_already_analyzed_content(article, render_word_diff_func)
        return

    # Analyze button
    if _render_analyze_button(article, analyze_article_func):
        return

    # LIA mode diff
    if st.session_state.lia_mode and article.title in st.session_state.lia_corrected_content:
        _render_lia_diff(article, render_word_diff_func)
        return

    # Regex mode issues - always show issue groups even if empty
    from .issue_groups import render_issue_groups
    render_issue_groups(article)

    # Action buttons at bottom (for all modes) - but NOT publication section (handled in issue_groups)
    _render_action_buttons(article)


# ---------------------------------------------------------------------------
# Navigation & header
# ---------------------------------------------------------------------------

_STATUS_LABELS = {
    "pending": "En attente",
    "analyzed": "Analysé",
    "approved": "Prêt à publier",
    "ignored": "Ignoré",
    "published": "Publié",
}


def _render_article_navigation(article):
    """Render article navigation header."""
    total = len(st.session_state.articles)
    current = st.session_state.current_article_index

    col1, col2, col3 = st.columns([1, 6, 1])

    with col1:
        if st.button(
            "⬅️ Précédent",
            disabled=current == 0,
            width='stretch',
            help="Article précédent",
        ):
            st.session_state.current_article_index -= 1
            st.session_state.manual_edit_mode = False
            st.session_state.confirm_publish = False
            _reset_confirm_flag(article.title)
            st.rerun()

    with col2:
        st.header(f"📄 {article.title}")
        meta_cols = st.columns([2, 2, 3])
        with meta_cols[0]:
            status = st.session_state.article_status.get(article.title, "pending")
            st.markdown(
                status_pill(_STATUS_LABELS.get(status, status.title()), status),
                unsafe_allow_html=True,
            )
        with meta_cols[1]:
            if st.session_state.lia_mode:
                st.caption("🤖 Mode IA")
            else:
                st.caption("🔧 Mode règles")
        with meta_cols[2]:
            if article.url:
                st.markdown(f"[↗ Voir sur Wikipédia]({article.url})")

        # Progress through the article queue
        if total > 0:
            st.progress(
                (current + 1) / total,
                text=f"Article {current + 1} sur {total}",
            )

    with col3:
        if st.button(
            "Suivant ➡️",
            disabled=current == total - 1,
            width='stretch',
            help="Article suivant",
        ):
            st.session_state.current_article_index += 1
            st.session_state.manual_edit_mode = False
            st.session_state.confirm_publish = False
            _reset_confirm_flag(article.title)
            st.rerun()

    # Fetch and display character count if not already available
    if not article.content and st.session_state.site:
        try:
            import pywikibot
            with st.spinner("Chargement de l'article..."):
                page = pywikibot.Page(st.session_state.site, article.title)
                if page.exists():
                    content = page.get()
                    article.content = content
                    st.caption(f"📏 {len(content):,} caractères".replace(",", " "))
                else:
                    st.caption("⚠️ Article inexistant")
        except Exception as e:
            st.caption(f"⚠️ Erreur de chargement : {str(e)[:80]}")
    elif article.content:
        st.caption(f"📏 {len(article.content):,} caractères".replace(",", " "))
    elif article.title in st.session_state.corrected_content:
        st.caption(f"📏 {len(st.session_state.corrected_content[article.title]):,} caractères".replace(",", " "))
    else:
        st.caption("📏 Chargement...")

    divider()


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _render_analyze_button(article, analyze_article_func) -> bool:
    """
    Render analyze button if article hasn't been analyzed yet.

    Args:
        article: Current article object.
        analyze_article_func: Function to analyze article.

    Returns:
        True if analyze button was shown and clicked, False otherwise.
    """
    # Check if article is already analyzed (has corrected content)
    is_already_analyzed = article.title in st.session_state.corrected_content
    
    # In LIA mode, also check if it has LIA corrected content
    if st.session_state.lia_mode:
        is_already_analyzed = is_already_analyzed or article.title in st.session_state.lia_corrected_content
    
    # Check if article has issues (regex mode)
    has_issues = article.title in st.session_state.issues
    
    can_analyze = not is_already_analyzed and not has_issues

    if can_analyze:
        st.info("Cet article n'a pas encore été analysé.", icon="ℹ️")
        if st.button("🔍 Analyser l'article", type="primary", width='stretch'):
            with st.spinner("Analyse en cours..."):
                # Check if client is initialized for IA mode
                if st.session_state.lia_mode and not st.session_state.lia_client:
                    st.error("❌ Client IA non initialisé. Vérifiez les variables d'environnement.")
                    return True

                analyze_article_func(article)
            st.rerun()
        return True
    elif is_already_analyzed:
        # Article already analyzed, show message and skip to review
        st.info("✅ Cet article a déjà été analysé et est prêt pour publication.", icon="✅")
        return False
    return False


# ---------------------------------------------------------------------------
# Already analyzed content
# ---------------------------------------------------------------------------

def _render_already_analyzed_content(article, render_word_diff_func):
    """
    Render content for articles that have already been analyzed with corrected content.
    
    Args:
        article: Current article object.
        render_word_diff_func: Function to render word diff.
    """
    st.subheader("✅ Article déjà analysé")
    
    corrected = st.session_state.corrected_content[article.title]
    
    # Try to get original content for diff if available
    original = article.content if article.content else ""
    
    # Always show diff if we have issues detected, regardless of content similarity
    has_issues = article.title in st.session_state.issues and len(st.session_state.issues[article.title]) > 0
    
    if original and has_issues:
        # Show diff if we have both original and corrected
        delta = len(corrected) - len(original)
        delta_label = f"{'+' if delta >= 0 else ''}{delta} caractères"
        st.caption(f"🔴 texte barré = supprimé · 🟢 texte en gras = ajouté  ·  {delta_label}")
        
        with st.container(border=True):
            diff_html = render_word_diff_func(original, corrected)
            st.markdown(f'<div class="diff-box">{diff_html}</div>', unsafe_allow_html=True)
    else:
        # Just show corrected content if no original available or no issues
        st.caption(f"📏 {len(corrected):,} caractères (contenu corrigé)".replace(",", " "))
        
        with st.expander("📋 Voir le wikicode corrigé", expanded=True):
            st.code(corrected, language="None")
    
    # Publication buttons
    _render_publication_buttons_for_analyzed(article, corrected)


def _render_publication_buttons_for_analyzed(article, corrected):
    """
    Render publication buttons for already analyzed articles.
    
    Args:
        article: Current article object.
        corrected: Corrected content string.
    """
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Publier", type="primary", width='stretch'):
            st.session_state.article_status[article.title] = "approved"
            st.toast(f"Prêt pour « {article.title} »", icon="✅")
            st.rerun()

    with col2:
        if st.button("❌ Ignorer", width='stretch'):
            st.session_state.article_status[article.title] = "ignored"
            st.toast(f"Article « {article.title} » ignoré", icon="ℹ️")
            st.rerun()

    with col3:
        if st.button("🔄 Réanalyser", width='stretch'):
            # Clear the corrected content to allow re-analysis
            if article.title in st.session_state.corrected_content:
                del st.session_state.corrected_content[article.title]
            if article.title in st.session_state.lia_corrected_content:
                del st.session_state.lia_corrected_content[article.title]
            st.session_state.article_status[article.title] = "pending"
            st.toast(f"Réinitialisation de « {article.title} »", icon="🔄")
            st.rerun()

    # Publication section if approved
    if st.session_state.article_status[article.title] == "approved":
        _render_publication_section(article)


# ---------------------------------------------------------------------------
# LIA (AI) mode
# ---------------------------------------------------------------------------

def _render_lia_diff(article, render_word_diff_func):
    """
    Render LIA mode diff between original and corrected content.

    Args:
        article: Current article object.
        render_word_diff_func: Function to render word diff.
    """
    st.subheader("🤖 Correction par IA")
    original = article.content if article.content else st.session_state.corrected_content[article.title]
    corrected = st.session_state.lia_corrected_content[article.title]

    delta = len(corrected) - len(original)
    delta_label = f"{'+' if delta >= 0 else ''}{delta} caractères"
    st.caption(f"🔴 texte barré = supprimé · 🟢 texte en gras = ajouté  ·  {delta_label}")

    with st.container(border=True):
        diff_html = render_word_diff_func(original, corrected)
        st.markdown(f'<div class="diff-box">{diff_html}</div>', unsafe_allow_html=True)

    # Option pour afficher le wikicode brut corrigé
    with st.expander("📋 Voir le wikicode corrigé brut", expanded=False):
        st.code(corrected, language="None")

    # Publication buttons for LIA mode
    _render_lia_publication_buttons(article, corrected)


def _render_lia_publication_buttons(article, corrected):
    """
    Render publication buttons for LIA mode.

    Args:
        article: Current article object.
        corrected: Corrected content string.
    """
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Publier", type="primary", width='stretch'):
            # Store the LIA-corrected content as the final corrected content
            st.session_state.corrected_content[article.title] = corrected
            st.session_state.article_status[article.title] = "approved"
            st.toast(f"Prêt pour « {article.title} »", icon="✅")
            st.rerun()

    with col2:
        if st.button("❌ Ignorer", width='stretch'):
            st.session_state.article_status[article.title] = "ignored"
            st.toast(f"Article « {article.title} » ignoré", icon="ℹ️")
            st.rerun()

    with col3:
        if st.button("🔄 Réanalyser", width='stretch', help="Supprime le résultat courant pour relancer l'analyse"):
            del st.session_state.issues[article.title]
            del st.session_state.lia_corrected_content[article.title]
            st.session_state.article_status[article.title] = "pending"
            st.rerun()

    # Publication section for LIA mode (same as regex mode)
    if st.session_state.article_status[article.title] == "approved":
        _render_publication_section(article)


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------

def _render_publication_section(article):
    """
    Render publication section with summary input and publish button.

    Args:
        article: Current article object.
    """
    st.divider()
    st.subheader("📤 Publication")

    with st.container(border=True):
        # Auto-generate summary based on correction types (same as regex mode)
        correction_types_key = f"{article.title}_correction_types"
        correction_types = st.session_state.get(correction_types_key, [])
        
        # Use the edit_summaries module for random summary
        from wikipedia_maintenance.utils.edit_summaries import get_random_summary
        auto_summary = get_random_summary()

        if correction_types and st.session_state.publisher:
            auto_summary = st.session_state.publisher.generate_edit_summary(
                num_corrections=len(correction_types),
                correction_types=correction_types
            )

        summary_input = st.text_input(
            "Résumé de modification",
            value=auto_summary,
            help="Résumé qui apparaîtra dans l'historique de l'article (généré automatiquement selon les corrections)",
            key=f"summary_input_{article.title}"
        )

        if st.session_state.dry_run:
            st.caption("🧪 Mode simulation actif — aucune modification ne sera réellement publiée.")

        summary_ready = bool(summary_input.strip())
        if not summary_ready:
            st.caption("⚠️ Le résumé de modification ne peut pas être vide.")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "📤 Publier sur Wikipédia",
                type="primary",
                width='stretch',
                disabled=not summary_ready,
            ):
                with st.spinner("Publication en cours..."):
                    success, message = st.session_state.publisher.publish(
                        page_title=article.title,
                        content=st.session_state.corrected_content[article.title],
                        summary=summary_input,
                        minor=True
                    )

                if success:
                    st.success(f"✅ {message}")
                    st.session_state.article_status[article.title] = "published"

                    # Mark article as published in tracker
                    if not st.session_state.dry_run:
                        mode = "LIA" if st.session_state.lia_mode else "regex"
                        st.session_state.published_tracker.mark_as_published(article.title, category="category", mode=mode)

                    # Remove article from the list to avoid reprocessing
                    st.session_state.articles = [a for a in st.session_state.articles if a.title != article.title]

                    # Move to next article if available
                    if st.session_state.articles:
                        st.session_state.current_article_index = min(st.session_state.current_article_index, len(st.session_state.articles) - 1)
                        st.rerun()
                    else:
                        st.balloons()
                        st.info("🎉 Tous les articles ont été traités !")
                else:
                    st.error(f"❌ {message}")

        with col2:
            if st.button("🗑️ Annuler", width='stretch'):
                st.session_state.article_status[article.title] = "analyzed"
                st.rerun()


# ---------------------------------------------------------------------------
# Bottom action bar / manual edit
# ---------------------------------------------------------------------------

def _reset_confirm_flag(article_title: str):
    """Clear any pending 'confirm reset' state for an article."""
    st.session_state.pop(f"confirm_reset_{article_title}", None)


def _render_action_buttons(article):
    """
    Render action buttons at the bottom of the article view.

    Args:
        article: Current article object.
    """
    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("✅ Publier", type="primary", use_container_width=True):
            st.session_state.article_status[article.title] = "approved"
            st.toast(f"Prêt pour publication de « {article.title} »", icon="✅")
            st.rerun()

    with col2:
        if st.button("❌ Ignorer", use_container_width=True):
            st.session_state.article_status[article.title] = "ignored"
            st.toast(f"Article « {article.title} » ignoré", icon="ℹ️")
            st.rerun()

    with col3:
        if st.button("✏️ Édition manuelle", use_container_width=True):
            st.session_state.manual_edit_mode = True
            st.rerun()

    with col4:
        confirm_key = f"confirm_reset_{article.title}"
        if st.button("🔄 Réinitialiser", use_container_width=True, help="Efface l'analyse et les corrections de cet article"):
            st.session_state[confirm_key] = True
            st.rerun()

    # Two-step confirmation before wiping analysis/corrections for this article
    if st.session_state.get(f"confirm_reset_{article.title}"):
        st.warning(
            f"⚠️ Réinitialiser « {article.title} » effacera l'analyse et toute correction en cours. "
            "Cette action est irréversible.",
            icon="⚠️",
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirmer la réinitialisation", type="primary", use_container_width=True, key=f"confirm_reset_yes_{article.title}"):
                if article.title in st.session_state.issues:
                    del st.session_state.issues[article.title]
                if article.title in st.session_state.corrected_content:
                    del st.session_state.corrected_content[article.title]
                if article.title in st.session_state.lia_corrected_content:
                    del st.session_state.lia_corrected_content[article.title]
                st.session_state.article_status[article.title] = "pending"
                _reset_confirm_flag(article.title)
                st.rerun()
        with c2:
            if st.button("Annuler", use_container_width=True, key=f"confirm_reset_no_{article.title}"):
                _reset_confirm_flag(article.title)
                st.rerun()

    # Manual edit mode
    if st.session_state.manual_edit_mode:
        st.divider()
        st.subheader("✏️ Édition manuelle")
        # Use article.content if no corrected content exists yet
        current_content = st.session_state.corrected_content.get(article.title, article.content if article.content else "")
        edited_content = st.text_area(
            "Modifier le contenu",
            value=current_content,
            height=300,
            key=f"manual_edit_{article.title}",
        )
        st.caption(f"📏 {len(edited_content):,} caractères".replace(",", " "))

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Sauvegarder les modifications", type="primary", use_container_width=True):
                st.session_state.corrected_content[article.title] = edited_content
                st.session_state.article_status[article.title] = "approved"
                st.session_state.manual_edit_mode = False
                st.toast("Modifications sauvegardées", icon="💾")
                st.rerun()
        with c2:
            if st.button("❌ Annuler l'édition", use_container_width=True):
                st.session_state.manual_edit_mode = False
                st.rerun()