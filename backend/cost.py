"""
Cost calculation — pure derived data, no new capture logic.

Pricing is hardcoded here (not in the database) because it's a small,
infrequently-changing reference table, and keeping it in code makes it
version-controlled and visible in diffs when rates change.

Source: https://docs.claude.com/en/docs/about-claude/pricing (verified June 2026)
"""

# Price per token (converted from Anthropic's published "per million tokens" rate)
PRICING = {
    "claude-sonnet-4-6": {
        "input_per_token": 3.00 / 1_000_000,
        "output_per_token": 15.00 / 1_000_000,
    },
    # Add more models here as needed, e.g.:
    # "claude-haiku-4-5-20251001": {"input_per_token": 1.00 / 1_000_000, "output_per_token": 5.00 / 1_000_000},
}

DEFAULT_PRICING = {"input_per_token": 3.00 / 1_000_000, "output_per_token": 15.00 / 1_000_000}


def event_cost(event: dict) -> float:
    """Returns the dollar cost of a single event. Tool calls always cost $0."""
    if event["type"] != "llm_call":
        return 0.0

    rates = PRICING.get(event["name"], DEFAULT_PRICING)
    tokens_in = event.get("tokens_in") or 0
    tokens_out = event.get("tokens_out") or 0

    return (tokens_in * rates["input_per_token"]) + (tokens_out * rates["output_per_token"])


def run_cost_breakdown(events: list[dict]) -> dict:
    """
    Returns a full cost breakdown for a run:
      - per-event costs (in event order)
      - total cost
      - total tokens in/out
    """
    breakdown = []
    total_cost = 0.0
    total_tokens_in = 0
    total_tokens_out = 0

    for event in events:
        cost = event_cost(event)
        total_cost += cost
        total_tokens_in += event.get("tokens_in") or 0
        total_tokens_out += event.get("tokens_out") or 0

        breakdown.append({
            "event_id": event["id"],
            "type": event["type"],
            "name": event["name"],
            "tokens_in": event.get("tokens_in") or 0,
            "tokens_out": event.get("tokens_out") or 0,
            "cost_usd": round(cost, 6),
        })

    return {
        "events": breakdown,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
    }