# P3 — Agents & Reconciler
**Branch: your own branch on https://github.com/Manasi200801/Par-agents.git**
**You own: `compass/agents/`, `compass/reconciler.py`, `compass/router.py`**

---

## What Compass is (read this first)

Compass is a demand-planning override copilot. A machine forecasts sales (437 units). A human planner overrides it (360 units) and types a reason. Your job: run the evidence agents and the reconciler. The agents each read a specific data table, find a signal relevant to this decision, and return a plain-English claim with the rows that back it up. The reconciler (Claude Opus) reads all their output and produces a recommended number + confidence + rationale. One pass, no loop, no debate.

**Key insight from the data (know this):** Planners at Alpine are right 71% of the time when they *raise* a forecast, but only 34% when they *cut* it. Downward overrides mostly destroy accuracy. Your agents and reconciler should gently surface this pattern when relevant.

---

## The interface everyone uses (import from `compass.contracts`)

```python
from compass.contracts import DecisionContext, Signal, MemoryContext, ReconcilerOutput
```

Every agent takes a `DecisionContext` and returns `list[Signal]`. Empty list = agent found nothing relevant = agent stays silent. The frontend only shows agent cards when there is at least one signal.

---

## What you build

### 1. `compass/agents/demand.py`

Reads: `future_order_book`, `customers`, `returns`

```python
# compass/agents/demand.py
from compass.contracts import DecisionContext, Signal
from compass.loader import load_future_order_book, load_customers, load_returns
import pandas as pd

_order_book = None
_customers  = None
_returns    = None

def _load():
    global _order_book, _customers, _returns
    if _order_book is None:
        _order_book = load_future_order_book()
        _customers  = load_customers()
        _returns    = load_returns()

def get_signals(ctx: DecisionContext) -> list[Signal]:
    _load()
    signals = []

    # Signal 1: confirmed orders in this product × sales_org
    orders = _order_book[
        (_order_book['product_id']   == ctx.product_id) &
        (_order_book['sales_org_id'] == ctx.sales_org_id)
    ]
    confirmed = orders[orders['status'] == 'confirmed']
    if len(confirmed) > 0:
        total_confirmed = confirmed['confirmed_qty'].sum()
        machine_val = ctx.machine_value
        direction = "supports_override" if total_confirmed < machine_val else "contradicts_override"
        signals.append(Signal(
            agent_name    = "Demand",
            claim         = f"{len(confirmed)} confirmed orders in this org total "
                           f"{int(total_confirmed)} units "
                           f"({'below' if total_confirmed < machine_val else 'above'} machine forecast of {int(machine_val)}).",
            direction     = direction,
            magnitude     = min(abs(total_confirmed - machine_val) / max(machine_val, 1), 1.0),
            confidence    = 0.9,
            table         = "future_order_book",
            evidence_rows = confirmed[['customer_id','confirmed_qty','status',
                                       'requested_delivery_week']].head(5).to_dict('records'),
        ))

    # Signal 2: declining customers in this org
    declining = _customers[
        (_customers['sales_org_id'] == ctx.sales_org_id) &
        (_customers['is_declining']  == True)
    ]
    if len(declining) > 0:
        signals.append(Signal(
            agent_name    = "Demand",
            claim         = f"{len(declining)} customers in {ctx.sales_org_id} are flagged as declining.",
            direction     = "supports_override" if ctx.override_value < ctx.machine_value else "contradicts_override",
            magnitude     = 0.4,
            confidence    = 0.6,
            table         = "customers",
            evidence_rows = declining[['customer_id','customer_name','segment']].head(3).to_dict('records'),
        ))

    # Signal 3: recent returns for this product
    recent_returns = _returns[
        (_returns['product_id']   == ctx.product_id) &
        (_returns['sales_org_id'] == ctx.sales_org_id)
    ].tail(10)
    if len(recent_returns) > 0:
        total_return_qty = recent_returns['return_qty'].sum()
        signals.append(Signal(
            agent_name    = "Demand",
            claim         = f"Recent {len(recent_returns)} return events for this SKU in this org: "
                           f"{int(total_return_qty)} units returned. "
                           f"Top reason: {recent_returns['return_reason'].mode().iloc[0] if len(recent_returns) > 0 else 'n/a'}.",
            direction     = "supports_override" if ctx.override_value < ctx.machine_value else "neutral",
            magnitude     = 0.3,
            confidence    = 0.5,
            table         = "returns",
            evidence_rows = recent_returns[['return_reason','return_qty','date']].head(3).to_dict('records'),
        ))

    return signals
```

---

