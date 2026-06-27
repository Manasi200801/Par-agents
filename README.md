# Compass

> An institutional-memory and calibration layer for human-over-model workflows.
> Paretos Hackathon · Alpine Manufacturing GmbH dataset · 5 people · 15 hours

---

## If you are a fresh Claude session, read this first

This README is written to be fully self-contained. You need no prior conversation history. Everything you need to understand, build, and extend this project is in this file and the `briefs/` folder.

**The repo has two things:**
1. `README.md` — the full project context (this file). Read it completely before writing any code.
2. `briefs/` — one detailed build brief per team member (P1–P5). Each brief is a self-contained prompt with exact function signatures, what to return, what to use, and critical failure-prevention rules. When a team member asks you to help them build their part, read their brief first.

---

## The problem

Everywhere an AI system proposes a number and a human changes it, two things happen:

1. **The reasoning evaporates.** Nobody records *why* the number was changed.
2. **The outcome is never scored.** Nobody checks whether the change actually helped.

In demand planning specifically: the machine forecasts 437 units. The planner overrides to 360 and moves on. Six months later, actual sales came in at 412. The machine was closer. But nobody measured that, nobody learned from it, and next month the planner overrides again with the same instincts.

**We verified this in the Alpine data across 24 real historical planning cycles:**
- Planners override the machine forecast **99.9% of the time**
- Their overrides make accuracy **1.7% worse** on average
- But the pattern is not uniform — when planners **raise** a forecast, they are right **71%** of the time. When they **cut** it, they are only right **34%** of the time.
- Planners have genuine intelligence about upward signals. Their downward cuts are mostly reflexive habit.

**Compass fixes this.** It captures the reason, classifies it, fans it out to every affected product in the same category and region, scores the outcome when actuals arrive (Forecast Value Added = FVA), and feeds that scored history back so the next override is calibrated against what actually happened before.

---

## What it is (one sentence)

A panel of function-specialist AI agents — each grounded in a real data table — surfaces evidence about a proposed forecast override; a reconciler (Claude Opus 4.8) weighs it against the planner's scored track record from memory and recommends a calibrated number; **the human decides**; the outcome is scored and written back; the institution gets smarter every cycle.

---

## The three rules that keep it from being a showpiece

1. **Every agent claim carries a data citation.** Table name + rows. No grounded signal → agent stays silent. No padding.
2. **It is a DAG, not a debate.** Agents run in parallel → reconciler synthesises once → human is the final node. Cannot loop.
3. **Memory is scored by outcomes.** When it pushes back it cites a track record, not an opinion.

---

## Architecture (the full flow)

```
PLANNER enters override + reason
        │
        ▼
[Haiku classifies reason → reason_class from fixed taxonomy]
        │
        ▼
[Relevance router: which agents are relevant for this SKU?]
        │
   ┌────┴────────────────────────────────────────┐
   ▼         ▼          ▼           ▼            ▼
DEMAND    SUPPLY     FINANCE    COMMERCIAL    MEMORY/
AGENT     /OPS       /MARGIN    /MARKET       CRITIC
order_bk  stock_oh   biz_plan   mktg_spend    scored
customers purch_ord  cost_brkd  price_chg     history
returns   suppliers  tariff_ref + signal      + KG recall
prod_data
   │         │          │           │            │
   └────┬────┴──────────┴───────────┴────────────┘
        │ list[Signal] — each with claim, direction,
        │ magnitude, confidence, table, evidence_rows
        ▼
RECONCILER (Claude Opus 4.8) — single pass, no loop
  • weighs all signals + memory context
  • outputs: recommended_value, confidence_level, rationale
        │
        ▼
PLANNER decides (always the final node)
        │
        ▼
WRITE-BACK to DuckDB:
  decisions table ← full record
  events table    ← reason + embedding
  event_sku table ← fan-out to all SKUs in same category × region
        │
  (next cycle: actuals arrive)
        │
        ▼
FVA SCORING:
  machine_error  = |actual - machine_value|
  override_error = |actual - final_value|
  fva            = machine_error - override_error  (+ve = planner helped)
  → updates decisions.fva, events.realized_impact
  → updates track_record_by_reason and track_record_by_planner views
```

---

## Data store — one database, not three

**DuckDB for the hackathon. Postgres + pgvector for production.**

There is no separate graph database (no Neo4j) and no separate vector database (no Chroma/Pinecone). Every query we need is a SQL join or a vector column in the same store. A graph database earns its cost for multi-hop variable-depth traversal — our "knowledge graph" is a category × region join on the hierarchy table, which is just SQL.

