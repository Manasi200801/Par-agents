"""
Commercial / Market agent — reads marketing_spends, price_changes.
"""

import pandas as pd
from compass.contracts import DecisionContext, Signal
from compass.loader import load_marketing_spends, load_price_changes

_mkt    = None
_prices = None


def _load():
    global _mkt, _prices
    if _mkt is None:
        _mkt    = load_marketing_spends()
        _prices = load_price_changes()


def get_signals(ctx: DecisionContext) -> list:
    _load()
    signals = []

    # Signal 1: active campaigns for this category × sales_org
    campaigns = _mkt[
        (_mkt['category']     == ctx.category) &
        (_mkt['sales_org_id'] == ctx.sales_org_id)
    ].sort_values('period_month').tail(3)

    if len(campaigns) > 0:
        total_spend = campaigns['spend_eur'].sum()
        campaign_types = ', '.join(campaigns['campaign_type'].unique())
        signals.append(Signal(
            agent_name    = "Commercial / Market",
            claim         = (
                f"{len(campaigns)} recent campaign(s) for {ctx.category} in {ctx.sales_org_id}. "
                f"Total spend: €{total_spend:,.0f}. "
                f"Types: {campaign_types}."
            ),
            direction     = "supports_override" if ctx.override_value > ctx.machine_value else "neutral",
            magnitude     = 0.4,
            confidence    = 0.6,
            table         = "marketing_spends",
            evidence_rows = campaigns[['campaign_id', 'campaign_type', 'period_month',
                                       'spend_eur']].to_dict('records'),
        ))

    # Signal 2: recent price change for this product
    price_hist = _prices[
        (_prices['product_id']   == ctx.product_id) &
        (_prices['sales_org_id'] == ctx.sales_org_id) &
        (_prices['channel_id']   == ctx.channel_id)
    ].sort_values('effective_month')

    if len(price_hist) >= 2:
        latest = price_hist.iloc[-1]['price_eur_per_pcs']
        prev   = price_hist.iloc[-2]['price_eur_per_pcs']
        if prev > 0 and abs(latest - prev) / prev > 0.02:
            direction_word = "increased" if latest > prev else "decreased"
            signals.append(Signal(
                agent_name    = "Commercial / Market",
                claim         = (
                    f"List price {direction_word} from €{prev:.2f} to €{latest:.2f} "
                    f"({(latest/prev - 1):+.1%}) effective "
                    f"{price_hist.iloc[-1]['effective_month']}."
                ),
                direction     = "supports_override" if latest < prev else "contradicts_override",
                magnitude     = abs(latest - prev) / max(prev, 1),
                confidence    = 0.9,
                table         = "price_changes",
                evidence_rows = price_hist.tail(3)[['effective_month',
                                                     'price_eur_per_pcs']].to_dict('records'),
            ))

    return signals
