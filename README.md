# Compass

**A demand-planning override copilot with a panel of grounded agents and institutional memory.**

> Paretos Hackathon · Alpine Manufacturing GmbH dataset · 5 people / 15 hours

---

## The problem

Alpine's machine forecast is overridden by human planners **99.9% of the time** (verified in the data — median override ~17%, 84% downward). Every override encodes a judgment: a promotion, a competitor exit, a channel overstock, a rumor heard through the grapevine. Today, **that reasoning evaporates the moment the number is changed** — and nobody measures whether the override actually helped. Across real demand-planning research, human overrides improve accuracy only about half the time.

Compass captures the *why*, scores whether the *why* was worth anything against actuals, and feeds that scored knowledge back so each planning cycle is smarter than the last.

## The idea in one sentence

A panel of function-specialist AI agents — each grounded in a real Alpine data domain — surfaces evidence about a proposed forecast override; a **reconciler** agent weighs it against the planner's track record from scored memory and recommends a calibrated number; **the human decides**; the outcome is scored and written back, so the institution gets smarter every cycle.

## Why it's useful, not a showpiece

1. **Every agent claim carries a data citation** (a table + rows). No grounded signal → the agent stays silent. No vibes.
2. **It's a DAG, not a debate.** Agents contribute once, in parallel → the reconciler synthesizes once → the human planner is the final node. It physically cannot loop or go in circles.
3. **Memory is scored by outcomes, not self-assertion.** When Compass pushes back it states a fact — *"the last 4 times you cut Bearings in DACH for 'channel overstock', actuals came in 9% above your number"* — not an argument.

---

## Architecture

```
                          ┌─────────────────────────────────────┐
   PLANNER (frontend)     │   Machine forecast: 437 units        │
   proposes override  ──► │   Planner override: 360  (-17%)      │
   + free-text reason     │   Reason: "competitor exiting DACH"  │
                          └──────────────────┬──────────────────┘
                                             │
        ┌────────────────────────────────────┼────────────────────────────────────┐
        ▼                ▼                    ▼                   ▼                 ▼
 ┌────────────┐  ┌──────────────┐   ┌────────────────┐  ┌──────────────┐  ┌──────────────┐
 │  DEMAND    │  │   SUPPLY/    │   │    FINANCE/    │  │  COMMERCIAL/ │  │   MEMORY /   │
 │  AGENT     │  │   OPS AGENT  │   │  MARGIN AGENT  │  │ MARKET AGENT │  │   CRITIC     │
 ├────────────┤  ├──────────────┤   ├────────────────┤  ├──────────────┤  ├──────────────┤
 │future_order│  │stock_on_hand │   │business_plan   │  │marketing_    │  │FVA track     │
 │_book       │  │purchase_     │   │cost_breakdown  │  │spends        │  │record (this  │
 │customers   │  │orders (OTIF) │   │price_changes   │  │price_changes │  │planner +     │
 │.is_declin- │  │suppliers     │   │tariff_         │  │+ planner's   │  │reason-type)  │
 │ing, returns│  │production    │   │reference       │  │market signal │  │+ KG: similar │
 └─────┬──────┘  └──────┬───────┘   └───────┬────────┘  └──────┬───────┘  │past events   │
       │                │                   │                  │          └──────┬───────┘
       └────────────────┴─────────┬─────────┴──────────────────┴─────────────────┘
                                   ▼
                         ┌───────────────────────┐
                         │   RECONCILER (judge)  │   single pass, no loop
                         │  • weighs each signal │
                         │  • applies FVA priors │
                         │  • rec. number +      │
                         │    confidence + trail │
                         └───────────┬───────────┘
                                     ▼
                         PLANNER decides (final node)
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │  WRITE-BACK to MEMORY + KG     │
                    │  override, reason (classified),│
                    │  event node → linked SKUs      │
                    └────────────────────────────────┘
                                     │
                          (next cycle: actuals arrive)
                                     ▼
                    ┌────────────────────────────────┐
                    │  SCORING: machine_err vs       │
                    │  override_err → FVA → update   │
                    │  track records & event impacts │
                    └────────────────────────────────┘
```

---

## The agents

Each agent is grounded in a real Alpine table — no "same LLM, different hat" theater.

| Agent | Reads | Example contribution |
|-------|-------|----------------------|
| **Demand** | `future_order_book`, `customers` (`is_declining`, `key_account_flag`), `returns` | "Two key accounts in SO04 placed confirmed orders above plan; one declining customer offsets it." |
| **Supply / Ops** | `stock_on_hand`, `purchase_orders` (OTIF = expected vs actual), `suppliers` (lead time), `production_data` (planned vs actual, capacity) | "Stock cover is 2 weeks; supplier OTIF is 71%. Raising the forecast risks a stockout you can't fulfill." |
| **Finance / Margin** | `business_plan`, `cost_breakdown`, `price_changes`, `tariff_reference` | "Cutting volume here puts you 12% under the BU revenue plan; tariff surcharge just rose for this region." |
| **Commercial / Market** | `marketing_spends`, `price_changes`, **+ planner's injected market signal** | "A Social Media campaign for this category launches next month — historically a +8% lift." |
| **Memory / Critic** | Scored override store + Knowledge Graph | "Your 'competitor exit' overrides realize +13% on average, not the +20% guessed; your downward bias on Consumer Products costs ~6 pts of accuracy." |

The **Reconciler** consumes all five, applies the memory priors, and emits a recommended number, a confidence level, and a one-screen evidence trail.

---

## The knowledge graph

The KG does one job a relational store can't: **propagate one market signal across many SKUs.**

