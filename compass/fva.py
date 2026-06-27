"""Historical Forecast Value Added reconstruction and replay queries.

Methodology: compare the machine forecast and planner demand plan for the first
full month after each planning cutoff (H+1).  This avoids comparing a complete
monthly statistical forecast with a partially covered month from the 12-week
weekly demand plan.
"""
from __future__ import annotations

from pathlib import Path
import os

import numpy as np
import pandas as pd

from compass.loader import load_demand_plan, load_sales_actuals, load_stat_forecast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FVA_BASE_PATH = Path(os.getenv("COMPASS_FVA_BASE", PROJECT_ROOT / "data" / "fva_base.parquet"))
MEANINGFUL_OVERRIDE_THRESHOLD = 0.05
_fva_df: pd.DataFrame | None = None


def _as_string(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        df[column] = df[column].astype("string")
    return df


def _month_start(series: pd.Series) -> pd.Series:
    return series.dt.to_period("M").dt.to_timestamp()


def _month_horizon(cutoff: pd.Series, target: pd.Series) -> pd.Series:
    return (target.dt.year - cutoff.dt.year) * 12 + (target.dt.month - cutoff.dt.month)


def build_fva_base(output_path: str | Path = FVA_BASE_PATH) -> pd.DataFrame:
    """Build leakage-safe H+1 machine-vs-planner-vs-actual records."""
    stat = load_stat_forecast(
        columns=["cutoff_date", "product_id", "sales_org_id", "forecast_month", "stat_forecast_qty_bu"]
    )
    plan = load_demand_plan(
        columns=["cutoff_date", "product_id", "sales_org_id", "date", "total_forecast_qty_bu"]
    )
    actual = load_sales_actuals(
        columns=["product_id", "sales_org_id", "date", "quantity_bu"]
    )

    _as_string(stat, ["product_id", "sales_org_id"])
    _as_string(plan, ["product_id", "sales_org_id"])
    _as_string(actual, ["product_id", "sales_org_id"])

    # Machine forecast: exactly the next calendar month after the cutoff.
    stat["target_month"] = _month_start(stat["forecast_month"])
    stat["horizon_month"] = _month_horizon(stat["cutoff_date"], stat["target_month"])
    stat_h1 = (
        stat.loc[stat["horizon_month"] == 1,
                 ["cutoff_date", "product_id", "sales_org_id", "target_month", "stat_forecast_qty_bu"]]
        .rename(columns={"stat_forecast_qty_bu": "stat_qty"})
    )

    # Planner plan: weekly rows summed into month, then exactly H+1.
    plan["target_month"] = _month_start(plan["date"])
    plan_monthly = (
        plan.groupby(
            ["cutoff_date", "product_id", "sales_org_id", "target_month"],
            observed=True,
            as_index=False,
        )["total_forecast_qty_bu"]
        .sum()
        .rename(columns={"total_forecast_qty_bu": "plan_qty"})
    )
    plan_monthly["horizon_month"] = _month_horizon(
        plan_monthly["cutoff_date"], plan_monthly["target_month"]
    )
    plan_h1 = plan_monthly.loc[
        plan_monthly["horizon_month"] == 1,
        ["cutoff_date", "product_id", "sales_org_id", "target_month", "plan_qty"],
    ]

    # Historical machine and planner data have no channel, so aggregate actuals
    # across channels at product x sales-org x month.
    actual["target_month"] = _month_start(actual["date"])
    actual_monthly = (
        actual.groupby(
            ["product_id", "sales_org_id", "target_month"],
            observed=True,
            as_index=False,
        )["quantity_bu"]
        .sum()
        .rename(columns={"quantity_bu": "actual_qty"})
    )

    # The latest actual month is partial in the supplied snapshot; exclude it.
    latest_actual_month = actual_monthly["target_month"].max()
    actual_monthly = actual_monthly[actual_monthly["target_month"] < latest_actual_month]

    base = (
        stat_h1.merge(
            plan_h1,
            on=["cutoff_date", "product_id", "sales_org_id", "target_month"],
            how="inner",
            validate="one_to_one",
        )
        .merge(
            actual_monthly,
            on=["product_id", "sales_org_id", "target_month"],
            how="inner",
            validate="many_to_one",
        )
    )

    denominator = base["stat_qty"].abs().replace(0, np.nan)
    base["override_pct"] = (base["plan_qty"] - base["stat_qty"]) / denominator
    base["is_meaningful_override"] = base["override_pct"].abs() >= MEANINGFUL_OVERRIDE_THRESHOLD
    base["machine_err"] = (base["actual_qty"] - base["stat_qty"]).abs()
    base["planner_err"] = (base["actual_qty"] - base["plan_qty"]).abs()
    base["fva"] = base["machine_err"] - base["planner_err"]
    base["planner_helped"] = base["fva"] > 0

    base = base.sort_values(
        ["cutoff_date", "product_id", "sales_org_id", "target_month"]
    ).reset_index(drop=True)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    base.to_parquet(output, index=False)
    global _fva_df
    _fva_df = base
    return base


def _get_fva_df() -> pd.DataFrame:
    global _fva_df
    if _fva_df is None:
        if not FVA_BASE_PATH.exists():
            _fva_df = build_fva_base(FVA_BASE_PATH)
        else:
            _fva_df = pd.read_parquet(FVA_BASE_PATH)
    return _fva_df


def _wape(error: pd.Series, actual: pd.Series) -> float:
    denominator = actual.abs().sum()
    return float(error.sum() / denominator) if denominator else float("nan")


def get_replay_chart_data() -> pd.DataFrame:
    """Return one row per historical cutoff for the real two-line replay."""
    df = _get_fva_df()
    rows: list[dict[str, object]] = []
    for cutoff, group in df.groupby("cutoff_date", observed=True):
        rows.append({
            "cutoff_date": cutoff,
            "mae_machine": float(group["machine_err"].mean()),
            "mae_planner": float(group["planner_err"].mean()),
            "wape_machine": _wape(group["machine_err"], group["actual_qty"]),
            "wape_planner": _wape(group["planner_err"], group["actual_qty"]),
            "n_rows": int(len(group)),
            "pct_helped": float(group["planner_helped"].mean()),
        })
    return pd.DataFrame(rows).sort_values("cutoff_date").reset_index(drop=True)


def get_cycle_detail(cutoff_date) -> pd.DataFrame:
    df = _get_fva_df()
    cutoff = pd.Timestamp(cutoff_date)
    return df[df["cutoff_date"] == cutoff].copy()


def get_headline_stats() -> dict[str, object]:
    """Return defensible, method-labelled statistics for slides and UI."""
    df = _get_fva_df()
    meaningful = df[df["is_meaningful_override"]]
    return {
        "method": "H+1 full-month comparison; actuals aggregated across channels",
        "cutoffs": int(df["cutoff_date"].nunique()),
        "total_rows": int(len(df)),
        "exact_override_share": float((df["plan_qty"] != df["stat_qty"]).mean()),
        "meaningful_override_threshold": MEANINGFUL_OVERRIDE_THRESHOLD,
        "meaningful_override_share": float(df["is_meaningful_override"].mean()),
        "median_abs_meaningful_override_pct": float(meaningful["override_pct"].abs().median()),
        "downward_share_meaningful": float((meaningful["override_pct"] < 0).mean()),
        "pct_helped_all": float(df["planner_helped"].mean()),
        "pct_helped_meaningful": float(meaningful["planner_helped"].mean()),
        "mae_machine": float(df["machine_err"].mean()),
        "mae_planner": float(df["planner_err"].mean()),
        "wape_machine": _wape(df["machine_err"], df["actual_qty"]),
        "wape_planner": _wape(df["planner_err"], df["actual_qty"]),
    }
