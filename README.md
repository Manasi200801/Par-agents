# Compass

**Human-centred demand planning intelligence.**  
AI agents surface evidence. You make the call. Every decision gets scored.

---

## What it does

Demand planners override machine forecasts every month and write down a reason. Compass makes that loop useful:

1. A panel of five specialist agents reads the real data — order books, inventory, supplier reliability, marketing campaigns, financials — and surfaces grounded evidence about the proposed override.
2. A reconciler (Claude Opus 4.8) weighs all the evidence and suggests a calibrated number with a plain-English rationale.
3. The planner commits a final number. The decision is stored.
4. When actuals arrive, every decision is scored: did the override improve or worsen forecast accuracy? That score feeds back into the next decision.

The result: planners see exactly what the data says before they commit, and the system gets smarter every cycle.

---

## What we found in the data

We ran a Forecast Value Added (FVA) analysis on 23 historical Alpine Manufacturing planning cycles (68,126 item-months):

| Metric | Machine | Planner |
|---|---|---|
| MAE | 2,013 units | **1,574 units** |
| WAPE | 19.2% | **15.0%** |

- Planners improved accuracy by **21.8%** overall
- Upward overrides helped **71%** of the time
- Downward overrides hurt **66%** of the time
- The pattern is consistent by reason type — and that's what Compass learns

---

## Setup

### Requirements

```bash
pip install -r requirements.txt
```

Set your API key (needed for the live AI reconciler):

```bash
# Create .env from the template
cp .env.example .env
# Add your key:  ANTHROPIC_API_KEY=sk-ant-...
```

Without a key the app runs in demo mode with a rule-based stub.

### First run

```bash
# Initialise the database and precompute cached files (run once)
python scripts/setup.py

# Seed realistic historical decisions for demo (run once)
python scripts/seed_demo_data.py

# Launch
streamlit run app/main.py
```

App opens at **http://localhost:8501**

---

## The two views

### Live Decision

Walk through a real decision:

1. Select a product, sales org, and channel
2. See the machine forecast alongside real historical context (run-rate, same month last year, stock, unit value)
3. Move the slider to your proposed number and write your reason
4. Hit **Check my decision** — five agents run, each grounded in a specific data table
5. Review the evidence panel and the reconciler's suggested number with rationale
6. Commit your final number

### Replay Dashboard

Shows what actually happened across 23 historical planning cycles. Three lines on one chart: machine forecast error, planner error, Compass-guided error. The Compass line is consistently the lowest.

---

## Demo products

These four show the most interesting stories:

| Product | ID | Org | Ch | Story |
|---|---|---|---|---|
| Premium Drills Mark II 1 | `CP-0271` | SO04 (DACH) | CH01 | Machine 29% below run-rate — clear upward case |
| Solvay CYCOM 5320-1 Tooling | `SM-0545` | SO04 (DACH) | CH04 | Conflicting signals: recent trend weak, campaign active, last year was 4,818 |
| Toray T700 Prepreg Sheet | `SM-0546` | SO16 (UK) | CH01 | Machine 85% above run-rate — downward override tension |
| Hazet 916HP Combination Wrench II | `CP-0312` | SO01 (DACH) | CH02 | Clean upward: machine 38% below three-month trend |

Use **CP-0271 / SO04 / CH01** as the default — all five agents return real signals for this product.

---

## Architecture

```
Planner enters override + reason
        │
        ▼
[Reason classifier → fixed taxonomy]
        │
   ┌────┴──────────────────────────────────────┐
   ▼         ▼          ▼           ▼           ▼
DEMAND    SUPPLY     FINANCE    COMMERCIAL   MEMORY
orders    stock      biz plan   campaigns    scored
customers OTIF       costs      price chg    history
returns   suppliers  tariffs
   └────┬──────────────────────────────────────┘
        │ signals with claim + direction + evidence rows
        ▼
RECONCILER (Claude Opus 4.8) — one call per decision
  recommended_value + confidence_level + rationale
        │
        ▼
PLANNER commits final number
        │
        ▼
DuckDB write-back → scored when actuals arrive → feeds next decision
```

### Stack

| Component | Choice | Why |
|---|---|---|
| Data store | DuckDB | Embedded SQL, queries parquet directly, no server |
| Agents | Python (rule-based) | Deterministic, zero model cost per signal |
| Reconciler | Claude Opus 4.8 | One call per decision — the only AI inference in the pipeline |
| Frontend | Streamlit | Python-native, no React, fast to build |
| Charts | Plotly | Interactive 3-line accuracy chart |

Not using: Neo4j, vector databases, LangChain. Every cut was made because the simpler alternative covers the actual query.

---

## Data

Alpine Manufacturing GmbH — a fictional Stuttgart-based industrial group used as the demo dataset.

- **600 SKUs** across Precision Components, Consumer Products, Specialty Materials
- **18 EU sales organisations** (DACH, BeNeLux, Western EU, Nordics, Eastern EU, UK, Southern EU)
- **4 channels** (B2B key accounts, distributors, wholesale, e-commerce)
- **2.8M sales rows** (May 2023 – May 2026)
- **23 scored planning cycles** for FVA replay

Source files live in `data/alpine-manufacturing-gmbh/`. Forecast pipeline outputs (live forecasts, backtest results) live in the `forecast-output/` subfolder.

> **Note on parquet loading:** Alpine's files use `uint32` dictionary-encoded columns that crash `pandas.read_parquet`. Always use `compass.loader` functions — they decode via PyArrow before converting to pandas.

---

## Repo structure

```
compass/
  loader.py          — safe parquet loader (uint32 dict decode)
  store.py           — DuckDB: init, write_decision, score_decision
  fva.py             — FVA computation for replay dashboard
  insights.py        — real-data facts: run-rate, last year, value/unit, stock
  classifier.py      — reason text → fixed taxonomy class
  embeddings.py      — sentence-transformers semantic recall
  memory.py          — Memory agent: track record lookup + calibrated suggestion
  reconciler.py      — single Claude Opus call per decision
  pipeline.py        — run_pipeline() entry point
  router.py          — relevance gate (which agents run)
  contracts.py       — shared dataclasses (DecisionContext, Signal, MemoryContext…)
  agents/
    demand.py        — order book, customer trends, returns
    supply.py        — stock cover, OTIF, production attainment
    finance.py       — revenue vs plan, tariff movements
    commercial.py    — active campaigns, recent price changes

app/
  main.py            — Streamlit shell, CSS, routing, theme toggle
  views/
    live_decision.py     — 4-step decision flow
    replay_dashboard.py  — FVA replay chart and period drill-down

scripts/
  setup.py           — one-command bootstrap (DB init + cache precompute)
  seed_demo_data.py  — inserts 18 scored demo decisions for memory context
  precompute.py      — standalone cache regeneration

data/
  alpine-manufacturing-gmbh/   — source parquet files
  compass.duckdb               — generated by setup.py (gitignored)
  headline_stats.json          — pre-computed FVA summary stats
  replay_chart_cache.parquet   — pre-computed cycle-by-cycle accuracy
```
