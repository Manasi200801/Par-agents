"""
Finance / Margin agent — reads business_plan, cost_breakdown, tariff_reference.
"""

import pandas as pd
from compass.contracts import DecisionContext, Signal
from compass.loader import load_business_plan, load_cost_breakdown, load_tariff_reference

_plan    = None
_costs   = None
_tariffs = None


def _load():
    global _plan, _costs, _tariffs
    if _plan is None:
        _plan    = load_business_plan()
        _costs   = load_cost_breakdown()
        _tariffs = load_tariff_reference()


def get_signals(ctx: DecisionContext) -> list:
    _load()
    signals = []

    # Signal 1: override delta vs. business plan
    plan_rows = _plan[
        (_plan['business_unit'] == ctx.business_unit) &
        (_plan['sales_org_id']  == ctx.sales_org_id)
    ]
    if len(plan_rows) > 0:
        latest_cut  = plan_rows['cutoff_date'].max()
        latest_plan = plan_rows[plan_rows['cutoff_date'] == latest_cut]
        plan_revenue = latest_plan['planned_revenue_eur'].sum()
        # rough revenue delta: use average price from price_changes if available
        price_approx = 10.0
        override_delta_rev = (ctx.override_value - ctx.machine_value) * price_approx
        if plan_revenue > 0 and abs(override_delta_rev) > plan_revenue * 0.05:
            signals.append(Signal(
                agent_name    = "Finance / Margin",
                claim         = (
                    f"This override shifts estimated revenue by ~€{override_delta_rev:,.0f}. "
                    f"Business plan for {ctx.business_unit} × {ctx.sales_org_id} "
                    f"is €{plan_revenue:,.0f}/month."
                ),
                direction     = "contradicts_override",
                magnitude     = min(abs(override_delta_rev / plan_revenue), 1.0),
                confidence    = 0.5,
                table         = "business_plan",
                evidence_rows = latest_plan[['period_month', 'planned_revenue_eur',
                                              'planned_gross_margin_eur']].head(3).to_dict('records'),
            ))

    # Signal 2: tariff trend for this product category
    tariff_rows = _tariffs[
        _tariffs['product_category'] == ctx.category
    ].sort_values('effective_date')
    if len(tariff_rows) >= 2:
        latest = tariff_rows.iloc[-1]['tariff_rate_pct']
        prev   = tariff_rows.iloc[-2]['tariff_rate_pct']
        if latest > prev:
            signals.append(Signal(
                agent_name    = "Finance / Margin",
                claim         = (
                    f"Tariff rate for {ctx.category} rose from {prev:.1%} to {latest:.1%} "
                    f"as of {tariff_rows.iloc[-1]['effective_date']}. "
                    f"Cost pressure is increasing."
                ),
                direction     = "neutral",
                magnitude     = float(latest - prev),
                confidence    = 0.95,
                table         = "tariff_reference",
                evidence_rows = tariff_rows.tail(3)[['sourcing_region', 'tariff_rate_pct',
                                                      'effective_date']].to_dict('records'),
            ))

    return signals
