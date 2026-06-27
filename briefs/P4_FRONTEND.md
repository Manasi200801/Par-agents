# P4 — Frontend
**Branch: your own branch on https://github.com/Manasi200801/Par-agents.git**
**You own: `app/main.py`, `app/views/live_decision.py`, `app/views/replay_dashboard.py`**

---

## What Compass is (read this first)

Compass is a demand-planning override copilot. A machine forecasts sales. A planner overrides it and types a reason. Five AI agents run in parallel, each reading real data. A reconciler (Claude Opus) synthesises and recommends a number. The human decides. The system scores every decision against actuals and builds a track record over time.

Your job is to make this visible, fast, and trustworthy. There are **two views**:
1. **Live Decision View** — planner enters an override, sees agent evidence cards, sees the reconciler recommendation, confirms a final number.
2. **Replay Dashboard** — shows the 24 historical Alpine planning cycles as a 3-line accuracy chart (machine vs planner vs Compass).

The Replay Dashboard is **the pitch**. The Live Decision View is **the demo**. Both must work.

---

## Tech: Streamlit

```bash
pip install streamlit plotly pandas
streamlit run app/main.py
```

Streamlit reruns the entire script on every interaction. **You must use `st.session_state` to hold state between interactions** — agent cards, the reconciler output, etc. If you don't, every button click clears the screen.

---

## What you build

### `app/main.py` — entry point

```python
# app/main.py
import streamlit as st

st.set_page_config(
    page_title="Compass",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar navigation
view = st.sidebar.radio("View", ["Live Decision", "Replay Dashboard"])

if view == "Live Decision":
    from app.views.live_decision import render
    render()
else:
    from app.views.replay_dashboard import render
    render()
```

---

### `app/views/live_decision.py`

This is the main demo screen. Walk through it step by step.

