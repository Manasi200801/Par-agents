"""Compass Live Decision view.

This module owns the complete planner workflow:
Review -> Override -> Analyse -> Reconcile -> Decide -> Commit.

It consumes real backend functions when they are available and falls back to
fully deterministic demo data when they are not.
"""
from __future__ import annotations

import datetime as dt
import html
import time
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from compass.contracts import DecisionContext, MemoryContext, ReconcilerOutput, Signal


# -----------------------------------------------------------------------------
# Demo constants
# -----------------------------------------------------------------------------
DEFAULT_REASON = "A competitor is rumoured to be exiting the DACH market."

MACHINE_VALUES: dict[str, float] = {
    "CP-0271": 906.0,
    "PC-0029": 3157.0,
    "SM-0507": 2203.0,
}

DEFAULT_OVERRIDES: dict[str, float] = {
    "CP-0271": 750.0,
    "PC-0029": 2700.0,
    "SM-0507": 1900.0,
}

PREVIOUS_ACTUALS: dict[str, float] = {
    "CP-0271": 870.0,
    "PC-0029": 3094.0,
    "SM-0507": 2269.0,
}

UNIT_MARGINS: dict[str, float] = {
    "CP-0271": 24.0,
    "PC-0029": 31.0,
    "SM-0507": 18.0,
}


def _get_machine_value(product_id: str, sales_org_id: str, channel_id: str) -> float:
    """Return live forecast value; try recent months then fall back to the constant."""
    try:
        from compass.store import get_live_machine_value
        today = dt.date.today().replace(day=1)
        for offset in [1, 0, -1, -2]:
            month = (today + dt.timedelta(days=32 * offset)).replace(day=1)
            try:
                result = get_live_machine_value(product_id, sales_org_id, channel_id, str(month))
                if result and result.get("machine_value") is not None:
                    return float(result["machine_value"])
            except KeyError:
                continue
    except Exception:
        pass
    return MACHINE_VALUES.get(product_id, 400.0)

DIRECTION_META = {
    "supports_override": (
        "Supports your plan",
        "support",
        "#55DDA4",
        "✓",
        "This supports your decision",
    ),
    "contradicts_override": (
        "Challenges your plan",
        "challenge",
        "#FF626F",
        "!",
        "This needs attention",
    ),
    "neutral": (
        "Worth noting",
        "neutral",
        "#6EA8FF",
        "•",
        "Useful context",
    ),
}

AGENT_DISPLAY_NAMES = {
    "Demand Agent": "Demand outlook",
    "Supply and Operations Agent": "Supply readiness",
    "Supply / Ops Agent": "Supply readiness",
    "Finance and Margin Agent": "Financial impact",
    "Commercial and Market Agent": "Market signals",
    "Memory and Historical Decisions Agent": "Past decisions",
    "Memory / Critic Agent": "Past decisions",
}


