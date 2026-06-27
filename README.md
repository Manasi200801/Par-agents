# Compass

> An institutional-memory and calibration layer for human-over-model workflows.

Paretos Hackathon · 5 people · 15 hours

---

## The problem

Everywhere an AI system proposes a number and a human changes it, two things happen:

1. **The reasoning evaporates.** Nobody records *why* the number was changed.
2. **The outcome is never scored.** Nobody checks whether the change actually helped.

This is not a niche problem. It happens in demand forecasting, ad budgets, hospital staffing, credit limits, pricing — anywhere an AI model proposes and a human overrides. Research on demand planning specifically shows human overrides improve accuracy only about half the time. Small gut-feel adjustments usually make things *worse*. Large overrides backed by genuine market intelligence usually help. But nobody knows which is which, because the reasoning is never captured and the outcomes are never scored.

The result: the institution never learns. Every planning cycle starts from zero. The planner's expertise does not compound.

**Compass fixes this.** It captures the reason, classifies it, fans it out to every affected entity, scores the outcome when actuals arrive, and feeds that scored history back — so each cycle the system can say *"the last four times you cited 'competitor exit' for this product category, actuals came in at +13%, not the +20% you guessed. Suggest a smaller upward revision."*

That is a fact, not an argument. And that is the product.

---

## What it is (one sentence)

A panel of function-specialist AI agents — each grounded in a real data domain — surfaces evidence about a proposed forecast override; a reconciler weighs it against the planner's scored track record from memory; the human decides; the outcome is scored and written back; the institution gets smarter every cycle.

---

## The three rules that keep it from being a showpiece

1. **Every agent claim carries a data citation.** A table name and the rows it read. If an agent cannot find a grounded signal, it stays silent. No padding, no hallucination.
2. **It is a DAG, not a debate.** Agents contribute once, in parallel. The reconciler synthesizes once. The human is the final node. There is no back-and-forth loop. It cannot go in circles by design.
3. **Memory is scored by outcomes, not self-assertion.** The system earns its opinions by measuring Forecast Value Added (FVA) against actuals. When it pushes back, it cites history. Never vibes.

---

## How it works — the full flow

### 1. Planner opens a product and proposes an override

The UI shows the machine forecast for a product + sales org + channel. The planner enters their proposed number and a free-text reason:

```
Machine forecast:   437 units
Planner override:   360 units  (-17%)
Reason:             "Competitor rumoured to be exiting DACH market"
```

### 2. Five agents run in parallel — each reads a different data domain

Each agent is a function that queries one set of tables, finds signals relevant to this decision, and returns a structured evidence card. If nothing relevant is found, the card is empty and not shown.

**Demand Agent** — reads `future_order_book`, `customers` (is_declining, key_account_flag, segment), `returns`
> "Two key-account wholesale partners in SO04 placed confirmed orders above the current plan. One large account is flagged as declining and may not convert."

**Supply / Ops Agent** — reads `stock_on_hand`, `purchase_orders` (OTIF), `suppliers` (lead time), `production_data`
> "Stock cover is 2.1 weeks. This supplier's on-time delivery rate is 71%. A downward override combined with low stock risks a service failure if demand comes in higher."

**Finance / Margin Agent** — reads `business_plan`, `cost_breakdown`, `price_changes`, `tariff_reference`
> "Cutting this volume puts the Precision Components BU 12% below its revenue plan. Tariff surcharge on Southeast Asia sourcing rose 6% last quarter."

**Commercial / Market Agent** — reads `marketing_spends`, `price_changes`, and the planner's free-text signal
> "A social media campaign for this category is active in SO04 this month. Historical campaign lift for this type: approximately +8%."

**Memory / Critic Agent** — reads the scored decision history and the knowledge graph
> "You have made 4 overrides citing 'competitor exit' in the past 12 months. Average realized impact: +13% above machine forecast. Your average guess: +20%. Your downward bias on Consumer Products costs approximately 6 accuracy points per cycle."

### 3. The reconciler synthesizes — one pass, no loop

