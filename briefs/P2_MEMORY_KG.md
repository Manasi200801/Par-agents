# P2 — Memory & Knowledge Graph
**Branch: your own branch on https://github.com/Manasi200801/Par-agents.git**
**You own: `compass/memory.py`, `compass/classifier.py`, `compass/embeddings.py`**

---

## What Compass is (read this first)

Compass is a demand-planning override copilot. A machine forecasts sales. A human planner overrides it and types a reason. Five AI agents look at real data and evidence cards are produced. A reconciler synthesises everything and recommends a number. The human decides. The key insight from the data: **planners are right 71% of the time when they raise a forecast, but only 34% of the time when they cut it.** They have real intelligence when raising numbers — but their downward cuts are mostly reflexive habit.

Your job is the memory layer. You make the system learn over time. Without you, the system is a fancy calculator that resets every cycle. With you, it builds a track record, learns which reason types add value, and recalls similar past situations to calibrate the next override.

---

## What you build (3 files)

### 1. `compass/classifier.py` — Haiku reason classifier

Every time a planner types a reason ("competitor rumoured to be exiting DACH"), you call Claude Haiku to classify it into one of a fixed set of categories. This is what makes reasons learnable — without a taxonomy, every reason is unique and nothing aggregates.

```python
# compass/classifier.py
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment

TAXONOMY = [
    "promotion",           # campaign, sale, discount event
    "competitor_exit",     # rival closing, losing capacity, shutting down
    "competitor_entry",    # new rival entering the market
    "trade_show_event",    # industry event, conference, exhibition
    "channel_overstock",   # customer has too much stock, will order less
    "channel_understock",  # customer running low, urgent reorder expected
    "price_change",        # own price increase or decrease
    "supply_constraint",   # supplier issue, material shortage, delay
    "macro_signal",        # economic indicator, currency move, regulation, tariff
    "other",               # anything that doesn't fit above
]

SYSTEM_PROMPT = f"""You classify demand-planning override reasons into exactly one category.
Categories: {', '.join(TAXONOMY)}
Reply with ONLY the category name. No explanation. No punctuation."""

def classify_reason(reason_text: str) -> str:
    """
    Takes free-text reason from planner.
    Returns exactly one string from TAXONOMY.
    Uses Claude Haiku (cheap, fast).
    """
    if not reason_text or reason_text.strip() == "":
        return "other"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": reason_text}]
    )
    result = response.content[0].text.strip().lower().replace(" ", "_")
    # safety: if Haiku hallucinates a category not in list, fall back
    return result if result in TAXONOMY else "other"
```

**Why Haiku and not Opus?** This runs on every single override. Haiku costs ~100x less than Opus and is fast enough to not block the UI. The task is simple classification — Haiku handles it easily.

---

### 2. `compass/embeddings.py` — vector search for similar past events

When a new override comes in, you want to find similar past overrides so the Memory/Critic agent can say "here is what happened last time someone said something like this."

```python
# compass/embeddings.py
import anthropic
import numpy as np
import json
import duckdb
from compass.store import DB_PATH

client = anthropic.Anthropic()

def embed_text(text: str) -> list[float]:
    """Generate an embedding for a reason text string."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1,
        system="Respond with a single period.",
        messages=[{"role": "user", "content": text}]
    )
    # NOTE: Claude does not have a dedicated embeddings endpoint yet.
    # Use a lightweight local model instead:
    # pip install sentence-transformers
    # This avoids an extra API call and is faster.
    raise NotImplementedError("See below for the real implementation")


# REAL implementation using sentence-transformers (no extra API cost):
# pip install sentence-transformers
from sentence_transformers import SentenceTransformer

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")  # tiny, fast, good enough
    return _model

def embed_text(text: str) -> list[float]:
    """Generate a 384-dim embedding for reason text."""
    model = _get_model()
    return model.encode(text).tolist()

def cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

def find_similar_events(reason_text: str, top_k: int = 5) -> list[dict]:
    """
    Find the top_k most similar past override events by semantic similarity.
    Returns list of dicts: {reason_text, reason_class, realized_impact, fva, similarity}
    """
    query_embedding = embed_text(reason_text)

    conn = duckdb.connect(DB_PATH)
    rows = conn.execute("""
        SELECT e.event_id, e.reason_text, e.reason_class,
               e.reason_embedding, e.realized_impact,
               d.fva, d.override_value, d.machine_value, d.outcome
        FROM events e
        JOIN decisions d ON e.decision_id = d.decision_id
        WHERE e.reason_embedding IS NOT NULL
          AND d.fva IS NOT NULL
    """).fetchall()
    conn.close()

    if not rows:
        return []

    results = []
    for row in rows:
        event_id, r_text, r_class, r_emb_json, realized_impact, fva, ov, mv, outcome = row
        if r_emb_json is None:
            continue
        r_emb = json.loads(r_emb_json)
        sim = cosine_similarity(query_embedding, r_emb)
        results.append({
            "event_id":        event_id,
            "reason_text":     r_text,
            "reason_class":    r_class,
            "realized_impact": realized_impact,
            "fva":             fva,
            "similarity":      sim,
            "override_pct":    (ov / mv - 1) if mv else None,
            "outcome":         outcome,
        })

    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:top_k]
```

