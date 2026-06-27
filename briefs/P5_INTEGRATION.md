# P5 — Integration, Demo Narrative & Pitch
**Branch: your own branch on https://github.com/Manasi200801/Par-agents.git**
**You own: `compass/contracts.py`, `compass/stubs.py`, `scripts/inject_events.py`, `scripts/precompute.py` (coordinate with P1), the final merge, and the pitch**

---

## What Compass is (read this first)

Compass is a demand-planning override copilot. A machine forecasts sales. A human planner overrides it and types a reason. Five AI agents look at real data and return evidence. A reconciler (Claude Opus) synthesises and recommends a calibrated number. The human decides. The decision is scored when actuals arrive. Over time, the system learns which types of overrides help and which hurt.

**Your job is the most critical at the start and the end.** At hour 0, you write the shared contracts and stubs so everyone else can work in parallel. At hour 12, you wire everything together. At hour 14, you own the demo narrative. At hour 15, you deliver the pitch.

---

## Hour 0 — Do these first (before anyone else writes code)

### 1. Create `compass/contracts.py`

Copy the file from `briefs/SHARED_CONTRACTS.py` exactly as written. Push it immediately so everyone can import from it.

```bash
cp briefs/SHARED_CONTRACTS.py compass/contracts.py
git add compass/contracts.py
git commit -m "P5: shared contracts — do not modify without team agreement"
git push origin your-branch
```

**Tell every team member: import `DecisionContext`, `Signal`, `MemoryContext`, `ReconcilerOutput`, `DecisionRecord` from `compass.contracts`. Do not redefine these anywhere.**

---

### 2. Create `compass/stubs.py` — so P4 can run from minute one

```python
# compass/stubs.py
# Stub implementations of every function P4 needs.
# P3/P2/P1 replace these with real implementations.
# P4 imports from stubs.py until the real modules are ready,
# then swaps the import line.

from compass.contracts import (DecisionContext, Signal, MemoryContext,
                                ReconcilerOutput, DecisionRecord)
import uuid

def classify_reason_stub(reason_text: str) -> str:
    keywords = {
        "promot": "promotion", "campaign": "promotion", "sale": "promotion",
        "competitor": "competitor_exit", "rival": "competitor_exit",
        "stock": "channel_overstock", "overstock": "channel_overstock",
        "price": "price_change", "tariff": "macro_signal",
        "supply": "supply_constraint", "shortage": "supply_constraint",
    }
    for kw, cls in keywords.items():
        if kw in reason_text.lower():
            return cls
    return "other"

def run_pipeline_stub(ctx: DecisionContext) -> ReconcilerOutput:
    return ReconcilerOutput(
        recommended_value = round(ctx.machine_value * 0.95, 1),
        confidence_level  = "low",
        rationale         = (
            f"STUB — P3 not yet integrated. Based on historical data, "
            f"downward overrides at Alpine help only 34% of the time. "
            f"Recommend staying closer to the machine forecast of {ctx.machine_value:.0f}."
        ),
        signals_used      = [
            Signal(
                agent_name    = "Demand (stub)",
                claim         = "STUB: real agent not yet connected.",
                direction     = "neutral",
                magnitude     = 0.3,
                confidence    = 0.3,
                table         = "future_order_book",
                evidence_rows = [],
            )
        ],
        memory_context    = MemoryContext(
            planner_fva_history   = {},
            reason_type_history   = {},
            similar_past_events   = [],
            calibrated_suggestion = None,
            confidence_level      = "low",
        ),
    )

def commit_decision_stub(ctx: DecisionContext, final_value: float,
                         output: ReconcilerOutput) -> str:
    decision_id = str(uuid.uuid4())
    print(f"[STUB] Would save decision {decision_id}: "
          f"machine={ctx.machine_value}, override={ctx.override_value}, final={final_value}")
    return decision_id

def get_replay_chart_data_stub():
    import pandas as pd, numpy as np
    dates = pd.date_range("2024-05-01", periods=24, freq="MS")
    np.random.seed(42)
    return pd.DataFrame({
        "cutoff_date":  dates,
        "mae_machine":  np.random.uniform(1500, 2500, 24),
        "mae_planner":  np.random.uniform(1600, 2800, 24),
        "n_rows":       [5924] * 24,
        "pct_helped":   np.random.uniform(0.35, 0.55, 24),
    })
```

Push this immediately after `contracts.py`.

---

### 3. Create the folder structure

```bash
mkdir -p compass/agents app/views scripts data briefs
touch compass/__init__.py
touch compass/agents/__init__.py
touch app/__init__.py
touch app/views/__init__.py
```

