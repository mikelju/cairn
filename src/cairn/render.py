"""The deterministic renderer: numbers and study terms come from references, not the model."""

from typing import Any

from cairn.content import ObservationLedger, Sentence, Text, UnresolvedRef

THOUSAND = 1000


def format_value(value: Any) -> str:
    """Format a resolved value by its type; anything else has no format."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.0f}" if abs(value) >= THOUSAND else f"{value:.1f}"
    if isinstance(value, str):
        return value
    raise UnresolvedRef(f"value of type {type(value).__name__} cannot be formatted")


def render_sentence(sentence: Sentence, ledger: ObservationLedger) -> str:
    pieces = [
        part.text if isinstance(part, Text) else format_value(ledger.resolve(part))
        for part in sentence.parts
    ]
    return "".join(pieces)


def render(sentences: list[Sentence], ledger: ObservationLedger) -> str:
    """Render the sentences in order, one space between them."""
    return " ".join(render_sentence(sentence, ledger) for sentence in sentences)
