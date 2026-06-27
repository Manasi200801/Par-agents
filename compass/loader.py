# compass/loader.py
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
from pathlib import Path

DATA_ROOT = Path("data/alpine-manufacturing-gmbh/source-data")

def load_parquet(path: str) -> pd.DataFrame:
    """Load any parquet file from this dataset safely."""
    parquet_path = Path(path)
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

    table = pq.read_table(parquet_path)
    new_cols = []
    for field in table.schema:
        col = table.column(field.name)
        if pa.types.is_dictionary(field.type):
            col = col.cast(field.type.value_type)
        new_cols.append(col)
    return pa.table(new_cols, names=table.schema.names).to_pandas()


def load_sales_actuals() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_sales_actuals.parquet")

def load_stat_forecast() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_statistical_forecast.parquet")

def load_demand_plan() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_demand_plan.parquet")

def load_products() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_products.parquet")

def load_stock_on_hand() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_stock_on_hand.parquet")

def load_future_order_book() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_future_order_book.parquet")

def load_customers() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_customers.parquet")

def load_purchase_orders() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_purchase_orders.parquet")

def load_suppliers() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_suppliers.parquet")

def load_production_data() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_production_data.parquet")

def load_returns() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_returns.parquet")

def load_business_plan() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_business_plan.parquet")

def load_cost_breakdown() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_cost_breakdown.parquet")

def load_price_changes() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_price_changes.parquet")

def load_tariff_reference() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_tariff_reference.parquet")

def load_marketing_spends() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_marketing_spends.parquet")

def load_sales_org() -> pd.DataFrame:
    return load_parquet(DATA_ROOT / "alpine_sales_org.parquet")