# -----------------------------------------------------------------------------
# View-specific styling
# -----------------------------------------------------------------------------
VIEW_CSS = """
<style>
    .hero {
        padding: 1.25rem 1.35rem;
        border: 1px solid rgba(148,171,202,.16);
        border-radius: 22px;
        background:
            radial-gradient(circle at 88% 10%, rgba(157,123,255,.18), transparent 30%),
            linear-gradient(145deg, rgba(18,24,38,.96), rgba(11,15,23,.96));
        box-shadow: 0 20px 55px rgba(0,0,0,.24);
        margin-bottom: 1rem;
    }
    .eyebrow {
        color: #78DDF7;
        font-size: .68rem;
        font-weight: 800;
        letter-spacing: .12em;
        text-transform: uppercase;
    }
    .hero-title {
        color: #F4F7FB;
        font-size: clamp(2rem, 4vw, 3.45rem);
        line-height: 1.02;
        margin: .35rem 0 .55rem;
        letter-spacing: -.045em;
    }
    .hero-copy, .muted-copy {
        color: #9AA8BC;
        font-size: .9rem;
        line-height: 1.65;
        max-width: 820px;
    }
    .context-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: .65rem;
        margin: .85rem 0 1.1rem;
    }
    .context-box, .glass-card, .signal-card, .passport-card, .recommendation-card {
        border: 1px solid rgba(148,171,202,.16);
        background: linear-gradient(145deg, rgba(18,24,38,.94), rgba(13,18,29,.94));
        border-radius: 17px;
        box-shadow: 0 14px 35px rgba(0,0,0,.18);
    }
    .context-box { padding: .78rem .85rem; min-height: 74px; }
    .context-label, .value-label {
        color: #7F8DA2;
        font-size: .63rem;
        font-weight: 750;
        letter-spacing: .08em;
        text-transform: uppercase;
    }
    .context-value {
        color: #E9EEF7;
        font-size: .82rem;
        font-weight: 700;
        margin-top: .25rem;
        overflow-wrap: anywhere;
    }
    .glass-card { padding: 1.15rem 1.2rem; }

    .forecast-card {
        position: relative;
        overflow: hidden;
        padding: 1.2rem;
        min-height: 322px;
        border: 1px solid rgba(98,216,244,.24);
        border-radius: 20px;
        background:
            radial-gradient(circle at 90% 8%, rgba(98,216,244,.18), transparent 34%),
            linear-gradient(150deg, rgba(18,28,43,.98), rgba(10,17,28,.98));
        box-shadow: 0 18px 48px rgba(0,0,0,.22);
    }
    .forecast-card::after {
        content: "";
        position: absolute;
        width: 150px;
        height: 150px;
        right: -70px;
        bottom: -70px;
        border-radius: 999px;
        background: rgba(178,149,255,.08);
        filter: blur(2px);
    }
    .forecast-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: .75rem;
    }
    .forecast-heading {
        color: #F4F7FB;
        font-size: 1rem;
        font-weight: 800;
        margin-top: .25rem;
    }
    .forecast-badge {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        padding: .34rem .62rem;
        border: 1px solid rgba(98,216,244,.28);
        border-radius: 999px;
        color: #8FE7FA;
        background: rgba(98,216,244,.07);
        font-size: .62rem;
        font-weight: 800;
        letter-spacing: .05em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .forecast-main {
        display: flex;
        align-items: flex-end;
        gap: .65rem;
        margin: 1.05rem 0 1rem;
    }
    .forecast-number {
        color: #62D8F4;
        font-size: clamp(3.2rem, 6vw, 4.5rem);
        font-weight: 900;
        letter-spacing: -.065em;
        line-height: .92;
        text-shadow: 0 10px 35px rgba(98,216,244,.16);
    }
    .forecast-unit {
        color: #9BA9BC;
        font-size: .78rem;
        font-weight: 700;
        padding-bottom: .45rem;
    }
    .forecast-message {
        color: #B9C4D3;
        font-size: .78rem;
        line-height: 1.55;
        margin-bottom: .95rem;
    }
    .forecast-mini-grid {
        position: relative;
        z-index: 1;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: .55rem;
    }
    .forecast-mini {
        padding: .72rem;
        border: 1px solid rgba(148,171,202,.13);
        border-radius: 13px;
        background: rgba(255,255,255,.026);
    }
    .forecast-mini-label {
        color: #7F8DA2;
        font-size: .58rem;
        font-weight: 800;
        letter-spacing: .07em;
        text-transform: uppercase;
    }
    .forecast-mini-value {
        color: #F3F6FB;
        font-size: .92rem;
        font-weight: 800;
        margin-top: .22rem;
    }
    .forecast-mini-value.planner-tone { color: #FFBD63; }
    .forecast-mini-note {
        color: #8F9DB0;
        font-size: .62rem;
        margin-top: .14rem;
        line-height: 1.3;
    }

    .card-title { color: #F4F7FB; font-size: 1.05rem; font-weight: 800; margin-top: .3rem; }
    .card-copy { color: #91A0B5; font-size: .78rem; line-height: 1.55; margin-top: .2rem; }
    .big-value { font-size: 3.4rem; font-weight: 850; letter-spacing: -.055em; line-height: 1; }
    .machine { color: #62D8F4; }
    .planner { color: #FFBD63; }
    .compass { color: #B295FF; }
    .positive { color: #55DDA4; }
    .negative { color: #FF7B7B; }
    .mode-pill, .direction-pill {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        padding: .27rem .6rem;
        border-radius: 999px;
        font-size: .62rem;
        font-weight: 800;
        letter-spacing: .045em;
        text-transform: uppercase;
        border: 1px solid rgba(148,171,202,.18);
        background: rgba(255,255,255,.025);
    }
    .mode-pill.live { color: #55DDA4; border-color: rgba(85,221,164,.32); }
    .mode-pill.fallback { color: #FFBD63; border-color: rgba(255,189,99,.32); }
    .signal-card {
        position: relative;
        overflow: hidden;
        min-height: 205px;
        padding: 1.05rem;
        margin-bottom: .45rem;
        border-radius: 19px;
        transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
    }
    .signal-card:hover {
        transform: translateY(-2px);
    }
    .signal-card.support-card {
        border: 1px solid rgba(85,221,164,.36);
        background:
            radial-gradient(circle at 92% 8%, rgba(85,221,164,.18), transparent 34%),
            linear-gradient(145deg, rgba(13,34,31,.98), rgba(10,20,26,.98));
        box-shadow: 0 15px 38px rgba(32,151,110,.11);
    }
    .signal-card.challenge-card {
        border: 1px solid rgba(255,98,111,.58);
        background:
            radial-gradient(circle at 92% 7%, rgba(255,70,87,.26), transparent 37%),
            linear-gradient(145deg, rgba(55,20,29,.98), rgba(25,14,23,.98));
        box-shadow: 0 16px 42px rgba(255,70,87,.15);
    }
    .signal-card.challenge-card::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 5px;
        background: linear-gradient(#FF5364, #FF8792);
    }
    .signal-card.neutral-card {
        border: 1px solid rgba(110,168,255,.34);
        background:
            radial-gradient(circle at 92% 8%, rgba(110,168,255,.17), transparent 34%),
            linear-gradient(145deg, rgba(17,29,48,.98), rgba(11,19,30,.98));
        box-shadow: 0 15px 38px rgba(49,100,180,.10);
    }
    .signal-card-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: .6rem;
    }
    .signal-icon {
        width: 34px;
        height: 34px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 11px;
        font-size: 1rem;
        font-weight: 950;
        border: 1px solid currentColor;
        background: rgba(255,255,255,.045);
    }
    .signal-icon.support { color: #55DDA4; }
    .signal-icon.challenge {
        color: #FF7B87;
        background: rgba(255,74,91,.13);
        box-shadow: 0 0 0 5px rgba(255,74,91,.055);
    }
    .signal-icon.neutral { color: #84B8FF; }
    .signal-name {
        color: #F6F8FC;
        font-size: 1.02rem;
        font-weight: 850;
        margin: .78rem 0 .28rem;
    }
    .signal-summary {
        color: #8796AA;
        font-size: .66rem;
        font-weight: 750;
        letter-spacing: .03em;
        margin-bottom: .55rem;
    }
    .signal-claim {
        color: #D6DEE9;
        font-size: .79rem;
        line-height: 1.58;
        min-height: 64px;
    }
    .signal-friendly-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: .6rem;
        border-top: 1px solid rgba(148,171,202,.13);
        margin-top: .85rem;
        padding-top: .72rem;
        color: #8E9DB0;
        font-size: .66rem;
        font-weight: 720;
    }
    .support { color: #55DDA4; border-color: rgba(85,221,164,.32); }
    .challenge { color: #FF7B87; border-color: rgba(255,98,111,.45); }
    .neutral { color: #84B8FF; border-color: rgba(120,175,255,.32); }
    .recommendation-card {
        padding: 1.35rem;
        border-color: rgba(178,149,255,.34);
        background:
            radial-gradient(circle at 78% 20%, rgba(157,123,255,.17), transparent 36%),
            linear-gradient(145deg, rgba(21,24,42,.98), rgba(12,16,27,.98));
    }
    .recommendation-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1.35fr;
        gap: 1rem;
        align-items: end;
    }
    .passport-card {
        padding: 1.25rem;
        border-color: rgba(85,221,164,.35);
        background:
            radial-gradient(circle at 88% 12%, rgba(85,221,164,.12), transparent 30%),
            linear-gradient(145deg, rgba(16,30,32,.95), rgba(11,17,27,.97));
    }
    .passport-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: .65rem;
        margin-top: 1rem;
    }
    .passport-cell {
        border-radius: 13px;
        border: 1px solid rgba(148,171,202,.14);
        background: rgba(255,255,255,.022);
        padding: .78rem;
    }
    @media (max-width: 1050px) {
        .context-grid { grid-template-columns: repeat(3, 1fr); }
        .recommendation-grid { grid-template-columns: 1fr 1fr; }
        .recommendation-grid > div:last-child { grid-column: 1 / -1; }
    }
    @media (max-width: 700px) {
        .context-grid, .passport-grid { grid-template-columns: repeat(2, 1fr); }
    }
</style>
"""


