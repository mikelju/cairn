"""E3: agent behaviour in replay. Tools, arguments and refusals per question, offline.

Each question replays the committed recording through the real loop. A real recording in
`recordings/` wins when it is not stale; otherwise the fixture recording stands in. The
expectations are per question, not per recording content, so the real recordings that arrive
in increment 14 are judged by the same table.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from cairn.content import QuoteRef, Text
from cairn.live import ask_replay
from cairn.loop import ANSWER_TOOL, FIRST_TOOL, LoopResult, LoopStatus
from cairn.passages import load_passages
from cairn.questions import QUESTIONS
from cairn.recording import StaleRecording

ROOT = Path(__file__).parents[2]
REAL = ROOT / "recordings"
FIXTURES = ROOT / "tests" / "fixtures" / "recordings"
MODEL = "opus-4-6"
STUDY = {"study_design", "incidence", "body_weight_change", "tk_summary"}
BODY_WEIGHT_POPULATIONS = {"main_and_recovery", "main"}

pytestmark = pytest.mark.usefixtures("block_sockets")


@dataclass(frozen=True)
class Expect:
    """What the loop must do for one question."""

    required: dict[str, dict[str, Any]] = field(default_factory=dict)  # tool -> arguments subset
    allowed: frozenset[str] = frozenset()  # tools besides run_job and write_answer
    doc: str = ""  # a guideline question quotes this guideline document


EXPECT: dict[str, Expect] = {
    "Q1": Expect({"run_job": {"kind": "validate_study"}}, frozenset(STUDY)),
    "Q2": Expect({"run_job": {"kind": "validate_study"}, "incidence": {}}, frozenset(STUDY)),
    "Q3": Expect({"body_weight_change": {"sex": "F"}}, frozenset(STUDY)),
    "Q4": Expect({"tk_summary": {"sex": "M", "dose": 20, "day": 1}}, frozenset(STUDY)),
    "Q5": Expect({"run_job": {"kind": "validate_study"}}, frozenset(STUDY)),
    "Q6": Expect(allowed=frozenset(STUDY)),
    "Q7": Expect(allowed=frozenset(STUDY)),
    "Q8": Expect(allowed=frozenset({"body_weight_change", "study_design", "search_guidance"})),
    "G1": Expect({"search_guidance": {}}, frozenset({"search_guidance"}), "ich-m4sr2"),
    "G2": Expect({"search_guidance": {}}, frozenset({"search_guidance"}), "fda-2005"),
    "G3": Expect({"search_guidance": {}}, frozenset({"search_guidance"}), "ich-s9"),
}
PASSAGE_DOC = {p.passage_id: p.doc for p in load_passages()}
PASSAGE_SECTION = {p.passage_id: p.section for p in load_passages()}


def replay(question_id: str) -> LoopResult:
    """The real recording when it is current, otherwise the fixture."""
    try:
        return ask_replay(question_id, REAL, MODEL)
    except StaleRecording:
        return ask_replay(question_id, FIXTURES, MODEL)


@pytest.fixture(scope="module")
def results() -> dict[str, LoopResult]:
    return {question_id: replay(question_id) for question_id in QUESTIONS}


def tools_used(result: LoopResult) -> list[str]:
    return [step.tool for step in result.steps]


def accepted(result: LoopResult) -> bool:
    return result.status is LoopStatus.ANSWERED and result.verdict is not None and result.verdict.ok


def test_e3_covers_every_question() -> None:
    assert list(EXPECT) == list(QUESTIONS)
    assert len(QUESTIONS) == 11


@pytest.mark.parametrize("question_id", list(QUESTIONS))
def test_e3_run_job_first_and_expected_tools(
    question_id: str, results: dict[str, LoopResult]
) -> None:
    result, expect = results[question_id], EXPECT[question_id]
    used = tools_used(result)
    if used:  # a question the model declines outright calls nothing
        assert used[0] == FIRST_TOOL
    called = {tool: [s.arguments for s in result.steps if s.tool == tool] for tool in used}
    for tool, wanted in expect.required.items():
        assert tool in called, f"{question_id} never called {tool}"
        assert any(
            all(arguments.get(k) == v for k, v in wanted.items()) for arguments in called[tool]
        ), f"{question_id}: {tool} arguments {called[tool]} lack {wanted}"
    assert set(used) <= {FIRST_TOOL, ANSWER_TOOL} | expect.allowed


@pytest.mark.parametrize("question_id", ["Q1", "Q2", "Q3", "Q4", "Q5", "G1", "G2", "G3"])
def test_e3_answers_pass_the_verifier(question_id: str, results: dict[str, LoopResult]) -> None:
    result = results[question_id]
    assert result.status is LoopStatus.ANSWERED
    assert result.verdict is not None and result.verdict.ok, result.verdict
    assert result.rendered


def test_e3_q6_is_never_accepted_as_asked(results: dict[str, LoopResult]) -> None:
    """Deviation D3: declining in plain text counts; a drafted claim must be blocked."""
    result = results["Q6"]
    assert result.status in (LoopStatus.DECLINED, LoopStatus.ANSWERED)
    assert not accepted(result)
    if result.status is LoopStatus.ANSWERED:
        assert result.verdict is not None and 6 in result.verdict.rules


def test_e3_q7_is_declined_as_clinical_advice(results: dict[str, LoopResult]) -> None:
    result = results["Q7"]
    assert result.status is LoopStatus.DECLINED
    assert ANSWER_TOOL not in tools_used(result)
    assert result.rendered is None


def test_e3_q8_never_includes_tk_animals_in_the_means(results: dict[str, LoopResult]) -> None:
    """Approved criterion (D109): the schema rejects it or the model declines and explains."""
    result = results["Q8"]
    body_weight = [s for s in result.steps if s.tool == "body_weight_change"]
    succeeded = [s for s in body_weight if s.obs_id is not None]
    rejected = [s for s in body_weight if s.error and "population" in s.error]
    # No successful call used a population that could include TK satellite animals.
    assert all(
        s.arguments.get("population", "main_and_recovery") in BODY_WEIGHT_POPULATIONS
        for s in succeeded
    )
    assert all(s.obs_id is None for s in rejected)
    if rejected:
        return
    if result.status is LoopStatus.DECLINED:
        assert result.message
        return
    # No rejection happened: the answer must say that TK animals are not included.
    assert result.status is LoopStatus.ANSWERED and result.rendered
    text = result.rendered.lower()
    assert "tk" in text and ("not support" in text or "excluded" in text)


@pytest.mark.parametrize("question_id", ["G1", "G2", "G3"])
def test_e3_guidance_answers_quote_the_expected_guideline(
    question_id: str, results: dict[str, LoopResult]
) -> None:
    result = results[question_id]
    quotes = [
        part
        for sentence in result.sentences
        for part in sentence.parts
        if isinstance(part, QuoteRef)
    ]
    assert quotes, "the answer holds no QuoteRef"
    assert {PASSAGE_DOC[q.passage_id] for q in quotes} == {EXPECT[question_id].doc}
    assert all(q.passage_id in result.ledger.retrieved for q in quotes)
    if question_id == "G1":  # spec: a verbatim passage on ICH M4S(R2) section 2.6.6.3
        assert any(q.sentence_ids and PASSAGE_SECTION[q.passage_id] == "2.6.6.3" for q in quotes), (
            "G1 quotes no sentence of section 2.6.6.3"
        )
    own = [
        part.text
        for sentence in result.sentences
        for part in sentence.parts
        if isinstance(part, Text)
    ]
    assert not any(char.isdigit() for text in own for char in text)