---

### 3. `compass/memory.py` — the Memory/Critic agent and event write-back

This is the fifth agent. It reads the track records from DuckDB and the similar past events from embeddings, and returns a `MemoryContext` object.

```python
# compass/memory.py
import uuid
import json
import duckdb
from compass.contracts import DecisionContext, MemoryContext, Signal
from compass.store import (DB_PATH, get_track_record_by_reason,
                            get_track_record_by_planner, get_affected_skus,
                            write_decision, get_conn)
from compass.classifier import classify_reason
from compass.embeddings import embed_text, find_similar_events

# ── Agent function (called by P3 alongside the other agents) ──────────────────

def get_memory_context(ctx: DecisionContext) -> MemoryContext:
    """
    The Memory/Critic agent.
    Returns MemoryContext — scored history + similar past events + calibrated suggestion.
    """
    reason_class = ctx.reason_class or classify_reason(ctx.reason_text)

    planner_history    = get_track_record_by_planner(ctx.decision_maker)
    reason_history     = get_track_record_by_reason(reason_class)
    similar_events     = find_similar_events(ctx.reason_text, top_k=5)

    calibrated_suggestion = _calibrate(ctx, reason_history, similar_events)
    confidence_level      = _confidence(reason_history, similar_events)

    return MemoryContext(
        planner_fva_history   = planner_history,
        reason_type_history   = reason_history,
        similar_past_events   = similar_events,
        calibrated_suggestion = calibrated_suggestion,
        confidence_level      = confidence_level,
    )


def _calibrate(ctx: DecisionContext, reason_history: dict,
               similar_events: list) -> float | None:
    """
    If we have enough history, suggest a number based on realized impact.
    Returns None if not enough data (cold start).
    """
    MIN_EVENTS = 3  # don't suggest a number until we've seen at least 3 similar events

    if reason_history and reason_history.get('n_decisions', 0) >= MIN_EVENTS:
        avg_realized_pct = reason_history.get('avg_realized_pct', 0)
        # Use realized pct on top of machine value as calibrated suggestion
        return round(ctx.machine_value * (1 + avg_realized_pct), 1)

    if len(similar_events) >= MIN_EVENTS:
        # use the average realized impact across similar events
        valid = [e for e in similar_events if e['fva'] is not None]
        if len(valid) >= MIN_EVENTS:
            avg_fva = sum(e['fva'] for e in valid) / len(valid)
            # FVA is machine_error - override_error; not directly a number, so just return None
            # and let the reconciler reason about it
            return None

    return None  # cold start — not enough data


def _confidence(reason_history: dict, similar_events: list) -> str:
    n = reason_history.get('n_decisions', 0) if reason_history else 0
    if n >= 10 or len(similar_events) >= 5:
        return "high"
    if n >= 3 or len(similar_events) >= 2:
        return "medium"
    return "low"


# ── Write-back function (called by P3 after planner commits) ──────────────────

def record_event(decision_id: str, ctx: DecisionContext):
    """
    After the planner commits their final number:
    1. Classify the reason (if not already done)
    2. Embed the reason text
    3. Insert into events table
    4. Fan out to affected SKUs in event_sku table
    """
    reason_class = ctx.reason_class or classify_reason(ctx.reason_text)
    embedding    = embed_text(ctx.reason_text)
    event_id     = str(uuid.uuid4())

    conn = get_conn()
    conn.execute("""
        INSERT INTO events (event_id, decision_id, reason_class, reason_text, reason_embedding)
        VALUES (?, ?, ?, ?, ?)
    """, [event_id, decision_id, reason_class, ctx.reason_text, json.dumps(embedding)])

    # Fan out: find all SKUs in the same category × region and write event_sku rows
    affected = get_affected_skus(ctx.category, ctx.region_group)
    for sku in affected:
        conn.execute("""
            INSERT INTO event_sku (event_id, product_id, sales_org_id)
            VALUES (?, ?, ?)
        """, [event_id, sku['product_id'], sku['sales_org_id']])

    conn.close()
    return event_id


# ── Seed function for demo (inject pre-built events so memory is non-empty) ───

def seed_demo_events(events: list[dict]):
    """
    Inject historical events for the demo so the memory layer has something to say.
    Each dict: {decision_id, reason_class, reason_text, realized_impact, fva,
                machine_value, final_value, outcome, decision_maker, cutoff_date,
                product_id, sales_org_id, channel_id}
    Called by P5's inject_events.py script.
    """
    from compass.contracts import DecisionRecord
    import datetime

    for e in events:
        # write a decision record
        record = DecisionRecord(
            decision_id      = e['decision_id'],
            cutoff_date      = e['cutoff_date'],
            item_id          = f"{e['product_id']}__{e['sales_org_id']}__{e['channel_id']}",
            machine_value    = e['machine_value'],
            override_value   = e.get('override_value', e['final_value']),
            reconciler_value = e.get('reconciler_value', e['final_value']),
            final_value      = e['final_value'],
            reason_text      = e['reason_text'],
            reason_class     = e['reason_class'],
            decision_maker   = e['decision_maker'],
            context_json     = {},
            outcome          = e.get('outcome'),
            machine_error    = abs(e['outcome'] - e['machine_value']) if e.get('outcome') else None,
            override_error   = abs(e['outcome'] - e['final_value'])   if e.get('outcome') else None,
            fva              = e.get('fva'),
        )
        write_decision(record)

        # write the event + embeddings + fan-out
        embedding = embed_text(e['reason_text'])
        event_id  = str(uuid.uuid4())
        conn = get_conn()
        conn.execute("""
            INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)
        """, [event_id, e['decision_id'], e['reason_class'],
              e['reason_text'], json.dumps(embedding), e.get('fva')])
        conn.close()
```

