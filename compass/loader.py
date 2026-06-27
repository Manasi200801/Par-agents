"""Safe, centralised access to the Alpine Parquet dataset.

All runtime code should import these functions rather than reading Parquet files
independently.  The source files contain dictionary-encoded strings with uint32
indices, so dictionary columns are decoded before conversion to pandas.
"""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(
    os.getenv(
        "COMPASS_DATA_ROOT",
        PROJECT_ROOT / "data" / "alpine-manufacturing-gmbh",
    )
).resolve()
SOURCE_ROOT = DATA_ROOT / "source-data"
FORECAST_OUTPUT_ROOT = DATA_ROOT / "forecast-output"
FORECAST_INPUT_ROOT = DATA_ROOT / "forecast-input"

TABLES: dict[str, Path] = {
    # Source business tables
    "sales_actuals": SOURCE_ROOT / "alpine_sales_actuals.parquet",
    "stat_forecast": SOURCE_ROOT / "alpine_statistical_forecast.parquet",
    "demand_plan": SOURCE_ROOT / "alpine_demand_plan.parquet",
    "products": SOURCE_ROOT / "alpine_products.parquet",
    "sales_org": SOURCE_ROOT / "alpine_sales_org.parquet",
    "channels": SOURCE_ROOT / "alpine_channels.parquet",
    "customers": SOURCE_ROOT / "alpine_customers.parquet",
    "suppliers": SOURCE_ROOT / "alpine_suppliers.parquet",
    "stock_on_hand": SOURCE_ROOT / "alpine_stock_on_hand.parquet",
    "future_order_book": SOURCE_ROOT / "alpine_future_order_book.parquet",
    "production_data": SOURCE_ROOT / "alpine_production_data.parquet",
    "marketing_spends": SOURCE_ROOT / "alpine_marketing_spends.parquet",
    "business_plan": SOURCE_ROOT / "alpine_business_plan.parquet",
    "price_changes": SOURCE_ROOT / "alpine_price_changes.parquet",
    "purchase_orders": SOURCE_ROOT / "alpine_purchase_orders.parquet",
    "delivery_data": SOURCE_ROOT / "alpine_delivery_data.parquet",
    "returns": SOURCE_ROOT / "alpine_returns.parquet",
    "cost_breakdown": SOURCE_ROOT / "alpine_cost_breakdown.parquet",
    "tariff_reference": SOURCE_ROOT / "alpine_tariff_reference.parquet",
    "monthly_mart": SOURCE_ROOT / "alpine_actuals_plan_forecast_monthly.parquet",
    # Forecast pipeline outputs needed for channel-level live decisions
    "live_forecasts": FORECAST_OUTPUT_ROOT / "live_forecasts.parquet",
    "forecast_metadata": FORECAST_OUTPUT_ROOT / "meta_data.parquet",
    "forecast_error_metrics": FORECAST_OUTPUT_ROOT / "final_error_metrics.parquet",
    "overall_error_metrics": FORECAST_OUTPUT_ROOT / "final_overall_error_metrics.parquet",
    "backtest_forecasts": FORECAST_OUTPUT_ROOT / "final_backtest_forecasts.parquet",
    "target_time_series": FORECAST_INPUT_ROOT / "target_time_series.parquet",
}


def _decode_dictionary_columns(table: pa.Table) -> pa.Table:
    """Return an Arrow table whose dictionary columns are plain value columns."""
    decoded: list[pa.ChunkedArray] = []
    for field in table.schema:
        column = table.column(field.name)
        if pa.types.is_dictionary(field.type):
            column = column.cast(field.type.value_type)
        decoded.append(column)
    return pa.table(decoded, names=table.schema.names)


def load_parquet(
    path: str | Path,
    *,
    columns: Iterable[str] | None = None,
    filters=None,
) -> pd.DataFrame:
    """Load a Parquet file safely and return a pandas DataFrame.

    ``columns`` and ``filters`` are passed to PyArrow so callers can avoid
    loading millions of irrelevant rows.
    """
    parquet_path = Path(path)
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Parquet file not found: {parquet_path}. "
            "Set COMPASS_DATA_ROOT to the alpine-manufacturing-gmbh folder."
        )
    table = pq.read_table(parquet_path, columns=columns, filters=filters)
    return _decode_dictionary_columns(table).to_pandas()


def load_table(
    name: str,
    *,
    columns: Iterable[str] | None = None,
    filters=None,
) -> pd.DataFrame:
    """Load one registered dataset by logical name."""
    try:
        path = TABLES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown table {name!r}. Valid names: {sorted(TABLES)}") from exc
    return load_parquet(path, columns=columns, filters=filters)


def validate_dataset() -> dict[str, dict[str, object]]:
    """Fail fast if required files are absent; return row counts and columns."""
    manifest: dict[str, dict[str, object]] = {}
    for name, path in TABLES.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing required dataset {name}: {path}")
        metadata = pq.read_metadata(path)
        manifest[name] = {
            "path": str(path),
            "rows": metadata.num_rows,
            "columns": metadata.schema.names,
        }
    return manifest


# Explicit wrappers keep the public API stable for the other team members.
def load_sales_actuals(**kwargs): return load_table("sales_actuals", **kwargs)
def load_stat_forecast(**kwargs): return load_table("stat_forecast", **kwargs)
def load_demand_plan(**kwargs): return load_table("demand_plan", **kwargs)
def load_products(**kwargs): return load_table("products", **kwargs)
def load_sales_org(**kwargs): return load_table("sales_org", **kwargs)
def load_channels(**kwargs): return load_table("channels", **kwargs)
def load_customers(**kwargs): return load_table("customers", **kwargs)
def load_suppliers(**kwargs): return load_table("suppliers", **kwargs)
def load_stock_on_hand(**kwargs): return load_table("stock_on_hand", **kwargs)
def load_future_order_book(**kwargs): return load_table("future_order_book", **kwargs)
def load_production_data(**kwargs): return load_table("production_data", **kwargs)
def load_marketing_spends(**kwargs): return load_table("marketing_spends", **kwargs)
def load_business_plan(**kwargs): return load_table("business_plan", **kwargs)
def load_price_changes(**kwargs): return load_table("price_changes", **kwargs)
def load_purchase_orders(**kwargs): return load_table("purchase_orders", **kwargs)
def load_delivery_data(**kwargs): return load_table("delivery_data", **kwargs)
def load_returns(**kwargs): return load_table("returns", **kwargs)
def load_cost_breakdown(**kwargs): return load_table("cost_breakdown", **kwargs)
def load_tariff_reference(**kwargs): return load_table("tariff_reference", **kwargs)
def load_monthly_mart(**kwargs): return load_table("monthly_mart", **kwargs)
def load_live_forecasts(**kwargs): return load_table("live_forecasts", **kwargs)
def load_forecast_metadata(**kwargs): return load_table("forecast_metadata", **kwargs)
def load_forecast_error_metrics(**kwargs): return load_table("forecast_error_metrics", **kwargs)
def load_overall_error_metrics(**kwargs): return load_table("overall_error_metrics", **kwargs)
def load_backtest_forecasts(**kwargs): return load_table("backtest_forecasts", **kwargs)
def load_target_time_series(**kwargs): return load_table("target_time_series", **kwargs)
