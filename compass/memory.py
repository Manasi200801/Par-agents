"""
Memory / Critic agent and event write-back.
This is the fifth agent in the panel — it reads scored history and
similar past events, then returns a MemoryContext for the reconciler.
"""

import json
import uuid

from compass.contracts import DecisionContext, DecisionRecord, MemoryContext
from compass.store import (
    get_conn,
    get_track_record_by_reason,
    get_track_record_by_planner,
    get_affected_skus,
    write_decision,
)
from compass.classifier import classify_reason
from compass.embeddings import embed_text, find_similar_events

_MIN_EVENTS = 3  # minimum scored events before we issue a calibrated suggestion


# ── Agent function ─────────────────────────────────────────────────────────────

def get_memory_context(ctx: DecisionContext) -> MemoryContext:
    """
    The Memory/Critic agent.
    Called by P3's pipeline alongside the other four agents.
    Returns MemoryContext with scored history, similar events, and an
    optional calibrated suggestion (None on cold start).
    """
    reason_class = ctx.reason_class or classify_reason(ctx.reason_text)

    planner_history = get_track_record_by_planner(ctx.decision_maker)
    reason_history  = get_track_record_by_reason(reason_class)
    similar_events  = find_similar_events(ctx.reason_text, top_k=5)

    return MemoryContext(
        planner_fva_history   = planner_history,
        reason_type_history   = reason_history,
        similar_past_events   = similar_events,
        calibrated_suggestion = _calibrate(ctx, reason_history),
        confidence_level      = _confidence(reason_history, similar_events),
    )


def _calibrate(ctx: DecisionContext, reason_history: dict) -> float | None:
    """
    Return a history-calibrated number if we have enough past events.
    Uses the average realized outcome percentage for this reason type,
    applied to the machine value. Returns None on cold start.
    """
    if not reason_history:
        return None
    if reason_history.get("n_decisions", 0) < _MIN_EVENTS:
        return None
    avg_realized_pct = reason_history.get("avg_realized_pct") or 0.0
    return round(ctx.machine_value * (1 + avg_realized_pct), 1)


def _confidence(reason_history: dict, similar_events: list) -> str:
    n = reason_history.get("n_decisions", 0) if reason_history else 0
    if n >= 10 or len(similar_events) >= 5:
        return "high"
    if n >= _MIN_EVENTS or len(similar_events) >= 2:
        return "medium"
    return "low"


# ── Write-back (called by P3 after planner commits) ───────────────────────────

def record_event(decision_id: str, ctx: DecisionContext) -> str:
    """
    After the planner commits their final number:
      1. Classify reason (if not already classified)
      2. Embed the reason text
      3. Insert into events table
      4. Fan out to all SKUs in same category × region (event_sku table)

    IMPORTANT: call this AFTER write_decision() — event references decision_id.
    Returns the new event_id.
    """
    reason_class = ctx.reason_class or classify_reason(ctx.reason_text)
    embedding    = embed_text(ctx.reason_text)
    event_id     = str(uuid.uuid4())

    # Fetch before opening the write connection — DuckDB disallows mixing
    # read-only and read-write connections to the same file simultaneously.
    affected_skus = get_affected_skus(ctx.category, ctx.region_group)

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO events
                (event_id, decision_id, reason_class, reason_text, reason_embedding)
            VALUES (?, ?, ?, ?, ?)
            """,
            [event_id, decision_id, reason_class, ctx.reason_text, json.dumps(embedding)],
        )

        for sku in affected_skus:
            conn.execute(
                "INSERT INTO event_sku (event_id, product_id, sales_org_id, channel_id) VALUES (?,?,?,?)",
                [event_id, sku["product_id"], sku["sales_org_id"], sku["channel_id"]],
            )
    finally:
        conn.close()

    return event_id


# ── Demo seeding (called by scripts/inject_events.py) ─────────────────────────

def seed_demo_events(events: list) -> None:
    """
    Inject pre-built historical events so memory has something to say on day 1.

    Each dict in events must have:
        decision_id, cutoff_date, product_id, sales_org_id, channel_id,
        decision_maker, reason_text, reason_class,
        machine_value, override_value, final_value,
        outcome (float), fva (float)

    Optional: reconciler_value (defaults to final_value)
    """
    for e in events:
        record = DecisionRecord(
            decision_id      = e["decision_id"],
            cutoff_date      = e["cutoff_date"],
            item_id          = f"{e['product_id']}__{e['sales_org_id']}__{e['channel_id']}",
            machine_value    = e["machine_value"],
            override_value   = e.get("override_value", e["final_value"]),
            reconciler_value = e.get("reconciler_value", e["final_value"]),
            final_value      = e["final_value"],
            reason_text      = e["reason_text"],
            reason_class     = e["reason_class"],
            decision_maker   = e["decision_maker"],
            context_json     = {},
            outcome          = e.get("outcome"),
            machine_error    = abs(e["outcome"] - e["machine_value"]) if e.get("outcome") else None,
            override_error   = abs(e["outcome"] - e["final_value"])   if e.get("outcome") else None,
            fva              = e.get("fva"),
        )
        write_decision(record)

        embedding = embed_text(e["reason_text"])
        event_id  = str(uuid.uuid4())
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                [
                    event_id, e["decision_id"], e["reason_class"],
                    e["reason_text"], json.dumps(embedding), e.get("fva"),
                ],
            )
        finally:
            conn.close()