A single reasoning step (Claude Opus 4.8) reads all five evidence cards and the planner's proposed number, then outputs:

- **Recommended number** — e.g., 402 units
- **Confidence level** — low / medium / high (scales with how much scored history exists)
- **Evidence trail** — which agents contributed what, in plain language

The planner sees this on one screen. They can accept, reject, or adjust.

### 4. The human decides — always the final node

The planner finalizes a number. Compass records:

```
decision_id:       uuid
cutoff:            2025-06-01
item_id:           CP-0271 × SO04 × CH01
machine_proposal:  437
planner_override:  360
reconciler_rec:    402
final_decision:    390
reason_text:       "Competitor rumoured to be exiting DACH market"
reason_class:      competitor_exit          ← classified by Haiku
decision_maker:    planner_id_007
affected_skus:     [CP-0271, CP-0272, CP-0280, ...]  ← KG fan-out
```

### 5. The knowledge graph fans the event out to related SKUs

When the planner logs "competitor exiting DACH, Consumer Products," this event is not stored against just one SKU. It is linked to **every SKU in the same category and region** via the product hierarchy. The next time any of those SKUs comes up in the planning cycle, the Memory agent already knows about this event and its eventual outcome.

This is what makes institutional memory genuinely institutional — one planner's insight propagates automatically to 40 related SKUs, not just the one they were looking at.

### 6. Actuals arrive — the decision is scored

One cycle later, real sales numbers come in. Compass calculates:

```
machine_error    = |actual - machine_proposal|   = |412 - 437|  = 25
override_error   = |actual - final_decision|     = |412 - 390|  = 22
fva              = machine_error - override_error = +3   ← positive = planner helped
```

This FVA score is written back to the decision record and to the event node in the knowledge graph. The realized impact is now a data point: "competitor-exit events in DACH Consumer Products have historically resulted in +13% above machine forecast on average."

### 7. The next cycle is smarter

Every future decision in the same category, region, or reason type now has more scored history behind it. The Memory agent's claims become more precise. The reconciler's confidence level rises. The planner's personal track record is updated.

**This is the compounding loop.** Cycle 1: cold start, low confidence, mostly capture. Cycle 6: "we've scored 12 competitor-exit events, here is the realized distribution." Cycle 12: the system knows which planners add value on which product types, and which overrides consistently destroy accuracy.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND (Streamlit)                  │
│   Live Decision View                Replay Dashboard         │
│   ┌───────────────────────┐        ┌──────────────────────┐ │
│   │ Machine:  437 units   │        │ Cycle accuracy chart │ │
│   │ Override: [   360   ] │        │ • Machine baseline   │ │
│   │ Reason:   [text box ] │        │ • Unaided planner    │ │
│   │                       │        │ • Planner + Compass  │ │
│   │ [Submit for analysis] │        │   (curve improves)   │ │
│   └───────────────────────┘        └──────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │ override + reason
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     AGENT LAYER (parallel)                   │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌─────┐│
│  │ DEMAND   │ │ SUPPLY   │ │ FINANCE  │ │COMMERC.│ │MEMO ││
│  │ AGENT    │ │ OPS      │ │ MARGIN   │ │MARKET  │ │CRIT.││
│  │          │ │ AGENT    │ │ AGENT    │ │AGENT   │ │     ││
│  │order_book│ │stock_oh  │ │biz_plan  │ │mktg_   │ │FVA  ││
│  │customers │ │purch_ord │ │cost_brkd │ │spends  │ │track││
│  │returns   │ │suppliers │ │price_chg │ │price_  │ │recs ││
│  │          │ │prod_data │ │tariff_ref│ │chg +   │ │+ KG ││
│  │          │ │          │ │          │ │signal  │ │     ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ └──┬──┘│
│       └────────────┴────────────┴────────────┴─────────┘   │
│                             │ 5 evidence cards               │
└─────────────────────────────┼───────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  RECONCILER (Claude Opus 4.8)                │
│  Single pass · No loop · Synthesizes all 5 cards            │
│  Output: recommended number + confidence + evidence trail    │
└──────────────────────────┬──────────────────────────────────┘
                           │ recommendation
                           ▼
                   PLANNER (final node)
                   Human always decides
                           │ final number
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  SINGLE DATA STORE (DuckDB)                  │
│                                                              │
│  ┌─────────────┐  ┌───────────┐  ┌──────────┐  ┌────────┐ │
│  │  hierarchy  │  │ decisions │  │  events  │  │event_  │ │
│  │  (product   │  │ (universal│  │ (one per │  │sku     │ │
│  │   & org     │  │  record + │  │  override│  │(fan-out│ │
│  │  hierarchy) │  │  FVA col) │  │  + embed)│  │ table) │ │
│  └─────────────┘  └───────────┘  └──────────┘  └────────┘ │
│                                                              │
│  Track records = GROUP BY views over decisions table        │
│  Vector search = embedding column on events.reason_text     │
└─────────────────────────────┬───────────────────────────────┘
                              │ (next cycle: actuals arrive)
                              ▼
                       FVA SCORING JOB
                  machine_err vs override_err
                  → update realized_fva on event
                  → update per-planner track record
                  → update per-reason-type track record