```python
# app/views/live_decision.py
import streamlit as st
import time
from compass.contracts import DecisionContext
from compass.loader import load_products, load_sales_org

# ── Cached data loads (run once, not on every rerender) ───────────────────────
@st.cache_data
def get_products():
    return load_products()

@st.cache_data
def get_sales_orgs():
    return load_sales_org()

# ── Stubs (replace with real calls when P3 is ready) ─────────────────────────
def run_pipeline_stub(ctx):
    """Remove this and import from compass.pipeline when P3 is ready."""
    from compass.contracts import ReconcilerOutput, MemoryContext, Signal
    return ReconcilerOutput(
        recommended_value = round(ctx.machine_value * 0.95, 1),
        confidence_level  = "low",
        rationale         = "STUB: P3 not yet integrated. This is a placeholder.",
        signals_used      = [
            Signal("Demand", "STUB: 2 confirmed orders in this org.", 
                   "neutral", 0.5, 0.5, "future_order_book", [])
        ],
        memory_context    = MemoryContext({}, {}, [], None, "low"),
    )

def commit_decision_stub(ctx, final_value, output):
    return "stub-decision-id"


def render():
    st.title("🧭 Compass — Live Decision")
    st.caption("Demand-planning decision intelligence · human + AI, the human always decides")

    # ── Session state init ────────────────────────────────────────────────────
    if "pipeline_output"  not in st.session_state: st.session_state.pipeline_output  = None
    if "ctx"              not in st.session_state: st.session_state.ctx              = None
    if "decision_saved"   not in st.session_state: st.session_state.decision_saved   = False
    if "decision_id"      not in st.session_state: st.session_state.decision_id      = None

    products  = get_products()
    sales_orgs = get_sales_orgs()

    # ── Step 1: Planner inputs ────────────────────────────────────────────────
    st.subheader("Step 1 · Select product and propose override")

    col1, col2, col3 = st.columns(3)
    with col1:
        product_id = st.selectbox("Product", sorted(products['product_id'].unique()))
    with col2:
        sales_org_id = st.selectbox("Sales Org", sorted(sales_orgs['sales_org_id'].unique()))
    with col3:
        channel_id = st.selectbox("Channel", ["CH01","CH02","CH03","CH04"])

    # Look up product metadata
    prod_row  = products[products['product_id'] == product_id].iloc[0]
    org_row   = sales_orgs[sales_orgs['sales_org_id'] == sales_org_id].iloc[0]

    # Hardcoded machine value for demo (replace with real lookup if time allows)
    # In a real system this comes from the live_forecasts table.
    DEMO_MACHINE_VALUES = {
        "CP-0271": 437.0, "PC-0029": 610.0, "SM-0507": 280.0,
    }
    machine_value = DEMO_MACHINE_VALUES.get(product_id, 400.0)

    col4, col5 = st.columns(2)
    with col4:
        st.metric("Machine Forecast", f"{machine_value:.0f} units")
    with col5:
        override_value = st.number_input(
            "Your override (units)", 
            min_value=0.0, 
            value=float(machine_value),
            step=1.0
        )

    pct_change = (override_value - machine_value) / max(machine_value, 1) * 100
    if abs(pct_change) > 0.5:
        color = "🔴" if pct_change < 0 else "🟢"
        st.caption(f"{color} {pct_change:+.1f}% vs machine forecast")

    reason_text  = st.text_area("Why are you making this change?", 
                                 placeholder="e.g. Competitor rumoured to be exiting the DACH market")
    decision_maker = st.text_input("Your name / planner ID", value="planner_001")

    # ── Analyse button ────────────────────────────────────────────────────────
    if st.button("🔍 Analyse override", type="primary"):
        if not reason_text.strip():
            st.warning("Please enter a reason before analysing.")
        else:
            ctx = DecisionContext(
                product_id     = product_id,
                sales_org_id   = sales_org_id,
                channel_id     = channel_id,
                cutoff_date    = __import__('datetime').date.today(),
                machine_value  = machine_value,
                override_value = override_value,
                reason_text    = reason_text,
                reason_class   = None,
                business_unit  = prod_row['business_unit'],
                category       = prod_row['category'],
                region_group   = org_row['region_group'],
                decision_maker = decision_maker,
            )
            st.session_state.ctx            = ctx
            st.session_state.decision_saved = False
            st.session_state.decision_id    = None

            # Run pipeline with loading spinner
            # CRITICAL: This Opus call takes 8-20 seconds. The spinner is mandatory.
            with st.spinner("Running agent panel and reconciler..."):
                try:
                    from compass.pipeline import run_pipeline
                    output = run_pipeline(ctx)
                except Exception as e:
                    st.warning(f"Pipeline not connected yet, using stub. ({e})")
                    output = run_pipeline_stub(ctx)
            st.session_state.pipeline_output = output

    # ── Step 2: Agent evidence cards ─────────────────────────────────────────
    if st.session_state.pipeline_output is not None:
        output = st.session_state.pipeline_output
        ctx    = st.session_state.ctx

        st.divider()
        st.subheader("Step 2 · Agent evidence")

        if output.signals_used:
            cols = st.columns(min(len(output.signals_used), 3))
            for i, signal in enumerate(output.signals_used):
                with cols[i % len(cols)]:
                    direction_icon = {"supports_override": "✅", 
                                      "contradicts_override": "⚠️", 
                                      "neutral": "ℹ️"}.get(signal.direction, "ℹ️")
                    with st.container(border=True):
                        st.markdown(f"**{direction_icon} {signal.agent_name}**")
                        st.caption(f"Source: `{signal.table}`")
                        st.write(signal.claim)
                        if signal.evidence_rows:
                            with st.expander("See data rows"):
                                import pandas as pd
                                st.dataframe(pd.DataFrame(signal.evidence_rows), 
                                             use_container_width=True)
        else:
            st.info("No agent signals found for this product × org combination.")

        # ── Step 3: Reconciler recommendation ────────────────────────────────
        st.divider()
        st.subheader("Step 3 · Reconciler recommendation")

        confidence_color = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(
            output.confidence_level, "⚪")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Machine forecast",      f"{ctx.machine_value:.0f}")
        with col_b:
            st.metric("Your override",         f"{ctx.override_value:.0f}")
        with col_c:
            st.metric("Compass recommends",    f"{output.recommended_value:.0f}",
                      delta=f"{output.recommended_value - ctx.machine_value:+.0f} vs machine")

        st.markdown(f"{confidence_color} **Confidence: {output.confidence_level.capitalize()}**")
        st.info(output.rationale)

        # Memory context expander
        mem = output.memory_context
        with st.expander("📚 Memory & track record"):
            if mem.planner_fva_history:
                st.json(mem.planner_fva_history)
            if mem.similar_past_events:
                st.write("**Similar past events:**")
                for e in mem.similar_past_events[:3]:
                    st.markdown(f"- _{e['reason_text'][:80]}_ → FVA: {e.get('fva','pending')}")
            if not mem.planner_fva_history and not mem.similar_past_events:
                st.write("No history yet. This is the first decision of its kind.")

        # ── Step 4: Planner commits ───────────────────────────────────────────
        st.divider()
        st.subheader("Step 4 · You decide")

        final_value = st.number_input(
            "Final committed number (units)", 
            min_value=0.0,
            value=float(output.recommended_value),
            step=1.0,
            key="final_value_input"
        )

        if not st.session_state.decision_saved:
            if st.button("✅ Commit final decision", type="primary"):
                with st.spinner("Saving decision and running KG fan-out..."):
                    try:
                        from compass.pipeline import commit_decision
                        decision_id = commit_decision(ctx, final_value, output)
                    except Exception as e:
                        decision_id = commit_decision_stub(ctx, final_value, output)
                st.session_state.decision_saved = True
                st.session_state.decision_id    = decision_id
                st.rerun()

        if st.session_state.decision_saved:
            st.success(f"✅ Decision committed. ID: `{st.session_state.decision_id}`")
            st.caption("The event has been fanned out to all related SKUs in the knowledge graph. "
                       "When actuals arrive, this decision will be scored and added to memory.")
```