Push empty `__init__.py` files so Python imports work.

---

### 4. Create `requirements.txt`

```
anthropic
pandas
pyarrow
duckdb
streamlit
plotly
sentence-transformers
```

Push this so everyone installs the same packages.

---

## Hour 2–8 — Your job while others build

### Write `scripts/inject_events.py` — the demo narrative

This is the most important non-code thing you own. The Memory/Critic agent only says something interesting if there are past scored events in the database. You inject them.

Design **10–15 realistic market events** across the 3 business units and multiple reason types. Each event needs:
- A realistic reason text (what a planner would actually type)
- The right reason class
- Machine value, override value, realized outcome (so FVA can be computed)
- A planner name (use 2–3 fictional planners so track records show contrast)

```python
# scripts/inject_events.py
# Run: python scripts/inject_events.py
# Must be run AFTER scripts/precompute.py (DB must be initialised)

from compass.memory import seed_demo_events
import datetime

EVENTS = [
    # ── Competitor exit events (upward, usually right) ────────────────────────
    {
        "decision_id":    "demo-event-001",
        "cutoff_date":    datetime.date(2025, 3, 1),
        "product_id":     "CP-0271",
        "sales_org_id":   "SO04",
        "channel_id":     "CH01",
        "decision_maker": "planner_anna",
        "reason_text":    "Competitor Bauer Tools rumoured to be exiting DACH market for bearings",
        "reason_class":   "competitor_exit",
        "machine_value":  437.0,
        "override_value": 524.0,   # planner raised +20%
        "final_value":    524.0,
        "outcome":        511.0,   # actual came in at +17% — planner was close
        "fva":            74.0,    # machine_err=74, override_err=13 → FVA=+61 (planner helped)
    },
    {
        "decision_id":    "demo-event-002",
        "cutoff_date":    datetime.date(2025, 4, 1),
        "product_id":     "PC-0084",
        "sales_org_id":   "SO02",
        "channel_id":     "CH01",
        "decision_maker": "planner_anna",
        "reason_text":    "Heard from trade show that rival exiting Nordic fasteners segment",
        "reason_class":   "competitor_exit",
        "machine_value":  310.0,
        "override_value": 372.0,   # +20%
        "final_value":    372.0,
        "outcome":        348.0,   # actual +12%
        "fva":            38.0,
    },
    {
        "decision_id":    "demo-event-003",
        "cutoff_date":    datetime.date(2025, 5, 1),
        "product_id":     "SM-0507",
        "sales_org_id":   "SO08",
        "channel_id":     "CH02",
        "decision_maker": "planner_marco",
        "reason_text":    "Key competitor pulling out of composites in France",
        "reason_class":   "competitor_exit",
        "machine_value":  195.0,
        "override_value": 234.0,
        "final_value":    234.0,
        "outcome":        228.0,
        "fva":            30.0,
    },
    # ── Channel overstock events (downward, often wrong) ─────────────────────
    {
        "decision_id":    "demo-event-004",
        "cutoff_date":    datetime.date(2025, 2, 1),
        "product_id":     "CP-0271",
        "sales_org_id":   "SO04",
        "channel_id":     "CH01",
        "decision_maker": "planner_marco",
        "reason_text":    "Customer says they are overstocked, will skip one order",
        "reason_class":   "channel_overstock",
        "machine_value":  420.0,
        "override_value": 294.0,   # cut -30%
        "final_value":    294.0,
        "outcome":        398.0,   # customer came back — actual close to machine
        "fva":            -82.0,   # planner hurt accuracy
    },
    {
        "decision_id":    "demo-event-005",
        "cutoff_date":    datetime.date(2025, 1, 1),
        "product_id":     "PC-0029",
        "sales_org_id":   "SO01",
        "channel_id":     "CH01",
        "decision_maker": "planner_anna",
        "reason_text":    "Distributor mentioned high stock levels in Q4",
        "reason_class":   "channel_overstock",
        "machine_value":  610.0,
        "override_value": 427.0,   # cut -30%
        "final_value":    427.0,
        "outcome":        578.0,   # machine was right
        "fva":            -119.0,
    },
    # ── Promotion events (upward, usually helps) ──────────────────────────────
    {
        "decision_id":    "demo-event-006",
        "cutoff_date":    datetime.date(2025, 6, 1),
        "product_id":     "CP-0271",
        "sales_org_id":   "SO04",
        "channel_id":     "CH02",
        "decision_maker": "planner_anna",
        "reason_text":    "Amazon promotion running for the whole category next month",
        "reason_class":   "promotion",
        "machine_value":  250.0,
        "override_value": 312.0,   # +25%
        "final_value":    312.0,
        "outcome":        305.0,
        "fva":            48.0,
    },
    {
        "decision_id":    "demo-event-007",
        "cutoff_date":    datetime.date(2025, 7, 1),
        "product_id":     "SM-0507",
        "sales_org_id":   "SO08",
        "channel_id":     "CH02",
        "decision_maker": "planner_marco",
        "reason_text":    "Black Friday campaign confirmed for Consumer Products in France",
        "reason_class":   "promotion",
        "machine_value":  180.0,
        "override_value": 225.0,
        "final_value":    225.0,
        "outcome":        218.0,
        "fva":            31.0,
    },
    # ── Supply constraint events (varied) ─────────────────────────────────────
    {
        "decision_id":    "demo-event-008",
        "cutoff_date":    datetime.date(2025, 3, 1),
        "product_id":     "PC-0084",
        "sales_org_id":   "SO01",
        "channel_id":     "CH01",
        "decision_maker": "planner_marco",
        "reason_text":    "Main supplier confirmed delay due to port congestion in Shanghai",
        "reason_class":   "supply_constraint",
        "machine_value":  380.0,
        "override_value": 285.0,   # cut because supply is constrained
        "final_value":    285.0,
        "outcome":        271.0,   # supply was indeed constrained — planner right
        "fva":            95.0,
    },
    # ── Macro signal events ────────────────────────────────────────────────────
    {
        "decision_id":    "demo-event-009",
        "cutoff_date":    datetime.date(2025, 4, 1),
        "product_id":     "SM-0507",
        "sales_org_id":   "SO04",
        "channel_id":     "CH01",
        "decision_maker": "planner_anna",
        "reason_text":    "New EU tariff on Southeast Asia materials announced, will raise costs",
        "reason_class":   "macro_signal",
        "machine_value":  220.0,
        "override_value": 198.0,   # cut expecting demand drop from price rise
        "final_value":    198.0,
        "outcome":        215.0,   # demand was sticky — machine was right
        "fva":            -17.0,
    },
    # ── Price change events ────────────────────────────────────────────────────
    {
        "decision_id":    "demo-event-010",
        "cutoff_date":    datetime.date(2025, 5, 1),
        "product_id":     "CP-0271",
        "sales_org_id":   "SO02",
        "channel_id":     "CH01",
        "decision_maker": "planner_marco",
        "reason_text":    "We are raising list price by 8% next month — expect some demand drop",
        "reason_class":   "price_change",
        "machine_value":  390.0,
        "override_value": 351.0,   # cut -10%
        "final_value":    351.0,
        "outcome":        362.0,
        "fva":            -11.0,   # slight hurt — demand was less sensitive than expected
    },
]

if __name__ == "__main__":
    print(f"Injecting {len(EVENTS)} demo events...")
    seed_demo_events(EVENTS)
    print("Done. Memory layer now has scored history for the demo.")
    print()
    print("Track record summary:")
    from collections import defaultdict
    by_class = defaultdict(list)
    for e in EVENTS:
        by_class[e['reason_class']].append(e['fva'])
    for cls, fvas in by_class.items():
        avg = sum(fvas) / len(fvas)
        print(f"  {cls}: n={len(fvas)}, avg_fva={avg:+.1f}")
```

