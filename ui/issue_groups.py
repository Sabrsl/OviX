"""
Issue groups UI module for Wikipedia Maintenance Tool.
Handles grouped display of detected issues by type and severity.
"""

import streamlit as st
from typing import List, Dict, Any

from .theme import COLORS, SPACING
from .components import badge, divider, spacer


# Severity styling constants
SEVERITY_STYLE = {
    "high": {
        "label": "Critique",
        "color": COLORS['severity_critical'],
        "icon": "🔴"
    },
    "medium": {
        "label": "Moyen",
        "color": COLORS['severity_major'],
        "icon": "🟠"
    },
    "low": {
        "label": "Mineur",
        "color": COLORS['severity_minor'],
        "icon": "🟢"
    }
}

STATUS_STYLE = {
    "pending": {"label": "En attente", "icon": "⏳"},
    "analyzed": {"label": "Analysé", "icon": "🔍"},
    "approved": {"label": "Approuvé", "icon": "✅"},
    "published": {"label": "Publié", "icon": "📤"},
    "ignored": {"label": "Ignoré", "icon": "⏭️"},
    "error": {"label": "Erreur", "icon": "❌"}
}


def render_issue_groups(article):
    """
    Render grouped issues display for an article.

    Args:
        article: Current article object.
    """
    # Check if article has been analyzed
    if article.title not in st.session_state.issues:
        st.info("👈 Cliquez sur '🔍 Analyser l'article' pour détecter les problèmes")
        return

    issues = st.session_state.issues[article.title]

    if not issues:
        # Check if article status is approved (corrections applied)
        status = st.session_state.article_status.get(article.title, "pending")
        corrections_applied_key = f"{article.title}_corrections_applied"
        corrections_applied = st.session_state.get(corrections_applied_key, False)

        if status == "approved" and corrections_applied:
            st.success("✅ Corrections appliquées avec succès !")
            _render_publication_section_inline(article)
        else:
            st.success("✅ Aucun problème détecté !")
        return

    st.subheader(f"Problèmes détectés ({len(issues)})")

    # Severity counts
    high_severity = [i for i in issues if i.severity == "high"]
    medium_severity = [i for i in issues if i.severity == "medium"]
    low_severity = [i for i in issues if i.severity == "low"]

    # Display severity metrics
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("🔴 Critiques", len(high_severity))
        c2.metric("🟠 Moyens", len(medium_severity))
        c3.metric("🟢 Mineurs", len(low_severity))

    divider()

    # Select all/none buttons + live selection count
    selected_now = sum(
        1 for i in range(len(issues))
        if st.session_state.get(f"issue_{article.title}_{i}", True)
    )
    select_cols = st.columns([1, 1, 4])
    if select_cols[0].button("☑️ Tout cocher", width='stretch'):
        for i in range(len(issues)):
            st.session_state[f"issue_{article.title}_{i}"] = True
        st.rerun()
    if select_cols[1].button("⬜ Tout décocher", width='stretch'):
        for i in range(len(issues)):
            st.session_state[f"issue_{article.title}_{i}"] = False
        st.rerun()
    with select_cols[2]:
        st.caption(f"{selected_now} / {len(issues)} problème(s) sélectionné(s)")

    # Group issues by type
    _render_grouped_issues(article, issues)