### 2. `compass/agents/supply.py`

Reads: `stock_on_hand`, `purchase_orders`, `suppliers`, `production_data`

```python
# compass/agents/supply.py
from compass.contracts import DecisionContext, Signal
from compass.loader import load_stock_on_hand, load_purchase_orders, load_suppliers, load_production_data
import pandas as pd

_stock = _pos = _suppliers = _production = None

def _load():
    global _stock, _pos, _suppliers, _production
    if _stock is None:
        _stock      = load_stock_on_hand()
        _pos        = load_purchase_orders()
        _suppliers  = load_suppliers()
        _production = load_production_data()

def get_signals(ctx: DecisionContext) -> list[Signal]:
    _load()
    signals = []

    # Signal 1: stock cover weeks
    stock = _stock[
        (_stock['product_id']   == ctx.product_id) &
        (_stock['sales_org_id'] == ctx.sales_org_id)
    ].sort_values('date').tail(1)

    if len(stock) > 0:
        stock_qty   = stock.iloc[0]['stock_qty_bu']
        weekly_rate = ctx.machine_value / 4.0  # monthly forecast / 4 weeks
        cover_weeks = stock_qty / weekly_rate if weekly_rate > 0 else 0
        if cover_weeks < 3:
            signals.append(Signal(
                agent_name    = "Supply / Ops",
                claim         = f"Stock cover is only {cover_weeks:.1f} weeks at current demand rate. "
                               f"A downward override risks a stockout if demand comes in higher.",
                direction     = "contradicts_override" if ctx.override_value < ctx.machine_value else "neutral",
                magnitude     = max(0.0, (3 - cover_weeks) / 3),
                confidence    = 0.85,
                table         = "stock_on_hand",
                evidence_rows = stock[['date','stock_qty_bu','stock_value_eur']].to_dict('records'),
            ))

    # Signal 2: supplier OTIF
    supplier_pos = _pos[_pos['product_id'] == ctx.product_id]
    if len(supplier_pos) > 0:
        supplier_pos = supplier_pos.copy()
        supplier_pos['on_time'] = (
            supplier_pos['actual_delivery_week'] <= supplier_pos['expected_delivery_week']
        )
        otif = supplier_pos['on_time'].mean()
        if otif < 0.8:
            signals.append(Signal(
                agent_name    = "Supply / Ops",
                claim         = f"Supplier OTIF for this SKU is {otif:.0%}. "
                               f"Late deliveries are common — raising the forecast may not be fulfillable.",
                direction     = "contradicts_override" if ctx.override_value > ctx.machine_value else "neutral",
                magnitude     = (0.8 - otif),
                confidence    = 0.75,
                table         = "purchase_orders",
                evidence_rows = supplier_pos[['po_id','expected_delivery_week',
                                              'actual_delivery_week','on_time']].tail(5).to_dict('records'),
            ))

    return signals
```

---

### 3. `compass/agents/finance.py`

Reads: `business_plan`, `cost_breakdown`, `tariff_reference`

```python
# compass/agents/finance.py
from compass.contracts import DecisionContext, Signal
from compass.loader import load_business_plan, load_cost_breakdown, load_tariff_reference
import pandas as pd

_plan = _costs = _tariffs = None

def _load():
    global _plan, _costs, _tariffs
    if _plan is None:
        _plan    = load_business_plan()
        _costs   = load_cost_breakdown()
        _tariffs = load_tariff_reference()

def get_signals(ctx: DecisionContext) -> list[Signal]:
    _load()
    signals = []

    # Signal 1: how far is the override from the business plan?
    plan_rows = _plan[
        (_plan['business_unit'] == ctx.business_unit) &
        (_plan['sales_org_id']  == ctx.sales_org_id)
    ]
    # get latest cutoff
    if len(plan_rows) > 0:
        latest_cut   = plan_rows['cutoff_date'].max()
        latest_plan  = plan_rows[plan_rows['cutoff_date'] == latest_cut]
        plan_revenue = latest_plan['planned_revenue_eur'].sum()
        # rough revenue delta from the override
        price_approx  = 10.0  # rough EUR/unit — better: look up from price_changes
        override_delta_rev = (ctx.override_value - ctx.machine_value) * price_approx
        if abs(override_delta_rev) > plan_revenue * 0.05:
            direction = "contradicts_override"
            signals.append(Signal(
                agent_name    = "Finance / Margin",
                claim         = f"This override shifts estimated revenue by ~€{override_delta_rev:,.0f}. "
                               f"Business plan for this BU × org is €{plan_revenue:,.0f}/month.",
                direction     = direction,
                magnitude     = min(abs(override_delta_rev / plan_revenue), 1.0),
                confidence    = 0.5,  # rough estimate without exact price
                table         = "business_plan",
                evidence_rows = latest_plan[['period_month','planned_revenue_eur',
                                             'planned_gross_margin_eur']].head(3).to_dict('records'),
            ))

    # Signal 2: tariff surcharge trend
    tariff_rows = _tariffs[
        _tariffs['product_category'] == ctx.category
    ].sort_values('effective_date')
    if len(tariff_rows) >= 2:
        latest  = tariff_rows.iloc[-1]['tariff_rate_pct']
        prev    = tariff_rows.iloc[-2]['tariff_rate_pct']
        if latest > prev:
            signals.append(Signal(
                agent_name    = "Finance / Margin",
                claim         = f"Tariff rate for {ctx.category} rose from {prev:.1%} to {latest:.1%} "
                               f"as of {tariff_rows.iloc[-1]['effective_date'].date()}. "
                               f"Cost pressure is increasing.",
                direction     = "neutral",
                magnitude     = (latest - prev),
                confidence    = 0.95,
                table         = "tariff_reference",
                evidence_rows = tariff_rows.tail(3)[['sourcing_region','tariff_rate_pct',
                                                      'effective_date']].to_dict('records'),
            ))

    return signals
```

