"""
SHARED CONTRACTS — Everyone imports from this file.
Do not change without telling the whole team.
"""

from dataclasses import dataclass
from typing import Optional
import datetime


@dataclass
class DecisionContext:
    """Passed INTO every agent and the reconciler."""
    product_id: str
    sales_org_id: str
    channel_id: str
    cutoff_date: datetime.date
    machine_value: float        # stat_forecast qty
    override_value: float       # what planner is proposing
    reason_text: str            # planner's free-text reason
    reason_class: Optional[str] # filled after Haiku classifier runs
    business_unit: str
    category: str
    region_group: str
    decision_maker: str         # planner id / name


@dataclass
class Signal:
    """What every agent returns. Empty list = agent stays silent."""
    agent_name: str
    claim: str                  # one plain-English sentence
    direction: str              # "supports_override" | "contradicts_override" | "neutral"
    magnitude: float            # 0.0 – 1.0
    confidence: float           # 0.0 – 1.0
    table: str                  # which source table was read
    evidence_rows: list         # actual rows from the table (list of dicts)


@dataclass
class MemoryContext:
    """What the Memory/Critic agent returns."""
    planner_fva_history: dict           # avg_fva, n_decisions, pct_helpful
    reason_type_history: dict           # avg_fva, avg_override_pct, avg_realized_pct
    similar_past_events: list           # list of past event dicts
    calibrated_suggestion: Optional[float]
    confidence_level: str               # "low" | "medium" | "high"


@dataclass
class ReconcilerOutput:
    """What the Reconciler returns to the frontend."""
    recommended_value: float
    confidence_level: str       # "low" | "medium" | "high"
    rationale: str              # plain English, 2-4 sentences
    signals_used: list          # list of Signal objects
    memory_context: MemoryContext


@dataclass
class DecisionRecord:
    """Written to the decisions table after planner commits."""
    decision_id: str
    cutoff_date: datetime.date
    item_id: str                # f"{product_id}__{sales_org_id}__{channel_id}"
    machine_value: float
    override_value: float
    reconciler_value: float
    final_value: float
    reason_text: str
    reason_class: str
    decision_maker: str
    context_json: dict
    outcome: Optional[float] = None
    machine_error: Optional[float] = None
    override_error: Optional[float] = None
    fva: Optional[float] = None