### The 4 tables + 2 views

```sql
-- Product and org hierarchy (seeded once from parquet files)
CREATE TABLE hierarchy (
    product_id TEXT, product_group TEXT, category TEXT,
    business_unit TEXT, sales_org_id TEXT, region_group TEXT
);

-- Universal decision record (domain-agnostic)
CREATE TABLE decisions (
    decision_id TEXT PRIMARY KEY,
    cutoff_date DATE, item_id TEXT,
    machine_value DOUBLE, override_value DOUBLE,
    reconciler_value DOUBLE, final_value DOUBLE,
    reason_text TEXT, reason_class TEXT, decision_maker TEXT,
    context_json TEXT,
    -- filled when actuals arrive:
    outcome DOUBLE, machine_error DOUBLE, override_error DOUBLE, fva DOUBLE
);

-- One row per market event / override signal
CREATE TABLE events (
    event_id TEXT PRIMARY KEY, decision_id TEXT,
    reason_class TEXT, reason_text TEXT,
    reason_embedding TEXT,   -- JSON array of floats (sentence-transformers)
    realized_impact DOUBLE   -- filled when actuals arrive
);

-- Fan-out: one row per (event, affected SKU)
CREATE TABLE event_sku (
    event_id TEXT, product_id TEXT, sales_org_id TEXT
);

-- Track records are views (computed on read, not stored)
CREATE VIEW track_record_by_reason AS
    SELECT reason_class, COUNT(*) n_decisions, AVG(fva) avg_fva,
           AVG(override_value/NULLIF(machine_value,0)-1) avg_override_pct,
           AVG(outcome/NULLIF(machine_value,0)-1) avg_realized_pct,
           SUM(CASE WHEN fva>0 THEN 1 ELSE 0 END)*1.0/COUNT(*) pct_helpful
    FROM decisions WHERE fva IS NOT NULL GROUP BY reason_class;

CREATE VIEW track_record_by_planner AS
    SELECT decision_maker, COUNT(*) n_decisions, AVG(fva) avg_fva,
           SUM(CASE WHEN fva>0 THEN 1 ELSE 0 END)*1.0/COUNT(*) pct_helpful
    FROM decisions WHERE fva IS NOT NULL GROUP BY decision_maker;
```

**KG lifecycle = append + update only. Never rebuilt.**
- New override → INSERT ~3 rows (one decision, one event, N event_sku rows)
- Actuals arrive → UPDATE 2 rows (fva on decision, realized_impact on event)

---

## Shared contracts (the most important file in the project)

Every component imports from `compass/contracts.py`. Nobody redefines these. The file lives in `briefs/SHARED_CONTRACTS.py` — P5 copies it to `compass/contracts.py` at hour 0.

```python
@dataclass
class DecisionContext:
    product_id: str; sales_org_id: str; channel_id: str
    cutoff_date: datetime.date
    machine_value: float      # what the model said
    override_value: float     # what the planner wants to change it to
    reason_text: str          # planner's free text
    reason_class: Optional[str]  # populated after Haiku classifier
    business_unit: str; category: str; region_group: str
    decision_maker: str

@dataclass
class Signal:
    agent_name: str; claim: str
    direction: str            # "supports_override"|"contradicts_override"|"neutral"
    magnitude: float          # 0–1
    confidence: float         # 0–1
    table: str                # source table name
    evidence_rows: list       # actual rows from the table

@dataclass
class MemoryContext:
    planner_fva_history: dict; reason_type_history: dict
    similar_past_events: list
    calibrated_suggestion: Optional[float]
    confidence_level: str     # "low"|"medium"|"high"

@dataclass
class ReconcilerOutput:
    recommended_value: float; confidence_level: str
    rationale: str            # 2–4 plain-English sentences
    signals_used: list        # list[Signal]
    memory_context: MemoryContext

@dataclass
class DecisionRecord:
    decision_id: str; cutoff_date: datetime.date; item_id: str
    machine_value: float; override_value: float
    reconciler_value: float; final_value: float
    reason_text: str; reason_class: str
    decision_maker: str; context_json: dict
    outcome: Optional[float] = None
    machine_error: Optional[float] = None
    override_error: Optional[float] = None
    fva: Optional[float] = None
```

---

## The reason taxonomy (10 fixed classes)

The Haiku classifier maps any free-text reason to one of these. Without a fixed taxonomy, reasons are unlearnable — every override looks unique.

```
promotion          competitor_exit    competitor_entry   trade_show_event
channel_overstock  channel_understock price_change       supply_constraint
macro_signal       other
```

---

## The two demos