def _render_grouped_issues(article, issues):
    """
    Render issues grouped by type with severity indicators.

    Args:
        article: Current article object.
        issues: List of issue objects.
    """
    SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

    groups = {}  # issue_type -> list of indices (order of first appearance)
    for i, issue in enumerate(issues):
        groups.setdefault(issue.issue_type, []).append(i)

    def group_sort_key(item):
        issue_type, indices = item
        worst_rank = min(SEVERITY_RANK.get(issues[i].severity, 2) for i in indices)
        return (worst_rank, -len(indices))

    sorted_groups = sorted(groups.items(), key=group_sort_key)

    selected_indices = []
    for issue_type, indices in sorted_groups:
        worst_rank = min(SEVERITY_RANK.get(issues[i].severity, 2) for i in indices)
        worst_severity = [s for s, r in SEVERITY_RANK.items() if r == worst_rank][0]
        group_style = SEVERITY_STYLE.get(worst_severity, SEVERITY_STYLE["low"])

        group_selected = sum(
            1 for i in indices
            if st.session_state.get(f"issue_{article.title}_{i}", True)
        )

        with st.expander(
            f"{group_style['icon']} {issue_type} ({group_selected}/{len(indices)}) - {group_style['label']}",
            expanded=False
        ):
            for i in indices:
                issue = issues[i]
                severity_style = SEVERITY_STYLE.get(issue.severity, SEVERITY_STYLE["low"])

                col1, col2 = st.columns([1, 10])

                checkbox_key = f"issue_{article.title}_{i}"
                is_checked = st.session_state.get(checkbox_key, True)

                with col1:
                    checked = st.checkbox(
                        f"Sélectionner : {issue.description}",
                        value=is_checked,
                        key=checkbox_key,
                        label_visibility="collapsed"
                    )
                    if checked:
                        selected_indices.append(i)

                with col2:
                    st.markdown(
                        f"{badge(severity_style['label'], issue.severity, small=True)} "
                        f"**{issue.description}**",
                        unsafe_allow_html=True
                    )

                    if issue.original_text:
                        st.code(issue.original_text, language="None")

                    if issue.suggested_text and issue.suggested_text != issue.original_text:
                        st.markdown(f"→ `{issue.suggested_text}`")

                    spacer(height=SPACING['xs'])

    # Apply corrections button
    divider()
    if selected_indices:
        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                f"✅ Appliquer les {len(selected_indices)} correction(s) sélectionnée(s)",
                type="primary",
                width='stretch',
            ):
                with st.spinner("Application des corrections..."):
                    _apply_selected_corrections(article, issues, selected_indices)

        with col2:
            _render_group_reset_control(article)
    else:
        st.caption("Sélectionnez au moins un problème ci-dessus pour appliquer une correction.")
        _render_group_reset_control(article, width='content')


def _render_group_reset_control(article, width: str = 'stretch'):
    """Two-step confirmation before discarding the current analysis state."""
    confirm_key = f"confirm_group_reset_{article.title}"

    if not st.session_state.get(confirm_key):
        if st.button("🗑️ Réinitialiser", width=width,
                     help="Revient à l'état analysé, la sélection actuelle sera perdue"):
            st.session_state[confirm_key] = True
            st.rerun()
    else:
        st.warning("⚠️ Repartir de l'analyse d'origine ? La sélection en cours sera perdue.", icon="⚠️")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirmer", type="primary", width='stretch', key=f"{confirm_key}_yes"):
                st.session_state.article_status[article.title] = "analyzed"
                st.session_state.pop(f"{article.title}_corrections_applied", None)
                st.session_state.pop(confirm_key, None)
                st.rerun()
        with c2:
            if st.button("Annuler", width='stretch', key=f"{confirm_key}_no"):
                st.session_state.pop(confirm_key, None)
                st.rerun()


def _apply_selected_corrections(article, issues, selected_indices):
    """
    Apply selected corrections to the article.

    Args:
        article: Current article object.
        issues: List of all issues.
        selected_indices: Indices of selected issues to apply.
    """
    selected_issues = [issues[i] for i in selected_indices]

    if not selected_issues:
        st.warning("Aucun problème sélectionné")
        return

    # Use publisher.Corrector (same as manual mode in app.py)
    from wikipedia_maintenance.utils.publisher import Corrector

    # Get the ORIGINAL content from the article, not the corrected_content
    # This ensures we have the true original for diff display
    original_content = article.content if article.content else st.session_state.corrected_content.get(article.title, "")

    if not original_content:
        st.error("Contenu original non disponible")
        return

    # Use publisher.Corrector with apply_corrections (same as manual mode)
    corrector = Corrector(original_content)
    corrected_content = corrector.apply_corrections(issues, selected_indices=selected_indices)

    st.session_state.corrected_content[article.title] = corrected_content
    st.session_state.article_status[article.title] = "approved"
    st.session_state[f"{article.title}_corrections_applied"] = True
    st.session_state[f"{article.title}_original_content"] = original_content

    # Store correction types for auto-generated summary (only issues with suggested corrections)
    correction_types = [issue.issue_type for issue in selected_issues if issue.suggested_text is not None]
    st.session_state[f"{article.title}_correction_types"] = correction_types

    # Remove applied issues from the list
    remaining_issues = [issues[i] for i in range(len(issues)) if i not in selected_indices]
    st.session_state.issues[article.title] = remaining_issues

    st.toast(f"{len(selected_issues)} correction(s) appliquée(s)", icon="✅")
    st.rerun()


