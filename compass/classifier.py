"""
Reason classifier — maps planner free text to a fixed taxonomy class.
Uses Claude Haiku: cheap, fast, runs on every override.
"""

import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment

TAXONOMY = [
    "promotion",            # campaign, sale, discount event
    "competitor_exit",      # rival closing, losing capacity, shutting down
    "competitor_entry",     # new rival entering the market
    "trade_show_event",     # industry event, conference, exhibition
    "channel_overstock",    # customer has too much stock, will order less
    "channel_understock",   # customer running low, urgent reorder expected
    "price_change",         # own price increase or decrease
    "supply_constraint",    # supplier issue, material shortage, delay
    "macro_signal",         # economic indicator, currency move, regulation, tariff
    "other",                # anything that doesn't fit above
]

_SYSTEM = (
    "You classify demand-planning override reasons into exactly one category.\n"
    "Categories: " + ", ".join(TAXONOMY) + "\n"
    "Reply with ONLY the category name. No explanation. No punctuation."
)


def classify_reason(reason_text: str) -> str:
    """
    Takes free-text reason from planner.
    Returns exactly one string from TAXONOMY.
    Falls back to 'other' if Haiku returns something unexpected.
    """
    if not reason_text or not reason_text.strip():
        return "other"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        system=_SYSTEM,
        messages=[{"role": "user", "content": reason_text}],
    )
    result = response.content[0].text.strip().lower().replace(" ", "_")
    return result if result in TAXONOMY else "other"
