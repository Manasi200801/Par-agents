"""
Supply / Ops agent — reads stock_on_hand, purchase_orders, suppliers, production_data.
"""

import pandas as pd
from compass.contracts import DecisionContext, Signal
from compass.loader import load_stock_on_hand, load_purchase_orders, load_suppliers, load_production_data

_stock      = None
_pos        = None
_suppliers  = None
_production = None


def _load():
    global _stock, _pos, _suppliers, _production
    if _stock is None:
        _stock      = load_stock_on_hand()
        _pos        = load_purchase_orders()
        _suppliers  = load_suppliers()
        _production = load_production_data()


def get_signals(ctx: DecisionContext) -> list:
    _load()
    signals = []
    _stock_snapshot = None  # (stock df row, cover_weeks) for fallback

    # Signal 1: stock cover weeks
    stock = _stock[
        (_stock['product_id']   == ctx.product_id) &
        (_stock['sales_org_id'] == ctx.sales_org_id)
    ].sort_values('date').tail(1)

    if len(stock) > 0:
        stock_qty   = stock.iloc[0]['stock_qty_bu']
        weekly_rate = ctx.machine_value / 4.0
        cover_weeks = stock_qty / weekly_rate if weekly_rate > 0 else 0
        _stock_snapshot = (stock, cover_weeks)
        if cover_weeks < 3:
            signals.append(Signal(
                agent_name    = "Supply / Ops",
                claim         = (
                    f"Stock cover is only {cover_weeks:.1f} weeks at current demand rate. "
                    f"A downward override risks a stockout if demand comes in higher."
                ),
                direction     = "contradicts_override" if ctx.override_value < ctx.machine_value else "neutral",
                magnitude     = max(0.0, (3 - cover_weeks) / 3),
                confidence    = 0.85,
                table         = "stock_on_hand",
                evidence_rows = stock[['date', 'stock_qty_bu', 'stock_value_eur']].to_dict('records'),
            ))

    # Signal 2: supplier OTIF for this product
    supplier_pos = _pos[_pos['product_id'] == ctx.product_id].copy()
    if len(supplier_pos) > 0:
        scored = supplier_pos.dropna(subset=['actual_delivery_week', 'expected_delivery_week'])
        if len(scored) > 0:
            scored = scored.copy()
            scored['on_time'] = scored['actual_delivery_week'] <= scored['expected_delivery_week']
            otif = scored['on_time'].mean()
            if otif < 0.8:
                signals.append(Signal(
                    agent_name    = "Supply / Ops",
                    claim         = (
                        f"Supplier OTIF for this SKU is {otif:.0%}. "
                        f"Late deliveries are common — raising the forecast may not be fulfillable."
                    ),
                    direction     = "contradicts_override" if ctx.override_value > ctx.machine_value else "neutral",
                    magnitude     = (0.8 - otif),
                    confidence    = 0.75,
                    table         = "purchase_orders",
                    evidence_rows = scored[['po_id', 'expected_delivery_week',
                                            'actual_delivery_week', 'on_time']].tail(5).to_dict('records'),
                ))

    # Signal 3: production output vs planned for this product
    prod = _production[_production['product_id'] == ctx.product_id].sort_values('period_month').tail(3)
    if len(prod) > 0:
        prod = prod.copy()
        prod['attainment'] = prod['actual_output'] / prod['planned_output'].replace(0, float('nan'))
        avg_attainment = prod['attainment'].mean()
        if avg_attainment < 0.9 and ctx.override_value > ctx.machine_value:
            signals.append(Signal(
                agent_name    = "Supply / Ops",
                claim         = (
                    f"Production attainment for this SKU is {avg_attainment:.0%} "
                    f"over the last {len(prod)} months. "
                    f"Raising the forecast may create unfulfillable demand."
                ),
                direction     = "contradicts_override",
                magnitude     = (0.9 - avg_attainment),
                confidence    = 0.7,
                table         = "production_data",
                evidence_rows = prod[['period_month', 'planned_output', 'actual_output']].to_dict('records'),
            ))

    # Fallback: always surface supply status so the panel is never silent
    if len(signals) == 0:
        if _stock_snapshot is not None:
            s_df, cw = _stock_snapshot
            signals.append(Signal(
                agent_name    = "Supply / Ops",
                claim         = (
                    f"Stock cover is {cw:.1f} weeks at the machine forecast rate — "
                    f"no supply constraint identified for this override."
                ),
                direction     = "neutral",
                magnitude     = 0.1,
                confidence    = 0.8,
                table         = "stock_on_hand",
                evidence_rows = s_df[['date', 'stock_qty_bu', 'stock_value_eur']].to_dict('records'),
            ))
        else:
            signals.append(Signal(
                agent_name    = "Supply / Ops",
                claim         = "No stock data found for this product — supply status unverified.",
                direction     = "neutral",
                magnitude     = 0.0,
                confidence    = 0.3,
                table         = "stock_on_hand",
                evidence_rows = [],
            ))

    return signals