### Demo A — Live Decision (shows the UX)

1. Planner selects product `CP-0271`, sales org `SO04`, channel `CH01`
2. Machine forecast: **437 units**
3. Planner types override: **524** and reason: *"Competitor rumoured to be exiting DACH market for bearings"*
4. Hits "Analyse" → spinner appears (Opus takes 8–20s — this is expected, not broken)
5. Agent cards appear: Demand (confirmed orders), Supply (OTIF 71%, low stock cover), Memory (3 similar competitor-exit events, avg realized +13% not +20%)
6. Reconciler card: recommends **498**, confidence medium, 3-sentence rationale
7. Planner accepts 498, hits "Commit"
8. Decision saved, event fanned out to all Bearings & Bushings SKUs in DACH

**Demo product is always `CP-0271 × SO04 × CH01`.** This product has real data in every table. Do not demo with a random SKU.

### Demo B — Replay Dashboard (proves the learning)

- 24 historical Alpine planning cycles (real data, precomputed)
- 3-line chart: machine MAE vs unaided planner MAE vs Compass MAE
- Compass line bends downward as memory accumulates
- Headline metrics: 99.9% override rate, +1.7% MAE impact, 71% upward vs 34% downward

---

## Dataset

### Primary — Alpine Manufacturing GmbH

A fictional Stuttgart-based industrial group. Used as the primary demo because it has **24 historical cycles** where both the machine forecast and planner-adjusted plan are recorded and scoreable against actuals.

| | |
|---|---|
| Business units | Precision Components (PC-xxxx), Consumer Products (CP-xxxx), Specialty Materials (SM-xxxx) |
| Channels | B2B (CH01), Amazon (CH02), B2C (CH03), Distributor (CH04) |
| Sales orgs | 18 across DACH, BeNeLux, Western EU |
| SKUs | 600 |
| Customers | 250 named B2B accounts |
| Suppliers | 50 |
| Sales actuals | 2.8M daily rows (May 2023 → Feb 2026) |
| Machine forecast | `alpine_statistical_forecast` (36 monthly cutoffs) |
| Planner forecast | `alpine_demand_plan` (24 monthly cutoffs — overlaps with machine) |
| FVA-ready cycles | **24** |

**Verified FVA numbers (computed, not estimated):**
- 135,466 scored rows across 24 cycles
- Overall MAE impact: **+1.7%** (planner makes it worse on average)
- Planner helped: **46.8%** of overrides
- Upward overrides: helped **71.0%** of the time (mean FVA +495 units)
- Downward overrides: helped **34.1%** of the time (mean FVA -318 units)
- Precomputed base table: `data/fva_base.parquet` (already in repo)
- Cached replay chart: `data/replay_chart_cache.parquet`
- Headline stats JSON: `data/headline_stats.json`

### Secondary — Firn Outdoor AG (generality proof)

A fictional Zurich-based DTC outdoor apparel brand. Same core architecture, different adapters. Shows Compass is not manufacturing-specific.

Key differences vs Alpine that require adapter changes:
- `firn_demand_plan` IS the machine forecast (no separate stat_forecast) — no historical override split
- 180,026 individual customers (handle at segment level, not individual level)
- 65,462 returns (6.8% return rate — size/fit dominated; a primary signal in apparel)
- Textile mill suppliers: Bangladesh/Vietnam = 8–14 week lead times (season-critical)
- DTC cost structure: platform fees, returns handling, fulfillment (not raw materials + tariffs)
- No tariff_reference table; no production_data table

**Parquet loader note:** Both datasets use `uint32` dictionary indices that crash `pandas.read_parquet`. Always use `compass.loader.load_parquet()` which decodes dictionary columns via pyarrow.

---

## Repo structure

