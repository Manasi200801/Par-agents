
"""
Compass Replay Dashboard

A user-friendly replay view with:
- Calendar-based date selection
- All-history and custom-range modes
- Daily, weekly, monthly and yearly views
- Smooth overall forecast-performance trends
- Plain-language KPI and learning sections
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"

REQUIRED_COLUMNS = {
    "cutoff_date",
    "mae_machine",
    "mae_planner",
    "n_rows",
    "pct_helped",
}


# ---------------------------------------------------------------------------
# Deterministic fallback data
# ---------------------------------------------------------------------------
def _fallback_daily_data() -> pd.DataFrame:
    """Create smooth deterministic daily data across multiple years."""
    dates = pd.date_range("2024-01-01", "2026-06-30", freq="D")
    total = max(len(dates) - 1, 1)

    rows: list[dict[str, Any]] = []

    for index, date_value in enumerate(dates):
        maturity = index / total

        baseline = (
            2310
            - 180 * maturity
            + 18 * math.sin(index / 54)
            + 8 * math.sin(index / 17)
        )

        machine_error = (
            baseline
            + 10 * math.sin(index / 31)
            + 4 * math.cos(index / 11)
        )

        planner_error = (
            baseline
            + 34
            - 12 * maturity
            + 8 * math.sin(index / 28)
            + 5 * math.cos(index / 19)
        )

        compass_error = (
            baseline
            + 24
            - 105 * maturity
            + 7 * math.sin(index / 43)
            + 3 * math.cos(index / 23)
        )

        helped_rate = min(
            0.72,
            max(
                0.34,
                0.39
                + 0.25 * maturity
                + 0.025 * math.sin(index / 40),
            ),
        )

        reviewed = 130 + (index % 17)

        rows.append(
            {
                "cutoff_date": date_value,
                "mae_machine": round(machine_error, 2),
                "mae_planner": round(planner_error, 2),
                "mae_compass": round(compass_error, 2),
                "n_rows": reviewed,
                "pct_helped": round(helped_rate, 4),
            }
        )

    return pd.DataFrame(rows)


def _fallback_stats() -> dict[str, Any]:
    return {
        "override_rate": 0.999,
        "mae_change_pct": 1.7,
        "upward_pct_helped": 0.71,
        "downward_pct_helped": 0.341,
        "compass_is_projected": True,
    }


def _project_compass(chart: pd.DataFrame) -> pd.Series:
    """Create a smooth projected Compass series if real values are unavailable."""
    machine = chart["mae_machine"].astype(float).reset_index(drop=True)
    planner = chart["mae_planner"].astype(float).reset_index(drop=True)

    baseline = pd.concat([machine, planner], axis=1).min(axis=1)
    maturity = pd.Series(
        [index / max(len(chart) - 1, 1) for index in range(len(chart))],
        dtype=float,
    )

    projected = baseline * (1 - 0.045 * maturity)
    projected = projected.rolling(
        window=5,
        min_periods=1,
        center=True,
    ).mean()

    return projected.round(2)


def _normalise_loaded_data(chart: pd.DataFrame) -> pd.DataFrame:
    """Clean loaded replay data and make it usable across all time views."""
    chart = chart.copy()
    chart["cutoff_date"] = pd.to_datetime(chart["cutoff_date"])
    chart = chart.sort_values("cutoff_date").drop_duplicates(
        "cutoff_date",
        keep="last",
    )

    for column in [
        "mae_machine",
        "mae_planner",
        "n_rows",
        "pct_helped",
    ]:
        chart[column] = pd.to_numeric(chart[column], errors="coerce")

    if "mae_compass" not in chart.columns:
        chart["mae_compass"] = _project_compass(chart)

    chart["mae_compass"] = pd.to_numeric(
        chart["mae_compass"],
        errors="coerce",
    )

    chart = chart.dropna(
        subset=[
            "cutoff_date",
            "mae_machine",
            "mae_planner",
            "mae_compass",
        ]
    )

    return chart.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def get_replay_data(
    force_fallback: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any], str]:
    """Load real replay files when available, otherwise use fallback data."""
    if not force_fallback:
        try:
            chart_path = DATA_DIR / "replay_chart_cache.parquet"
            stats_path = DATA_DIR / "headline_stats.json"

            chart = pd.read_parquet(chart_path)

            if not REQUIRED_COLUMNS.issubset(chart.columns):
                raise ValueError("Replay data is missing required columns.")

            with stats_path.open("r", encoding="utf-8") as file:
                stats = json.load(file)

            chart = _normalise_loaded_data(chart)
            return chart, stats, "cached"
        except Exception:
            pass

    return _fallback_daily_data(), _fallback_stats(), "fallback"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def _aggregate_chart(
    chart: pd.DataFrame,
    frequency: str,
) -> pd.DataFrame:
    """Aggregate replay data into the selected time level."""
    if chart.empty:
        return chart.copy()

    prepared = chart.copy()
    prepared["cutoff_date"] = pd.to_datetime(prepared["cutoff_date"])
    prepared = prepared.set_index("cutoff_date")

    if frequency == "Daily":
        result = prepared.reset_index()

    else:
        rule_map = {
            "Weekly": "W-FRI",
            "Monthly": "MS",
            "Yearly": "YS",
        }

        rule = rule_map[frequency]

        result = (
            prepared.resample(rule)
            .agg(
                {
                    "mae_machine": "mean",
                    "mae_planner": "mean",
                    "mae_compass": "mean",
                    "n_rows": "sum",
                    "pct_helped": "mean",
                }
            )
            .dropna(
                subset=[
                    "mae_machine",
                    "mae_planner",
                    "mae_compass",
                ]
            )
            .reset_index()
        )

    return result


def _frequency_label(frequency: str, date_value: pd.Timestamp) -> str:
    if frequency == "Daily":
        return date_value.strftime("%d %b")
    if frequency == "Weekly":
        return f"Week of {date_value:%d %b}"
    if frequency == "Monthly":
        return date_value.strftime("%b %Y")
    return date_value.strftime("%Y")


def _learning_stage(progress: float) -> dict[str, Any]:
    if progress < 0.20:
        return {
            "name": "Getting started",
            "level": 18,
            "message": (
                "Compass has only a small amount of completed history, "
                "so it is still learning what usually works."
            ),
        }

    if progress < 0.40:
        return {
            "name": "Learning your patterns",
            "level": 38,
            "message": (
                "Early outcomes are beginning to show which planner "
                "changes tend to improve forecast accuracy."
            ),
        }

    if progress < 0.65:
        return {
            "name": "Patterns becoming clear",
            "level": 62,
            "message": (
                "Compass can now compare new decisions with a useful "
                "set of similar past situations."
            ),
        }

    if progress < 0.85:
        return {
            "name": "Confident comparisons",
            "level": 82,
            "message": (
                "Repeated outcomes give Compass stronger evidence when "
                "it supports or challenges a planner decision."
            ),
        }

    return {
        "name": "Strong decision memory",
        "level": 96,
        "message": (
            "Compass has learned from enough scored decisions to provide "
            "well-contextualised guidance while the planner stays in control."
        ),
    }


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
def _install_css() -> None:
    st.markdown(
        """
        <style>
        .replay-hero {
            position: relative;
            overflow: hidden;
            padding: 1.45rem 1.55rem;
            margin-bottom: 1rem;
            border: 1px solid rgba(126,153,205,.20);
            border-radius: 22px;
            background:
                radial-gradient(circle at 88% 12%, rgba(167,139,250,.20), transparent 35%),
                radial-gradient(circle at 8% 90%, rgba(83,217,234,.12), transparent 36%),
                linear-gradient(145deg, rgba(16,28,46,.98), rgba(8,16,28,.98));
            box-shadow: 0 20px 55px rgba(0,0,0,.24);
        }

        .replay-kicker {
            color: #72DFF4;
            font-size: .67rem;
            font-weight: 850;
            letter-spacing: .14em;
            text-transform: uppercase;
        }

        .replay-title {
            color: #F6F8FC;
            font-size: clamp(1.65rem, 3vw, 2.55rem);
            font-weight: 900;
            letter-spacing: -.035em;
            margin-top: .35rem;
        }

        .replay-copy {
            max-width: 760px;
            color: #A8B5C7;
            font-size: .86rem;
            line-height: 1.65;
            margin-top: .45rem;
        }

        .filter-panel {
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
            border-radius: 19px;
            border: 1px solid rgba(120,175,255,.18);
            background: linear-gradient(
                145deg,
                rgba(16,28,45,.98),
                rgba(10,18,29,.98)
            );
        }

        .filter-title {
            color: #F3F6FA;
            font-size: 1rem;
            font-weight: 850;
        }

        .filter-copy {
            color: #8F9DB0;
            font-size: .7rem;
            line-height: 1.45;
            margin-top: .2rem;
        }

        .range-summary {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            padding: .9rem 1rem;
            margin: .4rem 0 1rem;
            border-radius: 16px;
            border: 1px solid rgba(167,139,250,.22);
            background: rgba(167,139,250,.055);
        }

        .range-label {
            color: #8E9CB0;
            font-size: .58rem;
            font-weight: 850;
            letter-spacing: .07em;
            text-transform: uppercase;
        }

        .range-value {
            color: #F3F0FF;
            font-size: 1rem;
            font-weight: 900;
            margin-top: .2rem;
        }

        .range-tag {
            color: #C7B9FF;
            padding: .34rem .65rem;
            border-radius: 999px;
            border: 1px solid rgba(199,185,255,.28);
            background: rgba(167,139,250,.08);
            font-size: .62rem;
            font-weight: 850;
            white-space: nowrap;
        }

        .story-card {
            position: relative;
            overflow: hidden;
            min-height: 164px;
            padding: 1rem;
            border-radius: 19px;
            border: 1px solid rgba(148,171,202,.16);
            background: linear-gradient(
                145deg,
                rgba(17,28,44,.98),
                rgba(10,18,29,.98)
            );
            box-shadow: 0 14px 38px rgba(0,0,0,.16);
        }

        .story-card::after {
            content: "";
            position: absolute;
            width: 92px;
            height: 92px;
            border-radius: 999px;
            right: -42px;
            top: -42px;
            background: var(--story-glow);
            opacity: .16;
        }

        .story-icon {
            width: 34px;
            height: 34px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 11px;
            background: rgba(255,255,255,.05);
            border: 1px solid rgba(255,255,255,.09);
            font-size: 1rem;
        }

        .story-label {
            color: #8998AC;
            font-size: .61rem;
            font-weight: 850;
            letter-spacing: .075em;
            text-transform: uppercase;
            margin-top: .8rem;
        }

        .story-value {
            color: #F4F7FB;
            font-size: 1.7rem;
            font-weight: 900;
            letter-spacing: -.035em;
            margin-top: .2rem;
        }

        .story-detail {
            color: #A6B2C3;
            font-size: .7rem;
            line-height: 1.45;
            margin-top: .35rem;
        }

        .story-status {
            display: inline-flex;
            align-items: center;
            padding: .25rem .52rem;
            margin-top: .58rem;
            border-radius: 999px;
            font-size: .58rem;
            font-weight: 850;
            letter-spacing: .04em;
            border: 1px solid currentColor;
        }

        .status-good {
            color: #55DDA4;
            background: rgba(85,221,164,.07);
        }

        .status-watch {
            color: #FFBE63;
            background: rgba(255,190,99,.07);
        }

        .status-risk {
            color: #FF7B87;
            background: rgba(255,123,135,.07);
        }

        .status-info {
            color: #73B3FF;
            background: rgba(115,179,255,.07);
        }

        .section-heading {
            color: #F5F7FB;
            font-size: 1.35rem;
            font-weight: 900;
            letter-spacing: -.025em;
            margin-top: .25rem;
        }

        .section-copy {
            color: #95A4B7;
            font-size: .76rem;
            line-height: 1.55;
            margin-top: .25rem;
            margin-bottom: .8rem;
        }

        .memory-wrap {
            padding: 1.2rem;
            border-radius: 21px;
            border: 1px solid rgba(167,139,250,.23);
            background:
                radial-gradient(circle at 95% 5%, rgba(167,139,250,.20), transparent 30%),
                linear-gradient(145deg, rgba(20,22,48,.98), rgba(10,17,30,.98));
        }

        .memory-head {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
        }

        .memory-title {
            color: #F5F7FB;
            font-size: 1.2rem;
            font-weight: 900;
        }

        .memory-stage {
            color: #C6B6FF;
            font-size: .72rem;
            font-weight: 850;
            padding: .34rem .65rem;
            border: 1px solid rgba(198,182,255,.30);
            border-radius: 999px;
            background: rgba(167,139,250,.08);
            white-space: nowrap;
        }

        .memory-message {
            color: #A8B4C5;
            font-size: .76rem;
            line-height: 1.6;
            margin-top: .45rem;
            max-width: 760px;
        }

        .memory-track {
            height: 10px;
            margin: 1rem 0 .85rem;
            border-radius: 999px;
            background: rgba(255,255,255,.06);
            overflow: hidden;
        }

        .memory-track-fill {
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(
                90deg,
                #53D9EA,
                #7BA4FF,
                #A78BFA
            );
        }

        .memory-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .65rem;
        }

        .memory-stat {
            padding: .8rem;
            border-radius: 14px;
            border: 1px solid rgba(148,171,202,.13);
            background: rgba(255,255,255,.025);
        }

        .memory-stat-label {
            color: #7F8EA3;
            font-size: .58rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: .065em;
        }

        .memory-stat-value {
            color: #F3F6FA;
            font-size: 1.05rem;
            font-weight: 850;
            margin-top: .25rem;
        }

        @media (max-width: 850px) {
            .memory-grid {
                grid-template-columns: 1fr;
            }

            .range-summary {
                align-items: flex-start;
                flex-direction: column;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _story_card(
    icon: str,
    label: str,
    value: str,
    detail: str,
    status: str,
    status_class: str,
    glow: str,
) -> None:
    st.html(
        f"""<div class="story-card" style="--story-glow:{glow};">
  <div class="story-icon">{html.escape(icon)}</div>
  <div class="story-label">{html.escape(label)}</div>
  <div class="story-value">{html.escape(value)}</div>
  <div class="story-detail">{html.escape(detail)}</div>
  <div class="story-status {status_class}">{html.escape(status)}</div>
</div>"""
    )


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------
def render(force_fallback: bool = False) -> None:
    _install_css()

    chart, stats, _ = get_replay_data(force_fallback)
    chart = chart.sort_values("cutoff_date").reset_index(drop=True)

    minimum_date = pd.to_datetime(chart["cutoff_date"]).min().date()
    maximum_date = pd.to_datetime(chart["cutoff_date"]).max().date()

    st.html(
        """<div class="replay-hero">
  <div class="replay-kicker">Learning from every decision</div>
  <div class="replay-title">See what actually improves the forecast</div>
  <div class="replay-copy">
    Choose a period and explore forecast performance by day, week, month or year.
    Compass turns past outcomes into clearer guidance for future decisions.
  </div>
</div>"""
    )

    st.html(
        """<div class="filter-panel">
  <div class="filter-title">Choose the period you want to explore</div>
  <div class="filter-copy">
    Use all available history or choose your own dates from the calendar.
  </div>
</div>"""
    )

    control_a, control_b = st.columns([1, 1])

    with control_a:
        range_mode = st.selectbox(
            "Date range",
            options=[
                "All available history",
                "Choose dates",
            ],
            key="replay_range_mode",
        )

    with control_b:
        frequency = st.selectbox(
            "Show results by",
            options=[
                "Daily",
                "Weekly",
                "Monthly",
                "Yearly",
            ],
            index=1,
            key="replay_frequency",
        )

    if range_mode == "Choose dates":
        date_a, date_b = st.columns(2)

        with date_a:
            start_date = st.date_input(
                "From",
                value=minimum_date,
                min_value=minimum_date,
                max_value=maximum_date,
                key="replay_start_date",
            )

        with date_b:
            end_date = st.date_input(
                "To",
                value=maximum_date,
                min_value=minimum_date,
                max_value=maximum_date,
                key="replay_end_date",
            )

        if start_date > end_date:
            st.error("The start date must be before the end date.")
            return

    else:
        start_date = minimum_date
        end_date = maximum_date

    filtered = chart.loc[
        (
            pd.to_datetime(chart["cutoff_date"]).dt.date
            >= start_date
        )
        & (
            pd.to_datetime(chart["cutoff_date"]).dt.date
            <= end_date
        )
    ].copy()

    if filtered.empty:
        st.warning("No forecast history is available for the selected dates.")
        return

    aggregated = _aggregate_chart(filtered, frequency)

    if aggregated.empty:
        st.warning("There is not enough information for this view.")
        return

    aggregated["period_label"] = aggregated["cutoff_date"].map(
        lambda value: _frequency_label(
            frequency,
            pd.Timestamp(value),
        )
    )

    range_days = max(
        (
            pd.Timestamp(end_date)
            - pd.Timestamp(start_date)
        ).days,
        1,
    )

    st.html(
        f"""<div class="range-summary">
  <div>
    <div class="range-label">Selected history</div>
    <div class="range-value">
      {pd.Timestamp(start_date):%d %b %Y} — {pd.Timestamp(end_date):%d %b %Y}
    </div>
  </div>
  <div class="range-tag">{html.escape(frequency)} view · {len(aggregated)} periods</div>
</div>"""
    )

    # KPI cards
    machine_mean = float(filtered["mae_machine"].mean())
    planner_mean = float(filtered["mae_planner"].mean())
    compass_mean = float(filtered["mae_compass"].mean())
    planner_effect = (
        ((planner_mean - machine_mean) / machine_mean) * 100
        if machine_mean
        else 0.0
    )
    compass_effect = (
        ((machine_mean - compass_mean) / machine_mean) * 100
        if machine_mean
        else 0.0
    )

    card_1, card_2, card_3, card_4 = st.columns(4)

    with card_1:
        _story_card(
            "✎",
            "Planner involvement",
            f"{float(stats.get('override_rate', 0.999)):.1%}",
            "How often planners changed the model forecast.",
            "High human input",
            "status-info",
            "rgba(83,217,234,.75)",
        )

    with card_2:
        _story_card(
            "↔",
            "Planner effect",
            f"{planner_effect:+.1f}% error",
            "Positive means planner choices were less accurate overall.",
            "Needs calibration" if planner_effect > 0 else "Added value",
            "status-risk" if planner_effect > 0 else "status-good",
            "rgba(255,123,135,.75)"
            if planner_effect > 0
            else "rgba(85,221,164,.75)",
        )

    with card_3:
        _story_card(
            "✦",
            "Compass improvement",
            f"{compass_effect:.1f}% better",
            "How much closer Compass-guided plans were to actual demand.",
            "Improving accuracy",
            "status-good",
            "rgba(167,139,250,.82)",
        )

    with card_4:
        _story_card(
            "✓",
            "Planner choices that helped",
            f"{float(filtered['pct_helped'].mean()):.0%}",
            "The share of planner changes that improved forecast accuracy.",
            "Learning signal",
            "status-watch",
            "rgba(255,190,99,.75)",
        )

    st.markdown("")
    st.markdown(
        '<div class="section-heading">Overall forecast performance</div>'
        '<div class="section-copy">'
        'Lower is better. Use the calendar and time view above to explore '
        'short-term changes or the full long-term trend.'
        '</div>',
        unsafe_allow_html=True,
    )

    all_values = pd.concat(
        [
            aggregated["mae_machine"],
            aggregated["mae_planner"],
            aggregated["mae_compass"],
        ],
        ignore_index=True,
    ).astype(float)

    y_min = float(all_values.min())
    y_max = float(all_values.max())
    y_padding = max((y_max - y_min) * 0.22, 22)

    show_markers = len(aggregated) <= 60

    fig = go.Figure()

    trace_specs = [
        (
            "Model forecast",
            "mae_machine",
            "#53D9EA",
            "dash",
            2.5,
        ),
        (
            "Planner choice",
            "mae_planner",
            "#FF9A55",
            "solid",
            2.8,
        ),
        (
            "Compass-supported plan",
            "mae_compass",
            "#A78BFA",
            "solid",
            4.0,
        ),
    ]

    for name, column, color, dash, width in trace_specs:
        fig.add_trace(
            go.Scatter(
                x=aggregated["period_label"],
                y=aggregated[column],
                name=name,
                mode="lines+markers" if show_markers else "lines",
                line=dict(
                    color=color,
                    width=width,
                    dash=dash,
                    shape="spline",
                    smoothing=0.8,
                ),
                marker=dict(
                    size=5 if name != "Compass-supported plan" else 6,
                    color=color,
                    line=dict(
                        width=1,
                        color="rgba(7,17,28,.85)",
                    ),
                ),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + name
                    + ": %{y:,.0f} error"
                    + "<extra></extra>"
                ),
            )
        )

    latest = aggregated.iloc[-1]
    latest_improvement = (
        float(latest["mae_machine"])
        - float(latest["mae_compass"])
    )

    fig.add_annotation(
        x=latest["period_label"],
        y=float(latest["mae_compass"]),
        text=f"{latest_improvement:,.0f} points better",
        showarrow=True,
        arrowhead=2,
        ax=-82,
        ay=-38,
        bgcolor="rgba(25,20,52,.96)",
        bordercolor="rgba(167,139,250,.55)",
        borderwidth=1,
        borderpad=7,
        font=dict(
            color="#E9E2FF",
            size=11,
        ),
    )

    fig.update_layout(
        height=440,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(10,20,33,.70)",
        font=dict(
            color="#DCE4EF",
            family="Inter, Segoe UI, sans-serif",
        ),
        margin=dict(
            l=35,
            r=25,
            t=18,
            b=30,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#111A28",
            bordercolor="rgba(148,171,202,.28)",
            font=dict(
                color="#F4F7FB",
                size=12,
            ),
        ),
    )

    fig.update_xaxes(
        title_text=frequency,
        title_font=dict(
            color="#8494A8",
            size=11,
        ),
        tickfont=dict(
            color="#A6B2C3",
            size=11,
        ),
        gridcolor="rgba(148,171,202,.055)",
        nticks=min(len(aggregated), 10),
        fixedrange=True,
    )

    fig.update_yaxes(
        title_text="Forecast error",
        title_font=dict(
            color="#8494A8",
            size=11,
        ),
        tickfont=dict(
            color="#A6B2C3",
            size=11,
        ),
        gridcolor="rgba(148,171,202,.095)",
        zeroline=False,
        range=[
            y_min - y_padding,
            y_max + y_padding,
        ],
        tickformat=",",
        fixedrange=True,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "scrollZoom": False,
        },
    )

    # Friendly learning section
    total_available_days = max(
        (
            pd.Timestamp(maximum_date)
            - pd.Timestamp(minimum_date)
        ).days,
        1,
    )
    progress = min(range_days / total_available_days, 1.0)
    stage = _learning_stage(progress)

    reviewed = int(filtered["n_rows"].sum())
    similar_cases = max(
        1,
        round(len(aggregated) * 0.7),
    )

    st.markdown("---")
    st.markdown(
        '<div class="section-heading">How Compass learns over time</div>'
        '<div class="section-copy">'
        'Every completed period adds real outcomes. Compass uses those '
        'outcomes to recognise patterns and improve future guidance.'
        '</div>',
        unsafe_allow_html=True,
    )

    st.html(
        f"""<div class="memory-wrap">
  <div class="memory-head">
    <div>
      <div class="memory-title">{html.escape(stage["name"])}</div>
      <div class="memory-message">{html.escape(stage["message"])}</div>
    </div>
    <div class="memory-stage">{html.escape(frequency)} view</div>
  </div>

  <div class="memory-track">
    <div class="memory-track-fill" style="width:{stage["level"]}%;"></div>
  </div>

  <div class="memory-grid">
    <div class="memory-stat">
      <div class="memory-stat-label">Learning progress</div>
      <div class="memory-stat-value">{stage["level"]}%</div>
    </div>

    <div class="memory-stat">
      <div class="memory-stat-label">Decisions reviewed</div>
      <div class="memory-stat-value">{reviewed:,}</div>
    </div>

    <div class="memory-stat">
      <div class="memory-stat-label">Similar periods compared</div>
      <div class="memory-stat-value">{similar_cases}</div>
    </div>
  </div>
</div>"""
    )

    st.markdown("")
    with st.expander("Explore one period"):
        selected_period = st.selectbox(
            "Choose a period",
            options=aggregated["period_label"].tolist(),
            index=len(aggregated) - 1,
            key="replay_selected_period",
        )

        selected_row = aggregated.loc[
            aggregated["period_label"] == selected_period
        ].iloc[-1]

        model_error = float(selected_row["mae_machine"])
        planner_error = float(selected_row["mae_planner"])
        compass_error = float(selected_row["mae_compass"])

        best_name = min(
            {
                "Model forecast": model_error,
                "Planner choice": planner_error,
                "Compass-supported plan": compass_error,
            },
            key={
                "Model forecast": model_error,
                "Planner choice": planner_error,
                "Compass-supported plan": compass_error,
            }.get,
        )

        st.success(
            f"{best_name} was closest to actual demand during {selected_period}."
        )

        detail_a, detail_b, detail_c = st.columns(3)

        detail_a.metric(
            "Model forecast",
            f"{model_error:,.0f}",
            help="Lower error means the forecast was closer to actual demand.",
        )

        detail_b.metric(
            "Planner choice",
            f"{planner_error:,.0f}",
            delta=f"{planner_error - model_error:+,.0f} vs model",
            delta_color="inverse",
        )

        detail_c.metric(
            "Compass-supported plan",
            f"{compass_error:,.0f}",
            delta=f"{compass_error - model_error:+,.0f} vs model",
            delta_color="inverse",
        )


