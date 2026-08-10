"""
Theme configuration for Wikipedia Maintenance Tool.
Defines color palette and global CSS for professional dark theme.
"""

# Color palette (anthracite dark theme)
COLORS = {
    # Backgrounds
    'bg_primary': '#14161a',
    'bg_secondary': '#1c1f26',
    'bg_tertiary': '#2a2e37',
    'bg_card': '#1e2128',
    'bg_hover': '#242832',

    # Text
    'text_primary': '#e8eaed',
    'text_secondary': '#9aa0a6',
    'text_muted': '#6b7280',

    # Accents
    'accent_blue': '#5b8dee',
    'accent_blue_hover': '#4a7bd6',
    'accent_blue_light': 'rgba(91, 141, 238, 0.1)',
    'accent_blue_ring': 'rgba(91, 141, 238, 0.35)',

    # Severity colors
    'severity_critical': '#ef4444',
    'severity_critical_bg': 'rgba(239, 68, 68, 0.15)',
    'severity_major': '#f59e0b',
    'severity_major_bg': 'rgba(245, 158, 11, 0.15)',
    'severity_minor': '#10b981',
    'severity_minor_bg': 'rgba(16, 185, 129, 0.15)',

    # Status colors
    'status_success': '#10b981',
    'status_error': '#ef4444',
    'status_warning': '#f59e0b',
    'status_info': '#3b82f6',

    # Borders
    'border_light': '#2a2e37',
    'border_medium': '#374151',

    # Diff colors
    'diff_del_bg': 'rgba(211, 47, 47, 0.12)',
    'diff_del_text': '#ef4444',
    'diff_ins_bg': 'rgba(46, 125, 50, 0.12)',
    'diff_ins_text': '#10b981',

    # Scrollbar
    'scrollbar_track': '#1c1f26',
    'scrollbar_thumb': '#374151',
    'scrollbar_thumb_hover': '#4b5563',
}

# Typography
FONTS = {
    'sans_serif': '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    'serif': '"Merriweather", Georgia, serif',
    'mono': '"Source Code Pro", "Fira Code", monospace',
}

# Spacing
SPACING = {
    'xs': '0.25rem',
    'sm': '0.5rem',
    'md': '1rem',
    'lg': '1.5rem',
    'xl': '2rem',
}

# Border radius
BORDER_RADIUS = {
    'sm': '4px',
    'md': '6px',
    'lg': '8px',
    'xl': '12px',
}

# Transitions
TRANSITIONS = {
    'fast': '120ms ease',
    'base': '180ms ease',
}