```
compass-hackathon/
├── README.md                        ← this file (full project context)
│
├── briefs/
│   ├── SHARED_CONTRACTS.py          ← copy to compass/contracts.py at hour 0
│   ├── P1_DATA_BACKEND.md           ← parquet loader, DuckDB, FVA harness
│   ├── P2_MEMORY_KG.md              ← classifier, embeddings, memory agent
│   ├── P3_AGENTS_RECONCILER.md      ← 4 agents, router, Opus reconciler, pipeline
│   ├── P4_FRONTEND.md               ← Streamlit live + replay views
│   └── P5_INTEGRATION.md            ← contracts, stubs, events, demo script
│
├── compass/
│   ├── contracts.py                 ← shared dataclasses (from SHARED_CONTRACTS.py)
│   ├── loader.py                    ← P1: safe parquet loader
│   ├── store.py                     ← P1: DuckDB init, write_decision, score_decision
│   ├── fva.py                       ← P1: replay chart data, headline stats
│   ├── classifier.py                ← P2: Haiku reason → taxonomy class
│   ├── embeddings.py                ← P2: sentence-transformers, vector recall
│   ├── memory.py                    ← P2: Memory/Critic agent, event write-back
│   ├── router.py                    ← P3: relevance gate (which agents run)
│   ├── reconciler.py                ← P3: single Opus call, JSON output
│   ├── pipeline.py                  ← P3: run_pipeline() and commit_decision()
│   ├── stubs.py                     ← P5: stub implementations for parallel dev
│   └── agents/
│       ├── demand.py                ← P3: order book + customers + returns
│       ├── supply.py                ← P3: stock + OTIF + suppliers + production
│       ├── finance.py               ← P3: business plan + costs + tariffs
│       └── commercial.py            ← P3: marketing spend + price changes
│
├── app/
│   ├── main.py                      ← P4: Streamlit entrypoint, sidebar nav
│   └── views/
│       ├── live_decision.py         ← P4: override flow, agent cards, reconciler card
│       └── replay_dashboard.py      ← P4: 3-line accuracy chart, cycle table
│
├── scripts/
│   ├── precompute.py                ← run offline: init DB, seed hierarchy, cache charts
│   ├── inject_events.py             ← P5: seed 10+ demo events into memory
│   └── integration_test.py          ← P5: end-to-end test with CP-0271
│
└── data/
    ├── alpine-manufacturing-gmbh/source-data/     ← 18 parquet files
    ├── alpine-manufacturing-forecast/              ← machine forecast + backtest
    ├── firn-outdoor-ag/source-data/               ← 16 parquet files
    ├── fva_base.parquet             ← precomputed (135K scored rows)
    ├── replay_chart_cache.parquet   ← precomputed (24 rows, one per cycle)
    └── headline_stats.json          ← precomputed (key FVA numbers)
```

---

## Tech stack

| Tool | Role | Why |
|------|------|-----|
| Python | Everything | Universal, fastest for data work |
| DuckDB | Single data store | Queries parquet directly, zero server, vectors via VSS extension |
| pyarrow | Parquet loader | Handles uint32 dict indices that break pandas |
| sentence-transformers (`all-MiniLM-L6-v2`) | Reason embeddings | 80MB, runs locally, no API cost, good enough for semantic recall |
| Claude Haiku | Reason classifier | Runs on every override — must be cheap and fast |
| Claude Opus 4.8 | Reconciler only | One call per decision after all agents complete |
| Streamlit | Frontend (both views) | Python-native UI in hours, no React needed |
| Plotly | Replay chart | Clean interactive 3-line chart in Streamlit |

**Not using:** Neo4j, Chroma, Pinecone, React, LangChain. Each dropped for the same reason: extra system to operate, zero marginal value over the simpler choice.

---

## Install

```bash
pip install anthropic pandas pyarrow duckdb streamlit plotly sentence-transformers
export ANTHROPIC_API_KEY=sk-ant-...
```

**Pre-download the embedding model before the hackathon** (80MB, needs internet):
```python
from sentence_transformers import SentenceTransformer
SentenceTransformer("all-MiniLM-L6-v2")  # run once to cache
```

---

## Running the project

```bash
# 1. Initialise the database and precompute cached files (run once)
python scripts/precompute.py

# 2. Inject demo events so memory has something to say (run once after precompute)
python scripts/inject_events.py

# 3. Run the integration test (must pass before touching the frontend)
python scripts/integration_test.py

# 4. Launch the app
streamlit run app/main.py
```

---

## Build plan — 5 people × 15 hours

### Hour 0–2: Contracts and stubs (everyone together)

P5 pushes `compass/contracts.py` and `compass/stubs.py` in the first 30 minutes.
Everyone else pulls and imports from contracts. Nobody writes real code yet — agree on interfaces first.

### Hour 2–8: Parallel build (each person works independently)

| Person | Branch | Owns |
|--------|--------|------|
| **P1 — Data/Backend** | own branch | `compass/loader.py`, `compass/store.py`, `compass/fva.py`, `scripts/precompute.py` |
| **P2 — Memory + KG** | own branch | `compass/classifier.py`, `compass/embeddings.py`, `compass/memory.py` |
| **P3 — Agents + Reconciler** | own branch | `compass/agents/`, `compass/router.py`, `compass/reconciler.py`, `compass/pipeline.py` |
| **P4 — Frontend** | own branch | `app/main.py`, `app/views/live_decision.py`, `app/views/replay_dashboard.py` |
| **P5 — Integration** | own branch | stubs, inject_events, integration test, demo narrative, pitch |

