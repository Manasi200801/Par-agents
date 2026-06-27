"""DuckDB persistence and small query helpers for Compass."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import json
import os
from pathlib import Path
from typing import Iterator

import duckdb
import numpy as np
import pandas as pd

from compass.contracts import DecisionRecord
from compass.loader import load_forecast_metadata, load_live_forecasts

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("COMPASS_DB_PATH", PROJECT_ROOT / "data" / "compass.duckdb"))


def _json_default(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serialisable")


def dumps_json(value) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False)


def get_conn(*, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


@contextmanager
def connection(*, read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    conn = get_conn(read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create persistent tables and derived track-record views."""
    with connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hierarchy (
                item_id BIGINT,
                product_id TEXT,
                product_group TEXT,
                category TEXT,
                business_unit TEXT,
                sales_org_id TEXT,
                region_group TEXT,
                channel_id TEXT,
                PRIMARY KEY (item_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                cutoff_date DATE,
                target_month DATE,
                item_id TEXT,
                machine_value DOUBLE,
                override_value DOUBLE,
                reconciler_value DOUBLE,
                final_value DOUBLE,
                reason_text TEXT,
                reason_class TEXT,
                decision_maker TEXT,
                context_json TEXT,
                outcome DOUBLE,
                machine_error DOUBLE,
                proposed_error DOUBLE,
                reconciler_error DOUBLE,
                override_error DOUBLE,
                fva DOUBLE,
                compass_value_added DOUBLE,
                scored_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                decision_id TEXT,
                reason_class TEXT,
                reason_text TEXT,
                reason_embedding TEXT,
                realized_impact DOUBLE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_sku (
                event_id TEXT,
                product_id TEXT,
                sales_org_id TEXT,
                channel_id TEXT,
                PRIMARY KEY (event_id, product_id, sales_org_id, channel_id)
            )
        """)
        conn.execute("""
            CREATE OR REPLACE VIEW track_record_by_reason AS
            SELECT
                reason_class,
                COUNT(*) AS n_decisions,
                AVG(fva) AS avg_fva,
                MEDIAN(fva) AS median_fva,
                AVG((override_value - machine_value) / NULLIF(ABS(machine_value), 0)) AS avg_override_pct,
                AVG((outcome - machine_value) / NULLIF(ABS(machine_value), 0)) AS avg_realized_pct,
                AVG(CASE WHEN fva > 0 THEN 1.0 ELSE 0.0 END) AS pct_helpful
            FROM decisions
            WHERE fva IS NOT NULL
            GROUP BY reason_class
        """)
        conn.execute("""
            CREATE OR REPLACE VIEW track_record_by_planner AS
            SELECT
                decision_maker,
                COUNT(*) AS n_decisions,
                AVG(fva) AS avg_fva,
                MEDIAN(fva) AS median_fva,
                AVG(CASE WHEN fva > 0 THEN 1.0 ELSE 0.0 END) AS pct_helpful
            FROM decisions
            WHERE fva IS NOT NULL
            GROUP BY decision_maker
        """)


def seed_hierarchy() -> int:
    """Seed only valid product-org-channel combinations from forecast metadata."""
    metadata = load_forecast_metadata(columns=[
        "item_id", "product_id", "product_group", "category", "business_unit",
        "sales_org_id", "channel_id",
    ])
    sales_org_path = Path(os.getenv("COMPASS_DATA_ROOT", PROJECT_ROOT / "data" / "alpine-manufacturing-gmbh")) / "source-data" / "alpine_sales_org.parquet"
    # Use the central loader to avoid the dictionary-index issue.
    from compass.loader import load_sales_org
    org = load_sales_org(columns=["sales_org_id", "region_group"])
    for column in ["product_id", "product_group", "category", "business_unit", "sales_org_id", "channel_id"]:
        metadata[column] = metadata[column].astype("string")
    org["sales_org_id"] = org["sales_org_id"].astype("string")
    org["region_group"] = org["region_group"].astype("string")
    hierarchy = metadata.merge(org, on="sales_org_id", how="left", validate="many_to_one")
    hierarchy = hierarchy[[
        "item_id", "product_id", "product_group", "category", "business_unit",
        "sales_org_id", "region_group", "channel_id",
    ]].drop_duplicates("item_id")

    with connection() as conn:
        conn.register("hierarchy_df", hierarchy)
        conn.execute("DELETE FROM hierarchy")
        conn.execute("INSERT INTO hierarchy SELECT * FROM hierarchy_df")
        conn.unregister("hierarchy_df")
    return len(hierarchy)


def write_decision(record: DecisionRecord) -> None:
    """Persist a committed decision without relying on table column order."""
    target_month = record.context_json.get("target_month") if record.context_json else None
    with connection() as conn:
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute("DELETE FROM decisions WHERE decision_id = ?", [record.decision_id])
            conn.execute("""
                INSERT INTO decisions (
                    decision_id, cutoff_date, target_month, item_id,
                    machine_value, override_value, reconciler_value, final_value,
                    reason_text, reason_class, decision_maker, context_json,
                    outcome, machine_error, override_error, fva
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                record.decision_id,
                record.cutoff_date,
                target_month,
                record.item_id,
                record.machine_value,
                record.override_value,
                record.reconciler_value,
                record.final_value,
                record.reason_text,
                record.reason_class,
                record.decision_maker,
                dumps_json(record.context_json),
                record.outcome,
                record.machine_error,
                record.override_error,
                record.fva,
            ])
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def score_decision(decision_id: str, actual: float) -> dict[str, float]:
    """Score machine, proposed planner, reconciler and final committed values."""
    with connection() as conn:
        row = conn.execute("""
            SELECT machine_value, override_value, reconciler_value, final_value
            FROM decisions WHERE decision_id = ?
        """, [decision_id]).fetchone()
        if row is None:
            raise KeyError(f"Unknown decision_id: {decision_id}")

        machine_value, proposed_value, reconciler_value, final_value = map(float, row)
        machine_error = abs(actual - machine_value)
        proposed_error = abs(actual - proposed_value)
        reconciler_error = abs(actual - reconciler_value)
        final_error = abs(actual - final_value)
        fva = machine_error - final_error
        compass_value_added = proposed_error - final_error
        realized_delta_vs_machine = (
            (actual - machine_value) / abs(machine_value) if machine_value else None
        )

        conn.execute("""
            UPDATE decisions SET
                outcome = ?, machine_error = ?, proposed_error = ?,
                reconciler_error = ?, override_error = ?, fva = ?,
                compass_value_added = ?, scored_at = CURRENT_TIMESTAMP
            WHERE decision_id = ?
        """, [
            actual, machine_error, proposed_error, reconciler_error,
            final_error, fva, compass_value_added, decision_id,
        ])
        conn.execute("""
            UPDATE events SET realized_impact = ? WHERE decision_id = ?
        """, [realized_delta_vs_machine, decision_id])

    return {
        "actual": float(actual),
        "machine_error": machine_error,
        "proposed_error": proposed_error,
        "reconciler_error": reconciler_error,
        "final_error": final_error,
        "fva": fva,
        "compass_value_added": compass_value_added,
    }


def get_live_machine_value(
    product_id: str,
    sales_org_id: str,
    channel_id: str,
    target_month,
) -> dict:
    """Return the channel-level live forecast quantity for one target month."""
    target_month = pd.Timestamp(target_month).to_period("M").to_timestamp()
    metadata = load_forecast_metadata(columns=[
        "item_id", "product_id", "sales_org_id", "channel_id",
        "business_unit", "category", "product_group",
    ])
    for column in ["product_id", "sales_org_id", "channel_id"]:
        metadata[column] = metadata[column].astype("string")
    match = metadata[(metadata["product_id"] == product_id)
                     & (metadata["sales_org_id"] == sales_org_id)
                     & (metadata["channel_id"] == channel_id)]
    if match.empty:
        raise KeyError(f"No forecast item for {product_id}/{sales_org_id}/{channel_id}")
    if len(match) != 1:
        raise ValueError("Forecast metadata is not unique for the requested item")
    item = match.iloc[0]
    live = load_live_forecasts(
        columns=["item_id", "date", "prediction"],
        filters=[("item_id", "=", int(item["item_id"]))],
    )
    live["target_month"] = live["date"].dt.to_period("M").dt.to_timestamp()
    month_rows = live[live["target_month"] == target_month]
    if month_rows.empty:
        raise KeyError(f"No live forecast for target month {target_month.date()}")
    return {
        "item_id": int(item["item_id"]),
        "machine_value": float(month_rows["prediction"].sum()),
        "forecast_rows": month_rows[["date", "prediction"]].to_dict("records"),
        "business_unit": str(item["business_unit"]),
        "category": str(item["category"]),
        "product_group": str(item["product_group"]),
    }


def _one_record(sql: str, params: list) -> dict:
    with connection(read_only=True) as conn:
        frame = conn.execute(sql, params).fetchdf()
    return frame.to_dict("records")[0] if not frame.empty else {}


def get_track_record_by_reason(reason_class: str) -> dict:
    return _one_record(
        "SELECT * FROM track_record_by_reason WHERE reason_class = ?",
        [reason_class],
    )


def get_track_record_by_planner(decision_maker: str) -> dict:
    return _one_record(
        "SELECT * FROM track_record_by_planner WHERE decision_maker = ?",
        [decision_maker],
    )


def get_affected_skus(category: str, region_group: str) -> list[dict[str, str]]:
    """Return valid forecasted item combinations, not an invented cross join."""
    with connection(read_only=True) as conn:
        rows = conn.execute("""
            SELECT DISTINCT product_id, sales_org_id, channel_id
            FROM hierarchy
            WHERE category = ? AND region_group = ?
            ORDER BY product_id, sales_org_id, channel_id
        """, [category, region_group]).fetchall()
    return [
        {"product_id": row[0], "sales_org_id": row[1], "channel_id": row[2]}
        for row in rows
    ]