```

---

## The data store — one store, not three

**Decision made: DuckDB for the hackathon. Postgres + pgvector for production.**

We are not using a separate graph database (Neo4j) or a separate vector database (Chroma, Pinecone). Here is why:

**Why no graph database:** The only graph feature we need is event-to-SKU fan-out — "this competitor-exit event affects all bearings SKUs in DACH." That is a `WHERE category = 'Bearings' AND region = 'DACH'` join on the hierarchy table. A graph database earns its cost when you need multi-hop variable-depth traversal of irregular relationships. We do not have those queries. We have joins. A relational table is simpler, cheaper, and faster for joins.

**Why no separate vector database:** Modern stores handle vector columns natively. DuckDB has VSS extension; Postgres has pgvector. An extra service to deploy, configure, and keep in sync with the main store is operational cost with no benefit.

**The "knowledge graph" is a logical concept, not an infrastructure choice.** It is the set of entity and event tables below, queried with SQL.

### Schema

```sql
-- Product and org hierarchy (loaded once from source data)
CREATE TABLE hierarchy (
    product_id      TEXT,
    product_group   TEXT,
    category        TEXT,
    business_unit   TEXT,
    sales_org_id    TEXT,
    region_group    TEXT
);

-- One row per planner decision (the universal record)
CREATE TABLE decisions (
    decision_id     TEXT PRIMARY KEY,
    cutoff          DATE,
    item_id         TEXT,          -- product_id × sales_org_id × channel_id
    machine_value   FLOAT,         -- what the model said
    override_value  FLOAT,         -- what the planner changed it to
    final_value     FLOAT,         -- what was actually submitted
    reason_text     TEXT,          -- planner's free text
    reason_class    TEXT,          -- taxonomy class (from Haiku)
    decision_maker  TEXT,
    context_json    JSON,          -- snapshot of agent evidence cards
    outcome         FLOAT,         -- actual (written later)
    machine_error   FLOAT,         -- |actual - machine| (written later)
    override_error  FLOAT,         -- |actual - final| (written later)
    fva             FLOAT          -- machine_error - override_error (written later)
);

-- One row per market event / override signal
CREATE TABLE events (
    event_id        TEXT PRIMARY KEY,
    decision_id     TEXT REFERENCES decisions(decision_id),
    reason_class    TEXT,
    reason_text     TEXT,
    reason_embedding FLOAT[],      -- vector column for semantic recall
    realized_impact  FLOAT         -- written when actuals arrive
);

-- Fan-out: one row per (event, affected SKU)
CREATE TABLE event_sku (
    event_id        TEXT REFERENCES events(event_id),
    product_id      TEXT,
    sales_org_id    TEXT
);

-- Track records are views, not stored tables
CREATE VIEW track_record_by_reason AS
    SELECT reason_class,
           COUNT(*) AS n_decisions,
           AVG(fva) AS avg_fva,
           AVG(override_value / NULLIF(machine_value,0) - 1) AS avg_override_pct,
           AVG(outcome / NULLIF(machine_value,0) - 1) AS avg_realized_pct
    FROM decisions
    WHERE fva IS NOT NULL
    GROUP BY reason_class;

