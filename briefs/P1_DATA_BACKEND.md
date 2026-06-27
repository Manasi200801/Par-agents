# P1 — Data & Backend
**Branch: your own branch on https://github.com/Manasi200801/Par-agents.git**
**You own: `compass/loader.py`, `compass/store.py`, `compass/fva.py`, `scripts/precompute.py`**

---

## What Compass is (read this first)

Compass is a demand-planning override copilot. A machine model forecasts sales (437 units). A human planner overrides it (360 units) and types a reason. Five AI agents look at real data and return evidence. A reconciler (Claude Opus) synthesizes and recommends a number. The human decides. The decision is stored, scored against actuals when they arrive (FVA = did the human help?), and fed back into memory so the next cycle is smarter.

**Your job is the foundation everything else stands on.** You own all data access. Every other person imports your functions. If your loader breaks, the whole project breaks.

---

## Your deliverables

### 1. `compass/loader.py` — the parquet loader

The Alpine and Firn parquet files use `uint32` dictionary indices. Plain `pandas.read_parquet` crashes with `ArrowTypeError`. You must use pyarrow and decode dictionary columns manually.

```python
# compass/loader.py
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd

DATA_ROOT = "data/alpine-manufacturing-gmbh/source-data"

def load_parquet(path: str) -> pd.DataFrame:
    """Load any parquet file from this dataset safely."""
    table = pq.read_table(path)
    new_cols = []
    for field in table.schema:
        col = table.column(field.name)
        if pa.types.is_dictionary(field.type):
            col = col.cast(field.type.value_type)
        new_cols.append(col)
    return pa.table(new_cols, names=table.schema.names).to_pandas()


def load_sales_actuals() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_sales_actuals.parquet")

def load_stat_forecast() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_statistical_forecast.parquet")

def load_demand_plan() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_demand_plan.parquet")

def load_products() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_products.parquet")

def load_stock_on_hand() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_stock_on_hand.parquet")

def load_future_order_book() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_future_order_book.parquet")

def load_customers() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_customers.parquet")

def load_purchase_orders() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_purchase_orders.parquet")

def load_suppliers() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_suppliers.parquet")

def load_production_data() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_production_data.parquet")

def load_returns() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_returns.parquet")

def load_business_plan() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_business_plan.parquet")

def load_cost_breakdown() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_cost_breakdown.parquet")

def load_price_changes() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_price_changes.parquet")

def load_tariff_reference() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_tariff_reference.parquet")

def load_marketing_spends() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_marketing_spends.parquet")

def load_sales_org() -> pd.DataFrame:
    return load_parquet(f"{DATA_ROOT}/alpine_sales_org.parquet")
```

**CRITICAL:** Every other team member imports from `compass.loader`. Nobody else touches parquet files directly. If they do, they'll hit the dict-decode bug and waste an hour.

---

### 2. `compass/store.py` — DuckDB setup and query helpers

DuckDB is a database that runs entirely in-process (no server). You set it up once, create the 4 tables, and expose helper functions everyone else calls.

