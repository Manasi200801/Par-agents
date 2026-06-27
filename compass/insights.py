"""Decision-story facts computed from the real Alpine dataset.

These helpers turn raw history into the small set of business numbers a demand
planner actually reasons with: recent run-rate, same month last year, the value
of a unit, and the current stock position. Everything here is derived from the
source parquet files — nothing is hard-coded. Each function returns ``None``
(or a dict with ``None`` fields) when the data is missing, so callers can
degrade gracefully.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import pandas as pd

from compass.loader import (
    load_price_changes,
    load_sales_actuals,
    load_stock_on_hand,
)


@lru_cache(maxsize=256)
def _monthly_actuals(
    product_id: str,
    sales_org_id: str,
    channel_id: str,
) -> Optional[pd.DataFrame]:
    """Monthly actual quantity and revenue for one product/org/channel."""
    df = load_sales_actuals(
        filters=[
            ("product_id", "=", product_id),
            ("sales_org_id", "=", sales_org_id),
            ("channel_id", "=", channel_id),
        ]
    )
    if df.empty:
        return None
    monthly = (
        df.assign(m=df["date"].dt.to_period("M"))
        .groupby("m")
        .agg(qty=("quantity_bu", "sum"), rev=("revenue_eur", "sum"))
        .sort_index()
    )
    return monthly


def _complete_months(monthly: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Drop a trailing partial month (data cut-off) so baselines stay honest.

    The latest month is dropped only if it looks like a data-cut-off artefact —
    less than 45% of the median of the preceding months. A genuinely low month
    is kept.
    """
    if monthly is None or monthly.empty:
        return monthly
    if len(monthly) >= 4:
        recent = float(monthly["qty"].iloc[-1])
        prior = monthly["qty"].iloc[-7:-1] if len(monthly) >= 7 else monthly["qty"].iloc[:-1]
        reference = float(prior.median())
        if reference > 0 and recent < 0.45 * reference:
            return monthly.iloc[:-1]
    return monthly


@lru_cache(maxsize=256)
def demand_baseline(
    product_id: str,
    sales_org_id: str,
    channel_id: str,
) -> Optional[dict]:
    """Recent run-rate, last completed month, and realised value per unit."""
    monthly = _complete_months(_monthly_actuals(product_id, sales_org_id, channel_id))
    if monthly is None or monthly.empty:
        return None

    last = monthly.iloc[-1]
    run_rate = float(monthly["qty"].iloc[-3:].mean())

    tail = monthly.iloc[-6:]
    total_qty = float(tail["qty"].sum())
    value_per_unit = float(tail["rev"].sum() / total_qty) if total_qty > 0 else None

    return {
        "run_rate": run_rate,
        "last_month_label": monthly.index[-1].strftime("%b %Y"),
        "last_month_qty": float(last["qty"]),
        "value_per_unit": value_per_unit,
        "n_months": int(len(monthly)),
    }


@lru_cache(maxsize=256)
def same_month_last_year(
    product_id: str,
    sales_org_id: str,
    channel_id: str,
    target_month: str,
) -> Optional[float]:
    """Actual quantity for the same calendar month one year before the cycle."""
    monthly = _monthly_actuals(product_id, sales_org_id, channel_id)
    if monthly is None or monthly.empty:
        return None
    try:
        period = pd.Period(target_month, "M") - 12
    except Exception:
        return None
    if period in monthly.index:
        return float(monthly.loc[period, "qty"])
    return None


@lru_cache(maxsize=256)
def latest_unit_price(
    product_id: str,
    sales_org_id: str,
    channel_id: str,
) -> Optional[float]:
    """Most recent list price (fallback when realised value per unit is absent)."""
    df = load_price_changes(
        filters=[
            ("product_id", "=", product_id),
            ("sales_org_id", "=", sales_org_id),
            ("channel_id", "=", channel_id),
        ]
    )
    if df.empty:
        return None
    row = df.sort_values("effective_month").iloc[-1]
    return float(row["price_eur_per_pcs"])


@lru_cache(maxsize=256)
def stock_position(product_id: str, sales_org_id: str) -> Optional[dict]:
    """Latest stock-on-hand snapshot for one product/org."""
    df = load_stock_on_hand(
        filters=[
            ("product_id", "=", product_id),
            ("sales_org_id", "=", sales_org_id),
        ]
    )
    if df.empty:
        return None
    row = df.sort_values("date").iloc[-1]
    return {
        "qty": float(row["stock_qty_bu"]),
        "value": float(row["stock_value_eur"]),
        "as_of": pd.Timestamp(row["date"]).strftime("%d %b %Y"),
    }