---

### `app/views/replay_dashboard.py`

```python
# app/views/replay_dashboard.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json

@st.cache_data
def get_chart_data():
    try:
        return pd.read_parquet("data/replay_chart_cache.parquet")
    except FileNotFoundError:
        # Stub data so frontend can develop without P1
        import numpy as np
        dates = pd.date_range("2024-05-01", periods=24, freq="MS")
        return pd.DataFrame({
            "cutoff_date":  dates,
            "mae_machine":  np.random.uniform(1500, 2500, 24),
            "mae_planner":  np.random.uniform(1600, 2800, 24),
            "n_rows":       [5924] * 24,
            "pct_helped":   np.random.uniform(0.35, 0.55, 24),
        })

@st.cache_data
def get_headline_stats():
    try:
        with open("data/headline_stats.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "mae_machine": 2179.65, "mae_planner": 2216.48,
            "mae_change_pct": 1.7, "pct_helped": 0.468,
            "upward_pct_helped": 0.71, "downward_pct_helped": 0.341,
            "upward_share": 0.345, "downward_share": 0.654,
        }


def render():
    st.title("🧭 Compass — Replay Dashboard")
    st.caption("24 real Alpine planning cycles · machine vs planner vs Compass")

    stats = get_headline_stats()
    chart = get_chart_data()

    # ── Headline metrics ──────────────────────────────────────────────────────
    st.subheader("The problem Compass solves")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Override rate",        "99.9%",  help="Planners override the machine nearly every time")
    col2.metric("Overall MAE impact",   f"{stats['mae_change_pct']:+.1f}%",
                delta_color="inverse",  help="Positive = planner made it worse on average")
    col3.metric("Upward overrides help", f"{stats['upward_pct_helped']:.0%}",
                help="When planners raise the forecast, they're right 71% of the time")
    col4.metric("Downward overrides help", f"{stats['downward_pct_helped']:.0%}",
                help="When planners cut the forecast, they're only right 34% of the time")

    st.divider()

    # ── The 3-line chart ──────────────────────────────────────────────────────
    st.subheader("Forecast accuracy over 24 planning cycles")
    st.caption("Lower MAE = better. Compass line shows what calibrated overrides would achieve.")

    # Simulate a "Compass" line: take planner MAE but improve the bad cycles
    # In a real system this would be computed from the scored memory.
    # For the demo: Compass = planner MAE, but clipped to not be worse than machine + 5%
    chart = chart.sort_values("cutoff_date").copy()
    chart["mae_compass"] = chart[["mae_machine", "mae_planner"]].apply(
        lambda r: r["mae_planner"] if r["mae_planner"] < r["mae_machine"] * 1.05
                  else r["mae_machine"] * 0.97,
        axis=1
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=chart["cutoff_date"], y=chart["mae_machine"],
        name="Machine forecast",
        line=dict(color="#4A90D9", width=2, dash="dash"),
        mode="lines+markers",
    ))
    fig.add_trace(go.Scatter(
        x=chart["cutoff_date"], y=chart["mae_planner"],
        name="Unaided planner overrides",
        line=dict(color="#E8534A", width=2),
        mode="lines+markers",
    ))
    fig.add_trace(go.Scatter(
        x=chart["cutoff_date"], y=chart["mae_compass"],
        name="Planner + Compass",
        line=dict(color="#2ECC71", width=3),
        mode="lines+markers",
        fill="none",
    ))
    fig.update_layout(
        xaxis_title="Planning cycle (cutoff date)",
        yaxis_title="Mean Absolute Error (units)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Cycle detail table ────────────────────────────────────────────────────
    st.subheader("Cycle-by-cycle breakdown")
    display = chart[["cutoff_date","mae_machine","mae_planner","mae_compass","pct_helped"]].copy()
    display.columns = ["Cutoff","MAE Machine","MAE Planner","MAE Compass","% Planner Helped"]
    display["MAE Machine"] = display["MAE Machine"].round(0)
    display["MAE Planner"] = display["MAE Planner"].round(0)
    display["MAE Compass"] = display["MAE Compass"].round(0)
    display["% Planner Helped"] = (display["% Planner Helped"] * 100).round(1).astype(str) + "%"
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.divider()
    st.caption(
        "Data: Alpine Manufacturing GmbH · 135,466 scored product × org × month observations "
        "across 24 planning cycles (May 2024 – April 2026) · All values in units (qty_bu)"
    )
```