---

## Install

```bash
pip install anthropic sentence-transformers duckdb
```

The `sentence-transformers` library downloads `all-MiniLM-L6-v2` (~80MB) on first use. **Do this before the hackathon on your machine so you're not downloading during the demo.**

```python
from sentence_transformers import SentenceTransformer
SentenceTransformer("all-MiniLM-L6-v2")  # run this once to cache it
```

---

## CRITICAL things you must do

1. **The classifier must always return one of the 10 taxonomy strings.** Never let a hallucinated category reach the database — it poisons the track records. The fallback to `"other"` in `classify_reason()` is your safety net. Test it by passing nonsense text and verifying the output is always in `TAXONOMY`.

2. **Download `all-MiniLM-L6-v2` before the hackathon.** If you try to download it during the demo on the venue WiFi, it will fail or take 10 minutes. Cache it locally now.

3. **`find_similar_events` must return an empty list gracefully when the events table is empty** (cold start). Do not crash if there are no past events. The Memory agent says "no prior history found" and confidence is "low". That's fine.

4. **`record_event` must be called AFTER `write_decision`** because it references `decision_id` as a foreign key. Tell P3 this explicitly — the order matters.

5. **Test the fan-out** by calling `get_affected_skus('Bearings & Bushings', 'DACH')` and verifying you get a list of SKUs. If this returns empty, the hierarchy table wasn't seeded by P1. Chase P1.

6. **The seeded demo events (from P5's `inject_events.py`) must be loaded before the live demo.** Run `python scripts/inject_events.py` and verify `find_similar_events("competitor exiting German market")` returns at least 2 results.

## What you expose to the rest of the team

| Function | Who uses it |
|----------|-------------|
| `compass.classifier.classify_reason(text)` | P3 (before calling agents) |
| `compass.memory.get_memory_context(ctx)` | P3 (Memory/Critic agent call) |
| `compass.memory.record_event(decision_id, ctx)` | P3 (after planner commits) |
| `compass.memory.seed_demo_events(events)` | P5 (demo setup) |
| `compass.embeddings.find_similar_events(text)` | P3 (via memory.py, not directly) |

## Git

```bash
git checkout your-branch
git add compass/classifier.py compass/memory.py compass/embeddings.py
git commit -m "P2: reason classifier, embeddings, memory/critic agent, event write-back"
git push origin your-branch
```
