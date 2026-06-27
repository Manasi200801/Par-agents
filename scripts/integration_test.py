# scripts/integration_test.py
# Run: python scripts/integration_test.py
# Requires: DB initialised + events injected + P3 pipeline built

import datetime
from compass.contracts import DecisionContext
from compass.pipeline import run_pipeline, commit_decision

ctx = DecisionContext(
    product_id     = "CP-0271",
    sales_org_id   = "SO04",
    channel_id     = "CH01",
    cutoff_date    = datetime.date(2025, 6, 1),
    machine_value  = 437.0,
    override_value = 360.0,
    reason_text    = "Competitor rumoured to be exiting the DACH market for bearings",
    reason_class   = None,
    business_unit  = "Consumer Products",
    category       = "Bearings & Bushings",
    region_group   = "DACH",
    decision_maker = "planner_anna",
)

print("Running pipeline...")
output = run_pipeline(ctx)
print(f"Reconciler recommends: {output.recommended_value} units")
print(f"Confidence: {output.confidence_level}")
print(f"Rationale: {output.rationale}")
print(f"Signals used: {len(output.signals_used)}")
print(f"Memory — similar events: {len(output.memory_context.similar_past_events)}")
print()
print("Committing decision (final = 390)...")
decision_id = commit_decision(ctx, 390.0, output)
print(f"Saved with ID: {decision_id}")
print("Integration test PASSED.")
