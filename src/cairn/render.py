"""The deterministic renderer: numbers and study terms come from references, not the model."""

from collections.abc import Callable
from typing import Any

from cairn.content import ObservationLedger, Sentence, Text, UnresolvedRef, ValueRef

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
    if value is None:
        raise UnresolvedRef("the reference points to no value (for example a group not examined)")
    raise UnresolvedRef(f"value of type {type(value).__name__} cannot be formatted")


def render_parts(sentence: Sentence, place: Callable[[ValueRef], str]) -> str:
    """Join the parts of a sentence exactly as the renderer does: no separator, in order."""
    return "".join(part.text if isinstance(part, Text) else place(part) for part in sentence.parts)


def render_sentence(sentence: Sentence, ledger: ObservationLedger) -> str:
    return render_parts(sentence, lambda ref: format_value(ledger.resolve(ref)))


def render(sentences: list[Sentence], ledger: ObservationLedger) -> str:
    """Render the sentences in order, one space between them."""
    return " ".join(render_sentence(sentence, ledger) for sentence in sentences)
