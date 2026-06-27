"""
Finance / Margin agent — reads business_plan, cost_breakdown, tariff_reference, price_changes.
"""

import pandas as pd
from compass.contracts import DecisionContext, Signal
from compass.loader import load_business_plan, load_cost_breakdown, load_tariff_reference, load_price_changes

_plan    = None
_costs   = None
_tariffs = None
_prices  = None


def _load():
    global _plan, _costs, _tariffs, _prices
    if _plan is None:
        _plan    = load_business_plan()
        _costs   = load_cost_breakdown()
        _tariffs = load_tariff_reference()
        _prices  = load_price_changes()


def _get_unit_price(product_id: str, sales_org_id: str, channel_id: str) -> float:
    """Return latest list price for this product; fall back to cost-based estimate."""
    if _prices is None:
        return None
    ph = _prices[
        (_prices["product_id"]   == product_id) &
        (_prices["sales_org_id"] == sales_org_id) &
        (_prices["channel_id"]   == channel_id)
    ].sort_values("effective_month")
    if len(ph) > 0:
        return float(ph.iloc[-1]["price_eur_per_pcs"])

    # Broader fallback: same product any org
    ph2 = _prices[_prices["product_id"] == product_id].sort_values("effective_month")
    if len(ph2) > 0:
        return float(ph2.iloc[-1]["price_eur_per_pcs"])
    return None


def get_signals(ctx: DecisionContext) -> list:
    _load()
    signals = []

    # Signal 1: override delta vs. business plan
    plan_rows = _plan[
        (_plan["business_unit"] == ctx.business_unit) &
        (_plan["sales_org_id"]  == ctx.sales_org_id)
    ]
    if len(plan_rows) > 0:
        latest_cut  = plan_rows["cutoff_date"].max()
        latest_plan = plan_rows[plan_rows["cutoff_date"] == latest_cut]
        plan_revenue = latest_plan["planned_revenue_eur"].sum()

        price = _get_unit_price(ctx.product_id, ctx.sales_org_id, ctx.channel_id)
        if price is not None and price > 0:
            override_delta_rev = (ctx.override_value - ctx.machine_value) * price
            price_note = f"at list price €{price:.2f}/unit"
        else:
            # No price data found — skip revenue signal to avoid fabricated numbers
            override_delta_rev = None
            price_note = None

        if override_delta_rev is not None and plan_revenue > 0 and abs(override_delta_rev) > plan_revenue * 0.05:
            signals.append(Signal(
                agent_name    = "Finance / Margin",
                claim         = (
                    f"This override shifts estimated revenue by ~€{override_delta_rev:,.0f} "
                    f"({price_note}). "
                    f"Business plan for {ctx.business_unit} × {ctx.sales_org_id} "
                    f"is €{plan_revenue:,.0f}/month."
                ),
                direction     = "contradicts_override",
                magnitude     = min(abs(override_delta_rev / plan_revenue), 1.0),
                confidence    = 0.6,
                table         = "business_plan",
                evidence_rows = latest_plan[["period_month", "planned_revenue_eur",
                                              "planned_gross_margin_eur"]].head(3).to_dict("records"),
            ))

    # Signal 2: tariff trend for this product category
    # Compare average rate across regions between the latest and previous effective date.
    tariff_rows = _tariffs[_tariffs["product_category"] == ctx.category].copy()
    if len(tariff_rows) >= 2:
        dates = sorted(tariff_rows["effective_date"].unique())
        if len(dates) >= 2:
            latest_date = dates[-1]
            prev_date   = dates[-2]
            latest_avg  = tariff_rows[tariff_rows["effective_date"] == latest_date]["tariff_rate_pct"].mean()
            prev_avg    = tariff_rows[tariff_rows["effective_date"] == prev_date]["tariff_rate_pct"].mean()
            if latest_avg > prev_avg * 1.10:  # at least 10% relative increase
                signals.append(Signal(
                    agent_name    = "Finance / Margin",
                    claim         = (
                        f"Average tariff rate for {ctx.category} rose from "
                        f"{prev_avg:.2f}% to {latest_avg:.2f}% "
                        f"({prev_date} → {latest_date}). "
                        f"Import cost pressure is increasing."
                    ),
                    direction     = "neutral",
                    magnitude     = float((latest_avg - prev_avg) / max(prev_avg, 0.01)),
                    confidence    = 0.9,
                    table         = "tariff_reference",
                    evidence_rows = tariff_rows[tariff_rows["effective_date"] == latest_date][
                        ["sourcing_region", "tariff_rate_pct", "effective_date"]
                    ].to_dict("records"),
                ))

    return signals
