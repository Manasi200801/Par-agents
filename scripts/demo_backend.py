"""Small terminal demo proving that the P1 backend works end to end."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compass.contracts import DecisionRecord
from compass.fva import get_headline_stats, get_replay_chart_data
from compass.store import (
    get_affected_skus,
    get_live_machine_value,
    init_db,
    score_decision,
    seed_hierarchy,
    write_decision,
)


def main() -> None:
    print("COMPASS P1 BACKEND DEMO")
    print("=" * 70)

    init_db()
    hierarchy_rows = seed_hierarchy()
    print(f"Valid forecast hierarchy rows: {hierarchy_rows:,}")

    machine = get_live_machine_value("CP-0281", "SO04", "CH01", "2026-05-01")
    print("\nLive forecast example:")
    print(json.dumps({
        "item_id": machine["item_id"],
        "machine_value": round(machine["machine_value"], 2),
        "category": machine["category"],
        "business_unit": machine["business_unit"],
    }, indent=2))

    affected = get_affected_skus("Bearings & Bushings", "DACH")
    print(f"\nAffected valid forecast items for Bearings & Bushings / DACH: {len(affected):,}")
    print("First 3:", affected[:3])

    stats = get_headline_stats()
    print("\nHistorical H+1 FVA headline statistics:")
    print(json.dumps(stats, indent=2))

    replay = get_replay_chart_data()
    print("\nReplay data, latest 3 completed cycles:")
    print(replay.tail(3).to_string(index=False))

    # Temporary sample decision proves write and scoring functions.
    demo_id = "P1-DEMO-001"
    record = DecisionRecord(
        decision_id=demo_id,
        cutoff_date=date(2026, 4, 1),
        item_id="CP-0281__SO04__CH01",
        machine_value=100.0,
        override_value=120.0,
        reconciler_value=110.0,
        final_value=112.0,
        reason_text="Competitor exit",
        reason_class="competitor_exit",
        decision_maker="demo-planner",
        context_json={
            "target_month": "2026-05-01",
            "signals": [],
            "demo_only": True,
        },
    )
    write_decision(record)
    result = score_decision(demo_id, actual=108.0)
    print("\nDecision scoring example:")
    print(json.dumps(result, indent=2))
    print("\nPASS: loader, DuckDB store, forecast lookup and FVA replay work.")


if __name__ == "__main__":
    main()
