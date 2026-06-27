"""
Relevance gate — decides which agents run for each decision.
Always runs demand, supply, memory. Finance and commercial are conditional.
"""

from compass.contracts import DecisionContext


def get_relevant_agents(ctx: DecisionContext) -> list:
    """
    Returns agent names to run. Cost control: not all agents run on every decision.
    'memory' is listed here but handled separately in pipeline.py.
    """
    agents = ["demand", "supply", "memory"]

    # Finance runs if the override is large (>10% swing)
    override_pct = abs(ctx.override_value - ctx.machine_value) / max(ctx.machine_value, 1)
    if override_pct > 0.10:
        agents.append("finance")

    # Commercial runs if the reason text suggests a market or commercial event
    market_keywords = ["promot", "campaign", "price", "competitor", "launch",
                       "event", "trade", "sale", "discount", "market"]
    if any(kw in ctx.reason_text.lower() for kw in market_keywords):
        agents.append("commercial")

    return agents
