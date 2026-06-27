import pandas as pd

FVA_BASE_PATH = "data/fva_base.parquet"

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
    })).reset_index()
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