def _render_publication_section_inline(article):
    """
    Render publication section inline to avoid circular import.

    Args:
        article: Current article object.
    """
    st.divider()
    st.subheader("📤 Publication")

    # Use article.content directly as original content (most reliable)
    original_content = article.content if article.content else ""
    corrected_content = st.session_state.corrected_content.get(article.title, "")

    # Auto-generate summary based on correction types
    correction_types_key = f"{article.title}_correction_types"
    correction_types = st.session_state.get(correction_types_key, [])
    auto_summary = "Correction typographique"  # default

    if correction_types and st.session_state.publisher:
        auto_summary = st.session_state.publisher.generate_edit_summary(
            corrections_count=len(correction_types),
            correction_types=correction_types
        )

    # Always show diff if we have both contents
    if original_content and corrected_content:
        st.subheader("📝 Corrections appliquées")
        delta = len(corrected_content) - len(original_content)
        delta_label = f"{'+' if delta >= 0 else ''}{delta} caractères"
        st.caption(f"🔴 texte barré = supprimé · 🟢 texte en gras = ajouté  ·  {delta_label}")

        # Import render_word_diff from app.py context
        import difflib
        import html

        def render_word_diff(original: str, corrected: str) -> str:
            """Génère un diff HTML qui préserve la structure wikicode."""
            import re

            def make_urls_clickable(text):
                """Rend les URLs copiables au clic dans le texte."""
                url_pattern = r'https?://[^\s<>"\'\)]+'
                def replace_url(match):
                    url = match.group(0)
                    return f'<span class="copyable-url" onclick="copyToClipboard(this, \'{url}\')" title="Cliquez pour copier">{url}</span>'
                return re.sub(url_pattern, replace_url, text)

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
                        escaped_line = html.escape(line)
                        clickable_line = make_urls_clickable(escaped_line)
                        out_lines.append(f'<span class="wm-diff-ins">{clickable_line}</span>')
                elif tag == "replace":
                    for orig_line, corr_line in zip(orig_lines[i1:i2], corr_lines[j1:j2]):
                        # Simple word-level diff for replaced lines
                        orig_words = orig_line.split()
                        corr_words = corr_line.split()
                        word_matcher = difflib.SequenceMatcher(None, orig_words, corr_words)

                        line_out = []
                        for wtag, wi1, wi2, wj1, wj2 in word_matcher.get_opcodes():
                            if wtag == "equal":
                                line_out.append(html.escape(" ".join(orig_words[wi1:wi2])))
                            elif wtag == "delete":
                                line_out.append(f'<span class="wm-diff-del">{html.escape(" ".join(orig_words[wi1:wi2]))}</span>')
                            elif wtag == "insert":
                                escaped_text = html.escape(" ".join(corr_words[wj1:wj2]))
                                clickable_text = make_urls_clickable(escaped_text)
                                line_out.append(f'<span class="wm-diff-ins">{clickable_text}</span>')
                            elif wtag == "replace":
                                line_out.append(f'<span class="wm-diff-del">{html.escape(" ".join(orig_words[wi1:wi2]))}</span>')
                                escaped_text = html.escape(" ".join(corr_words[wj1:wj2]))
                                clickable_text = make_urls_clickable(escaped_text)
                                line_out.append(f'<span class="wm-diff-ins">{clickable_text}</span>')
                        out_lines.append(" ".join(line_out))

            return '<br>'.join(out_lines)

        with st.container(border=True):
            diff_html = render_word_diff(original_content, corrected_content)
            st.markdown(f'<div class="diff-box">{diff_html}</div>', unsafe_allow_html=True)

        # Extract and display corrected URLs for easy copying
        import re
        corrected_urls = re.findall(r'https?://[^\s<>"\'\)]+', corrected_content)
        if corrected_urls:
            with st.expander("🔗 Liens corrigés (sélectionner pour copier)", expanded=False):
                for url in corrected_urls:
                    st.code(url, language=None)

        # Option to see raw corrected wikicode
        with st.expander("📋 Voir le wikicode corrigé brut", expanded=False):
            st.code(corrected_content, language="None")
    else:
        if not original_content:
            st.warning("⚠️ Contenu original non disponible pour le diff")
        if not corrected_content:
            st.warning("⚠️ Contenu corrigé non disponible")

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

                if not st.session_state.dry_run:
                    mode = "LIA" if st.session_state.lia_mode else "regex"
                    st.session_state.published_tracker.mark_as_published(article.title, category="category", mode=mode)

                st.session_state.articles = [a for a in st.session_state.articles if a.title != article.title]

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
            st.session_state.pop(f"{article.title}_corrections_applied", None)
            st.session_state.pop(f"{article.title}_original_content", None)
            st.rerun()