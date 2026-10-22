"""Published per-token prices in one table, and the cost of a call."""

# USD per million tokens (input, output).
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "opus-4-6": (5.0, 25.0),
    "sonnet-4-6": (3.0, 15.0),
}


def call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the cost in USD of one call, or raise KeyError for an unpriced model."""
    input_price, output_price = PRICES_PER_MTOK[model]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