---

## Hour 8–12 — Integration

Your job is to connect P1 + P2 + P3 → P4. Do this in order:

```
1. Confirm P1's loader works: python -c "from compass.loader import load_products; print(load_products().shape)"
2. Confirm P1's DB is initialised: python scripts/precompute.py
3. Run inject_events: python scripts/inject_events.py
4. Confirm P2's classifier: python -c "from compass.classifier import classify_reason; print(classify_reason('competitor exiting DACH'))"
5. Confirm P3's pipeline: python -c "from compass.pipeline import run_pipeline; ..." (use the test below)
6. Confirm P4's app runs: streamlit run app/main.py
7. Swap P4's stub imports for real imports
8. Do a full end-to-end demo run
```

### Integration test (run this at hour 8)

```python
# scripts/integration_test.py
import datetime
from compass.contracts import DecisionContext
from compass.pipeline import run_pipeline, commit_decision

ctx = DecisionContext(
    product_id     = "CP-0271",
    sales_org_id   = "SO04",
    channel_id     = "CH01",
    cutoff_date    = datetime.date(2025, 6, 1),
    machine_value  = 437.0,
    override_value = 360.0,
    reason_text    = "Competitor rumoured to be exiting the DACH market for bearings",
    reason_class   = None,
    business_unit  = "Consumer Products",
    category       = "Bearings & Bushings",
    region_group   = "DACH",
    decision_maker = "planner_anna",
)

print("Running pipeline...")
output = run_pipeline(ctx)
print(f"Reconciler recommends: {output.recommended_value} units")
print(f"Confidence: {output.confidence_level}")
print(f"Rationale: {output.rationale}")
print(f"Signals used: {len(output.signals_used)}")
print(f"Memory — similar events: {len(output.memory_context.similar_past_events)}")
print()
print("Committing decision (final = 390)...")
decision_id = commit_decision(ctx, 390.0, output)
print(f"Saved with ID: {decision_id}")
print("Integration test PASSED.")
```