---

### 4. `compass/agents/commercial.py`

Reads: `marketing_spends`, `price_changes`

```python
# compass/agents/commercial.py
from compass.contracts import DecisionContext, Signal
from compass.loader import load_marketing_spends, load_price_changes
import pandas as pd

_mkt = _prices = None

def _load():
    global _mkt, _prices
    if _mkt is None:
        _mkt    = load_marketing_spends()
        _prices = load_price_changes()

def get_signals(ctx: DecisionContext) -> list[Signal]:
    _load()
    signals = []

    # Signal 1: active campaigns for this category × org
    campaigns = _mkt[
        (_mkt['category']     == ctx.category) &
        (_mkt['sales_org_id'] == ctx.sales_org_id)
    ].sort_values('period_month').tail(3)

    if len(campaigns) > 0:
        total_spend = campaigns['spend_eur'].sum()
        signals.append(Signal(
            agent_name    = "Commercial / Market",
            claim         = f"{len(campaigns)} recent campaigns for {ctx.category} in this org. "
                           f"Total spend: €{total_spend:,.0f}. "
                           f"Campaign types: {', '.join(campaigns['campaign_type'].unique())}.",
            direction     = "supports_override" if ctx.override_value > ctx.machine_value else "neutral",
            magnitude     = 0.4,
            confidence    = 0.6,
            table         = "marketing_spends",
            evidence_rows = campaigns[['campaign_id','campaign_type','period_month',
                                       'spend_eur']].to_dict('records'),
        ))

    # Signal 2: recent price change for this product
    price_hist = _prices[
        (_prices['product_id']   == ctx.product_id) &
        (_prices['sales_org_id'] == ctx.sales_org_id) &
        (_prices['channel_id']   == ctx.channel_id)
    ].sort_values('effective_month')

    if len(price_hist) >= 2:
        latest = price_hist.iloc[-1]['price_eur_per_pcs']
        prev   = price_hist.iloc[-2]['price_eur_per_pcs']
        if abs(latest - prev) / max(prev, 1) > 0.02:
            direction_word = "increased" if latest > prev else "decreased"
            signals.append(Signal(
                agent_name    = "Commercial / Market",
                claim         = f"List price {direction_word} from €{prev:.2f} to €{latest:.2f} "
                               f"({(latest/prev-1):+.1%}) on {price_hist.iloc[-1]['effective_month'].date()}.",
                direction     = "supports_override" if latest < prev else "contradicts_override",
                magnitude     = abs(latest - prev) / max(prev, 1),
                confidence    = 0.9,
                table         = "price_changes",
                evidence_rows = price_hist.tail(3)[['effective_month',
                                                     'price_eur_per_pcs']].to_dict('records'),
            ))

    return signals
```

---

### 5. `compass/router.py` — relevance gate

Not all agents run on every decision. This keeps cost down.