```python
# compass/store.py
import duckdb
import pandas as pd
import json
import uuid
from datetime import date
from compass.contracts import DecisionRecord

DB_PATH = "compass/compass.duckdb"

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
            decision_id     TEXT PRIMARY KEY,
            cutoff_date     DATE,
            item_id         TEXT,
            machine_value   DOUBLE,
            override_value  DOUBLE,
            reconciler_value DOUBLE,
            final_value     DOUBLE,
            reason_text     TEXT,
            reason_class    TEXT,
            decision_maker  TEXT,
            context_json    TEXT,
            outcome         DOUBLE,
            machine_error   DOUBLE,
            override_error  DOUBLE,
            fva             DOUBLE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id         TEXT PRIMARY KEY,
            decision_id      TEXT,
            reason_class     TEXT,
            reason_text      TEXT,
            reason_embedding TEXT,   -- JSON array of floats
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
            AVG(outcome / NULLIF(machine_value, 0) - 1) AS avg_realized_pct,
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
    from compass.loader import load_products, load_sales_org
    products  = load_products()[['product_id','product_group','category','business_unit']]
    sales_org = load_sales_org()[['sales_org_id','region_group']]
    # cross join to make product × org rows (they're separate masters, not naturally joined)
    hier = products.merge(
        sales_org.drop_duplicates('sales_org_id'),
        how='cross'
    )
    conn = get_conn()
    conn.execute("DELETE FROM hierarchy")
    conn.execute("INSERT INTO hierarchy SELECT * FROM hier")
    conn.close()

def write_decision(record: DecisionRecord):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [
        record.decision_id, record.cutoff_date, record.item_id,
        record.machine_value, record.override_value, record.reconciler_value,
        record.final_value, record.reason_text, record.reason_class,
        record.decision_maker, json.dumps(record.context_json),
        record.outcome, record.machine_error, record.override_error, record.fva
    ])
    conn.close()

def score_decision(decision_id: str, actual: float):
    """Called when actuals arrive. Updates FVA on a stored decision."""
    conn = get_conn()
    row = conn.execute(
        "SELECT machine_value, final_value FROM decisions WHERE decision_id=?",
        [decision_id]
    ).fetchone()
    if row is None:
        conn.close()
        return
    machine_value, final_value = row
    machine_error  = abs(actual - machine_value)
    override_error = abs(actual - final_value)
    fva = machine_error - override_error  # positive = planner helped
    conn.execute("""
        UPDATE decisions
        SET outcome=?, machine_error=?, override_error=?, fva=?
        WHERE decision_id=?
    """, [actual, machine_error, override_error, fva, decision_id])
    # also update realized_impact on the linked event
    conn.execute("""
        UPDATE events SET realized_impact=?
        WHERE decision_id=?
    """, [fva, decision_id])
    conn.close()

def get_track_record_by_reason(reason_class: str) -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM track_record_by_reason WHERE reason_class=?",
        [reason_class]
    ).fetchdf()
    conn.close()
    return row.to_dict('records')[0] if len(row) else {}

def get_track_record_by_planner(decision_maker: str) -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM track_record_by_planner WHERE decision_maker=?",
        [decision_maker]
    ).fetchdf()
    conn.close()
    return row.to_dict('records')[0] if len(row) else {}

def get_affected_skus(category: str, region_group: str) -> list:
    """Fan-out: return all (product_id, sales_org_id) for this category × region."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT product_id, sales_org_id
        FROM hierarchy
        WHERE category=? AND region_group=?
    """, [category, region_group]).fetchall()
    conn.close()
    return [{"product_id": r[0], "sales_org_id": r[1]} for r in rows]
```

---

### 3. `compass/fva.py` — FVA scoring and cycle replay

This powers the replay dashboard. It reads the pre-computed `fva_base.parquet` (already generated — use it directly) and exposes query functions.

```python
# compass/fva.py
import pandas as pd
import numpy as np

FVA_BASE_PATH = "data/fva_base.parquet"  # pre-computed, already exists

_fva_df = None  # cached in memory

def _get_fva_df() -> pd.DataFrame:
    global _fva_df
    if _fva_df is None:
        df = pd.read_parquet(FVA_BASE_PATH)
        df = df[df['actual_qty'] > 0].copy()
        df['machine_err']  = (df['actual_qty'] - df['stat_qty']).abs()
        df['override_err'] = (df['actual_qty'] - df['plan_qty']).abs()
        df['fva']          = df['machine_err'] - df['override_err']
        _fva_df = df
    return _fva_df

def get_replay_chart_data() -> pd.DataFrame:
    """
    Returns one row per cutoff with MAE for machine and planner.
    Used by P4 to draw the 3-line replay chart.
    Schema: cutoff_date, mae_machine, mae_planner, n_rows
    """
    df = _get_fva_df()
    result = df.groupby('cutoff_date').apply(lambda g: pd.Series({
        'mae_machine':  g['machine_err'].mean(),
        'mae_planner':  g['override_err'].mean(),
        'n_rows':       len(g),
        'pct_helped':   (g['fva'] > 0).mean(),
    }), include_groups=False).reset_index()
    result = result.sort_values('cutoff_date')
    return result

def get_cycle_detail(cutoff_date) -> pd.DataFrame:
    """Returns all scored rows for one specific cutoff cycle."""
    df = _get_fva_df()
    return df[df['cutoff_date'] == pd.Timestamp(cutoff_date)].copy()

def get_headline_stats() -> dict:
    """Returns the key numbers for the pitch slide."""
    df = _get_fva_df()
    up = df[df['plan_qty'] > df['stat_qty']]
    dn = df[df['plan_qty'] < df['stat_qty']]
    return {
        "total_rows":         len(df),
        "pct_helped":         (df['fva'] > 0).mean(),
        "pct_hurt":           (df['fva'] < 0).mean(),
        "mae_machine":        df['machine_err'].mean(),
        "mae_planner":        df['override_err'].mean(),
        "mae_change_pct":     (df['override_err'].mean() - df['machine_err'].mean()) / df['machine_err'].mean() * 100,
        "upward_pct_helped":  (up['fva'] > 0).mean(),
        "downward_pct_helped":(dn['fva'] > 0).mean(),
        "upward_share":       len(up) / len(df),
        "downward_share":     len(dn) / len(df),
    }
```

