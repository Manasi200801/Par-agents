"""
Pipeline — the single entry point P4 calls.
run_pipeline()   → analysis only, no DB write
commit_decision() → writes to DB + triggers event fan-out
"""

import uuid
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
    Full analysis pipeline. Does NOT write to DB.
    Call this on the "Analyse" button.
    """
    # 1. Classify reason
    ctx.reason_class = classify_reason(ctx.reason_text)

    # 2. Gate: which agents are relevant?
    relevant = get_relevant_agents(ctx)

    # 3. Run evidence agents (memory handled separately)
    all_signals = []
    for name in relevant:
        if name == "memory":
            continue
        agent = AGENT_MAP.get(name)
        if agent:
            try:
                signals = agent.get_signals(ctx)
                all_signals.extend(signals)
            except Exception as e:
                print(f"[{name} agent] failed: {e}")

    # 4. Memory / Critic agent (always runs)
    memory = get_memory_context(ctx)

    # 5. Reconcile (single Opus call)
    output = reconcile(ctx, all_signals, memory)
    return output


def commit_decision(
    ctx: DecisionContext,
    final_value: float,
    reconciler_output: ReconcilerOutput,
) -> str:
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
        reason_class     = ctx.reason_class or "other",
        decision_maker   = ctx.decision_maker,
        context_json     = {
            "signals": [s.__dict__ for s in reconciler_output.signals_used],
            "memory":  {
                k: v for k, v in reconciler_output.memory_context.__dict__.items()
                if k != "similar_past_events"
            },
        },
    )
    write_decision(record)
    record_event(decision_id, ctx)
    return decision_id
