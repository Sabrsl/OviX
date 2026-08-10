"""
Reusable UI components for Wikipedia Maintenance Tool.
Contains badges, status pills, cards, and other visual elements.
"""

import streamlit as st
from typing import Optional, Dict, Any
from .theme import COLORS, BORDER_RADIUS, SPACING


def status_dot(color: str) -> str:
    """
    Generate a status dot HTML.
    
    Args:
        color: CSS color for the dot.
    
    Returns:
        HTML string for the status dot.
    """
    return f'<span class="status-dot" style="background-color: {color};"></span>'


def badge(text: str, severity: str = "info", small: bool = False) -> str:
    """
    Generate a badge HTML.
    
    Args:
        text: Badge text.
        severity: Severity level (critical, major, minor, info, success, warning, error).
        small: Whether to make the badge smaller.
    
    Returns:
        HTML string for the badge.
    """
    severity_colors = {
        'critical': COLORS['severity_critical'],
        'major': COLORS['severity_major'],
        'minor': COLORS['severity_minor'],
        'info': COLORS['status_info'],
        'success': COLORS['status_success'],
        'warning': COLORS['status_warning'],
        'error': COLORS['status_error'],
    }
    
    bg_colors = {
        'critical': COLORS['severity_critical_bg'],
        'major': COLORS['severity_major_bg'],
        'minor': COLORS['severity_minor_bg'],
        'info': 'rgba(59, 130, 246, 0.15)',
        'success': 'rgba(16, 185, 129, 0.15)',
        'warning': 'rgba(245, 158, 11, 0.15)',
        'error': 'rgba(239, 68, 68, 0.15)',
    }
    
    color = severity_colors.get(severity, COLORS['status_info'])
    bg_color = bg_colors.get(severity, 'rgba(59, 130, 246, 0.15)')
    font_size = '11px' if small else '12px'
    padding = '2px 6px' if small else '4px 8px'
    
    return f'''
    <span style="
        display: inline-flex;
        align-items: center;
        background-color: {bg_color};
        color: {color};
        font-size: {font_size};
        font-weight: 600;
        padding: {padding};
        border-radius: {BORDER_RADIUS['sm']};
        border: 1px solid {color};
    ">
        {text}
    </span>
    '''


def status_pill(text: str, status: str = "pending") -> str:
    """
    Generate a status pill HTML.
    
    Args:
        text: Pill text.
        status: Status type (pending, analyzed, approved, published, ignored).
    
    Returns:
        HTML string for the status pill.
    """
    status_colors = {
        'pending': COLORS['text_muted'],
        'analyzed': COLORS['status_info'],
        'approved': COLORS['accent_blue'],
        'published': COLORS['status_success'],
        'ignored': COLORS['text_muted'],
    }
    
    bg_colors = {
        'pending': 'rgba(107, 114, 128, 0.15)',
        'analyzed': 'rgba(59, 130, 246, 0.15)',
        'approved': COLORS['accent_blue_light'],
        'published': COLORS['severity_minor_bg'],
        'ignored': 'rgba(107, 114, 128, 0.15)',
    }
    
    color = status_colors.get(status, COLORS['text_muted'])
    bg_color = bg_colors.get(status, 'rgba(107, 114, 128, 0.15)')
    
    return f'''
    <span style="
        display: inline-flex;
        align-items: center;
        background-color: {bg_color};
        color: {color};
        font-size: 12px;
        font-weight: 500;
        padding: 4px 10px;
        border-radius: {BORDER_RADIUS['md']};
    ">
        {status_dot(color)}
        {text}
    </span>
    '''


