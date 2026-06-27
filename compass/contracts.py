"""
SHARED CONTRACTS - Everyone imports from this file.
P5 creates this file at Hour 0. No one changes it without telling the whole team.
Filename: compass/contracts.py
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
    machine_value: float
    override_value: float
    reason_text: str
    reason_class: Optional[str]
    business_unit: str
    category: str
    region_group: str
    decision_maker: str


@dataclass
class Signal:
    """What every agent returns. Empty list = agent stays silent."""
    agent_name: str
    claim: str
    direction: str
    magnitude: float
    confidence: float
    table: str
    evidence_rows: list


@dataclass
class MemoryContext:
    """What the Memory/Critic agent returns - separate type because it's richer."""
    planner_fva_history: dict
    reason_type_history: dict
    similar_past_events: list
    calibrated_suggestion: Optional[float]
    confidence_level: str


@dataclass
class ReconcilerOutput:
    """What the Reconciler returns to the frontend."""
    recommended_value: float
    confidence_level: str
    rationale: str
    signals_used: list
    memory_context: MemoryContext


@dataclass
class DecisionRecord:
    """Written to the decisions table after planner commits."""
    decision_id: str
    cutoff_date: datetime.date
    item_id: str
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