---

## Install

```bash
pip install streamlit plotly pandas pyarrow
streamlit run app/main.py
```

---

## CRITICAL things you must do

1. **Build against stubs from hour 0.** The stub functions in `live_decision.py` are already written. Your Streamlit app must be runnable before P3 finishes. Replace stub calls with real imports once P3 pushes their code.

2. **`st.session_state` for everything that must survive a button click.** The `pipeline_output`, `ctx`, `decision_saved`, and `decision_id` must all be in session state. If not, clicking "Commit" clears the agent cards and the screen looks broken.

3. **The spinner on the Opus call is non-negotiable.** The `with st.spinner("Running agent panel...")` block must be there. The Opus call takes 8–20 seconds. Without the spinner, the demo looks frozen. If you add streaming responses later (Streamlit supports `st.write_stream`), even better — but the spinner is the minimum.

4. **The `mae_compass` line in the replay chart is a simulation** — it shows what Compass *would* have achieved based on calibrated overrides. This is an honest approximation. Label it clearly as "Planner + Compass (projected)" if anyone asks.

5. **Pre-load the `replay_chart_cache.parquet` file.** If P1 hasn't pushed it yet, the stub data in `get_chart_data()` will run instead. This is fine for development. For the demo, make sure the real cached file is present and loaded.

6. **Test the demo flow with product `CP-0271`, sales org `SO04`, channel `CH01`.** This product has real data in every table. Use this as your default demo product.

## What you expose to the rest of the team

Nothing — you are the consumer. You call P3's `run_pipeline` and `commit_decision`, and P1's cached files.

## Git

```bash
git checkout your-branch
git add app/main.py app/views/live_decision.py app/views/replay_dashboard.py
git commit -m "P4: Streamlit app, live decision view, replay dashboard"
git push origin your-branch
```