```python
# compass/router.py
from compass.contracts import DecisionContext

def get_relevant_agents(ctx: DecisionContext) -> list[str]:
    """
    Return the names of agents that should run for this decision.
    Always run Demand + Memory. Others gate by context.
    """
    agents = ["demand", "memory"]

    # Supply always runs — stock and OTIF are always relevant
    agents.append("supply")

    # Finance runs if the override is large (>10%)
    override_pct = abs(ctx.override_value - ctx.machine_value) / max(ctx.machine_value, 1)
    if override_pct > 0.10:
        agents.append("finance")

    # Commercial runs if there's a reason text suggesting a market event
    market_keywords = ["promot", "campaign", "price", "competitor", "launch",
                       "event", "trade", "sale", "discount"]
    if any(kw in ctx.reason_text.lower() for kw in market_keywords):
        agents.append("commercial")

    return agents
```

---

### 6. `compass/reconciler.py` — Claude Opus, single pass

```python
# compass/reconciler.py
import anthropic
import json
from compass.contracts import DecisionContext, Signal, MemoryContext, ReconcilerOutput

client = anthropic.Anthropic()

def reconcile(
    ctx: DecisionContext,
    signals: list[Signal],
    memory: MemoryContext
) -> ReconcilerOutput:
    """
    Single Opus call. Reads all signals + memory, returns recommendation.
    This is the ONLY place Opus is called. Keep it to one call.
    """

    signals_text = "\n".join([
        f"- [{s.agent_name}] {s.claim} "
        f"(direction={s.direction}, confidence={s.confidence:.0%}, table={s.table})"
        for s in signals
    ]) or "No agent signals found."

    memory_text = _format_memory(ctx, memory)

    prompt = f"""You are the reconciler in a demand-planning override copilot called Compass.

CONTEXT:
- Product: {ctx.product_id} | Sales Org: {ctx.sales_org_id} | Category: {ctx.category}
- Machine forecast: {ctx.machine_value} units
- Planner override: {ctx.override_value} units ({(ctx.override_value/max(ctx.machine_value,1)-1):+.1%})
- Planner reason: "{ctx.reason_text}"
- Classified as: {ctx.reason_class}

EVIDENCE FROM AGENTS:
{signals_text}

MEMORY & TRACK RECORD:
{memory_text}

TASK:
1. Weigh the evidence. Which signals support or contradict the override?
2. Recommend a number (can be the machine value, override value, or something in between).
3. Give a confidence level: low / medium / high.
4. Write 2-4 plain-English sentences explaining the recommendation.

RULES:
- You are advising, not deciding. The human always decides.
- If evidence is genuinely mixed, say so and recommend staying close to the machine value.
- Never invent data. Only reference what is in the signals above.
- Be direct. No hedging beyond what the confidence level already communicates.

OUTPUT FORMAT (JSON only, no extra text):
{{
  "recommended_value": <number>,
  "confidence_level": "low|medium|high",
  "rationale": "<2-4 sentences>"
}}"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # safe fallback
        data = {
            "recommended_value": ctx.machine_value,
            "confidence_level":  "low",
            "rationale":         "Could not synthesize evidence. Defaulting to machine forecast."
        }

    return ReconcilerOutput(
        recommended_value = float(data["recommended_value"]),
        confidence_level  = data["confidence_level"],
        rationale         = data["rationale"],
        signals_used      = signals,
        memory_context    = memory,
    )


def _format_memory(ctx: DecisionContext, memory: MemoryContext) -> str:
    lines = []

    if memory.planner_fva_history:
        h = memory.planner_fva_history
        lines.append(
            f"Planner track record: {h.get('n_decisions',0)} past decisions, "
            f"{h.get('pct_helpful',0):.0%} improved accuracy (avg FVA {h.get('avg_fva',0):+.1f} units)."
        )
    else:
        lines.append("Planner track record: no history yet (cold start).")

    if memory.reason_type_history:
        r = memory.reason_type_history
        lines.append(
            f"Reason type '{ctx.reason_class}': {r.get('n_decisions',0)} past events, "
            f"avg override was {r.get('avg_override_pct',0):+.0%}, "
            f"avg realized was {r.get('avg_realized_pct',0):+.0%}."
        )

    if memory.similar_past_events:
        lines.append(f"Similar past events ({len(memory.similar_past_events)} found):")
        for e in memory.similar_past_events[:3]:
            fva = e.get('fva')
            impact = f"FVA={fva:+.0f}" if fva is not None else "not yet scored"
            lines.append(f"  - \"{e['reason_text'][:60]}...\" → {impact}")

    if memory.calibrated_suggestion:
        lines.append(
            f"History-calibrated suggestion: {memory.calibrated_suggestion} units "
            f"(confidence: {memory.confidence_level})."
        )

    return "\n".join(lines) if lines else "No memory context available."
```

---

### 7. `compass/pipeline.py` — the single function P4 calls

