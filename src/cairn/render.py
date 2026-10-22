"""The deterministic renderer: numbers and study terms come from references, not the model."""

from collections.abc import Callable
from functools import lru_cache
from typing import Any

from cairn.content import (
    ObservationLedger,
    QuoteRef,
    Sentence,
    Text,
    UnresolvedRef,
    ValueRef,
)
from cairn.guidelines import load_manifest
from cairn.passages import Passage, load_passages

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


@lru_cache(maxsize=1)
def _stored_passages() -> dict[str, Passage]:
    return {passage.passage_id: passage for passage in load_passages()}


def quote_data(ref: QuoteRef) -> dict[str, Any]:
    """The quotation of a QuoteRef as data: the stored sentences copied verbatim, with source.

    `link` is the official document link with `#page=N`, for the UI; nothing here is model text.
    """
    passage = _stored_passages().get(ref.passage_id)
    if passage is None:
        raise UnresolvedRef(f"unknown passage {ref.passage_id}")
    stored = {sentence.sentence_id: sentence.text for sentence in passage.sentences}
    if not ref.sentence_ids:
        raise UnresolvedRef(f"quotation of {ref.passage_id} names no sentence")
    missing = [sid for sid in ref.sentence_ids if sid not in stored]
    if missing:
        raise UnresolvedRef(f"unknown sentence {missing[0]} in {ref.passage_id}")
    guideline = load_manifest()["guidelines"][passage.doc]
    pages = (
        f"page {passage.page_start}"
        if passage.page_start == passage.page_end
        else f"pages {passage.page_start}-{passage.page_end}"
    )
    return {
        "passage_id": ref.passage_id,
        "sentence_ids": list(ref.sentence_ids),
        "text": " ".join(stored[sid] for sid in ref.sentence_ids),
        "guideline": guideline["title"],
        "section": passage.section,
        "page": passage.page_start,
        "citation": f"{guideline['title']}, section {passage.section}, {pages}",
        "link": f"{guideline['page_link_base']}#page={passage.page_start}",
    }


def render_quote(ref: QuoteRef) -> str:
    """The stored sentence text followed by guideline, section and page, all placed by code."""
    data = quote_data(ref)
    return f"{data['text']} ({data['citation']})"


def quotations(sentences: list[Sentence]) -> list[dict[str, Any]]:
    """Every quotation in the sentences, as data. Model text never counts, whatever it says."""
    return [quote_data(p) for s in sentences for p in s.parts if isinstance(p, QuoteRef)]


def render_parts(
    sentence: Sentence,
    place: Callable[[ValueRef], str],
    place_quote: Callable[[QuoteRef], str] = render_quote,
) -> str:
    """Join the parts in order, adding a space between text and a value only where words fuse."""
    out = ""
    previous: Text | ValueRef | QuoteRef | None = None
    for part in sentence.parts:
        if isinstance(part, Text):
            piece = part.text
        elif isinstance(part, QuoteRef):
            piece = place_quote(part)
        else:
            piece = place(part)
        mixed = isinstance(part, Text) != isinstance(previous, Text)
        quoted = isinstance(part, QuoteRef) or isinstance(previous, QuoteRef)
        fused_words = mixed and out[-1:].isalnum() and piece[:1].isalnum()
        bare = not (out[-1:].isspace() or piece[:1].isspace() or piece[:1] in ".,;:")
        if previous is not None and (fused_words or (quoted and out and bare)):
            out += " "
        out += piece
        previous = part
    return out


def render_sentence(
    sentence: Sentence,
    ledger: ObservationLedger,
    place_quote: Callable[[QuoteRef], str] = render_quote,
) -> str:
    return render_parts(sentence, lambda ref: format_value(ledger.resolve(ref)), place_quote)


def render(sentences: list[Sentence], ledger: ObservationLedger) -> str:
    """Render the sentences in order, one space between them."""
    return " ".join(render_sentence(sentence, ledger) for sentence in sentences)
