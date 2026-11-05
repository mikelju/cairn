"""Provenance parts: a rendered sentence as plain text and tags that show each piece source.

The text is exactly what `render_parts` produces; tags only add the source of each placed piece
(a study value, a guideline quotation or a person's decision). Nothing here changes the sentence.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cairn.content import (
    DecisionRef,
    ObservationLedger,
    QuoteRef,
    Sentence,
    Text,
    UnresolvedRef,
    ValueRef,
)
from cairn.highlight import highlights_by_sentence
from cairn.observation import Observation
from cairn.render import format_value, quote_data, render_parts

MAX_ROWS = 12
MAX_COLUMNS = 8
MAX_SOURCE_ROWS = 20
TOP_LEVEL = ("n_examined", "population", "kind")


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class SourceTable:
    """The group table a value came from; `mark` is the (row, column) of the used cell."""

    columns: list[str]
    rows: list[list[str]]
    mark: tuple[int, int]


@dataclass(frozen=True)
class DataTag:
    text: str
    tool: str
    column: str
    population: str
    table: SourceTable
    source_rows: list[dict[str, Any]]
    source_row_count: int
    kind: str = "data"


@dataclass(frozen=True)
class QuoteTag:
    text: str
    guideline: str
    section: str
    page: int
    citation: str
    sentence_ids: list[str]
    highlight: str  # the viewer link of the first sentence, or "" when it has none
    link: str  # the official document link
    kind: str = "quote"


@dataclass(frozen=True)
class DecisionTag:
    text: str
    slot: str
    who: str
    role: str
    value: str
    kind: str = "decision"


@dataclass(frozen=True)
class DecisionInfo:
    who: str
    role: str


Part = TextPart | DataTag | QuoteTag | DecisionTag


def _cell(value: Any) -> str:
    try:
        return format_value(value)
    except UnresolvedRef:
        return "-"


def _row_cells(row: dict[str, Any], columns: list[str]) -> list[str]:
    return [_cell(row.get(c)) for c in columns]


def _columns(row: dict[str, Any], used: str) -> list[str]:
    names = [k for k, v in row.items() if not isinstance(v, dict | list)]
    if used not in names:
        names.append(used)
    shown = names[:MAX_COLUMNS]
    if used not in shown:
        shown[-1] = used
    return shown


def _walk(
    observation: Observation, field_path: str
) -> tuple[Any, list[tuple[list[Any], int, str]]]:
    """The value and, for each list of dicts met on the way, (list, position, next key)."""
    path = field_path.removeprefix("values.")
    head, *rest = path.split(".")
    if head in TOP_LEVEL:
        return getattr(observation, head), []
    current: Any = observation.values
    rest = [head, *rest]
    lists: list[tuple[list[Any], int, str]] = []
    for position, step in enumerate(rest):
        if isinstance(current, list):
            index = int(step)
            following = rest[position + 1] if position + 1 < len(rest) else ""
            if isinstance(current[index], dict):
                lists.append((current, index, following))
            current = current[index]
        else:
            current = current[step]
    return current, lists


def _source_table(observation: Observation, field_path: str, value: Any) -> tuple[SourceTable, str]:
    """The table and used column of a value: the deepest list of dicts, else its own dict."""
    path = field_path.removeprefix("values.")
    steps = path.split(".")
    last = steps[-1]
    if steps[0] in TOP_LEVEL:
        return SourceTable([last], [[_cell(value)]], (0, 0)), last
    _, lists = _walk(observation, field_path)
    if lists:
        rows, index, column = lists[-1]
        if column == last:
            columns = _columns(rows[index], column)
            keep = list(range(min(len(rows), MAX_ROWS)))
            if index not in keep:
                keep[-1] = index
            table = [_row_cells(rows[i], columns) for i in keep]
            return SourceTable(columns, table, (keep.index(index), columns.index(column))), column
    holder: Any = observation.values
    for step in steps[:-1]:
        holder = holder[int(step)] if isinstance(holder, list) else holder[step]
    row = holder if isinstance(holder, dict) else {last: value}
    columns = _columns(row, last)
    return SourceTable(columns, [_row_cells(row, columns)], (0, columns.index(last))), last


def _data_tag(ref: ValueRef, piece: str, ledger: ObservationLedger) -> DataTag:
    observation = ledger.get(ref.obs_id)
    value, _ = _walk(observation, ref.field)
    table, column = _source_table(observation, ref.field, value)
    return DataTag(
        text=piece,
        tool=observation.tool.name,
        column=column,
        population=observation.population,
        table=table,
        source_rows=observation.source_rows[:MAX_SOURCE_ROWS],
        source_row_count=len(observation.source_rows),
    )


def _quote_tag(ref: QuoteRef, piece: str) -> QuoteTag:
    data = quote_data(ref)
    first = data["sentence_ids"][0]
    return QuoteTag(
        text=piece,
        guideline=data["guideline"],
        section=data["section"],
        page=data["page"],
        citation=data["citation"],
        sentence_ids=data["sentence_ids"],
        highlight=f"/highlight/{first}" if highlights_by_sentence().get(first) else "",
        link=data["link"],
    )


def provenance_parts(
    sentence: Sentence,
    ledger: ObservationLedger,
    decisions: Mapping[str, DecisionInfo] | None = None,
) -> list[Part]:
    """The sentence as ordered parts; their texts joined equal `render_sentence` exactly."""
    placed: list[str] = []

    def place(ref: ValueRef) -> str:
        placed.append(piece := format_value(ledger.resolve(ref)))
        return piece

    def place_quote(ref: QuoteRef) -> str:
        data = quote_data(ref)
        placed.append(piece := f"{data['text']} ({data['citation']})")
        return piece

    def place_decision(ref: DecisionRef) -> str:
        placed.append(piece := ledger.place_slot(ref))
        return piece

    full = render_parts(sentence, place, place_quote, place_decision)
    parts: list[Part] = []
    queue = iter(placed)
    cursor = 0

    def plain(text: str) -> None:
        if not text:
            return
        if parts and isinstance(parts[-1], TextPart):
            parts[-1] = TextPart(parts[-1].text + text)
        else:
            parts.append(TextPart(text))

    for part in sentence.parts:
        piece = part.text if isinstance(part, Text) else next(queue)
        if not full.startswith(piece, cursor) and full[cursor : cursor + 1] == " ":
            plain(" ")
            cursor += 1
        if isinstance(part, Text):
            plain(piece)
        elif isinstance(part, ValueRef):
            parts.append(_data_tag(part, piece, ledger))
        elif isinstance(part, QuoteRef):
            parts.append(_quote_tag(part, piece))
        else:
            info = (decisions or {}).get(part.slot, DecisionInfo("", ""))
            parts.append(DecisionTag(piece, part.slot, info.who, info.role, piece))
        cursor += len(piece)
    plain(full[cursor:])
    return parts


def joined(parts: list[Part]) -> str:
    """The plain text of the parts."""
    return "".join(p.text for p in parts)


# Digits that may stay in the text once every tag is removed: fixed headings written in code.
FIXED_DIGIT_WORDS: tuple[str, ...] = ()


def draft_parts(
    sentences: list[Sentence],
    ledger: ObservationLedger,
    decisions: Mapping[str, DecisionInfo] | None = None,
) -> list[Part]:
    """The draft body as parts: every sentence tagged, one space between sentences."""
    parts: list[Part] = []
    for index, sentence in enumerate(sentences):
        if index:
            parts.append(TextPart(" "))
        parts.extend(provenance_parts(sentence, ledger, decisions))
    return parts


def stray_digits(parts: list[Part]) -> str:
    """The digits left in the plain text once every tag and the fixed words are removed."""
    text = "".join(p.text for p in parts if isinstance(p, TextPart))
    for word in FIXED_DIGIT_WORDS:
        text = text.replace(word, "")
    return "".join(c for c in text if c.isdigit())


NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def stray_numbers(parts: list[Part]) -> int:
    """How many numbers (tokens, not digits) stay in the plain text outside every tag."""
    text = "".join(p.text for p in parts if isinstance(p, TextPart))
    for word in FIXED_DIGIT_WORDS:
        text = text.replace(word, "")
    return len(NUMBER.findall(text))


def number_tags(parts: list[Part]) -> int:
    """How many data tags show a number; a name or a unit such as RAT or mg/kg is not one."""
    return sum(isinstance(p, DataTag) and bool(re.search(r"\d", p.text)) for p in parts)


def tag_counts(parts: list[Part]) -> dict[str, int]:
    """How many tags of each kind: data, quote and decision."""
    return {
        k: sum(getattr(p, "kind", "") == k for p in parts) for k in ("data", "quote", "decision")
    }