If this runs without errors and prints a non-stub rationale, integration is done.

---

## Hour 12–14 — Demo narrative

### The demo script (practice this 5 times)

**Set up:** Open Streamlit. Go to Live Decision view. Product: `CP-0271`. Sales Org: `SO04`. Channel: `CH01`. Machine forecast shows 437.

**What you say:**
> "Every month the machine says 437. Anna, one of our planners, has been following news from Germany — she heard a competitor is pulling out. She overrides to 524. In any other system, that reasoning disappears the moment she hits save. In Compass, it doesn't."

Override to 524. Type: `"Competitor rumoured to be exiting the DACH market for bearings"`. Hit Analyse.

Wait for spinner (this is 8–15 seconds — do NOT apologise for it, say "the agents are reading live data").

**When agent cards appear:**
> "Each of these is a real agent reading a real table. The Supply agent flagged that stock cover is only 2 weeks and the supplier OTIF is 71%. The Memory agent pulled up three similar past events — competitor exits in this category have historically realised +13% uplift, not the +20% Anna guessed. The reconciler takes all of this and recommends 498."

Point to the reconciler card. Say:
> "Anna can accept 498, stick with 524, or change her mind entirely. She's the last decision-maker. The system advises, it never overrides."

Accept the recommendation (498). Hit Commit.

> "That decision is now in memory. When September actuals arrive, we'll know if 498 was right. That score goes back to Anna's track record and to the competitor-exit event type. Next time someone makes a similar call, the system has one more data point."

**Switch to Replay Dashboard.** Point to the chart.
> "These are 24 real planning cycles from Alpine's data. The red line is planners without Compass — they make things 1.7% worse on average. The green line shows what calibrated overrides would look like. The key insight: when planners raise the forecast, they're right 71% of the time. When they cut it, only 34%. Compass's job is to tell the difference."

---

## Hour 14–15 — Pre-demo checklist

Run through this **twice** before presenting:

```
□ python scripts/precompute.py          — DB initialised, caches fresh
□ python scripts/inject_events.py       — 10 demo events loaded
□ python scripts/integration_test.py    — end-to-end passes
□ streamlit run app/main.py             — app loads without errors
□ Live Decision: CP-0271 × SO04 × CH01  — all 4 agent cards appear
□ Reconciler card shows non-stub output
□ Commit button works, decision_id printed
□ Replay Dashboard: 3 lines render correctly
□ Kill and restart the app — session state resets cleanly
□ Network is not needed (all data local) — confirm offline mode works
```

### Fallback plan if Opus fails during demo

If the API call fails or times out:
1. The stub fallback in `reconciler.py` catches the error and returns the machine value with "low" confidence.
2. Say: "The reconciler is taking longer than expected — what you see here is the fallback, which recommends the machine baseline while we wait."
3. Move to the Replay Dashboard which requires no live API call.

**Pre-cache a reconciler response** for the exact demo flow (CP-0271, reason = competitor exit) so you can switch to it if the live call fails.

---

## CRITICAL things you must do

1. **Push `contracts.py` and `stubs.py` in the first 30 minutes.** Every other person is blocked until they can import from `contracts.py`. This is your most time-sensitive deliverable.
2. **Run `inject_events.py` before integration** or the Memory/Critic agent will have nothing to say and the demo will look like a cold start.
3. **The integration test must pass before you touch the frontend.** If P3 or P2 haven't pushed yet, work with their stubs. Only swap to real imports once the integration test passes cleanly.
4. **Freeze features at hour 12.** No new agent signals, no new UI elements. Stability over features.
5. **The demo product is `CP-0271 × SO04 × CH01`.** Do not demo with a random product. Pick this one, verify all agents return real signals for it, and only use this one in the presentation.

## Git

```bash
git checkout your-branch
git add compass/contracts.py compass/stubs.py
git commit -m "P5: shared contracts and stubs — everyone unblocked"
git push origin your-branch

# later:
git add scripts/inject_events.py scripts/integration_test.py requirements.txt
git commit -m "P5: demo event injection, integration test, requirements"
git push origin your-branch
```
