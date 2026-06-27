"""
Data loader — all parquet access goes through here.
Uses pyarrow to decode uint32 dictionary columns that crash pd.read_parquet.
"""

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import os

DATA_ROOT = os.environ.get(
    "COMPASS_DATA_ROOT",
    "data/alpine-manufacturing-gmbh/source-data"
)


def load_parquet(path: str) -> pd.DataFrame:
    table = pq.read_table(path)
    new_cols = []
    for field in table.schema:
        col = table.column(field.name)
        if pa.types.is_dictionary(field.type):
            col = col.cast(field.type.value_type)
        new_cols.append(col)
    return pa.table(new_cols, names=table.schema.names).to_pandas()


def _p(name: str) -> str:
    return f"{DATA_ROOT}/{name}.parquet"


def load_sales_actuals()       -> pd.DataFrame: return load_parquet(_p("alpine_sales_actuals"))
def load_stat_forecast()       -> pd.DataFrame: return load_parquet(_p("alpine_statistical_forecast"))
def load_demand_plan()         -> pd.DataFrame: return load_parquet(_p("alpine_demand_plan"))
def load_products()            -> pd.DataFrame: return load_parquet(_p("alpine_products"))
def load_sales_org()           -> pd.DataFrame: return load_parquet(_p("alpine_sales_org"))
def load_channels()            -> pd.DataFrame: return load_parquet(_p("alpine_channels"))
def load_stock_on_hand()       -> pd.DataFrame: return load_parquet(_p("alpine_stock_on_hand"))
def load_future_order_book()   -> pd.DataFrame: return load_parquet(_p("alpine_future_order_book"))
def load_customers()           -> pd.DataFrame: return load_parquet(_p("alpine_customers"))
def load_purchase_orders()     -> pd.DataFrame: return load_parquet(_p("alpine_purchase_orders"))
def load_suppliers()           -> pd.DataFrame: return load_parquet(_p("alpine_suppliers"))
def load_production_data()     -> pd.DataFrame: return load_parquet(_p("alpine_production_data"))
def load_returns()             -> pd.DataFrame: return load_parquet(_p("alpine_returns"))
def load_business_plan()       -> pd.DataFrame: return load_parquet(_p("alpine_business_plan"))
def load_cost_breakdown()      -> pd.DataFrame: return load_parquet(_p("alpine_cost_breakdown"))
def load_price_changes()       -> pd.DataFrame: return load_parquet(_p("alpine_price_changes"))
def load_tariff_reference()    -> pd.DataFrame: return load_parquet(_p("alpine_tariff_reference"))
def load_marketing_spends()    -> pd.DataFrame: return load_parquet(_p("alpine_marketing_spends"))
def load_actuals_plan_forecast() -> pd.DataFrame: return load_parquet(_p("alpine_actuals_plan_forecast_monthly"))
