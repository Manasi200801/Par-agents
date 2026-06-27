"""
Compass HTTP server — FastAPI wrapper around compass/pipeline.py
Exposes two endpoints the Next.js frontend calls:
  POST /analyze  → run_pipeline() — analysis only, no DB write
  POST /commit   → commit_decision() — writes to DB, returns decision_id

Run locally:
  pip install fastapi uvicorn
  uvicorn server:app --reload --port 8000

Set PIPELINE_URL=http://localhost:8000 in web/.env.local to connect the UI.

Deploy on Railway / Render: point start command at this file.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import datetime
import dataclasses
import json
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from compass.contracts import (
    DecisionContext,
    ReconcilerOutput,
    MemoryContext,
    Signal,
)
from compass.pipeline import run_pipeline, commit_decision
from compass.store import init_db

app = FastAPI(title="Compass Pipeline API")


@app.on_event("startup")
def startup():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ── Pydantic request models ─────────────────────────────────────────────────

class ContextIn(BaseModel):
    product_id: str
    sales_org_id: str
    channel_id: str
    cutoff_date: str          # "YYYY-MM-DD" string from the frontend
    machine_value: float
    override_value: float
    reason_text: str
    reason_class: Optional[str] = None
    business_unit: str
    category: str
    region_group: str
    decision_maker: str


class AnalyzeRequest(BaseModel):
    context: ContextIn


class CommitRequest(BaseModel):
    context: ContextIn
    final_value: float
    reconciler_output: dict   # the JSON that /analyze returned, passed back as-is


# ── Serialisation helpers ────────────────────────────────────────────────────

def _json_default(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return str(obj)
    raise TypeError(f"Not serialisable: {type(obj)}")


def _to_json(dataclass_obj) -> dict:
    """Convert a (nested) dataclass to a plain JSON-safe dict."""
    return json.loads(
        json.dumps(dataclasses.asdict(dataclass_obj), default=_json_default)
    )


def _ctx_from(req: ContextIn) -> DecisionContext:
    return DecisionContext(
        product_id=req.product_id,
        sales_org_id=req.sales_org_id,
        channel_id=req.channel_id,
        cutoff_date=datetime.date.fromisoformat(req.cutoff_date),
        machine_value=req.machine_value,
        override_value=req.override_value,
        reason_text=req.reason_text,
        reason_class=req.reason_class,
        business_unit=req.business_unit,
        category=req.category,
        region_group=req.region_group,
        decision_maker=req.decision_maker,
    )


def _reconciler_from(d: dict) -> ReconcilerOutput:
    """Reconstruct a ReconcilerOutput dataclass from the dict /analyze returned."""
    signals = [Signal(**s) for s in d.get("signals_used", [])]
    mem_raw = d.get("memory_context", {})
    memory = MemoryContext(
        planner_fva_history=mem_raw.get("planner_fva_history", {}),
        reason_type_history=mem_raw.get("reason_type_history", {}),
        similar_past_events=mem_raw.get("similar_past_events", []),
        calibrated_suggestion=mem_raw.get("calibrated_suggestion"),
        confidence_level=mem_raw.get("confidence_level", "low"),
    )
    return ReconcilerOutput(
        recommended_value=d["recommended_value"],
        confidence_level=d["confidence_level"],
        rationale=d["rationale"],
        signals_used=signals,
        memory_context=memory,
    )


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """
    Run the full 5-agent + reconciler pipeline.
    Does NOT write to DB. Safe to call on every planner keystroke (though
    in practice the UI calls it once per "Check this forecast" click).
    """
    try:
        ctx = _ctx_from(req.context)
        output = run_pipeline(ctx)
        result = _to_json(output)
        result["_source"] = "pipeline"
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/commit")
def commit(req: CommitRequest):
    """
    Called when the planner confirms their final number.
    Writes decision to DB, triggers event fan-out in the knowledge graph.
    Returns a decision_id the UI can display as confirmation.
    """
    try:
        ctx = _ctx_from(req.context)
        reconciler_output = _reconciler_from(req.reconciler_output)
        decision_id = commit_decision(ctx, req.final_value, reconciler_output)
        return {"decision_id": decision_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
