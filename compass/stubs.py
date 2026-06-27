# compass/stubs.py
# Stub implementations of every function P4 needs.
# P3/P2/P1 replace these with real implementations.
# P4 imports from stubs.py until the real modules are ready,
# then swaps the import line.

from compass.contracts import (DecisionContext, Signal, MemoryContext,
                                ReconcilerOutput, DecisionRecord)
import uuid


def classify_reason_stub(reason_text: str) -> str:
    keywords = {
        "promot": "promotion", "campaign": "promotion", "sale": "promotion",
        "competitor": "competitor_exit", "rival": "competitor_exit",
        "stock": "channel_overstock", "overstock": "channel_overstock",
        "price": "price_change", "tariff": "macro_signal",
        "supply": "supply_constraint", "shortage": "supply_constraint",
    }
    for kw, cls in keywords.items():
        if kw in reason_text.lower():
            return cls
    return "other"


def run_pipeline_stub(ctx: DecisionContext) -> ReconcilerOutput:
    return ReconcilerOutput(
        recommended_value = round(ctx.machine_value * 0.95, 1),
        confidence_level  = "low",
        rationale         = (
            f"STUB — P3 not yet integrated. Based on historical data, "
            f"downward overrides at Alpine help only 34% of the time. "
            f"Recommend staying closer to the machine forecast of {ctx.machine_value:.0f}."
        ),
        signals_used      = [
            Signal(
                agent_name    = "Demand (stub)",
                claim         = "STUB: real agent not yet connected.",
                direction     = "neutral",
                magnitude     = 0.3,
                confidence    = 0.3,
                table         = "future_order_book",
                evidence_rows = [],
            )
        ],
        memory_context    = MemoryContext(
            planner_fva_history   = {},
            reason_type_history   = {},
            similar_past_events   = [],
            calibrated_suggestion = None,
            confidence_level      = "low",
        ),
    )


def commit_decision_stub(ctx: DecisionContext, final_value: float,
                         output: ReconcilerOutput) -> str:
    decision_id = str(uuid.uuid4())
    print(f"[STUB] Would save decision {decision_id}: "
          f"machine={ctx.machine_value}, override={ctx.override_value}, final={final_value}")
    return decision_id


def get_replay_chart_data_stub():
    import pandas as pd, numpy as np
    dates = pd.date_range("2024-05-01", periods=24, freq="MS")
    np.random.seed(42)
    return pd.DataFrame({
        "cutoff_date":  dates,
        "mae_machine":  np.random.uniform(1500, 2500, 24),
        "mae_planner":  np.random.uniform(1600, 2800, 24),
        "n_rows":       [5924] * 24,
        "pct_helped":   np.random.uniform(0.35, 0.55, 24),
    })