def metric_card(title: str, value: str, delta: Optional[str] = None, help_text: Optional[str] = None) -> None:
    """
    Display a metric card with title, value, and optional delta.
    
    Args:
        title: Card title.
        value: Main value to display.
        delta: Optional delta/change text.
        help_text: Optional help tooltip text.
    """
    st.markdown(f"""
    <div style="
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border_light']};
        border-radius: {BORDER_RADIUS['md']};
        padding: {SPACING['md']};
        margin-bottom: {SPACING['sm']};
    ">
        <div style="
            font-size: 11px;
            color: {COLORS['text_secondary']};
            font-weight: 500;
            margin-bottom: {SPACING['xs']};
        ">
            {title}
        </div>
        <div style="
            font-size: 24px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        ">
            {value}
        </div>
        {f'<div style="font-size: 12px; color: {COLORS["status_success"]}; margin-top: {SPACING["xs"]};">{delta}</div>' if delta else ''}
    </div>
    """, unsafe_allow_html=True)
    
    if help_text:
        st.caption(help_text)


def info_box(message: str, severity: str = "info") -> None:
    """
    Display an info box with severity styling.
    
    Args:
        message: Message to display.
        severity: Severity level (info, success, warning, error).
    """
    severity_colors = {
        'info': COLORS['status_info'],
        'success': COLORS['status_success'],
        'warning': COLORS['status_warning'],
        'error': COLORS['status_error'],
    }
    
    bg_colors = {
        'info': 'rgba(59, 130, 246, 0.1)',
        'success': 'rgba(16, 185, 129, 0.1)',
        'warning': 'rgba(245, 158, 11, 0.1)',
        'error': 'rgba(239, 68, 68, 0.1)',
    }
    
    border_colors = {
        'info': 'rgba(59, 130, 246, 0.3)',
        'success': 'rgba(16, 185, 129, 0.3)',
        'warning': 'rgba(245, 158, 11, 0.3)',
        'error': 'rgba(239, 68, 68, 0.3)',
    }
    
    color = severity_colors.get(severity, COLORS['status_info'])
    bg_color = bg_colors.get(severity, 'rgba(59, 130, 246, 0.1)')
    border_color = border_colors.get(severity, 'rgba(59, 130, 246, 0.3)')
    
    st.markdown(f"""
    <div style="
        background-color: {bg_color};
        border: 1px solid {border_color};
        border-radius: {BORDER_RADIUS['md']};
        padding: {SPACING['md']};
        margin-bottom: {SPACING['md']};
    ">
        <div style="
            display: flex;
            align-items: center;
            gap: {SPACING['sm']};
        ">
            {status_dot(color)}
            <span style="
                color: {color};
                font-size: 13px;
                font-weight: 500;
            ">
                {message}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def article_header(title: str, url: str, status: str = "pending") -> None:
    """
    Display an article header with title, link, and status.
    
    Args:
        title: Article title.
        url: Article URL.
        status: Article status.
    """
    st.markdown(f"""
    <div style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: {SPACING['md']};
        border-bottom: 1px solid {COLORS['border_light']};
        margin-bottom: {SPACING['md']};
    ">
        <div>
            <h2 style="margin: 0; font-size: 1.3rem;">{title}</h2>
            <a href="{url}" target="_blank" style="
                color: {COLORS['accent_blue']};
                text-decoration: none;
                font-size: 12px;
                opacity: 0.8;
            ">
                Voir sur Wikipédia →
            </a>
        </div>
        {status_pill(status.title(), status)}
    </div>
    """, unsafe_allow_html=True)


def divider() -> None:
    """Display a styled divider."""
    st.markdown(f'<div style="border-top: 1px solid {COLORS["border_light"]}; margin: {SPACING["lg"]} 0;"></div>', unsafe_allow_html=True)


def spacer(height: str = "1rem") -> None:
    """
    Add vertical spacing.
    
    Args:
        height: CSS height value.
    """
    st.markdown(f'<div style="height: {height};"></div>', unsafe_allow_html=True)


def render_severity_badge(severity: str) -> str:
    """
    Render a severity badge for issues.
    
    Args:
        severity: Severity level (critical, major, minor).
    
    Returns:
        HTML string for the badge.
    """
    severity_labels = {
        'critical': 'Critique',
        'major': 'Moyen',
        'minor': 'Mineur',
    }
    
    label = severity_labels.get(severity, severity.title())
    return badge(label, severity, small=True)