# -----------------------------------------------------------------------------
# Fallback data loaders
# -----------------------------------------------------------------------------
def _fallback_products() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "product_id": "CP-0271",
                "product_name": "Bearing Assembly",
                "business_unit": "Precision Components",
                "category": "Bearings",
            },
            {
                "product_id": "PC-0029",
                "product_name": "Precision Coupling",
                "business_unit": "Precision Components",
                "category": "Couplings",
            },
            {
                "product_id": "SM-0507",
                "product_name": "Thermal Resin",
                "business_unit": "Specialty Materials",
                "category": "Industrial Resins",
            },
        ]
    )


def _fallback_sales_orgs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"sales_org_id": "SO04", "region_group": "DACH"},
            {"sales_org_id": "SO08", "region_group": "BeNeLux"},
            {"sales_org_id": "SO12", "region_group": "Western EU"},
        ]
    )


@st.cache_data(show_spinner=False)
def get_products(force_fallback: bool = False) -> tuple[pd.DataFrame, str]:
    """Load products from the backend, or return deterministic demo data."""
    if not force_fallback:
        try:
            from compass.loader import load_products

            products = load_products()
            if not isinstance(products, pd.DataFrame):
                products = pd.DataFrame(products)

            required = {"product_id", "business_unit", "category"}
            if not required.issubset(products.columns):
                missing = sorted(required - set(products.columns))
                raise ValueError(f"Product loader missing columns: {missing}")

            products = products.copy()
            if "product_name" not in products.columns:
                products["product_name"] = products["product_id"]
            return products, "live"
        except Exception:
            pass

    return _fallback_products(), "fallback"


@st.cache_data(show_spinner=False)
def get_sales_orgs(force_fallback: bool = False) -> tuple[pd.DataFrame, str]:
    """Load sales organisations from the backend, or use demo data."""
    if not force_fallback:
        try:
            from compass.loader import load_sales_org

            orgs = load_sales_org()
            if not isinstance(orgs, pd.DataFrame):
                orgs = pd.DataFrame(orgs)

            # Small compatibility adapter for a common backend column name.
            if "region" in orgs.columns and "region_group" not in orgs.columns:
                orgs = orgs.rename(columns={"region": "region_group"})

            required = {"sales_org_id", "region_group"}
            if not required.issubset(orgs.columns):
                missing = sorted(required - set(orgs.columns))
                raise ValueError(f"Sales-org loader missing columns: {missing}")
            return orgs, "live"
        except Exception:
            pass

    return _fallback_sales_orgs(), "fallback"


# -----------------------------------------------------------------------------
# Five-agent deterministic fallback pipeline
# -----------------------------------------------------------------------------
def run_pipeline_stub(ctx: DecisionContext) -> ReconcilerOutput:
    """Return a deterministic five-agent demo response.

    All five agents appear in the default scenario because each one has explicit
    fallback evidence. In live mode the UI renders only the signals returned by
    the backend, so an agent without evidence can remain silent.
    """
    demand_signal = Signal(
        agent_name="Demand Agent",
        claim=(
            "Confirmed orders and key-account demand exceed the planner's "
            "proposed commitment of 360 units."
        ),
        direction="contradicts_override",
        magnitude=0.82,
        confidence=0.86,
        table="future_order_book",
        evidence_rows=[
            {
                "customer_id": "C-142",
                "customer_type": "Key account",
                "confirmed_units": 84,
                "period": "2026-07",
            },
            {
                "customer_id": "C-087",
                "customer_type": "Distributor",
                "confirmed_units": 71,
                "period": "2026-07",
            },
            {
                "customer_id": "C-219",
                "customer_type": "Wholesale",
                "confirmed_units": 63,
                "period": "2026-07",
            },
        ],
    )

    supply_signal = Signal(
        agent_name="Supply and Operations Agent",
        claim=(
            "Available stock and confirmed inbound supply can support a commitment "
            "close to 420 units, although supplier reliability creates moderate risk."
        ),
        direction="neutral",
        magnitude=0.61,
        confidence=0.72,
        table="stock_on_hand",
        evidence_rows=[
            {
                "warehouse": "WH-DACH-02",
                "available_units": 258,
                "reserved_units": 46,
                "snapshot_date": "2026-06-26",
            },
            {
                "purchase_order": "PO-8831",
                "inbound_units": 168,
                "expected_date": "2026-07-08",
                "supplier_otif": "71%",
            },
        ],
    )

    finance_signal = Signal(
        agent_name="Finance and Margin Agent",
        claim=(
            "Reducing the commitment to 360 units could leave profitable demand "
            "unserved because this product generates a unit margin of €24."
        ),
        direction="contradicts_override",
        magnitude=0.67,
        confidence=0.79,
        table="product_margin",
        evidence_rows=[
            {
                "scenario": "Machine forecast",
                "units": 437,
                "estimated_margin_eur": 10488,
            },
            {
                "scenario": "Planner override",
                "units": 360,
                "estimated_margin_eur": 8640,
            },
            {
                "scenario": "Compass recommendation",
                "units": 402,
                "estimated_margin_eur": 9648,
            },
        ],
    )

    commercial_signal = Signal(
        agent_name="Commercial and Market Agent",
        claim=(
            "The reported competitor exit could increase addressable demand in DACH, "
            "making a large downward override difficult to justify."
        ),
        direction="contradicts_override",
        magnitude=0.76,
        confidence=0.74,
        table="market_events",
        evidence_rows=[
            {
                "event_id": "ME-104",
                "region": "DACH",
                "event_type": "Competitor exit rumour",
                "status": "Unconfirmed",
            },
            {
                "account_segment": "Industrial distributors",
                "potential_additional_units": 28,
                "confidence": "Medium",
            },
            {
                "account_segment": "Key accounts",
                "potential_additional_units": 19,
                "confidence": "Medium",
            },
        ],
    )

    memory_signal = Signal(
        agent_name="Memory and Historical Decisions Agent",
        claim=(
            "Similar competitor-exit decisions historically required smaller forecast "
            "adjustments than the planner's proposed reduction."
        ),
        direction="contradicts_override",
        magnitude=0.74,
        confidence=0.78,
        table="decisions",
        evidence_rows=[
            {
                "reason_class": "competitor_exit",
                "previous_override_pct": "+20.0%",
                "realised_impact_pct": "+13.1%",
                "fva": 4.2,
            },
            {
                "reason_class": "competitor_exit",
                "previous_override_pct": "+17.5%",
                "realised_impact_pct": "+11.8%",
                "fva": 2.9,
            },
            {
                "reason_class": "market_disruption",
                "previous_override_pct": "+15.0%",
                "realised_impact_pct": "+10.4%",
                "fva": 3.6,
            },
        ],
    )

    memory_context = MemoryContext(
        planner_fva_history={
            "avg_fva": 3.4,
            "n_decisions": 14,
            "pct_helpful": 0.64,
        },
        reason_type_history={
            "avg_fva": 4.2,
            "avg_override_pct": 0.20,
            "avg_realized_pct": 0.13,
        },
        similar_past_events=[
            {
                "reason_text": (
                    "A regional competitor stopped supplying two DACH distributors."
                ),
                "realized_impact": 0.12,
                "fva": 5.1,
            },
            {
                "reason_text": (
                    "Competitor capacity reduction was expected in the bearings category."
                ),
                "realized_impact": 0.14,
                "fva": 3.7,
            },
        ],
        calibrated_suggestion=round(ctx.machine_value * 0.96, 0),
        confidence_level="medium",
    )

    recommended_value = round(ctx.machine_value * 0.96, 0)

    return ReconcilerOutput(
        recommended_value=recommended_value,
        confidence_level="medium",
        rationale=(
            f"The market event is real but historical competitor exits in this category "
            f"have lifted demand, not reduced it. Confirmed orders and supply readiness "
            f"both support staying close to the model. "
            f"Compass recommends {recommended_value:.0f} units — a modest 4% haircut "
            f"from the machine forecast of {ctx.machine_value:.0f}, versus the planner's "
            f"proposed {ctx.override_value:.0f}."
        ),
        signals_used=[
            demand_signal,
            supply_signal,
            finance_signal,
            commercial_signal,
            memory_signal,
        ],
        memory_context=memory_context,
    )