- **Nodes:** Products → Product Groups → Categories → Business Units (the hierarchy), plus Sales Orgs → Region Groups, Customers, Suppliers, Channels, and **Event nodes** (every override / market signal with its classified reason).
- **Edges:** an Event links to the set of SKUs it plausibly affects via hierarchy + region. Log *"competitor exiting in DACH, Bearings & Bushings"* and the event fans out to **all bearings SKUs across DACH sales orgs**.
- **Payoff:** next cycle, any of those SKUs retrieves the linked event and its realized impact. One logged insight informs dozens of decisions.
- Built with **`networkx`** (in-memory) — no Neo4j setup tax.

---

## The learning loop

1. **Capture** — planner overrides + writes a reason; an LLM classifies the free text into a fixed taxonomy (promotion, competitor exit, trade show, channel overstock, price change, supply constraint, other). Without the taxonomy, every reason is unique and nothing is learnable.
2. **Link** — the override becomes an Event node in the KG, fanned out to affected SKUs.
3. **Score** — when actuals land, compute `machine_error` vs `override_error` → **Forecast Value Added (FVA)**. Update two track records: per-planner and per-reason-type.
4. **Recall** — next cycle, the Critic retrieves similar past events (KG neighborhood + vector similarity), the planner's FVA history, and the realized-impact distribution for that reason-type.
5. **Calibrate** — the Reconciler turns anecdote into a prior: *"competitor-exit events realize +13% ±4%; your proposed +20% is high — suggest +14%."* Confidence scales with how much scored history exists (cold start → low confidence → defer to the planner).

**Two substrates, deliberately stacked:**

- **Quantitative (real, from 24 historical cycles):** bias detection + FVA needs no reasons — pure machine-vs-plan-vs-actual. Truthful today; the demo safety net.
- **Qualitative (forward-simulated):** reason-memory + KG propagation, shown with a few injected market events across simulated cycles. (The historical overrides have no reasons attached — that *is* the problem being posed — so the reason loop is demonstrated going forward, not mined from the past.)

---

## Demos

**A. Live decision** — Planner opens a SKU, sees machine forecast + draft override + reason box → submits → five agent cards return grounded evidence → Reconciler shows a recommended number, confidence, and evidence trail → planner finalizes. Override + KG fan-out recorded live.

**B. Replay dashboard** — Step through N cycles; at each, the copilot recommends using only memory available up to that point. Plot accuracy: **machine baseline vs. unaided planner overrides vs. planner-with-Compass.** The Compass line bends below the others as memory accumulates. This chart is the pitch.

---

## The dataset

Alpine Manufacturing GmbH — a fictional Stuttgart industrial group. 3 business units (Precision Components, Consumer Products, Specialty Materials), 4 channels (B2B, Amazon, B2C, Distributor), 18 European sales orgs, 600 SKUs, 250 customers, 50 suppliers. All values in EUR. Source tables, a machine forecast, and a planner-adjusted demand plan are provided as Parquet files.

**Verified spine:** `alpine_statistical_forecast` (machine) and `alpine_demand_plan` (planner-adjusted) overlap on **24 monthly cutoffs**, both joinable to `alpine_sales_actuals` — giving 24 real, replayable planning cycles.

> **Loader note:** these Parquet files use uint32 dictionary indices that break a plain `pandas.read_parquet`. Read with `pyarrow.parquet` and decode dictionary columns to their value type first (or use DuckDB).

---

## Build plan — 5 × 15h

**H0–2 Contracts** (lock all inter-layer interfaces; everyone builds against stubs) · **H2–8** parallel build · **H8–12** integration · **H12–14** polish + injected-event narrative · **H14–15** rehearse.

| Person | Owns |
|--------|------|
| **P1 — Data/Backend** | Parquet loader (dict-decode), override reconstruction, FVA scoring, cycle-replay harness. DuckDB over the parquet files. |
| **P2 — Memory + KG** | `networkx` KG (event→SKU fan-out), reason-taxonomy classifier, vector store for similar-event recall, track-record aggregations. |
| **P3 — Agents** | Function-agents (retrieval tool per table + short narration) and the Reconciler. |
| **P4 — Frontend** | Streamlit app: live decision screen + replay dashboard with the accuracy chart. |
| **P5 — Integration + Narrative** | Glue, injected-event story, deterministic fallbacks, prompt tuning, pitch + rehearsal. |

### Scope discipline

- **Must-have:** override capture + reason classification + FVA scoring + memory recall + **2 grounded agents** (Demand + Supply) + Reconciler + live UI for one decision + replay chart + KG fan-out for **one** event type.
- **Stretch:** full 4-agent panel, multi-event propagation, planner-specific bias models, confidence intervals.
- **Pre-compute, don't compute live:** cache the heavy FVA joins; the demo never waits on a 1.3M-row join.

---

## Tech stack

Python · **DuckDB** + pyarrow (dict-decode loader) · **networkx** KG · **Chroma/FAISS** vectors · **Claude** (Opus 4.8 = reconciler/reasoning, Haiku = reason classification) via the Anthropic API · **Streamlit** frontend.

---

## Risks & honest caveats

- **Attribution is aggregate, not per-override.** FVA is only trustworthy over many overrides; we score patterns, not single decisions.
- **Cold start:** useful on day 1 (capture + classify); track-record confidence grows over cycles.
- **n=1 events:** one past event is a weak prior — show uncertainty, pool across the hierarchy, never autopilot.
- **Synthetic reasons:** the qualitative loop runs on injected forward events by necessity; we're upfront about it.
- **Gaming:** if planners feel surveilled they stop overriding — Compass is framed as decision-support, and scores reason-types more loudly than people.

---

## Bottom line

A panel that's a single-pass DAG over a scored-memory substrate. The quantitative (real-data) layer protects the demo; the KG + reason-memory layer delivers the "institutional knowledge compounds over time" story. The accuracy-curve chart is the thing that wins.
