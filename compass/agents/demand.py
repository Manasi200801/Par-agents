"""
Demand agent — reads future_order_book, customers, returns.
"""

import pandas as pd
from compass.contracts import DecisionContext, Signal
from compass.loader import load_future_order_book, load_customers, load_returns

_order_book = None
_customers  = None
_returns    = None


def _load():
    global _order_book, _customers, _returns
    if _order_book is None:
        _order_book = load_future_order_book()
        _customers  = load_customers()
        _returns    = load_returns()


def get_signals(ctx: DecisionContext) -> list:
    _load()
    signals = []

    # Signal 1: confirmed orders for this product × sales_org
    orders = _order_book[
        (_order_book['product_id']   == ctx.product_id) &
        (_order_book['sales_org_id'] == ctx.sales_org_id)
    ]
    confirmed = orders[orders['status'] == 'confirmed']
    if len(confirmed) > 0:
        total_confirmed = confirmed['confirmed_qty'].sum()
        direction = "supports_override" if total_confirmed < ctx.machine_value else "contradicts_override"
        signals.append(Signal(
            agent_name    = "Demand",
            claim         = (
                f"{len(confirmed)} confirmed orders in {ctx.sales_org_id} total "
                f"{int(total_confirmed)} units "
                f"({'below' if total_confirmed < ctx.machine_value else 'above'} "
                f"machine forecast of {int(ctx.machine_value)})."
            ),
            direction     = direction,
            magnitude     = min(abs(total_confirmed - ctx.machine_value) / max(ctx.machine_value, 1), 1.0),
            confidence    = 0.9,
            table         = "future_order_book",
            evidence_rows = confirmed[['customer_id', 'confirmed_qty', 'status',
                                       'requested_delivery_week']].head(5).to_dict('records'),
        ))

    # Signal 2: declining customers in this org
    declining = _customers[
        (_customers['sales_org_id'] == ctx.sales_org_id) &
        (_customers['is_declining']  == True)
    ]
    if len(declining) > 0:
        direction = "supports_override" if ctx.override_value < ctx.machine_value else "contradicts_override"
        signals.append(Signal(
            agent_name    = "Demand",
            claim         = f"{len(declining)} customer(s) in {ctx.sales_org_id} are flagged as declining.",
            direction     = direction,
            magnitude     = 0.4,
            confidence    = 0.6,
            table         = "customers",
            evidence_rows = declining[['customer_id', 'customer_name', 'segment']].head(3).to_dict('records'),
        ))

    # Signal 3: recent returns for this product in this org
    recent_returns = _returns[
        (_returns['product_id']   == ctx.product_id) &
        (_returns['sales_org_id'] == ctx.sales_org_id)
    ].tail(10)
    if len(recent_returns) > 0:
        total_return_qty = recent_returns['return_qty'].sum()
        top_reason = recent_returns['return_reason'].mode()
        top_reason_str = top_reason.iloc[0] if len(top_reason) > 0 else "n/a"
        signals.append(Signal(
            agent_name    = "Demand",
            claim         = (
                f"{len(recent_returns)} recent return events for this SKU: "
                f"{int(total_return_qty)} units returned. "
                f"Top reason: {top_reason_str}."
            ),
            direction     = "supports_override" if ctx.override_value < ctx.machine_value else "neutral",
            magnitude     = 0.3,
            confidence    = 0.5,
            table         = "returns",
            evidence_rows = recent_returns[['return_reason', 'return_qty', 'date']].head(3).to_dict('records'),
        ))

    return signals