```python
# compass/pipeline.py
import uuid
from datetime import date
from compass.contracts import DecisionContext, DecisionRecord, ReconcilerOutput
from compass.classifier import classify_reason
from compass.router     import get_relevant_agents
from compass.memory     import get_memory_context, record_event
from compass.reconciler import reconcile
from compass.store      import write_decision
import compass.agents.demand     as demand_agent
import compass.agents.supply     as supply_agent
import compass.agents.finance    as finance_agent
import compass.agents.commercial as commercial_agent

AGENT_MAP = {
    "demand":     demand_agent,
    "supply":     supply_agent,
    "finance":    finance_agent,
    "commercial": commercial_agent,
}

def run_pipeline(ctx: DecisionContext) -> ReconcilerOutput:
    """
    Full pipeline: classify → gate → agents → memory → reconciler.
    Returns ReconcilerOutput for the frontend to display.
    Does NOT write the decision — that happens when the planner commits.
    """
    # 1. Classify reason
    ctx.reason_class = classify_reason(ctx.reason_text)

    # 2. Gate: which agents are relevant?
    relevant = get_relevant_agents(ctx)

    # 3. Run relevant agents (in practice: parallel with threading if time allows)
    all_signals = []
    for name in relevant:
        if name == "memory":
            continue  # handled separately below
        agent = AGENT_MAP.get(name)
        if agent:
            signals = agent.get_signals(ctx)
            all_signals.extend(signals)

    # 4. Memory/Critic (always runs)
    memory = get_memory_context(ctx)

    # 5. Reconcile
    output = reconcile(ctx, all_signals, memory)
    return output


def commit_decision(ctx: DecisionContext, final_value: float,
                    reconciler_output: ReconcilerOutput) -> str:
    """
    Called when the planner confirms their final number.
    Writes to DB and triggers event fan-out.
    Returns decision_id.
    """
    decision_id = str(uuid.uuid4())

    record = DecisionRecord(
        decision_id      = decision_id,
        cutoff_date      = ctx.cutoff_date,
        item_id          = f"{ctx.product_id}__{ctx.sales_org_id}__{ctx.channel_id}",
        machine_value    = ctx.machine_value,
        override_value   = ctx.override_value,
        reconciler_value = reconciler_output.recommended_value,
        final_value      = final_value,
        reason_text      = ctx.reason_text,
        reason_class     = ctx.reason_class,
        decision_maker   = ctx.decision_maker,
        context_json     = {
            "signals": [s.__dict__ for s in reconciler_output.signals_used],
            "memory":  reconciler_output.memory_context.__dict__,
        },
    )
    write_decision(record)
    record_event(decision_id, ctx)
    return decision_id
```

---

## Install

```bash
pip install anthropic pandas
```

Set your API key: `export ANTHROPIC_API_KEY=sk-ant-...`

---

## CRITICAL things you must do

1. **The reconciler must have a JSON fallback.** Opus occasionally does not return clean JSON. The `try/except json.JSONDecodeError` block in `reconciler.py` is your safety net — if the fallback triggers during the demo it returns the machine value with "low" confidence. Test this by temporarily breaking the prompt and verifying the fallback fires.

2. **Never call Opus more than once per decision.** The router gates the agents to control cost. The reconciler is one call that sees everything. If you add a second Opus call anywhere, the demo costs 2x and takes 2x as long.

3. **All agent data is loaded once and cached.** The `_load()` pattern with module-level variables means the first call reads from parquet, subsequent calls use memory. Do NOT reload the dataframe on every call — it takes 3–5 seconds each time and will make the demo feel broken.

4. **`run_pipeline` does NOT write to the database.** `commit_decision` does. This matters because the planner might look at the recommendation and decide NOT to override. Only write when they confirm. Tell P4 to call `run_pipeline` on "analyse" and `commit_decision` on "confirm".

5. **Test with a product that has real data.** Use `CP-0271` in `SO04` with channel `CH01` — this was the sample from the FVA analysis. Don't test with a random product that has no order book or stock data or the agents will all return empty signals and the demo looks dead.

## What you expose to the rest of the team

| Function | Who uses it |
|----------|-------------|
| `compass.pipeline.run_pipeline(ctx)` | P4 (on "Analyse" button) |
| `compass.pipeline.commit_decision(ctx, final_value, output)` | P4 (on "Confirm" button) |

## Git

```bash
git checkout your-branch
git add compass/agents/ compass/reconciler.py compass/router.py compass/pipeline.py
git commit -m "P3: 4 grounded agents, router, Opus reconciler, pipeline"
git push origin your-branch
```