---

### 4. `scripts/precompute.py` — run this offline before the demo

```python
# scripts/precompute.py
# Run: python scripts/precompute.py
# Takes ~2 minutes. Caches results so the demo never hits raw parquet at runtime.
from compass.store import init_db, seed_hierarchy
from compass.fva   import get_replay_chart_data, get_headline_stats
import pandas as pd

print("Initialising database...")
init_db()

print("Seeding hierarchy...")
seed_hierarchy()

print("Caching replay chart data...")
chart = get_replay_chart_data()
chart.to_parquet("data/replay_chart_cache.parquet", index=False)

print("Caching headline stats...")
stats = get_headline_stats()
import json
with open("data/headline_stats.json", "w") as f:
    json.dump(stats, f, indent=2)

print("Done. Run this before every demo.")
```

---

## Install

```bash
pip install pyarrow pandas duckdb
```

---

## CRITICAL things you must do

1. **Never use `pd.read_parquet()` directly.** Always use `compass.loader.load_parquet()`. Test this first — if you don't see data from all 18 source tables, something is wrong.
2. **Run `scripts/precompute.py` and commit the output files** (`fva_base.parquet`, `replay_chart_cache.parquet`, `headline_stats.json`) to the repo. P4 depends on these at runtime.
3. **`init_db()` and `seed_hierarchy()` must be idempotent** — safe to run multiple times without duplicating data. Use `CREATE TABLE IF NOT EXISTS` and `DELETE FROM … INSERT INTO` pattern (already in the code above).
4. **Test `get_affected_skus('Bearings & Bushings', 'DACH')`** — it must return a non-empty list. If empty, the KG fan-out is broken and P2 cannot do their job.
5. **The `fva_base.parquet` already exists** at `D:\Claude Projects\Paretos Hackathon\fva_base.parquet`. Copy it into `data/` in the repo. Do not recompute it from scratch during the hackathon — it takes 3 minutes and blocks everyone.

## What you expose to the rest of the team

| Function | Who uses it |
|----------|-------------|
| `compass.loader.load_*()` | P2, P3 (agents read tables) |
| `compass.store.init_db()` | P5 (calls at app startup) |
| `compass.store.write_decision(record)` | P3 (after reconciler runs) |
| `compass.store.score_decision(id, actual)` | P5 (demo scoring) |
| `compass.store.get_affected_skus(cat, region)` | P2 (fan-out) |
| `compass.store.get_track_record_by_reason(cls)` | P2 (memory recall) |
| `compass.store.get_track_record_by_planner(id)` | P2 (memory recall) |
| `compass.fva.get_replay_chart_data()` | P4 (replay dashboard) |
| `compass.fva.get_headline_stats()` | P4 (stats display) |

## Git

```bash
git checkout your-branch
# work in compass/loader.py, compass/store.py, compass/fva.py, scripts/precompute.py
git add compass/loader.py compass/store.py compass/fva.py scripts/precompute.py
git add data/fva_base.parquet data/replay_chart_cache.parquet data/headline_stats.json
git commit -m "P1: data layer, DuckDB store, FVA replay harness"
git push origin your-branch
```
