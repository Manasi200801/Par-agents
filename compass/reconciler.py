"""
Reconciler — single Claude Opus call per decision.
Reads all agent signals + memory context, returns a recommended number + rationale.
This is the ONLY place Opus is called. Never add a second call.
"""

import json
import anthropic
from dotenv import load_dotenv
from compass.contracts import DecisionContext, Signal, MemoryContext, ReconcilerOutput

load_dotenv()
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env or environment


def reconcile(
    ctx: DecisionContext,
    signals: list,
    memory: MemoryContext,
) -> ReconcilerOutput:
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
- Planner override: {ctx.override_value} units ({(ctx.override_value / max(ctx.machine_value, 1) - 1):+.1%})
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

    try:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        data = {
            "recommended_value": ctx.machine_value,
            "confidence_level":  "low",
            "rationale":         (
                "Could not synthesize evidence. Defaulting to machine forecast. "
                "Review the agent signals manually before deciding."
            ),
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
            f"Planner track record ({ctx.decision_maker}): "
            f"{h.get('n_decisions', 0)} past decisions, "
            f"{h.get('pct_helpful', 0):.0%} improved accuracy "
            f"(avg FVA {h.get('avg_fva', 0):+.1f} units)."
        )
    else:
        lines.append(f"Planner track record ({ctx.decision_maker}): no history yet.")

    if memory.reason_type_history:
        r = memory.reason_type_history
        lines.append(
            f"Reason type '{ctx.reason_class}': {r.get('n_decisions', 0)} past events, "
            f"avg override was {r.get('avg_override_pct', 0):+.0%}, "
            f"avg realized was {r.get('avg_realized_pct', 0):+.0%}, "
            f"{r.get('pct_helpful', 0):.0%} were helpful."
        )

    if memory.similar_past_events:
        lines.append(f"Similar past events ({len(memory.similar_past_events)} found):")
        for e in memory.similar_past_events[:3]:
            fva = e.get('fva')
            impact = f"FVA={fva:+.0f}" if fva is not None else "not yet scored"
            text = e.get('reason_text', '')[:60]
            lines.append(f"  - \"{text}...\" → {impact}")

    if memory.calibrated_suggestion is not None:
        lines.append(
            f"History-calibrated suggestion: {memory.calibrated_suggestion} units "
            f"(confidence: {memory.confidence_level})."
        )

    return "\n".join(lines) if lines else "No memory context available."
