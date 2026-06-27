"""Compass Streamlit application shell.

This file owns only the shared page configuration, global styling, the single
Compass header, top-right workspace navigation, and routing between views.
"""
from __future__ import annotations

import streamlit as st

from app.views.live_decision import render as render_live_decision
from app.views.replay_dashboard import render as render_replay_dashboard


st.set_page_config(
    page_title="Compass — Decision Intelligence",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)


COMPASS_CSS = """
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

    html, body, [data-testid="stAppViewContainer"], .stApp {
        background: var(--bg) !important;
        color: var(--text) !important;
    }

    .stApp {
        background:
            radial-gradient(900px 520px at 8% -12%, rgba(63, 104, 180, .20), transparent 60%),
            var(--bg) !important;
    }

    /* The workspace navigation now lives in the top-right header. */
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

    div[data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 14px 16px;
    }

    /* Compact horizontal workspace selector. */
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


    /* Hide Streamlit chrome: menu, toolbar, Deploy button and header. */
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

st.markdown(COMPASS_CSS, unsafe_allow_html=True)
st.session_state.setdefault("compass_view", "Live Decision")


# Single Compass title on the left and workspace navigation on the right.
brand_col, workspace_col = st.columns([1.7, 1], vertical_alignment="center")

with brand_col:
    st.markdown(
        """
        <div class="brand-shell">
            <div class="brand-logo">🧭</div>
            <div>
                <div class="brand-title">Compass</div>
                <div class="brand-subtitle">Human-centred demand planning intelligence</div>
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

st.markdown('<div class="top-divider"></div>', unsafe_allow_html=True)


if st.session_state["compass_view"] == "Live Decision":
    # Try the real backend automatically; the view falls back safely if unavailable.
    render_live_decision(force_fallback=False)
else:
    render_replay_dashboard(force_fallback=False)
