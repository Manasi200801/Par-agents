"""Compass Streamlit application shell.

This file owns only the shared page configuration, global styling, the single
Compass header, top-right workspace navigation, and routing between views.
"""
from __future__ import annotations

import os
import sys

# Ensure the project root (Par-agents/) is on sys.path so that
# `from app.views.X import ...` works regardless of which directory
# Streamlit adds to sys.path when executing this script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from app.views.live_decision import render as render_live_decision
from app.views.replay_dashboard import render as render_replay_dashboard


st.set_page_config(
    page_title="Compass — Decision Intelligence",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# -----------------------------------------------------------------------------
# Theme CSS — injected first so all subsequent CSS can use these variables
# -----------------------------------------------------------------------------
DARK_VARS_CSS = """
<style>
:root {
    --bg: #07111d;
    --surface: #0f1828;
    --surface-2: #131e30;
    --border: #243247;
    --text: #f2f5f9;
    --muted: #91a0b5;
    --cyan: #5bd7f2;
    --violet: #a989ff;
    --green: #55dda4;
    --amber: #ffbd63;
}
</style>
"""

LIGHT_VARS_CSS = """
<style>
:root {
    --bg: #f4f7fc;
    --surface: #ffffff;
    --surface-2: #edf1f8;
    --border: #cdd8ea;
    --text: #0d1b2e;
    --muted: #4d6278;
    --cyan: #0891b2;
    --violet: #6d28d9;
    --green: #059669;
    --amber: #b45309;
}
</style>
"""

# Static chrome CSS — uses CSS variables, no Python format() needed.
COMPASS_STATIC_CSS = """
<style>
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background: var(--bg) !important;
        color: var(--text) !important;
    }

    .stApp {
        background:
            radial-gradient(900px 520px at 8% -12%, rgba(63, 104, 180, .20), transparent 60%),
            var(--bg) !important;
    }

    section[data-testid="stSidebar"],
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    .block-container {
        max-width: 1460px;
        padding-top: 1.35rem;
        padding-bottom: 2.5rem;
    }

    h1, h2, h3, h4 {
        color: var(--text) !important;
        letter-spacing: -.015em;
    }

    .brand-shell {
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 58px;
    }

    .brand-logo {
        width: 50px;
        height: 50px;
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        background: linear-gradient(135deg, var(--cyan), #7ca8ff);
        box-shadow: 0 12px 35px rgba(91, 215, 242, .20);
    }

    .brand-title {
        color: var(--text);
        font-size: 1.55rem;
        font-weight: 850;
        line-height: 1;
    }

    .brand-subtitle {
        color: var(--muted);
        font-size: .72rem;
        margin-top: .34rem;
    }

    .top-divider {
        height: 1px;
        margin: .85rem 0 1.35rem;
        background: var(--border);
    }

    .api-status {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: .63rem;
        font-weight: 700;
        letter-spacing: .07em;
        text-transform: uppercase;
        padding: .18rem .55rem;
        border-radius: 999px;
        margin-left: .5rem;
        vertical-align: middle;
    }
    .api-status.live {
        color: var(--green);
        background: rgba(85,221,164,.10);
        border: 1px solid rgba(85,221,164,.25);
    }
    .api-status.demo {
        color: var(--amber);
        background: rgba(255,189,99,.10);
        border: 1px solid rgba(255,189,99,.25);
    }

    div[data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 14px 16px;
    }

    div[data-testid="stRadio"] > label {
        color: var(--muted) !important;
        font-size: .68rem !important;
        font-weight: 800 !important;
        letter-spacing: .09em;
        text-transform: uppercase;
    }

    div[data-testid="stRadio"] [role="radiogroup"] {
        justify-content: flex-end;
        gap: .4rem;
    }

    div[data-testid="stRadio"] [role="radiogroup"] label {
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: .38rem .7rem;
        background: rgba(255,255,255,.025);
    }

    #MainMenu,
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    [data-testid="stAppDeployButton"],
    [data-testid="stToolbarActions"],
    .stDeployButton {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }
</style>
"""

# Light-mode overrides for view-level hardcoded dark colours.
LIGHT_VIEW_OVERRIDES = """
<style>
    /* ── Live Decision view ── */
    .hero {
        background:
            radial-gradient(circle at 88% 10%, rgba(109,40,217,.08), transparent 30%),
            linear-gradient(145deg, #ffffff, #f0f5ff) !important;
        border-color: rgba(99,131,179,.2) !important;
        box-shadow: 0 8px 28px rgba(0,0,0,.07) !important;
    }
    .hero-title { color: #0d1b2e !important; }
    .hero-copy, .muted-copy { color: #4d6278 !important; }
    .eyebrow { color: #0891b2 !important; }
    .context-box, .glass-card, .signal-card, .passport-card, .recommendation-card {
        background: linear-gradient(145deg, #ffffff, #f5f8ff) !important;
        border-color: rgba(99,131,179,.2) !important;
        box-shadow: 0 4px 18px rgba(0,0,0,.07) !important;
    }
    .forecast-card {
        background:
            radial-gradient(circle at 90% 8%, rgba(8,145,178,.08), transparent 34%),
            linear-gradient(150deg, #f0faff, #e8f5fd) !important;
        border-color: rgba(8,145,178,.22) !important;
        box-shadow: 0 6px 24px rgba(0,0,0,.07) !important;
    }
    .forecast-heading { color: #0d1b2e !important; }
    .forecast-badge {
        color: #0891b2 !important;
        background: rgba(8,145,178,.08) !important;
        border-color: rgba(8,145,178,.25) !important;
    }
    .forecast-number { color: #0891b2 !important; text-shadow: none !important; }
    .forecast-unit { color: #4d6278 !important; }
    .forecast-message { color: #3d5570 !important; }
    .forecast-mini {
        background: rgba(0,0,0,.03) !important;
        border-color: rgba(99,131,179,.18) !important;
    }
    .forecast-mini-label { color: #4d6278 !important; }
    .forecast-mini-value { color: #0d1b2e !important; }
    .forecast-mini-note { color: #5a7090 !important; }
    .context-label, .value-label { color: #4d6278 !important; }
    .context-value { color: #0d1b2e !important; }
    .card-title { color: #0d1b2e !important; }
    .card-copy { color: #4d6278 !important; }
    .machine { color: #0891b2 !important; }
    .planner { color: #b45309 !important; }
    .compass { color: #6d28d9 !important; }
    .positive { color: #059669 !important; }
    .negative { color: #dc2626 !important; }
    .signal-card.support-card {
        background:
            radial-gradient(circle at 92% 8%, rgba(5,150,105,.1), transparent 34%),
            linear-gradient(145deg, #f0fff8, #e8fff4) !important;
        border-color: rgba(5,150,105,.28) !important;
    }
    .signal-card.challenge-card {
        background:
            radial-gradient(circle at 92% 7%, rgba(220,38,38,.12), transparent 37%),
            linear-gradient(145deg, #fff5f5, #ffeaea) !important;
        border-color: rgba(220,38,38,.35) !important;
    }
    .signal-card.challenge-card::before {
        background: linear-gradient(#dc2626, #ef4444) !important;
    }
    .signal-card.neutral-card {
        background:
            radial-gradient(circle at 92% 8%, rgba(8,145,178,.1), transparent 34%),
            linear-gradient(145deg, #f0f8ff, #e8f3ff) !important;
        border-color: rgba(8,145,178,.25) !important;
    }
    .signal-icon { background: rgba(0,0,0,.04) !important; }
    .signal-name { color: #0d1b2e !important; }
    .signal-summary { color: #4d6278 !important; }
    .signal-claim { color: #1e3a52 !important; }
    .signal-friendly-meta { color: #5a7090 !important; border-color: rgba(99,131,179,.18) !important; }
    .support { color: #059669 !important; border-color: rgba(5,150,105,.28) !important; }
    .challenge { color: #dc2626 !important; border-color: rgba(220,38,38,.35) !important; }
    .neutral { color: #0891b2 !important; border-color: rgba(8,145,178,.28) !important; }
    .recommendation-card {
        background:
            radial-gradient(circle at 78% 20%, rgba(109,40,217,.08), transparent 36%),
            linear-gradient(145deg, #faf8ff, #f3eeff) !important;
        border-color: rgba(109,40,217,.25) !important;
    }
    .passport-card {
        background:
            radial-gradient(circle at 88% 12%, rgba(5,150,105,.08), transparent 30%),
            linear-gradient(145deg, #f0fff8, #eafff5) !important;
        border-color: rgba(5,150,105,.28) !important;
    }
    .passport-cell {
        background: rgba(0,0,0,.03) !important;
        border-color: rgba(99,131,179,.15) !important;
    }
    .mode-pill, .direction-pill {
        background: rgba(0,0,0,.045) !important;
        border-color: rgba(99,131,179,.22) !important;
        color: #0d1b2e !important;
    }
    .mode-pill.live { color: #059669 !important; border-color: rgba(5,150,105,.32) !important; }
    .mode-pill.fallback { color: #b45309 !important; border-color: rgba(180,83,9,.32) !important; }

    /* ── Replay Dashboard view ── */
    .replay-hero {
        background:
            radial-gradient(circle at 88% 12%, rgba(109,40,217,.08), transparent 35%),
            linear-gradient(145deg, #ffffff, #f0f4ff) !important;
        border-color: rgba(99,131,179,.2) !important;
        box-shadow: 0 8px 28px rgba(0,0,0,.07) !important;
    }
    .replay-kicker { color: #0891b2 !important; }
    .replay-title { color: #0d1b2e !important; }
    .replay-copy { color: #4d6278 !important; }
    .filter-panel {
        background: linear-gradient(145deg, #ffffff, #f4f7fc) !important;
        border-color: rgba(99,131,179,.2) !important;
    }
    .filter-title { color: #0d1b2e !important; }
    .filter-copy { color: #4d6278 !important; }
    .range-summary {
        background: rgba(109,40,217,.04) !important;
        border-color: rgba(109,40,217,.15) !important;
    }
    .range-label { color: #4d6278 !important; }
    .range-value { color: #0d1b2e !important; }
    .range-tag { color: #6d28d9 !important; background: rgba(109,40,217,.06) !important; border-color: rgba(109,40,217,.2) !important; }
    .story-card {
        background: linear-gradient(145deg, #ffffff, #f4f8ff) !important;
        border-color: rgba(99,131,179,.18) !important;
        box-shadow: 0 4px 16px rgba(0,0,0,.06) !important;
    }
    .story-icon { background: rgba(0,0,0,.04) !important; border-color: rgba(99,131,179,.15) !important; }
    .story-label { color: #4d6278 !important; }
    .story-value { color: #0d1b2e !important; }
    .story-detail { color: #4d6278 !important; }
    .status-good { color: #059669 !important; background: rgba(5,150,105,.07) !important; }
    .status-watch { color: #b45309 !important; background: rgba(180,83,9,.07) !important; }
    .status-risk { color: #dc2626 !important; background: rgba(220,38,38,.07) !important; }
    .status-info { color: #0891b2 !important; background: rgba(8,145,178,.07) !important; }
    .section-heading { color: #0d1b2e !important; }
    .section-copy { color: #4d6278 !important; }
    .memory-wrap {
        background:
            radial-gradient(circle at 95% 5%, rgba(109,40,217,.07), transparent 30%),
            linear-gradient(145deg, #faf8ff, #f3eeff) !important;
        border-color: rgba(109,40,217,.2) !important;
    }
    .memory-title { color: #0d1b2e !important; }
    .memory-stage { color: #6d28d9 !important; background: rgba(109,40,217,.06) !important; border-color: rgba(109,40,217,.2) !important; }
    .memory-message { color: #3d5570 !important; }
    .memory-track { background: rgba(0,0,0,.08) !important; }
    .memory-stat { background: rgba(0,0,0,.03) !important; border-color: rgba(99,131,179,.15) !important; }
    .memory-stat-label { color: #4d6278 !important; }
    .memory-stat-value { color: #0d1b2e !important; }

    /* ── Streamlit native widgets ── */
    /* Radio option label text */
    div[data-testid="stRadio"] [role="radiogroup"] label {
        color: #0d1b2e !important;
    }
    /* Metric widget values */
    [data-testid="stMetricValue"] > div { color: #0d1b2e !important; }
    [data-testid="stMetricLabel"] > div { color: #4d6278 !important; }
    [data-testid="stMetricDelta"] { color: #059669 !important; }
    /* Select / date input native widgets */
    [data-baseweb="select"] [data-baseweb="select-option"],
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div {
        background: #ffffff !important;
        color: #0d1b2e !important;
    }
    [data-baseweb="select"] svg { color: #4d6278 !important; }
    /* Slider */
    [data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
        background: var(--violet) !important;
    }
    /* Section headings rendered as plain HTML */
    .stMarkdown h2, .stMarkdown h3 { color: #0d1b2e !important; }
    p, li { color: #1e3a52; }

    /* ── API status chip in light mode ── */
    .api-status.live {
        background: rgba(5,150,105,.08) !important;
        border-color: rgba(5,150,105,.25) !important;
        color: #059669 !important;
    }
    .api-status.demo {
        background: rgba(180,83,9,.08) !important;
        border-color: rgba(180,83,9,.25) !important;
        color: #b45309 !important;
    }

    /* ── Theme toggle button ── */
    [data-testid="stBaseButton-secondary"] {
        background: rgba(13,27,46,.05) !important;
        color: #0d1b2e !important;
        border: 1px solid #cdd8ea !important;
        border-radius: 10px !important;
        font-size: .8rem !important;
    }
    [data-testid="stBaseButton-secondary"]:hover {
        background: rgba(13,27,46,.10) !important;
        border-color: #aebfd4 !important;
    }
</style>
"""


# -----------------------------------------------------------------------------
# App bootstrap
# -----------------------------------------------------------------------------
_api_live = bool(os.environ.get("ANTHROPIC_API_KEY"))
_api_dot_class = "live" if _api_live else "demo"
_api_dot_label = "● Live AI" if _api_live else "● Demo mode"

st.session_state.setdefault("compass_view", "Live Decision")
st.session_state.setdefault("dark_mode", True)

dark_mode: bool = bool(st.session_state["dark_mode"])

# Inject theme variables first, then static chrome CSS.
st.markdown(DARK_VARS_CSS if dark_mode else LIGHT_VARS_CSS, unsafe_allow_html=True)
st.markdown(COMPASS_STATIC_CSS, unsafe_allow_html=True)
if not dark_mode:
    st.markdown(LIGHT_VIEW_OVERRIDES, unsafe_allow_html=True)


# Header: brand left · workspace navigation centre-right · theme toggle far right.
brand_col, workspace_col, theme_col = st.columns([1.7, 1, 0.28], vertical_alignment="center")

with brand_col:
    st.markdown(
        f"""
        <div class="brand-shell">
            <div class="brand-logo">🧭</div>
            <div>
                <div class="brand-title">Compass</div>
                <div class="brand-subtitle">
                    Human-centred demand planning intelligence
                    <span class="api-status {_api_dot_class}">{_api_dot_label}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with workspace_col:
    st.session_state["compass_view"] = st.radio(
        "Workspace",
        options=["Live Decision", "Replay Dashboard"],
        horizontal=True,
        key="workspace_navigation",
        label_visibility="visible",
    )

with theme_col:
    icon = "☀️" if dark_mode else "🌙"
    label = "Light" if dark_mode else "Dark"
    if st.button(f"{icon} {label}", key="theme_toggle", use_container_width=True):
        st.session_state["dark_mode"] = not dark_mode
        st.rerun()

st.markdown('<div class="top-divider"></div>', unsafe_allow_html=True)


if st.session_state["compass_view"] == "Live Decision":
    render_live_decision(force_fallback=False, dark_mode=dark_mode)
else:
    render_replay_dashboard(force_fallback=False, dark_mode=dark_mode)