CREATE VIEW track_record_by_planner AS
    SELECT decision_maker,
           COUNT(*) AS n_decisions,
           AVG(fva) AS avg_fva,
           SUM(CASE WHEN fva > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS pct_helpful
    FROM decisions
    WHERE fva IS NOT NULL
    GROUP BY decision_maker;
```

### KG lifecycle — append and update only, never rebuilt

```
Planner submits override
    → INSERT one row into decisions
    → INSERT one row into events (with embedding)
    → INSERT N rows into event_sku (WHERE category=… AND region=…)
    → Cost: a few dozen tiny row inserts

Actuals arrive (next cycle)
    → UPDATE decisions SET outcome=…, machine_error=…, override_error=…, fva=…
    → UPDATE events SET realized_impact=…
    → Cost: two single-row updates
```

Zero rebuilds, ever. The store grows incrementally.

---

## The agents — implementation detail

Each agent is a Python function implementing the `EvidenceSource` interface:

```python
class EvidenceSource:
    def get_signals(self, context: DecisionContext) -> list[Signal]:
        ...

@dataclass
class Signal:
    claim: str          # plain-English finding
    direction: str      # "supports_override" | "contradicts_override" | "neutral"
    magnitude: float    # estimated impact magnitude (0–1 scale)
    confidence: float   # confidence in the signal (0–1 scale)
    table: str          # which table this came from
    evidence_rows: list # the actual rows (for citation)
```

If `get_signals` returns an empty list, the agent card is not shown in the UI. Agents are invoked via a **relevance router** that gates which agents run based on the decision context — not all five run on every decision.

### Reason taxonomy (auto-induced by Haiku)

The planner's free text is classified into a fixed set of categories. The taxonomy is not hand-written — it is induced from the first N overrides and refined as new reason types appear. Starter categories:

- `promotion` — campaign, sale, price event
- `competitor_exit` — rival closing, shutting down, losing capacity
- `competitor_entry` — new rival entering the market
- `trade_show_event` — industry event, conference effect
- `channel_overstock` — customer has too much inventory, will order less
- `channel_understock` — customer running low, urgent reorder expected
- `price_change` — own price increase or decrease
- `supply_constraint` — supplier issue, material shortage
- `macro_signal` — economic indicator, currency move, regulation
- `other` — catch-all for genuinely novel reasons

Classification uses Claude Haiku (cheap, fast, runs on every single override). This taxonomy is what makes the learning loop work — without it, every reason looks unique and nothing is learnable across cycles.

---

## The two demos

### Demo A — Live decision (sells the UX)

A planner sits at the screen. They select a SKU (`CP-0271 × SO04 × CH01`), enter an override (360 instead of 437), and type a reason. They hit submit. Within a few seconds:

- Five evidence cards appear — each citing a real table and a real finding
- The reconciler card appears with a recommended number (402), confidence (medium), and a plain-language summary
- The planner accepts, adjusts, or rejects
- The decision is saved, the KG fan-out executes, and the affected SKUs are shown

This demonstrates the full capture-and-advise loop in real time.

### Demo B — Replay dashboard (proves the learning)

Step through N historical planning cycles. At each cycle, Compass recommends using only the memory available up to that point. Plot three lines:

```
Forecast error (lower is better)
│
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  Machine baseline (flat — model doesn't learn from reasons)
│  ──────────────────────    Unaided planner overrides (noisy, sometimes worse)
│         ╲
│          ╲─────────────    Planner + Compass (bends down as memory accumulates)
│
└──────────────────────────── Cycles (time)
```

**This chart is the pitch.** It shows that the planner's expertise compounds over time — which is the stated goal of the project. Everything else is in service of this curve.

For the Alpine dataset: the 24 historical cycles (`statistical_forecast` vs `demand_plan` vs `sales_actuals`) are already in the data — the replay is real, not simulated.

For the Firn dataset: cycles are simulated forward with injected market events, since Firn has never recorded planner overrides before (which is literally the problem being posed).

---

## Datasets

### Primary demo — Alpine Manufacturing GmbH

A fictional Stuttgart-based industrial group. Used for the main demo because it has **24 historical planning cycles** where both the machine forecast and the planner-adjusted plan are recorded and can be scored against actuals.

| | |
|---|---|
| Business units | Precision Components, Consumer Products, Specialty Materials |
| Channels | B2B, Amazon, B2C, Distributor |
| Sales orgs | 18 across DACH, BeNeLux, Western EU |
| SKUs | 600 |
| Customers | 250 named B2B accounts |
| Suppliers | 50 |
| Sales actuals | 2.8 million daily rows (May 2023 → Feb 2026) |
| Machine forecast | `alpine_statistical_forecast` (36 monthly cutoffs) |
| Planner forecast | `alpine_demand_plan` (24 monthly cutoffs — overlapping with machine) |
| FVA-ready cycles | **24** (machine vs planner vs actuals) |

**Key verified data fact:** Planners override the machine forecast 99.9% of the time. Median override magnitude: ~17%. Direction: 84% downward. Whether this helps or hurts is what the replay chart will show.

### Generality proof — Firn Outdoor AG

A fictional Zurich-based direct-to-consumer outdoor apparel brand. Used to demonstrate that Compass is not a manufacturing-specific tool — it is a general system that runs on a completely different business domain by swapping adapters.

| | |
|---|---|
| Business units | Mountain Sports, Trail & Hike, Lifestyle |
| Channels | Webshop, Marketplaces, Wholesale, Outlet |
| Sales orgs | 18 across Europe (fulfillment-center based) |
| SKUs | 800 |
| Customers | 180,026 (individuals + 26 named wholesale partners) |
| Suppliers | 35 textile mills (Turkey, Bangladesh, Vietnam, Portugal, Italy) |
| Sales actuals | 961,740 weekly rows |
| Returns | 65,462 rows — dominated by "Wrong size" (35%) and "Fit issue" (25%) |
| FVA-ready cycles | 0 historical — Compass starts capturing from day 1 |

**Key differences that require adapter changes (not core changes):**
- Returns are a primary demand signal in apparel — high return SKUs need a downward prior
- 180K individual customers are handled at segment level (Returning, New, Loyalty, VIP)
- Textile mill lead times are 5–14 weeks — missing a season is catastrophic; Supply agent is critical
- Cost structure is DTC: platform fees, returns handling, fulfillment, marketing — not raw material and tariffs
- No historical machine vs planner split — the replay chart is built forward, not replayed backward
- No tariff reference table — tariff events are injected planner signals, not auto-read from a table

**The point:** change the adapters, run the same Compass. Zero changes to the core loop, schema, or agent interfaces.

---

## What the system is NOT

- It is not a replacement for the planner. The human is always the final node.
- It does not work without observable outcomes. If the result is never measured, the loop degrades to a logging tool.
- It does not work at microsecond cadence. It is designed for daily/weekly/monthly human-paced decisions.
- It does not score individual overrides as causal. FVA is only meaningful in aggregate over many similar decisions. We score patterns, not individual people.
- It does not autopilot. Low confidence = "here is what we know, which is not much yet, you should decide."

---

## Tech stack

| Tool | Role | Why this, not something else |
|------|------|------------------------------|
| **Python** | Everything | Universal, fastest for data work |
| **DuckDB** | Single data store (hackathon) | Queries parquet files directly with SQL; zero server setup; handles vectors with VSS extension |
| **Postgres + pgvector** | Single data store (production) | Same SQL, adds durability and concurrency |
| **pyarrow** | Parquet loader | The Alpine and Firn files use uint32 dictionary indices that break plain `pandas.read_parquet`. Use pyarrow and decode dictionary columns manually, or use DuckDB directly |
| **Claude Haiku** | Reason taxonomy classifier | Runs on every override; must be cheap and fast. Does one job: free text → reason class |
| **Claude Opus 4.8** | Reconciler | Runs once per decision after all agent cards are collected. The one step that needs genuine reasoning. Gate it — it is the real cost center |
| **Streamlit** | Frontend (both views) | Turns Python into a working UI in hours. Both the live decision screen and the replay dashboard in one app |
| **networkx** | In-memory graph (hackathon only) | If any in-memory graph traversal is needed during the hackathon. Drop in production — it's just the relational tables |

**Not using:** Neo4j (graph queries are joins, not traversals), Chroma/Pinecone (vector is one column in DuckDB), React (Streamlit is enough at 15 hours), LangChain (direct API calls are simpler and more debuggable at this scale).

---

## Cost model

The expensive thing is LLM inference. Everything else is negligible.

| Component | Cost | Notes |
|-----------|------|-------|
| Storage (DuckDB / parquet) | ~free | Decisions table at 1000 rows/month is kilobytes |
| FVA computation | ~free | A subtraction after a join |
| Embeddings (reason text) | Cents | One embedding per override, written once |
| Haiku (reason classification) | ~$0.001 per decision | 1000 decisions/month = $1 |
| Opus 4.8 (reconciler) | ~$0.05–0.15 per decision | 1000 decisions/month = $50–150 |

**Control the Opus spend:** (1) gate the reconciler — only run it when the planner actually submits an override, not on every page load; (2) gate the agents — use a relevance router to invoke only the 2–3 agents with relevant signals, not all 5 every time; (3) cache agent evidence cards for the same item within the same planning cycle.

---

## Build plan — 5 people × 15 hours

### Hour 0–2: Contracts (everyone together)

Lock the interfaces between all layers before anyone writes real code. The output of this session is:
- The JSON schema each agent returns (`Signal` dataclass)
- The `DecisionContext` object passed to agents
- The DuckDB schema (4 tables above) created and loadable
- Stub implementations of every component
- Agreement on which 2 agents are must-have (Demand + Supply)

Everyone builds against stubs in parallel. No one blocks on anyone else.

### Hour 2–8: Parallel build

| Person | Builds |
|--------|--------|
| **P1 — Data / Backend** | pyarrow loader with dict-decode fix · DuckDB setup over parquet files · override reconstruction (statistical_forecast vs demand_plan join) · FVA scoring function · cycle-replay harness that steps through 24 cycles |
| **P2 — Memory + KG** | decisions/events/event_sku tables · reason classifier (Haiku call) · embedding generation and storage · semantic recall query (vector similarity on reason_text) · track-record views · event fan-out query (hierarchy join) |
| **P3 — Agents + Reconciler** | Demand agent (order_book + customers + returns) · Supply agent (stock + OTIF + suppliers) · Reconciler (Opus call with all evidence cards + memory context) · relevance router stub |
| **P4 — Frontend** | Streamlit app skeleton · live decision screen (machine value, override input, reason box, agent cards, reconciler card) · replay dashboard (cycle stepper, three-line accuracy chart) · connects to stub APIs |
| **P5 — Integration + Narrative** | Interface glue between all components · injected market event scenarios for the qualitative demo · deterministic fallback values if any component fails · the pitch deck structure · manages the demo script |

### Hour 8–12: Integration

P5 drives. Connect real implementations to the Streamlit frontend. Run the 24-cycle replay end to end. Fix integration bugs. Add the Finance and Commercial agents if time allows.

### Hour 12–14: Polish

Freeze features. Pre-compute and cache all heavy joins so the demo never waits. Test the live decision flow 10 times. Prepare the injected-event story for the qualitative demo. Decide on the two or three numbers that go on the accuracy chart.

### Hour 14–15: Rehearse

Full demo run twice. Identify the single most likely failure point and add a manual fallback. Prepare the three questions judges will ask.

---

## Scope discipline

### Must ship (M)

- Override capture with free-text reason
- Haiku reason classifier → taxonomy class
- FVA scoring against actuals
- Memory recall (track record by reason class + by planner)
- **2 grounded agents:** Demand (order book + customers) and Supply (stock + OTIF)
- Reconciler synthesizing those 2 agents + memory
- Live decision UI showing the full flow
- Replay dashboard showing the accuracy chart over 24 cycles
- Event fan-out for at least one event type (competitor exit → category × region)

### Build if time allows (S)

- Finance/Margin agent
- Commercial/Market agent
- Planner-specific bias models
- Confidence intervals on the recommendation
- Multi-event-type fan-out
- The Firn dataset tab (generality proof)

### Do not build

- Real-time streaming / webhooks
- Multi-tenant auth
- Any UI beyond Streamlit
- Anything that requires more than 5 minutes to explain

---

## Questions judges will ask

**"Is this just a chatbot that argues with the planner?"**
No. Each agent reads a specific table and either finds a grounded signal or stays silent. The reconciler synthesizes evidence, not opinions. When it pushes back, it cites a scored track record, not reasoning from general knowledge.

**"Does this only work for manufacturing / demand forecasting?"**
No. The core loop (model proposes → human overrides with reason → outcome scored → memory updated) is domain-agnostic. We demonstrate this with Firn Outdoor AG — a DTC apparel brand — using the same core system with different adapters. Demand forecasting is the first vertical because Alpine gives us clean, historically-scoreable override data.

**"How does it get smarter — can you show that?"**
The replay dashboard shows it. Three lines: machine baseline (flat), unaided planner (noisy), planner-with-Compass (bends downward as cycles accumulate). The chart is built from real Alpine data — 24 real planning cycles, real overrides, real actuals.

**"What happens on day 1 when there's no history?"**
It captures and classifies. Confidence is low. The reconciler says so explicitly and defers to the planner. By cycle 3 it has enough to start making useful calibration statements. The system is designed to be honest about what it doesn't know yet.

**"Is this expensive to run?"**
The only meaningful cost is Opus inference for the reconciler — approximately $0.05–0.15 per decision. A planning team making 100 decisions per cycle spends $5–15 per cycle on AI inference. Everything else (storage, embeddings, Haiku classification) is negligible.

---

## Repository structure

```
compass/
├── README.md                    ← this file
├── data/
│   ├── alpine-manufacturing-gmbh/
│   │   ├── source-data/         ← 18 parquet files
│   │   └── forecast-output/     ← live forecasts, error metrics
│   ├── alpine-manufacturing-forecast/
│   │   ├── source-data/
│   │   ├── forecast-output/
│   │   └── forecast-baseline/   ← naive baseline comparison
│   └── firn-outdoor-ag/
│       └── source-data/         ← 16 parquet files
├── compass/
│   ├── data/
│   │   ├── loader.py            ← pyarrow loader with dict-decode fix
│   │   ├── store.py             ← DuckDB setup and query helpers
│   │   └── fva.py               ← FVA scoring and replay harness
│   ├── memory/
│   │   ├── schema.sql           ← the 4 tables + 2 views
│   │   ├── classifier.py        ← Haiku reason classifier
│   │   ├── embeddings.py        ← reason embedding + recall
│   │   └── track_records.py     ← group-by views + FVA aggregation
│   ├── agents/
│   │   ├── base.py              ← EvidenceSource interface + Signal dataclass
│   │   ├── demand.py            ← order book + customers + returns
│   │   ├── supply.py            ← stock + OTIF + suppliers + production
│   │   ├── finance.py           ← business plan + costs + tariffs
│   │   ├── commercial.py        ← marketing + price changes + signal
│   │   ├── memory_critic.py     ← track records + KG recall
│   │   └── reconciler.py        ← Opus synthesis
│   └── router.py                ← relevance gate (which agents run)
├── app/
│   ├── main.py                  ← Streamlit app entrypoint
│   ├── views/
│   │   ├── live_decision.py     ← live override flow
│   │   └── replay_dashboard.py  ← 24-cycle accuracy chart
│   └── components/
│       ├── agent_card.py        ← evidence card UI component
│       └── reconciler_card.py   ← recommendation UI component
└── scripts/
    ├── precompute_fva.py        ← run offline, cache results
    └── inject_events.py         ← inject demo market events for narrative
```