def commit_decision_stub(
    ctx: DecisionContext,
    final_value: float,
    output: ReconcilerOutput,
) -> str:
    """Create a stable, human-readable fallback decision ID."""
    del final_value, output  # The stable ID is based on decision context.
    product = ctx.product_id.replace("-", "")
    period = ctx.cutoff_date.strftime("%Y%m")
    return f"CMP-{product}-{ctx.sales_org_id}-{period}"


# -----------------------------------------------------------------------------
# Session state
# -----------------------------------------------------------------------------
def _init_state() -> None:
    defaults: dict[str, Any] = {
        "current_view": "Live Decision",
        "selected_product": "CP-0271",
        "selected_sales_org": "SO04",
        "selected_channel": "CH01",
        "planner_override": 750.0,
        "override_slider": 750,
        "override_number": 750.0,
        "reason_text": DEFAULT_REASON,
        "decision_maker": "planner_001",
        "pipeline_output": None,
        "ctx": None,
        "analysis_complete": False,
        "backend_mode": "pending",
        "decision_saved": False,
        "decision_id": None,
        "final_decision_mode": "Accept Compass recommendation",
        "final_value": 870.0,
        "final_custom_value": 870.0,
        "reason_class": "competitor_exit",
        "backend_error": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _reset_analysis() -> None:
    st.session_state.pipeline_output = None
    st.session_state.ctx = None
    st.session_state.analysis_complete = False
    st.session_state.backend_mode = "pending"
    st.session_state.decision_saved = False
    st.session_state.decision_id = None
    st.session_state.backend_error = None


def _sync_from_slider() -> None:
    value = float(st.session_state.override_slider)
    st.session_state.override_number = value
    st.session_state.planner_override = value
    _reset_analysis()


def _sync_from_number() -> None:
    value = float(st.session_state.override_number)
    st.session_state.override_slider = int(round(value))
    st.session_state.planner_override = value
    _reset_analysis()


def _on_product_change() -> None:
    product_id = st.session_state.selected_product
    override = DEFAULT_OVERRIDES.get(
        product_id,
        MACHINE_VALUES.get(product_id, 400.0),
    )
    st.session_state.override_slider = int(round(override))
    st.session_state.override_number = float(override)
    st.session_state.planner_override = float(override)
    _reset_analysis()


# -----------------------------------------------------------------------------
# Formatting and business helpers
# -----------------------------------------------------------------------------
def _classify_reason_stub(reason_text: str) -> str:
    text = reason_text.lower()
    if "competitor" in text and any(x in text for x in ("exit", "leav", "closing")):
        return "competitor_exit"
    if any(x in text for x in ("promotion", "campaign", "sale")):
        return "promotion"
    if any(x in text for x in ("stock", "inventory", "overstock")):
        return "channel_overstock"
    if any(x in text for x in ("supplier", "shortage", "constraint")):
        return "supply_constraint"
    if any(x in text for x in ("price", "pricing", "margin")):
        return "price_change"
    return "other"


def _planning_period(today: dt.date | None = None) -> str:
    current = today or dt.date.today()
    if current.month == 12:
        next_month = dt.date(current.year + 1, 1, 1)
    else:
        next_month = dt.date(current.year, current.month + 1, 1)
    return next_month.strftime("%Y-%m")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _confidence_percent(value: Any) -> float:
    confidence = _safe_float(value)
    return confidence * 100.0 if 0.0 <= confidence <= 1.0 else confidence


def _confidence_language(value: Any) -> str:
    """Turn a numeric confidence score into plain business language."""
    confidence = _confidence_percent(value)
    if confidence >= 80:
        return "Strong confidence"
    if confidence >= 65:
        return "Good confidence"
    return "Early signal"


def _magnitude_text(value: Any) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, (int, float)):
        number = float(value)
        return f"{number * 100:.0f}%" if 0 <= number <= 1 else f"{number:.1f}"
    return str(value)


def _display_value(
    value: float | None,
    prefix: str = "",
    suffix: str = "",
) -> str:
    if value is None:
        return "Not available"
    return f"{prefix}{value:,.0f}{suffix}"




EVIDENCE_SOURCE_LABELS = {
    "future_order_book": "Confirmed customer orders",
    "stock_on_hand": "Inventory and incoming supply",
    "purchase_orders": "Incoming purchase orders",
    "product_margin": "Margin and value analysis",
    "market_events": "Market and commercial signals",
    "decisions": "Similar past decisions",
}

