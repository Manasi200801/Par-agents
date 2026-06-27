"""
Data store — DuckDB setup and query helpers.
P1 owns this file. This is the full implementation.
P2/P3 import from here; do not duplicate any of these functions.
"""

import json
import os
import uuid
import duckdb
from compass.contracts import DecisionRecord

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "compass.duckdb")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_conn():
    return duckdb.connect(DB_PATH)


def init_db():
    """Run once at startup. Creates all 4 tables and 2 views."""
    conn = get_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS hierarchy (
            product_id    TEXT,
            product_group TEXT,
            category      TEXT,
            business_unit TEXT,
            sales_org_id  TEXT,
            region_group  TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id      TEXT PRIMARY KEY,
            cutoff_date      DATE,
            item_id          TEXT,
            machine_value    DOUBLE,
            override_value   DOUBLE,
            reconciler_value DOUBLE,
            final_value      DOUBLE,
            reason_text      TEXT,
            reason_class     TEXT,
            decision_maker   TEXT,
            context_json     TEXT,
            outcome          DOUBLE,
            machine_error    DOUBLE,
            override_error   DOUBLE,
            fva              DOUBLE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id         TEXT PRIMARY KEY,
            decision_id      TEXT,
            reason_class     TEXT,
            reason_text      TEXT,
            reason_embedding TEXT,
            realized_impact  DOUBLE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_sku (
            event_id     TEXT,
            product_id   TEXT,
            sales_org_id TEXT
        )
    """)

    conn.execute("""
        CREATE OR REPLACE VIEW track_record_by_reason AS
        SELECT
            reason_class,
            COUNT(*) AS n_decisions,
            AVG(fva) AS avg_fva,
            AVG(override_value / NULLIF(machine_value, 0) - 1) AS avg_override_pct,
            AVG(outcome / NULLIF(machine_value, 0) - 1)        AS avg_realized_pct,
            SUM(CASE WHEN fva > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS pct_helpful
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
            SUM(CASE WHEN fva > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS pct_helpful
        FROM decisions
        WHERE fva IS NOT NULL
        GROUP BY decision_maker
    """)

    conn.close()
    print("DB initialised.")


def seed_hierarchy():
    """Load product + sales_org hierarchy from parquet into hierarchy table."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pandas as pd

    def _load(path):
        t = pq.read_table(path)
        new = []
        for f in t.schema:
            c = t.column(f.name)
            if pa.types.is_dictionary(f.type):
                c = c.cast(f.type.value_type)
            new.append(c)
        return pa.table(new, names=t.schema.names).to_pandas()

    base = "data/alpine-manufacturing-gmbh/source-data"
    products  = _load(f"{base}/alpine_products.parquet")[
        ["product_id", "product_group", "category", "business_unit"]
    ]
    sales_org = _load(f"{base}/alpine_sales_org.parquet")[
        ["sales_org_id", "region_group"]
    ].drop_duplicates("sales_org_id")

    hier = products.merge(sales_org, how="cross")

    conn = get_conn()
    conn.execute("DELETE FROM hierarchy")
    conn.execute("INSERT INTO hierarchy SELECT * FROM hier")
    conn.close()
    print(f"Hierarchy seeded: {len(hier)} rows.")


def write_decision(record: DecisionRecord):
    conn = get_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            record.decision_id, record.cutoff_date, record.item_id,
            record.machine_value, record.override_value, record.reconciler_value,
            record.final_value, record.reason_text, record.reason_class,
            record.decision_maker, json.dumps(record.context_json),
            record.outcome, record.machine_error, record.override_error, record.fva,
        ],
    )
    conn.close()


def score_decision(decision_id: str, actual: float):
    """Called when actuals arrive. Computes and writes FVA."""
    conn = get_conn()
    row = conn.execute(
        "SELECT machine_value, final_value FROM decisions WHERE decision_id=?",
        [decision_id],
    ).fetchone()
    if row is None:
        conn.close()
        return
    machine_value, final_value = row
    machine_error  = abs(actual - machine_value)
    override_error = abs(actual - final_value)
    fva = machine_error - override_error
    conn.execute(
        """
        UPDATE decisions
        SET outcome=?, machine_error=?, override_error=?, fva=?
        WHERE decision_id=?
        """,
        [actual, machine_error, override_error, fva, decision_id],
    )
    conn.execute(
        "UPDATE events SET realized_impact=? WHERE decision_id=?",
        [fva, decision_id],
    )
    conn.close()


def get_track_record_by_reason(reason_class: str) -> dict:
    conn = get_conn()
    df = conn.execute(
        "SELECT * FROM track_record_by_reason WHERE reason_class=?",
        [reason_class],
    ).fetchdf()
    conn.close()
    return df.to_dict("records")[0] if len(df) else {}


def get_track_record_by_planner(decision_maker: str) -> dict:
    conn = get_conn()
    df = conn.execute(
        "SELECT * FROM track_record_by_planner WHERE decision_maker=?",
        [decision_maker],
    ).fetchdf()
    conn.close()
    return df.to_dict("records")[0] if len(df) else {}


def get_affected_skus(category: str, region_group: str) -> list:
    """Fan-out: all (product_id, sales_org_id) for this category × region."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT DISTINCT product_id, sales_org_id
        FROM hierarchy
        WHERE category=? AND region_group=?
        """,
        [category, region_group],
    ).fetchall()
    conn.close()
    return [{"product_id": r[0], "sales_org_id": r[1]} for r in rows]
