"""
FVA scoring and cycle replay — powers the Replay Dashboard.
Reads the pre-computed fva_base.parquet (never recomputes at runtime).
"""

import pandas as pd

FVA_BASE_PATH = "data/fva_base.parquet"

_fva_df = None


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
    """One row per cutoff: mae_machine, mae_planner, n_rows, pct_helped."""
    df = _get_fva_df()
    result = (
        df.groupby('cutoff_date')
        .apply(lambda g: pd.Series({
            'mae_machine': g['machine_err'].mean(),
            'mae_planner': g['override_err'].mean(),
            'n_rows':      len(g),
            'pct_helped':  (g['fva'] > 0).mean(),
        }), include_groups=False)
        .reset_index()
        .sort_values('cutoff_date')
    )
    return result


def get_cycle_detail(cutoff_date) -> pd.DataFrame:
    """All scored rows for one specific cutoff cycle."""
    df = _get_fva_df()
    return df[df['cutoff_date'] == pd.Timestamp(cutoff_date)].copy()


def get_headline_stats() -> dict:
    """Key numbers for the pitch slide."""
    df = _get_fva_df()
    up = df[df['plan_qty'] > df['stat_qty']]
    dn = df[df['plan_qty'] < df['stat_qty']]
    return {
        "total_rows":           len(df),
        "pct_helped":           float((df['fva'] > 0).mean()),
        "pct_hurt":             float((df['fva'] < 0).mean()),
        "mae_machine":          float(df['machine_err'].mean()),
        "mae_planner":          float(df['override_err'].mean()),
        "mae_change_pct":       float((df['override_err'].mean() - df['machine_err'].mean()) / df['machine_err'].mean() * 100),
        "upward_pct_helped":    float((up['fva'] > 0).mean()) if len(up) else 0.0,
        "downward_pct_helped":  float((dn['fva'] > 0).mean()) if len(dn) else 0.0,
        "upward_share":         float(len(up) / len(df)) if len(df) else 0.0,
        "downward_share":       float(len(dn) / len(df)) if len(df) else 0.0,
    }