EVIDENCE_COLUMN_LABELS = {
    "customer_id": "Customer",
    "customer_type": "Customer type",
    "confirmed_units": "Confirmed demand",
    "period": "Planning period",
    "warehouse": "Location",
    "available_units": "Available now",
    "reserved_units": "Already reserved",
    "snapshot_date": "Last updated",
    "purchase_order": "Purchase order",
    "inbound_units": "Incoming units",
    "expected_date": "Expected arrival",
    "supplier_otif": "Supplier reliability",
    "product_id": "Product",
    "unit_margin_eur": "Margin per unit",
    "machine_forecast_units": "Model forecast",
    "planner_override_units": "Planner proposal",
    "scenario": "Option",
    "units": "Units",
    "estimated_margin_eur": "Estimated margin",
    "event_id": "Market event",
    "region": "Market",
    "event_type": "Signal",
    "affected_category": "Product family",
    "status": "Status",
    "account_segment": "Customer segment",
    "potential_additional_units": "Potential extra demand",
    "confidence": "Confidence",
    "reason_class": "Reason type",
    "previous_override_pct": "Past adjustment",
    "realised_impact_pct": "Actual impact",
    "realized_impact_pct": "Actual impact",
    "reason_text": "Previous situation",
    "realized_impact": "Actual impact",
    "realised_impact": "Actual impact",
    "fva": "Forecast improvement",
    "evidence": "Supporting information",
}

EVIDENCE_COLUMN_ORDER = {
    "future_order_book": [
        "customer_id",
        "customer_type",
        "confirmed_units",
        "period",
    ],
    "stock_on_hand": [
        "warehouse",
        "available_units",
        "reserved_units",
        "purchase_order",
        "inbound_units",
        "expected_date",
        "supplier_otif",
        "snapshot_date",
    ],
    "product_margin": [
        "scenario",
        "units",
        "estimated_margin_eur",
    ],
    "market_events": [
        "event_type",
        "account_segment",
        "region",
        "status",
        "potential_additional_units",
        "confidence",
    ],
    "decisions": [
        "reason_class",
        "previous_override_pct",
        "realised_impact_pct",
        "realized_impact_pct",
        "fva",
    ],
}


def _format_evidence_value(column: str, value: Any) -> str:
    """Format raw evidence values in plain business language."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"

    if column in {"estimated_margin_eur", "unit_margin_eur"}:
        try:
            return f"€{float(value):,.0f}"
        except (TypeError, ValueError):
            return str(value)

    if column in {
        "confirmed_units",
        "available_units",
        "reserved_units",
        "inbound_units",
        "machine_forecast_units",
        "planner_override_units",
        "potential_additional_units",
        "units",
    }:
        try:
            return f"{float(value):,.0f}"
        except (TypeError, ValueError):
            return str(value)

    if column in {"realized_impact", "realised_impact"}:
        try:
            number = float(value)
            return f"{number * 100:.1f}%" if -1 <= number <= 1 else f"{number:.1f}%"
        except (TypeError, ValueError):
            return str(value)

    if column == "fva":
        try:
            number = float(value)
            sign = "+" if number > 0 else ""
            return f"{sign}{number:.1f} points"
        except (TypeError, ValueError):
            return str(value)

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, pd.Timestamp):
        return value.strftime("%d %b %Y")

    return str(value).replace("_", " ").strip()


def _make_evidence_user_friendly(
    signal: Signal,
    evidence_df: pd.DataFrame,
) -> tuple[str, pd.DataFrame]:
    """Rename, order and format evidence so business users can read it quickly."""
    source_key = str(getattr(signal, "table", "") or "")
    source_label = EVIDENCE_SOURCE_LABELS.get(
        source_key,
        source_key.replace("_", " ").title() if source_key else "Business records",
    )

    if evidence_df.empty:
        return source_label, evidence_df

    friendly = evidence_df.copy()
    friendly = friendly.dropna(axis=0, how="all").dropna(axis=1, how="all")

    preferred_order = [
        column
        for column in EVIDENCE_COLUMN_ORDER.get(source_key, [])
        if column in friendly.columns
    ]
    remaining_columns = [
        column for column in friendly.columns if column not in preferred_order
    ]
    friendly = friendly[preferred_order + remaining_columns]

    for column in friendly.columns:
        friendly[column] = friendly[column].map(
            lambda value, current_column=column: _format_evidence_value(
                current_column,
                value,
            )
        )

    friendly = friendly.rename(
        columns={
            column: EVIDENCE_COLUMN_LABELS.get(
                column,
                column.replace("_", " ").title(),
            )
            for column in friendly.columns
        }
    )

    return source_label, friendly


def _normalise_evidence(rows: Any) -> pd.DataFrame:
    """Convert backend evidence into a safe DataFrame for display."""
    if rows is None:
        return pd.DataFrame()

    if isinstance(rows, pd.DataFrame):
        return rows.copy()

    if isinstance(rows, dict):
        return pd.DataFrame([rows])

    if isinstance(rows, Iterable) and not isinstance(rows, (str, bytes)):
        try:
            return pd.DataFrame(list(rows))
        except Exception:
            return pd.DataFrame({"evidence": [str(rows)]})

    return pd.DataFrame({"evidence": [str(rows)]})

def _render_agent_card(signal: Signal) -> None:
    """Render one concise, business-friendly specialist insight card."""
    direction = str(getattr(signal, "direction", "neutral") or "neutral")
    label, css_class, accent, icon, summary = DIRECTION_META.get(
        direction,
        ("Evidence", "neutral", "#6EA8FF", "•", "Useful context"),
    )

    raw_agent_name = str(getattr(signal, "agent_name", "Specialist Agent"))
    friendly_name = AGENT_DISPLAY_NAMES.get(raw_agent_name, raw_agent_name)

    claim = html.escape(str(getattr(signal, "claim", "No insight supplied.")))
    agent_name = html.escape(friendly_name)
    confidence_text = html.escape(
        _confidence_language(getattr(signal, "confidence", 0.0))
    )
    evidence_df = _normalise_evidence(getattr(signal, "evidence_rows", None))
    record_word = "record" if len(evidence_df) == 1 else "records"

    st.markdown(
        f"""
        <div class="signal-card {css_class}-card">
            <div class="signal-card-top">
                <div class="signal-icon {css_class}">{icon}</div>
                <span class="direction-pill {css_class}">{label}</span>
            </div>
            <div class="signal-name">{agent_name}</div>
            <div class="signal-summary">{summary}</div>
            <div class="signal-claim">{claim}</div>
            <div class="signal-friendly-meta">
                <span>{confidence_text}</span>
                <span>{len(evidence_df)} supporting {record_word}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    source_label, friendly_evidence = _make_evidence_user_friendly(
        signal,
        evidence_df,
    )

    with st.expander(f"View the facts · {friendly_name}"):
        st.caption(
            f"Compass used: {source_label}. "
            "Missing information is shown as —."
        )
        if friendly_evidence.empty:
            st.info("No supporting information was available for this insight.")
        else:
            table_height = min(420, 38 * (len(friendly_evidence) + 1) + 18)
            st.dataframe(
                friendly_evidence,
                use_container_width=True,
                hide_index=True,
                height=table_height,
            )