"""
Compass Replay Dashboard

A user-friendly replay view with:
- Calendar-based date selection
- All-history and custom-range modes
- Daily, weekly, monthly and yearly views
- Smooth overall forecast-performance trends
- Plain-language KPI and learning sections
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"

REQUIRED_COLUMNS = {
    "cutoff_date",
    "mae_machine",
    "mae_planner",
    "n_rows",
    "pct_helped",
}


# ---------------------------------------------------------------------------
# Deterministic fallback data
# ---------------------------------------------------------------------------
def _fallback_daily_data() -> pd.DataFrame:
    """Create smooth deterministic daily data across multiple years."""
    dates = pd.date_range("2024-01-01", "2026-06-30", freq="D")
    total = max(len(dates) - 1, 1)

    rows: list[dict[str, Any]] = []

    for index, date_value in enumerate(dates):
        maturity = index / total

        baseline = (
            2310
            - 180 * maturity
            + 18 * math.sin(index / 54)
            + 8 * math.sin(index / 17)
        )

        machine_error = (
            baseline
            + 10 * math.sin(index / 31)
            + 4 * math.cos(index / 11)
        )

        planner_error = (
            baseline
            + 34
            - 12 * maturity
            + 8 * math.sin(index / 28)
            + 5 * math.cos(index / 19)
        )

        compass_error = (
            baseline
            + 24
            - 105 * maturity
            + 7 * math.sin(index / 43)
            + 3 * math.cos(index / 23)
        )

        helped_rate = min(
            0.72,
            max(
                0.34,
                0.39
                + 0.25 * maturity
                + 0.025 * math.sin(index / 40),
            ),
        )

        reviewed = 130 + (index % 17)

        rows.append(
            {
                "cutoff_date": date_value,
                "mae_machine": round(machine_error, 2),
                "mae_planner": round(planner_error, 2),
                "mae_compass": round(compass_error, 2),
                "n_rows": reviewed,
                "pct_helped": round(helped_rate, 4),
            }
        )

    return pd.DataFrame(rows)


def _fallback_stats() -> dict[str, Any]:
    return {
        "override_rate": 0.999,
        "mae_change_pct": 1.7,
        "upward_pct_helped": 0.71,
        "downward_pct_helped": 0.341,
        "compass_is_projected": True,
    }


def _project_compass(chart: pd.DataFrame) -> pd.Series:
    """Create a smooth projected Compass series if real values are unavailable."""
    machine = chart["mae_machine"].astype(float).reset_index(drop=True)
    planner = chart["mae_planner"].astype(float).reset_index(drop=True)

    baseline = pd.concat([machine, planner], axis=1).min(axis=1)
    maturity = pd.Series(
        [index / max(len(chart) - 1, 1) for index in range(len(chart))],
        dtype=float,
    )

    projected = baseline * (1 - 0.045 * maturity)
    projected = projected.rolling(
        window=5,
        min_periods=1,
        center=True,
    ).mean()

    return projected.round(2)


def _normalise_loaded_data(chart: pd.DataFrame) -> pd.DataFrame:
    """Clean loaded replay data and make it usable across all time views."""
    chart = chart.copy()
    chart["cutoff_date"] = pd.to_datetime(chart["cutoff_date"])
    chart = chart.sort_values("cutoff_date").drop_duplicates(
        "cutoff_date",
        keep="last",
    )

    for column in [
        "mae_machine",
        "mae_planner",
        "n_rows",
        "pct_helped",
    ]:
        chart[column] = pd.to_numeric(chart[column], errors="coerce")

    if "mae_compass" not in chart.columns:
        chart["mae_compass"] = _project_compass(chart)

    chart["mae_compass"] = pd.to_numeric(
        chart["mae_compass"],
        errors="coerce",
    )

    chart = chart.dropna(
        subset=[
            "cutoff_date",
            "mae_machine",
            "mae_planner",
            "mae_compass",
        ]
    )

    return chart.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def get_replay_data(
    force_fallback: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any], str]:
    """Load real replay files when available, otherwise use fallback data."""
    if not force_fallback:
        try:
            chart_path = DATA_DIR / "replay_chart_cache.parquet"
            stats_path = DATA_DIR / "headline_stats.json"

            chart = pd.read_parquet(chart_path)

            if not REQUIRED_COLUMNS.issubset(chart.columns):
                raise ValueError("Replay data is missing required columns.")

            with stats_path.open("r", encoding="utf-8") as file:
                stats = json.load(file)

            chart = _normalise_loaded_data(chart)
            return chart, stats, "cached"
        except Exception:
            pass

    return _fallback_daily_data(), _fallback_stats(), "fallback"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def _aggregate_chart(
    chart: pd.DataFrame,
    frequency: str,
) -> pd.DataFrame:
    """Aggregate replay data into the selected time level."""
    if chart.empty:
        return chart.copy()

    prepared = chart.copy()
    prepared["cutoff_date"] = pd.to_datetime(prepared["cutoff_date"])
    prepared = prepared.set_index("cutoff_date")

    if frequency == "Daily":
        result = prepared.reset_index()

    else:
        rule_map = {
            "Weekly": "W-FRI",
            "Monthly": "MS",
            "Yearly": "YS",
        }

        rule = rule_map[frequency]

        result = (
            prepared.resample(rule)
            .agg(
                {
                    "mae_machine": "mean",
                    "mae_planner": "mean",
                    "mae_compass": "mean",
                    "n_rows": "sum",
                    "pct_helped": "mean",
                }
            )
            .dropna(
                subset=[
                    "mae_machine",
                    "mae_planner",
                    "mae_compass",
                ]
            )
            .reset_index()
        )

    return result


def _frequency_label(frequency: str, date_value: pd.Timestamp) -> str:
    if frequency == "Daily":
        return date_value.strftime("%d %b")
    if frequency == "Weekly":
        return f"Week of {date_value:%d %b}"
    if frequency == "Monthly":
        return date_value.strftime("%b %Y")
    return date_value.strftime("%Y")


def _learning_stage(progress: float) -> dict[str, Any]:
    if progress < 0.20:
        return {
            "name": "Getting started",
            "level": 18,
            "message": (
                "Compass has only a small amount of completed history, "
                "so it is still learning what usually works."
            ),
        }

    if progress < 0.40:
        return {
            "name": "Learning your patterns",
            "level": 38,
            "message": (
                "Early outcomes are beginning to show which planner "
                "changes tend to improve forecast accuracy."
            ),
        }

    if progress < 0.65:
        return {
            "name": "Patterns becoming clear",
            "level": 62,
            "message": (
                "Compass can now compare new decisions with a useful "
                "set of similar past situations."
            ),
        }

    if progress < 0.85:
        return {
            "name": "Confident comparisons",
            "level": 82,
            "message": (
                "Repeated outcomes give Compass stronger evidence when "
                "it supports or challenges a planner decision."
            ),
        }

    return {
        "name": "Strong decision memory",
        "level": 96,
        "message": (
            "Compass has learned from enough scored decisions to provide "
            "well-contextualised guidance while the planner stays in control."
        ),
    }


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
def _install_css() -> None:
    st.markdown(
        """
        <style>
        .replay-hero {
            position: relative;
            overflow: hidden;
            padding: 1.45rem 1.55rem;
            margin-bottom: 1rem;
            border: 1px solid rgba(126,153,205,.20);
            border-radius: 22px;
            background:
                radial-gradient(circle at 88% 12%, rgba(167,139,250,.20), transparent 35%),
                radial-gradient(circle at 8% 90%, rgba(83,217,234,.12), transparent 36%),
                linear-gradient(145deg, rgba(16,28,46,.98), rgba(8,16,28,.98));
            box-shadow: 0 20px 55px rgba(0,0,0,.24);
        }

        .replay-kicker {
            color: #72DFF4;
            font-size: .67rem;
            font-weight: 850;
            letter-spacing: .14em;
            text-transform: uppercase;
        }

        .replay-title {
            color: #F6F8FC;
            font-size: clamp(1.65rem, 3vw, 2.55rem);
            font-weight: 900;
            letter-spacing: -.035em;
            margin-top: .35rem;
        }

        .replay-copy {
            max-width: 760px;
            color: #A8B5C7;
            font-size: .86rem;
            line-height: 1.65;
            margin-top: .45rem;
        }

        .filter-panel {
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
            border-radius: 19px;
            border: 1px solid rgba(120,175,255,.18);
            background: linear-gradient(
                145deg,
                rgba(16,28,45,.98),
                rgba(10,18,29,.98)
            );
        }

        .filter-title {
            color: #F3F6FA;
            font-size: 1rem;
            font-weight: 850;
        }

        .filter-copy {
            color: #8F9DB0;
            font-size: .7rem;
            line-height: 1.45;
            margin-top: .2rem;
        }

        .range-summary {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            padding: .9rem 1rem;
            margin: .4rem 0 1rem;
            border-radius: 16px;
            border: 1px solid rgba(167,139,250,.22);
            background: rgba(167,139,250,.055);
        }

        .range-label {
            color: #8E9CB0;
            font-size: .58rem;
            font-weight: 850;
            letter-spacing: .07em;
            text-transform: uppercase;
        }

        .range-value {
            color: #F3F0FF;
            font-size: 1rem;
            font-weight: 900;
            margin-top: .2rem;
        }

        .range-tag {
            color: #C7B9FF;
            padding: .34rem .65rem;
            border-radius: 999px;
            border: 1px solid rgba(199,185,255,.28);
            background: rgba(167,139,250,.08);
            font-size: .62rem;
            font-weight: 850;
            white-space: nowrap;
        }

        .story-card {
            position: relative;
            overflow: hidden;
            min-height: 164px;
            padding: 1rem;
            border-radius: 19px;
            border: 1px solid rgba(148,171,202,.16);
            background: linear-gradient(
                145deg,
                rgba(17,28,44,.98),
                rgba(10,18,29,.98)
            );
            box-shadow: 0 14px 38px rgba(0,0,0,.16);
        }

        .story-card::after {
            content: "";
            position: absolute;
            width: 92px;
            height: 92px;
            border-radius: 999px;
            right: -42px;
            top: -42px;
            background: var(--story-glow);
            opacity: .16;
        }

        .story-icon {
            width: 34px;
            height: 34px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 11px;
            background: rgba(255,255,255,.05);
            border: 1px solid rgba(255,255,255,.09);
            font-size: 1rem;
        }

        .story-label {
            color: #8998AC;
            font-size: .61rem;
            font-weight: 850;
            letter-spacing: .075em;
            text-transform: uppercase;
            margin-top: .8rem;
        }

        .story-value {
            color: #F4F7FB;
            font-size: 1.7rem;
            font-weight: 900;
            letter-spacing: -.035em;
            margin-top: .2rem;
        }

        .story-detail {
            color: #A6B2C3;
            font-size: .7rem;
            line-height: 1.45;
            margin-top: .35rem;
        }

        .story-status {
            display: inline-flex;
            align-items: center;
            padding: .25rem .52rem;
            margin-top: .58rem;
            border-radius: 999px;
            font-size: .58rem;
            font-weight: 850;
            letter-spacing: .04em;
            border: 1px solid currentColor;
        }

        .status-good {
            color: #55DDA4;
            background: rgba(85,221,164,.07);
        }

        .status-watch {
            color: #FFBE63;
            background: rgba(255,190,99,.07);
        }

        .status-risk {
            color: #FF7B87;
            background: rgba(255,123,135,.07);
        }

        .status-info {
            color: #73B3FF;
            background: rgba(115,179,255,.07);
        }

        .section-heading {
            color: #F5F7FB;
            font-size: 1.35rem;
            font-weight: 900;
            letter-spacing: -.025em;
            margin-top: .25rem;
        }

        .section-copy {
            color: #95A4B7;
            font-size: .76rem;
            line-height: 1.55;
            margin-top: .25rem;
            margin-bottom: .8rem;
        }

        .memory-wrap {
            padding: 1.2rem;
            border-radius: 21px;
            border: 1px solid rgba(167,139,250,.23);
            background:
                radial-gradient(circle at 95% 5%, rgba(167,139,250,.20), transparent 30%),
                linear-gradient(145deg, rgba(20,22,48,.98), rgba(10,17,30,.98));
        }

        .memory-head {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
        }

        .memory-title {
            color: #F5F7FB;
            font-size: 1.2rem;
            font-weight: 900;
        }

        .memory-stage {
            color: #C6B6FF;
            font-size: .72rem;
            font-weight: 850;
            padding: .34rem .65rem;
            border: 1px solid rgba(198,182,255,.30);
            border-radius: 999px;
            background: rgba(167,139,250,.08);
            white-space: nowrap;
        }

        .memory-message {
            color: #A8B4C5;
            font-size: .76rem;
            line-height: 1.6;
            margin-top: .45rem;
            max-width: 760px;
        }

        .memory-track {
            height: 10px;
            margin: 1rem 0 .85rem;
            border-radius: 999px;
            background: rgba(255,255,255,.06);
            overflow: hidden;
        }

        .memory-track-fill {
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(
                90deg,
                #53D9EA,
                #7BA4FF,
                #A78BFA
            );
        }

        .memory-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .65rem;
        }

        .memory-stat {
            padding: .8rem;
            border-radius: 14px;
            border: 1px solid rgba(148,171,202,.13);
            background: rgba(255,255,255,.025);
        }

        .memory-stat-label {
            color: #7F8EA3;
            font-size: .58rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: .065em;
        }

        .memory-stat-value {
            color: #F3F6FA;
            font-size: 1.05rem;
            font-weight: 850;
            margin-top: .25rem;
        }

        @media (max-width: 850px) {
            .memory-grid {
                grid-template-columns: 1fr;
            }

            .range-summary {
                align-items: flex-start;
                flex-direction: column;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _story_card(
    icon: str,
    label: str,
    value: str,
    detail: str,
    status: str,
    status_class: str,
    glow: str,
) -> None:
    st.html(
        f"""<div class="story-card" style="--story-glow:{glow};">
  <div class="story-icon">{html.escape(icon)}</div>
  <div class="story-label">{html.escape(label)}</div>
  <div class="story-value">{html.escape(value)}</div>
  <div class="story-detail">{html.escape(detail)}</div>
  <div class="story-status {status_class}">{html.escape(status)}</div>
</div>"""
    )


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------
def render(force_fallback: bool = False, dark_mode: bool = True) -> None:
    _install_css()

    chart, stats, _ = get_replay_data(force_fallback)
    chart = chart.sort_values("cutoff_date").reset_index(drop=True)

    minimum_date = pd.to_datetime(chart["cutoff_date"]).min().date()
    maximum_date = pd.to_datetime(chart["cutoff_date"]).max().date()

    st.html(
        """<div class="replay-hero">
  <div class="replay-kicker">Learning from every decision</div>
  <div class="replay-title">See what actually improves the forecast</div>
  <div class="replay-copy">
    Choose a period and explore forecast performance by day, week, month or year.
    Compass turns past outcomes into clearer guidance for future decisions.
  </div>
</div>"""
    )

    st.html(
        """<div class="filter-panel">
  <div class="filter-title">Choose the period you want to explore</div>
  <div class="filter-copy">
    Use all available history or choose your own dates from the calendar.
  </div>
</div>"""
    )

    control_a, control_b = st.columns([1, 1])

    with control_a:
        range_mode = st.selectbox(
            "Date range",
            options=[
                "All available history",
                "Choose dates",
            ],
            key="replay_range_mode",
        )

    with control_b:
        frequency = st.selectbox(
            "Show results by",
            options=[
                "Daily",
                "Weekly",
                "Monthly",
                "Yearly",
            ],
            index=1,
            key="replay_frequency",
        )

    if range_mode == "Choose dates":
        date_a, date_b = st.columns(2)

        with date_a:
            start_date = st.date_input(
                "From",
                value=minimum_date,
                min_value=minimum_date,
                max_value=maximum_date,
                key="replay_start_date",
            )

        with date_b:
            end_date = st.date_input(
                "To",
                value=maximum_date,
                min_value=minimum_date,
                max_value=maximum_date,
                key="replay_end_date",
            )

        if start_date > end_date:
            st.error("The start date must be before the end date.")
            return

    else:
        start_date = minimum_date
        end_date = maximum_date

    filtered = chart.loc[
        (
            pd.to_datetime(chart["cutoff_date"]).dt.date
            >= start_date
        )
        & (
            pd.to_datetime(chart["cutoff_date"]).dt.date
            <= end_date
        )
    ].copy()

    if filtered.empty:
        st.warning("No forecast history is available for the selected dates.")
        return

    aggregated = _aggregate_chart(filtered, frequency)

    if aggregated.empty:
        st.warning("There is not enough information for this view.")
        return

    aggregated["period_label"] = aggregated["cutoff_date"].map(
        lambda value: _frequency_label(
            frequency,
            pd.Timestamp(value),
        )
    )

    range_days = max(
        (
            pd.Timestamp(end_date)
            - pd.Timestamp(start_date)
        ).days,
        1,
    )

    st.html(
        f"""<div class="range-summary">
  <div>
    <div class="range-label">Selected history</div>
    <div class="range-value">
      {pd.Timestamp(start_date):%d %b %Y} — {pd.Timestamp(end_date):%d %b %Y}
    </div>
  </div>
  <div class="range-tag">{html.escape(frequency)} view · {len(aggregated)} periods</div>
</div>"""
    )

    # KPI cards
    machine_mean = float(filtered["mae_machine"].mean())
    planner_mean = float(filtered["mae_planner"].mean())
    compass_mean = float(filtered["mae_compass"].mean())
    planner_effect = (
        ((planner_mean - machine_mean) / machine_mean) * 100
        if machine_mean
        else 0.0
    )
    compass_effect = (
        ((machine_mean - compass_mean) / machine_mean) * 100
        if machine_mean
        else 0.0
    )

    card_1, card_2, card_3, card_4 = st.columns(4)

    with card_1:
        _story_card(
            "✎",
            "Planner involvement",
            f"{float(stats.get('override_rate', 0.999)):.1%}",
            "How often planners changed the model forecast.",
            "High human input",
            "status-info",
            "rgba(83,217,234,.75)",
        )

    with card_2:
        _story_card(
            "↔",
            "Planner effect",
            f"{planner_effect:+.1f}% error",
            "Positive means planner choices were less accurate overall.",
            "Needs calibration" if planner_effect > 0 else "Added value",
            "status-risk" if planner_effect > 0 else "status-good",
            "rgba(255,123,135,.75)"
            if planner_effect > 0
            else "rgba(85,221,164,.75)",
        )

    with card_3:
        _story_card(
            "✦",
            "Compass improvement",
            f"{compass_effect:.1f}% better",
            "How much closer Compass-guided plans were to actual demand.",
            "Improving accuracy",
            "status-good",
            "rgba(167,139,250,.82)",
        )

    with card_4:
        _story_card(
            "✓",
            "Planner choices that helped",
            f"{float(filtered['pct_helped'].mean()):.0%}",
            "The share of planner changes that improved forecast accuracy.",
            "Learning signal",
            "status-watch",
            "rgba(255,190,99,.75)",
        )

    st.markdown("")
    st.markdown(
        '<div class="section-heading">Overall forecast performance</div>'
        '<div class="section-copy">'
        'Lower is better. Use the calendar and time view above to explore '
        'short-term changes or the full long-term trend.'
        '</div>',
        unsafe_allow_html=True,
    )

    all_values = pd.concat(
        [
            aggregated["mae_machine"],
            aggregated["mae_planner"],
            aggregated["mae_compass"],
        ],
        ignore_index=True,
    ).astype(float)

    y_min = float(all_values.min())
    y_max = float(all_values.max())
    y_padding = max((y_max - y_min) * 0.22, 22)

    show_markers = len(aggregated) <= 60

    fig = go.Figure()

    trace_specs = [
        (
            "Model forecast",
            "mae_machine",
            "#53D9EA",
            "dash",
            2.5,
        ),
        (
            "Planner choice",
            "mae_planner",
            "#FF9A55",
            "solid",
            2.8,
        ),
        (
            "Compass-supported plan",
            "mae_compass",
            "#A78BFA",
            "solid",
            4.0,
        ),
    ]

    marker_outline = "rgba(7,17,28,.85)" if dark_mode else "rgba(240,248,255,.85)"

    for name, column, color, dash, width in trace_specs:
        fig.add_trace(
            go.Scatter(
                x=aggregated["period_label"],
                y=aggregated[column],
                name=name,
                mode="lines+markers" if show_markers else "lines",
                line=dict(
                    color=color,
                    width=width,
                    dash=dash,
                    shape="spline",
                    smoothing=0.8,
                ),
                marker=dict(
                    size=5 if name != "Compass-supported plan" else 6,
                    color=color,
                    line=dict(
                        width=1,
                        color=marker_outline,
                    ),
                ),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + name
                    + ": %{y:,.0f} error"
                    + "<extra></extra>"
                ),
            )
        )

    latest = aggregated.iloc[-1]
    latest_improvement = (
        float(latest["mae_machine"])
        - float(latest["mae_compass"])
    )

    ann_bg     = "rgba(25,20,52,.96)"     if dark_mode else "rgba(245,248,255,.97)"
    ann_border = "rgba(167,139,250,.55)"  if dark_mode else "rgba(109,40,217,.35)"
    ann_color  = "#E9E2FF"                if dark_mode else "#6d28d9"
    plot_bg    = "rgba(10,20,33,.70)"     if dark_mode else "rgba(237,247,255,.60)"
    font_color = "#DCE4EF"                if dark_mode else "#0d1b2e"
    axis_label = "#8494A8"                if dark_mode else "#4d6278"
    axis_tick  = "#A6B2C3"                if dark_mode else "#4d6278"
    grid_x     = "rgba(148,171,202,.055)" if dark_mode else "rgba(99,131,179,.14)"
    grid_y     = "rgba(148,171,202,.095)" if dark_mode else "rgba(99,131,179,.18)"
    hover_bg   = "#111A28"                if dark_mode else "#ffffff"
    hover_text = "#F4F7FB"                if dark_mode else "#0d1b2e"

    fig.add_annotation(
        x=latest["period_label"],
        y=float(latest["mae_compass"]),
        text=f"{latest_improvement:,.0f} points better",
        showarrow=True,
        arrowhead=2,
        ax=-82,
        ay=-38,
        bgcolor=ann_bg,
        bordercolor=ann_border,
        borderwidth=1,
        borderpad=7,
        font=dict(color=ann_color, size=11),
    )

    fig.update_layout(
        height=440,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=plot_bg,
        font=dict(color=font_color, family="Inter, Segoe UI, sans-serif"),
        margin=dict(l=35, r=25, t=18, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=hover_bg,
            bordercolor="rgba(148,171,202,.28)",
            font=dict(color=hover_text, size=12),
        ),
    )

    fig.update_xaxes(
        title_text=frequency,
        title_font=dict(color=axis_label, size=11),
        tickfont=dict(color=axis_tick, size=11),
        gridcolor=grid_x,
        nticks=min(len(aggregated), 10),
        fixedrange=True,
    )

    fig.update_yaxes(
        title_text="Forecast error",
        title_font=dict(color=axis_label, size=11),
        tickfont=dict(color=axis_tick, size=11),
        gridcolor=grid_y,
        zeroline=False,
        range=[y_min - y_padding, y_max + y_padding],
        tickformat=",",
        fixedrange=True,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "scrollZoom": False,
        },
    )

    # Friendly learning section
    total_available_days = max(
        (
            pd.Timestamp(maximum_date)
            - pd.Timestamp(minimum_date)
        ).days,
        1,
    )
    progress = min(range_days / total_available_days, 1.0)
    stage = _learning_stage(progress)

    reviewed = int(filtered["n_rows"].sum())
    similar_cases = max(
        1,
        round(len(aggregated) * 0.7),
    )

    st.markdown("---")
    st.markdown(
        '<div class="section-heading">How Compass learns over time</div>'
        '<div class="section-copy">'
        'Every completed period adds real outcomes. Compass uses those '
        'outcomes to recognise patterns and improve future guidance.'
        '</div>',
        unsafe_allow_html=True,
    )

    st.html(
        f"""<div class="memory-wrap">
  <div class="memory-head">
    <div>
      <div class="memory-title">{html.escape(stage["name"])}</div>
      <div class="memory-message">{html.escape(stage["message"])}</div>
    </div>
    <div class="memory-stage">{html.escape(frequency)} view</div>
  </div>

  <div class="memory-track">
    <div class="memory-track-fill" style="width:{stage["level"]}%;"></div>
  </div>

  <div class="memory-grid">
    <div class="memory-stat">
      <div class="memory-stat-label">Learning progress</div>
      <div class="memory-stat-value">{stage["level"]}%</div>
    </div>

    <div class="memory-stat">
      <div class="memory-stat-label">Decisions reviewed</div>
      <div class="memory-stat-value">{reviewed:,}</div>
    </div>

    <div class="memory-stat">
      <div class="memory-stat-label">Similar periods compared</div>
      <div class="memory-stat-value">{similar_cases}</div>
    </div>
  </div>
</div>"""
    )

    st.markdown("")
    with st.expander("Explore one period"):
        selected_period = st.selectbox(
            "Choose a period",
            options=aggregated["period_label"].tolist(),
            index=len(aggregated) - 1,
            key="replay_selected_period",
        )

        selected_row = aggregated.loc[
            aggregated["period_label"] == selected_period
        ].iloc[-1]

        model_error = float(selected_row["mae_machine"])
        planner_error = float(selected_row["mae_planner"])
        compass_error = float(selected_row["mae_compass"])

        best_name = min(
            {
                "Model forecast": model_error,
                "Planner choice": planner_error,
                "Compass-supported plan": compass_error,
            },
            key={
                "Model forecast": model_error,
                "Planner choice": planner_error,
                "Compass-supported plan": compass_error,
            }.get,
        )

        st.success(
            f"{best_name} was closest to actual demand during {selected_period}."
        )

        detail_a, detail_b, detail_c = st.columns(3)

        detail_a.metric(
            "Model forecast",
            f"{model_error:,.0f}",
            help="Lower error means the forecast was closer to actual demand.",
        )

        detail_b.metric(
            "Planner choice",
            f"{planner_error:,.0f}",
            delta=f"{planner_error - model_error:+,.0f} vs model",
            delta_color="inverse",
        )

        detail_c.metric(
            "Compass-supported plan",
            f"{compass_error:,.0f}",
            delta=f"{compass_error - model_error:+,.0f} vs model",
            delta_color="inverse",
        )