def get_global_css() -> str:
    """
    Generate global CSS for the application.
    Returns CSS string to be injected via st.markdown.
    """
    return f"""
    <style>
    /* Global theme */
    .stApp {{
        background-color: {COLORS['bg_primary']};
        color: {COLORS['text_primary']};
        font-family: {FONTS['sans_serif']};
        font-size: 14px;
    }}

    /* Smooth scrolling + custom scrollbar */
    * {{
        scrollbar-width: thin;
        scrollbar-color: {COLORS['scrollbar_thumb']} {COLORS['scrollbar_track']};
    }}

    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}

    ::-webkit-scrollbar-track {{
        background: {COLORS['scrollbar_track']};
    }}

    ::-webkit-scrollbar-thumb {{
        background-color: {COLORS['scrollbar_thumb']};
        border-radius: {BORDER_RADIUS['sm']};
    }}

    ::-webkit-scrollbar-thumb:hover {{
        background-color: {COLORS['scrollbar_thumb_hover']};
    }}

    /* Typography */
    h1 {{
        font-family: {FONTS['serif']};
        font-size: 1.8rem !important;
        font-weight: 600;
        color: {COLORS['text_primary']};
        margin-bottom: {SPACING['md']};
        letter-spacing: -0.01em;
    }}

    h2 {{
        font-family: {FONTS['sans_serif']};
        font-size: 1.4rem !important;
        font-weight: 600;
        color: {COLORS['text_primary']};
        margin-bottom: {SPACING['sm']};
    }}

    h3 {{
        font-family: {FONTS['sans_serif']};
        font-size: 1.2rem !important;
        font-weight: 500;
        color: {COLORS['text_primary']};
        margin-bottom: {SPACING['xs']};
    }}

    p, span, div {{
        color: {COLORS['text_primary']};
    }}

    /* Sidebar styling (covers current & older Streamlit sidebar selectors) */
    section[data-testid="stSidebar"],
    .css-1d391kg {{
        background-color: {COLORS['bg_secondary']};
        border-right: 1px solid {COLORS['border_light']};
    }}

    section[data-testid="stSidebar"] .block-container {{
        padding-top: {SPACING['lg']};
    }}

    /* Card containers */
    .stContainer {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border_light']};
        border-radius: {BORDER_RADIUS['md']};
        padding: {SPACING['md']};
        transition: border-color {TRANSITIONS['base']};
    }}

    /* Diff box styling */
    .diff-box {{
        font-family: {FONTS['mono']};
        font-size: 0.85em;
        line-height: 1.5;
        padding: {SPACING['md']};
        background-color: {COLORS['bg_secondary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: {BORDER_RADIUS['md']};
        color: {COLORS['text_primary']};
    }}

    .wm-diff-del {{
        text-decoration: line-through;
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border-radius: 2px;
        padding: 0 2px;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }}

    .wm-diff-ins {{
        font-weight: 600;
        background-color: rgba(16, 185, 129, 0.2);
        color: #10b981;
        border-radius: 2px;
        padding: 0 2px;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }}

    /* Status dot (supports a subtle pulse via .status-dot--live) */
    .status-dot {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 5px;
        vertical-align: middle;
    }}

    .status-dot--live {{
        box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6);
        animation: wm-pulse 2s infinite;
    }}

    @keyframes wm-pulse {{
        0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.55); }}
        70% {{ box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
    }}

    /* Buttons */
    .stButton > button {{
        font-size: 13px;
        padding: 0.4rem 1rem;
        border-radius: {BORDER_RADIUS['sm']};
        font-weight: 500;
        transition: background-color {TRANSITIONS['fast']}, border-color {TRANSITIONS['fast']}, transform {TRANSITIONS['fast']};
    }}

    .stButton > button:hover {{
        transform: translateY(-1px);
    }}

    .stButton > button:active {{
        transform: translateY(0);
    }}

    .stButton > button:focus-visible {{
        outline: none;
        box-shadow: 0 0 0 3px {COLORS['accent_blue_ring']};
    }}

    .stButton > button[kind="primary"] {{
        background-color: {COLORS['accent_blue']};
        border: none;
    }}

    .stButton > button[kind="primary"]:hover {{
        background-color: {COLORS['accent_blue_hover']};
    }}

    .stButton > button:disabled {{
        opacity: 0.45;
        transform: none;
    }}

    /* Inputs */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea {{
        font-size: 11px;
        background-color: {COLORS['bg_tertiary']};
        border: 1px solid {COLORS['border_light']};
        color: {COLORS['text_primary']};
        border-radius: {BORDER_RADIUS['sm']};
        transition: border-color {TRANSITIONS['fast']}, box-shadow {TRANSITIONS['fast']};
    }}

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {{
        border-color: {COLORS['accent_blue']};
        box-shadow: 0 0 0 3px {COLORS['accent_blue_ring']};
    }}

    /* Selectbox */
    .stSelectbox > div > div > select,
    .stSelectbox > div > div {{
        font-size: 11px;
        background-color: {COLORS['bg_tertiary']};
        border: 1px solid {COLORS['border_light']};
        color: {COLORS['text_primary']};
        border-radius: {BORDER_RADIUS['sm']};
        transition: border-color {TRANSITIONS['fast']};
    }}

    .stSelectbox > div > div:hover {{
        border-color: {COLORS['border_medium']};
    }}

    /* Checkbox & toggle labels */
    .stCheckbox > label,
    .stToggle > label {{
        font-size: 13px;
        color: {COLORS['text_primary']};
    }}

    /* Info boxes */
    .stAlert {{
        background-color: {COLORS['bg_secondary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: {BORDER_RADIUS['md']};
    }}

    /* Expander */
    .streamlit-expanderHeader,
    [data-testid="stExpander"] summary {{
        font-size: 13px;
        font-weight: 500;
        color: {COLORS['text_primary']};
        border-radius: {BORDER_RADIUS['sm']};
        transition: background-color {TRANSITIONS['fast']};
    }}

    [data-testid="stExpander"] summary:hover {{
        background-color: {COLORS['bg_hover']};
    }}

    [data-testid="stExpander"] {{
        border: 1px solid {COLORS['border_light']};
        border-radius: {BORDER_RADIUS['md']};
        background-color: {COLORS['bg_card']};
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: {SPACING['sm']};
    }}

    .stTabs [data-baseweb="tab"] {{
        background-color: {COLORS['bg_tertiary']};
        border-radius: {BORDER_RADIUS['sm']};
        padding: {SPACING['xs']} {SPACING['sm']};
        font-size: 13px;
        transition: background-color {TRANSITIONS['fast']};
    }}

    .stTabs [data-baseweb="tab"]:hover {{
        background-color: {COLORS['bg_hover']};
    }}

    .stTabs [aria-selected="true"] {{
        background-color: {COLORS['accent_blue_light']};
        color: {COLORS['accent_blue']};
    }}

    /* Container spacing */
    .block-container {{
        padding-top: {SPACING['md']};
        padding-bottom: {SPACING['md']};
    }}

    /* Metrics */
    [data-testid="stMetric"] {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border_light']};
        border-radius: {BORDER_RADIUS['md']};
        padding: {SPACING['sm']} {SPACING['md']};
        transition: border-color {TRANSITIONS['base']};
    }}

    [data-testid="stMetric"]:hover {{
        border-color: {COLORS['border_medium']};
    }}

    [data-testid="stMetricValue"] {{
        font-size: 1.3rem;
    }}

    /* Progress bar */
    .stProgress > div > div > div {{
        background-color: {COLORS['accent_blue']};
        border-radius: {BORDER_RADIUS['sm']};
    }}

    .stProgress > div > div {{
        background-color: {COLORS['bg_tertiary']};
        border-radius: {BORDER_RADIUS['sm']};
    }}

    /* Code blocks */
    .stCode {{
        background-color: {COLORS['bg_tertiary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: {BORDER_RADIUS['sm']};
        font-family: {FONTS['mono']};
        font-size: 0.85em;
    }}

    /* Divider spacing tightened for sidebar density */
    section[data-testid="stSidebar"] hr {{
        margin: {SPACING['sm']} 0;
        border-color: {COLORS['border_light']};
    }}

    /* Focus ring reset for accessibility across interactive elements */
    a:focus-visible,
    button:focus-visible,
    input:focus-visible,
    select:focus-visible {{
        outline: none;
        box-shadow: 0 0 0 3px {COLORS['accent_blue_ring']};
    }}
    </style>
    """


def apply_theme():
    """Apply the global theme to the Streamlit app."""
    import streamlit as st
    st.markdown(get_global_css(), unsafe_allow_html=True)