def _render_memory(memory: MemoryContext | None) -> None:
    with st.expander("Memory and track record", expanded=False):
        if memory is None:
            st.info("Cold start: no scored history exists for this decision type yet.")
            return

        planner = getattr(memory, "planner_fva_history", None) or {}
        reason = getattr(memory, "reason_type_history", None) or {}
        similar = getattr(memory, "similar_past_events", None) or []
        suggestion = getattr(memory, "calibrated_suggestion", None)
        confidence = getattr(memory, "confidence_level", None) or "Unknown"

        if not planner and not reason and not similar and suggestion is None:
            st.info("Cold start: no scored history exists for this decision type yet.")
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Previous decisions", int(_safe_float(planner.get("n_decisions"))))
        c2.metric("Helpful decisions", f"{_safe_float(planner.get('pct_helpful')) * 100:.0f}%")
        c3.metric("Average planner FVA", f"{_safe_float(planner.get('avg_fva')):.1f}")
        c4.metric("Memory confidence", str(confidence).title())

        st.markdown("#### Reason-type calibration")
        r1, r2, r3 = st.columns(3)
        r1.metric("Reason-type average FVA", f"{_safe_float(reason.get('avg_fva')):.1f}")
        r2.metric("Average previous override", f"{_safe_float(reason.get('avg_override_pct')) * 100:.1f}%")
        r3.metric("Average realised impact", f"{_safe_float(reason.get('avg_realized_pct')) * 100:.1f}%")

        if suggestion is not None:
            st.success(
                f"Calibrated suggestion from scored memory: {float(suggestion):.0f} units"
            )

        if similar:
            st.markdown("#### Similar past events")
            similar_df = _normalise_evidence(similar)
            st.dataframe(similar_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No similar past events were returned.")


def _render_passport(
    ctx: DecisionContext,
    output: ReconcilerOutput,
    final_value: float,
) -> None:
    reason = html.escape(str(ctx.reason_text))
    reason_class = html.escape(str(st.session_state.reason_class or "Pending"))
    backend_mode = html.escape(str(st.session_state.backend_mode).title())
    decision_id = html.escape(str(st.session_state.decision_id))

    st.html(
        f"""<div class="passport-card">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;">
                <div>
                    <div class="eyebrow" style="color:#55DDA4;">Commitment Passport</div>
                    <div style="color:#F4F7FB;font-size:1.45rem;font-weight:850;margin-top:.2rem;">
                        Human approved
                    </div>
                    <div style="margin-top:.28rem;color:#91A0B5;font-size:.76rem;">
                        {decision_id}
                    </div>
                </div>
                <span class="mode-pill live">● Awaiting actuals</span>
            </div>

            <div class="passport-grid">
                <div class="passport-cell">
                    <div class="value-label">Machine</div>
                    <div class="machine" style="font-size:1.65rem;font-weight:850;">{ctx.machine_value:.0f}</div>
                </div>
                <div class="passport-cell">
                    <div class="value-label">Planner</div>
                    <div class="planner" style="font-size:1.65rem;font-weight:850;">{ctx.override_value:.0f}</div>
                </div>
                <div class="passport-cell">
                    <div class="value-label">Compass</div>
                    <div class="compass" style="font-size:1.65rem;font-weight:850;">{output.recommended_value:.0f}</div>
                </div>
                <div class="passport-cell">
                    <div class="value-label">Final</div>
                    <div class="positive" style="font-size:1.65rem;font-weight:850;">{final_value:.0f}</div>
                </div>
            </div>

            <div style="margin-top:1rem;color:#C7D0DE;font-size:.78rem;line-height:1.75;">
                <strong>Decision:</strong> {html.escape(ctx.product_id)} × {html.escape(ctx.sales_org_id)} × {html.escape(ctx.channel_id)}<br>
                <strong>Planning period:</strong> {_planning_period(ctx.cutoff_date)} ·
                <strong>Planner:</strong> {html.escape(ctx.decision_maker)}<br>
                <strong>Reason class:</strong> {reason_class} ·
                <strong>Confidence:</strong> {html.escape(str(output.confidence_level).title())}<br>
                <strong>Reason:</strong> {reason}<br>
                <strong>Evidence signals:</strong> {len(output.signals_used or [])} ·
                <strong>Backend mode:</strong> {backend_mode}
            </div>

            <div style="margin-top:1rem;padding-top:.85rem;border-top:1px solid rgba(148,171,202,.17);color:#91A0B5;font-size:.72rem;line-height:1.55;">
                This decision is now captured for future learning. When actuals arrive,
                Compass can compare machine error with final-decision error and calculate
                Forecast Value Added.
            </div>
</div>"""
    )


# -----------------------------------------------------------------------------
# Main page
# -----------------------------------------------------------------------------
def render(force_fallback: bool = False, dark_mode: bool = True) -> None:
    """Render the complete Compass Live Decision experience."""
    _init_state()
    st.markdown(VIEW_CSS, unsafe_allow_html=True)

    products, product_mode = get_products(force_fallback)
    orgs, org_mode = get_sales_orgs(force_fallback)

    st.markdown(
        """
        <div class="hero">
            <h1 class="hero-title">Review and defend the commitment</h1>
            <p class="hero-copy">
                Review the forecast, add your business insight, and make the final call
                with support from five specialist agents.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    product_ids = sorted(products["product_id"].astype(str).unique().tolist())
    product_name_map = (
        products.assign(product_id=products["product_id"].astype(str))
        .drop_duplicates("product_id")
        .set_index("product_id")["product_name"]
        .astype(str)
        .to_dict()
    )
    org_ids = sorted(orgs["sales_org_id"].astype(str).unique().tolist())

    if not product_ids or not org_ids:
        st.error("No product or sales-organisation data is available.")
        return

    if st.session_state.selected_product not in product_ids:
        st.session_state.selected_product = product_ids[0]
    if st.session_state.selected_sales_org not in org_ids:
        st.session_state.selected_sales_org = org_ids[0]

    input_1, input_2, input_3, input_4 = st.columns([1.25, 1, .85, 1])
    with input_1:
        st.selectbox(
            "Product",
            product_ids,
            key="selected_product",
            format_func=lambda product_id: (
                f"{product_id} · {product_name_map.get(str(product_id), 'Unknown product')}"
            ),
            on_change=_on_product_change,
        )
    with input_2:
        st.selectbox(
            "Sales organisation",
            org_ids,
            key="selected_sales_org",
            on_change=_reset_analysis,
        )
    with input_3:
        st.selectbox(
            "Channel",
            ["CH01", "CH02", "CH03", "CH04"],
            key="selected_channel",
            on_change=_reset_analysis,
        )
    with input_4:
        st.text_input(
            "Planner ID",
            key="decision_maker",
            on_change=_reset_analysis,
        )

    product_id = str(st.session_state.selected_product)
    sales_org_id = str(st.session_state.selected_sales_org)
    channel_id = str(st.session_state.selected_channel)

    product_row = products.loc[
        products["product_id"].astype(str) == product_id
    ].iloc[0]
    org_row = orgs.loc[
        orgs["sales_org_id"].astype(str) == sales_org_id
    ].iloc[0]

    machine_value = _get_machine_value(product_id, sales_org_id, channel_id)
    previous_actual = PREVIOUS_ACTUALS.get(product_id)
    unit_margin = UNIT_MARGINS.get(product_id)

    st.markdown(
        f"""
        <div class="context-grid">
            <div class="context-box">
                <div class="context-label">Product</div>
                <div class="context-value">{html.escape(product_id)} · {html.escape(str(product_row['product_name']))}</div>
            </div>
            <div class="context-box">
                <div class="context-label">Region</div>
                <div class="context-value">{html.escape(str(org_row['region_group']))}</div>
            </div>
            <div class="context-box">
                <div class="context-label">Channel</div>
                <div class="context-value">{html.escape(channel_id)}</div>
            </div>
            <div class="context-box">
                <div class="context-label">Business unit</div>
                <div class="context-value">{html.escape(str(product_row['business_unit']))}</div>
            </div>
            <div class="context-box">
                <div class="context-label">Planning period</div>
                <div class="context-value">{_planning_period()}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([.85, 1.45], gap="large")

    with left:
        planner_plan = float(DEFAULT_OVERRIDES.get(product_id, machine_value))
        planner_gap = planner_plan - machine_value
        planner_gap_text = (
            f"{abs(planner_gap):.0f} {'above' if planner_gap > 0 else 'below'} the model"
            if planner_gap != 0
            else "Matches the model"
        )

        if previous_actual is None:
            actual_value_text = "Not available"
            actual_gap_text = "No previous comparison"
        else:
            actual_value_text = f"{float(previous_actual):.0f} units"
            actual_gap = float(previous_actual) - machine_value
            actual_gap_text = (
                f"{abs(actual_gap):.0f} {'above' if actual_gap > 0 else 'below'} this forecast"
                if actual_gap != 0
                else "Matches this forecast"
            )

        margin_value_text = (
            f"€{float(unit_margin):.0f} per unit"
            if unit_margin is not None
            else "Not available"
        )

        st.html(
            f"""<div class="forecast-card">
  <div class="forecast-top">
    <div>
      <div class="eyebrow">Forecast snapshot</div>
      <div class="forecast-heading">What the model expects this cycle</div>
    </div>
    <div class="forecast-badge">● Model outlook</div>
  </div>

  <div class="forecast-main">
    <div class="forecast-number">{machine_value:.0f}</div>
    <div class="forecast-unit">units expected</div>
  </div>

  <div class="forecast-message">
    Use this as the starting point, then apply your market knowledge before making the final commitment.
  </div>

  <div class="forecast-mini-grid">
    <div class="forecast-mini">
      <div class="forecast-mini-label">Current plan</div>
      <div class="forecast-mini-value planner-tone">{planner_plan:.0f} units</div>
      <div class="forecast-mini-note">{planner_gap_text}</div>
    </div>

    <div class="forecast-mini">
      <div class="forecast-mini-label">Last actual</div>
      <div class="forecast-mini-value">{actual_value_text}</div>
      <div class="forecast-mini-note">{actual_gap_text}</div>
    </div>

    <div class="forecast-mini">
      <div class="forecast-mini-label">Value per unit</div>
      <div class="forecast-mini-value">{margin_value_text}</div>
      <div class="forecast-mini-note">Estimated unit margin</div>
    </div>

    <div class="forecast-mini">
      <div class="forecast-mini-label">Product family</div>
      <div class="forecast-mini-value">{html.escape(str(product_row['category']))}</div>
      <div class="forecast-mini-note">Planning category</div>
    </div>
  </div>
</div>"""
        )

    with right:
        st.markdown(
            """
            <div class="glass-card">
                <div class="eyebrow">Planner judgment</div>
                <div class="card-title">Set the proposed commitment</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        slider_min = max(0, int(machine_value * .60))
        slider_max = int(machine_value * 1.35)

        # Keep state valid when a newly selected product has a different range.
        if not slider_min <= int(st.session_state.override_slider) <= slider_max:
            default_override = int(round(DEFAULT_OVERRIDES.get(product_id, machine_value)))
            st.session_state.override_slider = default_override
            st.session_state.override_number = float(default_override)

        control_a, control_b = st.columns([1.55, .7])
        with control_a:
            st.slider(
                "Planner override",
                min_value=slider_min,
                max_value=slider_max,
                key="override_slider",
                on_change=_sync_from_slider,
            )
        with control_b:
            st.number_input(
                "Units",
                min_value=0.0,
                step=1.0,
                key="override_number",
                on_change=_sync_from_number,
            )

        override_value = float(st.session_state.override_number)
        st.session_state.planner_override = override_value
        difference_pct = (
            (override_value - machine_value) / max(machine_value, 1.0) * 100.0
        )
        difference_class = "positive" if difference_pct >= 0 else "negative"
        st.markdown(
            f'<div class="{difference_class}" style="font-size:.82rem;font-weight:800;margin:.1rem 0 .7rem;">'
            f'{difference_pct:+.1f}% versus machine forecast</div>',
            unsafe_allow_html=True,
        )

        st.text_area(
            "What does the planner know that the model does not? *",
            key="reason_text",
            height=115,
            on_change=_reset_analysis,
        )

        analyse_clicked = st.button(
            "Ask Compass to Review",
            type="primary",
            use_container_width=True,
        )

    if analyse_clicked:
        reason_text = str(st.session_state.reason_text).strip()
        planner_id = str(st.session_state.decision_maker).strip()

        if override_value <= 0:
            st.error("Enter a valid planner override greater than zero.")
        elif not reason_text:
            st.error("Enter the planner's business reason before analysis.")
        elif not planner_id:
            st.error("Enter a planner ID before analysis.")
        else:
            ctx = DecisionContext(
                product_id=product_id,
                sales_org_id=sales_org_id,
                channel_id=channel_id,
                cutoff_date=dt.date.today(),
                machine_value=machine_value,
                override_value=override_value,
                reason_text=reason_text,
                reason_class=None,
                business_unit=str(product_row["business_unit"]),
                category=str(product_row["category"]),
                region_group=str(org_row["region_group"]),
                decision_maker=planner_id,
            )

            st.session_state.ctx = ctx
            st.session_state.reason_class = _classify_reason_stub(reason_text)
            st.session_state.decision_saved = False
            st.session_state.decision_id = None
            st.session_state.backend_error = None

            progress = st.progress(0, text="Understanding your reason")
            with st.spinner("Compass is reviewing your decision..."):
                progress.progress(20, text="Understanding your reason")
                time.sleep(.06)
                progress.progress(40, text="Checking demand and supply")
                time.sleep(.06)
                progress.progress(60, text="Reviewing finance, market and past decisions")

                if force_fallback:
                    output = run_pipeline_stub(ctx)
                    backend_mode = "fallback"
                else:
                    try:
                        from compass.pipeline import run_pipeline

                        output = run_pipeline(ctx)
                        backend_mode = "live"
                    except Exception as exc:
                        output = run_pipeline_stub(ctx)
                        backend_mode = "fallback"
                        st.session_state.backend_error = str(exc)

                progress.progress(82, text="Comparing the evidence")
                time.sleep(.06)
                progress.progress(100, text="Your recommendation is ready")

            progress.empty()
            st.session_state.pipeline_output = output
            st.session_state.backend_mode = backend_mode
            st.session_state.analysis_complete = True
            st.session_state.final_value = float(output.recommended_value)
            st.session_state.final_custom_value = float(output.recommended_value)
            st.rerun()

    if not st.session_state.analysis_complete:
        return

    output: ReconcilerOutput = st.session_state.pipeline_output
    ctx: DecisionContext = st.session_state.ctx
    signals = list(output.signals_used or [])

    st.markdown("---")
    st.markdown("## What Compass found")
    if signals:
        # First row: 3 cards. Second row: remaining 2 cards.
        first_row = signals[:3]
        second_row = signals[3:]

        cols = st.columns(len(first_row))
        for column, signal in zip(cols, first_row):
            with column:
                _render_agent_card(signal)

        if second_row:
            cols = st.columns(len(second_row))
            for column, signal in zip(cols, second_row):
                with column:
                    _render_agent_card(signal)
    else:
        st.info("Compass did not find any meaningful evidence for this decision.")

    machine_delta = float(output.recommended_value) - float(ctx.machine_value)
    planner_delta = float(output.recommended_value) - float(ctx.override_value)

    st.markdown("---")
    st.markdown(
        f"""
        <div class="recommendation-card">
            <div class="eyebrow" style="color:#B295FF;">Compass Recommendation</div>
            <div class="recommendation-grid" style="margin-top:.9rem;">
                <div>
                    <div class="value-label">Machine forecast</div>
                    <div class="machine" style="font-size:2.05rem;font-weight:850;">{ctx.machine_value:.0f}</div>
                </div>
                <div>
                    <div class="value-label">Planner proposal</div>
                    <div class="planner" style="font-size:2.05rem;font-weight:850;">{ctx.override_value:.0f}</div>
                </div>
                <div>
                    <div class="value-label">Compass recommends</div>
                    <div class="compass" style="font-size:4.35rem;font-weight:900;line-height:.92;letter-spacing:-.06em;">{output.recommended_value:.0f}</div>
                    <div style="color:#91A0B5;font-size:.71rem;margin-top:.25rem;">units · {html.escape(str(output.confidence_level).title())} confidence</div>
                </div>
            </div>
            <div style="display:flex;gap:.75rem;flex-wrap:wrap;margin-top:1rem;">
                <span class="mode-pill">{machine_delta:+.0f} vs machine</span>
                <span class="mode-pill">{planner_delta:+.0f} vs planner</span>
                <span class="mode-pill">{len(signals)} evidence signals</span>
            </div>
            <div style="margin-top:1rem;padding-top:.9rem;border-top:1px solid rgba(178,149,255,.2);color:#C7D0DE;font-size:.81rem;line-height:1.7;">
                {html.escape(str(output.rationale))}
            </div>
            <div style="margin-top:.75rem;color:#91A0B5;font-size:.7rem;">
                Recommendation only — the human still decides.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_memory(output.memory_context)

    st.markdown("---")
    st.markdown("## Human final decision")

    choice = st.radio(
        "Choose how to commit",
        [
            "Accept Compass recommendation",
            "Keep my original override",
            "Enter another value",
        ],
        key="final_decision_mode",
        horizontal=True,
    )

    if choice == "Accept Compass recommendation":
        final_value = float(output.recommended_value)
    elif choice == "Keep my original override":
        final_value = float(ctx.override_value)
    else:
        final_value = float(
            st.number_input(
                "Custom final commitment",
                min_value=0.0,
                step=1.0,
                key="final_custom_value",
            )
        )

    st.session_state.final_value = final_value

    st.markdown(
        f"""
        <div class="glass-card">
            <div class="value-label">Final human commitment</div>
            <div class="big-value positive">{final_value:.0f}</div>
            <div style="color:#91A0B5;font-size:.72rem;margin-top:.2rem;">units · Human approval required</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.decision_saved:
        if st.button(
            "Commit Final Decision",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner("Saving decision and linking related products..."):
                if force_fallback:
                    decision_id = commit_decision_stub(ctx, final_value, output)
                    commit_mode = "fallback"
                else:
                    try:
                        from compass.pipeline import commit_decision

                        decision_id = commit_decision(ctx, final_value, output)
                        commit_mode = st.session_state.backend_mode
                    except Exception as exc:
                        decision_id = commit_decision_stub(ctx, final_value, output)
                        commit_mode = "fallback"
                        st.session_state.backend_error = str(exc)

            st.session_state.decision_saved = True
            st.session_state.decision_id = str(decision_id)
            st.session_state.backend_mode = commit_mode
            st.session_state.final_value = final_value
            st.rerun()

    if st.session_state.decision_saved:
        _render_passport(ctx, output, float(st.session_state.final_value))