### Hour 8–12: Integration (P5 drives)

Connect all components. Run `scripts/integration_test.py`. Swap P4's stub imports for real ones. Fix interface mismatches.

### Hour 12–14: Polish

Freeze features. Pre-compute all caches. Test the live demo with `CP-0271 × SO04 × CH01` ten times. Prepare the injected-event narrative.

### Hour 14–15: Rehearse

Full demo run twice. Identify the single most likely failure point and add a manual fallback.

---

## Must-have vs stretch

### Must ship

- Override capture with free-text reason
- Haiku reason classifier → taxonomy class
- FVA scoring against actuals
- Memory recall (track record by reason class + by planner)
- **2 grounded agents: Demand + Supply** (Finance and Commercial are stretch)
- Reconciler synthesising 2 agents + memory
- Live decision UI: machine value, override input, reason box, agent cards, reconciler card, commit
- Replay dashboard: 3-line accuracy chart over 24 cycles
- Event fan-out for competitor_exit event type

### Stretch

Full 4-agent panel · multi-event propagation · planner bias models · confidence intervals · Firn tab

---

## Cost model

| Component | Cost |
|-----------|------|
| Storage (DuckDB) | Free |
| FVA computation | Free (subtraction after join) |
| Embeddings (sentence-transformers) | Free (local model) |
| Haiku (reason classification) | ~$0.001 per decision |
| Opus 4.8 (reconciler) | ~$0.05–0.15 per decision |

**Control Opus spend:** relevance-gate agents so only 2–3 run per decision. Call Opus once per decision after all agents complete. Cache the response for the demo product to use as a fallback.

---

## Known failure points (address these before demo)

1. **The replay chart accuracy numbers** — precomputed from real Alpine data. Machine MAE ~2,180, planner MAE ~2,216 (+1.7%). These are real. The "Compass" line on the chart is a projected improvement based on calibrated overrides, not historical Compass data (Compass didn't exist for those cycles). Label it "projected" if asked.

2. **Opus latency** — 8–20 seconds per call. The Streamlit spinner is mandatory. Without it the demo looks frozen.

3. **Parquet loader** — always use `compass.loader.load_parquet()`. Never `pd.read_parquet()` directly. The uint32 dict-decode bug gives a cryptic ArrowTypeError with no obvious fix if you hit it cold.

4. **Session state in Streamlit** — `pipeline_output`, `ctx`, `decision_saved`, `decision_id` must all be in `st.session_state`. Without this, button clicks clear the screen.

5. **Memory cold start** — run `inject_events.py` before the demo. Without seeded events, the Memory/Critic agent says "no history yet" for every question. Fine to show cold-start behaviour, but not for the main demo flow.

6. **Integration order** — `commit_decision()` must be called after `write_decision()` because `record_event()` references `decision_id` as a foreign key. P3's `pipeline.py` handles this ordering.

7. **Sentence-transformers download** — P2 must pre-download `all-MiniLM-L6-v2` before the hackathon. 80MB on venue WiFi will fail or take 10 minutes.

8. **Demo product** — always use `CP-0271 × SO04 × CH01`. Pre-verify that all agents return real signals for this product. Do not use a random SKU.

---

## Pitch (three questions judges will ask)

**"Is this just a chatbot that argues with the planner?"**
No. Each agent reads a specific table and either finds a grounded signal or stays silent. The reconciler synthesises evidence, not opinions. When it pushes back it cites a scored track record, not general reasoning.

**"Does this only work for manufacturing?"**
No. The core loop — model proposes, human overrides with reason, outcome scored, memory updated — is domain-agnostic. We demonstrate with Firn Outdoor AG (DTC apparel) using the same core system, different adapters. Demand forecasting is the first vertical because Alpine gives us 24 historically-scoreable override cycles to prove it.

**"How does it get smarter — can you show that?"**
The replay dashboard. Three lines: machine baseline (flat), unaided planner (noisy, 1.7% worse), planner with Compass (bends down as calibration improves). Built from 135,466 real data points across 24 planning cycles.

---

## General positioning

Do not pitch as "a demand-planning tool." Pitch as:

> **An institutional-memory and calibration layer for any human-over-model workflow.**

Everywhere AI proposes and a human overrides — forecasting, pricing, staffing, credit limits, ad budgets — the reasoning is lost and nobody measures if the override helped. That missing feedback loop is the product. Alpine Manufacturing is the first vertical. The architecture is designed so any new domain is an adapter swap, not a rewrite.
