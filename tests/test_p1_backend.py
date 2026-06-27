from __future__ import annotations

from datetime import date

from compass.contracts import DecisionRecord
from compass.fva import build_fva_base, get_headline_stats
from compass.loader import load_products, validate_dataset
from compass.store import (
    get_affected_skus,
    get_live_machine_value,
    init_db,
    score_decision,
    seed_hierarchy,
    write_decision,
)


def test_dataset_loads():
    manifest = validate_dataset()
    assert manifest["products"]["rows"] == 600
    assert len(load_products()) == 600


def test_hierarchy_fanout():
    init_db()
    assert seed_hierarchy() > 10_000
    affected = get_affected_skus("Bearings & Bushings", "DACH")
    assert affected
    assert {"product_id", "sales_org_id", "channel_id"} <= affected[0].keys()


def test_fva_methodology(tmp_path):
    base = build_fva_base(tmp_path / "fva.parquet")
    assert base["cutoff_date"].nunique() >= 20
    assert len(base) >= 50_000
    assert not base[["stat_qty", "plan_qty", "actual_qty"]].isna().any().any()
    assert (base["target_month"] > base["cutoff_date"]).all()


def test_decision_write_and_score():
    init_db()
    record = DecisionRecord(
        decision_id="TEST-001",
        cutoff_date=date(2026, 4, 1),
        item_id="CP-0281__SO04__CH01",
        machine_value=100.0,
        override_value=120.0,
        reconciler_value=110.0,
        final_value=112.0,
        reason_text="Competitor exit",
        reason_class="competitor_exit",
        decision_maker="planner-1",
        context_json={"target_month": "2026-05-01", "signals": []},
    )
    write_decision(record)
    result = score_decision("TEST-001", actual=108.0)
    assert result["machine_error"] == 8.0
    assert result["proposed_error"] == 12.0
    assert result["final_error"] == 4.0
    assert result["fva"] == 4.0
    assert result["compass_value_added"] == 8.0


def test_live_machine_value():
    result = get_live_machine_value("CP-0281", "SO04", "CH01", "2026-05-01")
    assert result["machine_value"] > 0
    assert result["category"]
    assert result["forecast_rows"]
