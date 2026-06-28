"""
Embeddings and vector recall for similar past override events.
Uses sentence-transformers (local, free, no API cost).
Pre-download the model before the hackathon:
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
"""

import json
import numpy as np
import duckdb
from sentence_transformers import SentenceTransformer

from compass.store import DB_PATH

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list:
    """Generate a 384-dim embedding vector for a reason text string."""
    return _get_model().encode(text).tolist()


def cosine_similarity(a: list, b: list) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / (denom + 1e-9))


def find_similar_events(reason_text: str, top_k: int = 5) -> list:
    """
    Find the top_k most semantically similar past override events.

    Returns a list of dicts:
        {event_id, reason_text, reason_class, realized_impact, fva,
         similarity, override_pct, outcome}

    Returns [] gracefully on cold start (no scored events yet).
    """
    query_vec = embed_text(reason_text)

    # read_only=True avoids write conflicts if another connection is open
    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        rows = conn.execute("""
            SELECT e.event_id, e.reason_text, e.reason_class,
                   e.reason_embedding, e.realized_impact,
                   d.fva, d.override_value, d.machine_value, d.outcome
            FROM events e
            JOIN decisions d ON e.decision_id = d.decision_id
            WHERE e.reason_embedding IS NOT NULL
              AND d.fva IS NOT NULL
        """).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    results = []
    for row in rows:
        event_id, r_text, r_class, r_emb_json, realized_impact, fva, ov, mv, outcome = row
        if not r_emb_json:
            continue
        try:
            r_emb = json.loads(r_emb_json)
        except (json.JSONDecodeError, TypeError):
            continue
        sim = cosine_similarity(query_vec, r_emb)
        results.append({
            "event_id":        event_id,
            "reason_text":     r_text,
            "reason_class":    r_class,
            "realized_impact": realized_impact,
            "fva":             fva,
            "similarity":      round(sim, 4),
            "override_pct":    round(ov / mv - 1, 4) if mv else None,
            "outcome":         outcome,
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]
