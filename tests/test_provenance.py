"""Provenance parts: the text is the rendered sentence, and each tag shows its source."""

import pytest

from cairn.content import (
    DecisionRef,
    ObservationLedger,
    QuoteRef,
    Sentence,
    Text,
    ValueRef,
)
from cairn.gateway import DEFAULT_MODEL, LLMGateway, Mode
from cairn.loop import PROMPT_VERSION, LoopResult, LoopStatus, ask, schema_hash
from cairn.questions import QUESTIONS
from cairn.recording import RecordingKey, ReplayClient, recorded_model
from cairn.render import render_sentence
from cairn.web import _recordings_dir
from cairn.web.provenance import (
    DataTag,
    DecisionInfo,
    DecisionTag,
    QuoteTag,
    TextPart,
    joined,
    provenance_parts,
)


def _replay(question_id: str) -> LoopResult:
    directory = _recordings_dir()
    model = recorded_model(directory, question_id, DEFAULT_MODEL)
    key = RecordingKey(question_id, PROMPT_VERSION, schema_hash(), model)
    client = ReplayClient.load(directory, key)
    return ask(QUESTIONS[question_id], LLMGateway(Mode.REPLAY, client=client), model)


@pytest.fixture(scope="module")
def answers() -> dict[str, LoopResult]:
    return {q: _replay(q) for q in QUESTIONS}


def test_joined_text_equals_the_rendered_sentence(answers: dict[str, LoopResult]) -> None:
    checked = 0
    for result in answers.values():
        if result.status is not LoopStatus.ANSWERED:
            continue
        for sentence in result.sentences:
            parts = provenance_parts(sentence, result.ledger)
            assert joined(parts) == render_sentence(sentence, result.ledger)
            checked += 1
    assert checked > 5


def test_data_chips_equal_the_marked_cell(answers: dict[str, LoopResult]) -> None:
    tags = [
        (tag, result)
        for result in answers.values()
        if result.status is LoopStatus.ANSWERED
        for sentence in result.sentences
        for tag in provenance_parts(sentence, result.ledger)
        if isinstance(tag, DataTag)
    ]
    assert tags
    for tag, _ in tags:
        row, column = tag.table.mark
        assert tag.table.rows[row][column] == tag.text
        assert tag.table.columns[column] == tag.column
        assert len(tag.table.rows) <= 12 and len(tag.table.columns) <= 8
        assert len(tag.source_rows) <= 20
        assert tag.tool and tag.population


def test_quote_tags_carry_page_and_sentence_id(answers: dict[str, LoopResult]) -> None:
    quotes = [
        tag
        for result in answers.values()
        if result.status is LoopStatus.ANSWERED
        for sentence in result.sentences
        for tag in provenance_parts(sentence, result.ledger)
        if isinstance(tag, QuoteTag)
    ]
    assert quotes
    for tag in quotes:
        assert (
            tag.page > 0
            and tag.sentence_ids
            and tag.guideline
            and tag.link.endswith(f"#page={tag.page}")
        )
        assert tag.highlight in ("", f"/highlight/{tag.sentence_ids[0]}")


def test_quote_between_text_keeps_the_rendered_spacing() -> None:
    ref = QuoteRef(passage_id="FDA-IV-01", sentence_ids=["FDA-IV-01.s2"])
    ledger = ObservationLedger()
    sentence = Sentence(parts=[Text(text="The guideline says"), ref, Text(text="and so on.")])
    parts = provenance_parts(sentence, ledger)
    assert joined(parts) == render_sentence(sentence, ledger)
    assert [type(p) for p in parts] == [TextPart, QuoteTag, TextPart]


def test_decision_tag_carries_who_role_and_value() -> None:
    ledger = ObservationLedger()
    ledger.slots = {"D1": "adverse from 100 mg/kg"}
    sentence = Sentence(parts=[Text(text="Judged:"), DecisionRef(slot="D1"), Text(text=".")])
    parts = provenance_parts(sentence, ledger, {"D1": DecisionInfo("A. Smith", "toxicologist")})
    tag = parts[1]
    assert isinstance(tag, DecisionTag)
    assert (tag.who, tag.role, tag.value) == ("A. Smith", "toxicologist", "adverse from 100 mg/kg")
    assert joined(parts) == render_sentence(sentence, ledger)


def test_top_level_field_has_a_one_cell_table() -> None:
    from cairn.tools import study_design

    ledger = ObservationLedger()
    obs_id = ledger.add(study_design())
    sentence = Sentence(
        parts=[Text(text="Population "), ValueRef(obs_id=obs_id, field="population")]
    )
    tag = provenance_parts(sentence, ledger)[-1]
    assert isinstance(tag, DataTag)
    assert tag.table.rows == [[tag.text]] and tag.table.mark == (0, 0)
