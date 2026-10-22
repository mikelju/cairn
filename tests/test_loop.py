"""Question loop tests over a scripted fake client: no network, no AWS."""

import json
from copy import deepcopy
from typing import Any

from cairn.gateway import LLMGateway, Mode
from cairn.loop import (
    MAX_CALLS,
    PROMPT,
    PROMPT_VERSION,
    LoopStatus,
    ask,
    schema_hash,
    tool_definitions,
)
from cairn.questions import QUESTIONS


class Script:
    def __init__(self, replies: list[dict[str, Any]]):
        self.replies = replies
        self.calls: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        index = min(len(self.calls), len(self.replies)) - 1
        return self.replies[index]


def use(name: str, arguments: dict[str, Any], ident: str = "t1") -> dict[str, Any]:
    block = {"type": "tool_use", "id": ident, "name": name, "input": arguments}
    return {"stop_reason": "tool_use", "content": [block], "usage": {"input_tokens": 5}}


def run(replies: list[dict[str, Any]], question: str = "Q?") -> tuple[Any, Script]:
    script = Script(replies)
    return ask(question, LLMGateway(Mode.LIVE, client=script)), script


JOB = use("run_job", {"kind": "validate_study"})
INCIDENCE = use("incidence", {})


def answer(*parts: dict[str, Any]) -> dict[str, Any]:
    return use("write_answer", {"sentences": [{"parts": list(parts)}]})


def ref(obs_id: str, field: str) -> dict[str, Any]:
    return {"type": "ref", "obs_id": obs_id, "field": field}


def text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value}


def test_loop_run_job_first_then_answer() -> None:
    result, script = run([JOB, INCIDENCE, answer(text("Examined: "), ref("O1", "n_examined"))])
    assert result.status is LoopStatus.ANSWERED
    assert [step.tool for step in result.steps] == ["run_job", "incidence", "write_answer"]
    assert result.verdict is not None and result.verdict.ok
    assert result.rendered and result.rendered.startswith("Examined: ")
    assert script.calls[0]["tool_choice"] == {"type": "auto"}
    assert all(call["tools"] for call in script.calls)


def test_loop_first_tool_not_run_job_is_an_error() -> None:
    replies = [INCIDENCE, JOB, INCIDENCE, answer(text("Examined: "), ref("O1", "n_examined"))]
    result, script = run(replies)
    assert result.steps[0].error and "run_job" in result.steps[0].error
    assert result.calls == 4
    first_feedback = script.calls[1]["messages"][-1]["content"][0]
    assert first_feedback["is_error"] is True
    assert result.status is LoopStatus.ANSWERED


def test_loop_cap_of_six_calls() -> None:
    result, script = run([JOB])
    assert result.status is LoopStatus.CAPPED
    assert result.calls == MAX_CALLS == len(script.calls)
    assert result.rendered is None


def test_loop_schema_error_counted_and_returned() -> None:
    bad = use("incidence", {"screen": "maybe"})
    result, script = run([JOB, bad, INCIDENCE, answer(text("Examined: "), ref("O1", "n_examined"))])
    assert result.steps[1].error
    assert result.calls == 4
    assert script.calls[2]["messages"][-1]["content"][0]["is_error"] is True
    assert result.status is LoopStatus.ANSWERED


def test_loop_answer_with_wrong_parts_is_an_error() -> None:
    bad = use("write_answer", {"sentences": [{"parts": [{"type": "number", "value": 3}]}]})
    result, _ = run([JOB, bad, JOB])
    assert result.steps[1].error and result.status is LoopStatus.CAPPED


def test_loop_only_text_ref_and_quote_parts() -> None:
    result, _ = run([JOB, INCIDENCE, answer(text("Examined: "), ref("O1", "n_examined"))])
    assert {type(part).__name__ for s in result.sentences for part in s.parts} <= {
        "Text",
        "ValueRef",
        "QuoteRef",
    }
    answer_schema = str(tool_definitions()[-1]["input_schema"])
    for kind in ("Text", "ValueRef", "QuoteRef"):
        assert kind in answer_schema


G2 = "How does the FDA 2005 guidance define the no observed adverse effect level (NOAEL)?"
NS1 = (
    "How should the no observed adverse effect level be determined "
    "and reported from a repeat-dose toxicity study?"
)
SEARCH = use("search_guidance", {"query": G2})


def quote(passage_id: str, *sentence_ids: str) -> dict[str, Any]:
    return {"type": "quote", "passage_id": passage_id, "sentence_ids": list(sentence_ids)}


def test_loop_search_guidance_feeds_the_ledger_and_rule_8_sees_it() -> None:
    from cairn.tools import call_tool

    hits = [h for h in call_tool("search_guidance", {"query": G2})["hits"] if h["rerank_score"] > 0]
    top = hits[0]
    sentence_id = top["sentences"][0]["sentence_id"]
    good, _ = run(
        [JOB, SEARCH, answer(text("Defined as: "), quote(top["passage_id"], sentence_id))]
    )
    assert top["passage_id"] in good.ledger.retrieved
    assert good.verdict is not None and 8 not in good.verdict.rules
    other = call_tool("search_guidance", {"query": NS1})["hits"]
    elsewhere = next(h for h in other if h["passage_id"] not in good.ledger.retrieved)
    stray = quote(elsewhere["passage_id"], elsewhere["sentences"][0]["sentence_id"])
    bad, _ = run([JOB, SEARCH, answer(text("Defined as: "), stray)])
    assert bad.verdict is not None and 8 in bad.verdict.rules


def test_loop_hits_below_the_threshold_are_not_shown_to_the_model() -> None:
    from cairn import retrieval
    from cairn.tools import call_tool

    output = call_tool("search_guidance", {"query": G2})
    cut = sorted(h["rerank_score"] for h in output["hits"])[2]  # keeps the top three
    original = retrieval.load_threshold
    retrieval.load_threshold = lambda *a, **k: cut
    try:
        result, script = run([JOB, SEARCH, answer(text("Done."))])
    finally:
        retrieval.load_threshold = original
    returned = json.loads(
        next(
            block["content"]
            for message in script.calls[-1]["messages"]
            if isinstance(message["content"], list)
            for block in message["content"]
            if block.get("type") == "tool_result" and "hits" in str(block["content"])
        )
    )
    shown = {hit["passage_id"] for hit in returned["hits"]}
    expected = {h["passage_id"] for h in output["hits"] if h["rerank_score"] >= cut}
    assert shown == expected and len(shown) < len(output["hits"])
    assert set(result.ledger.retrieved) == expected


def test_loop_digit_rejected_before_rendering() -> None:
    result, _ = run([JOB, INCIDENCE, answer(text("Seen in 3 animals: "), ref("O1", "n_examined"))])
    assert result.status is LoopStatus.REJECTED
    assert result.rendered is None and result.verdict is None
    assert "digit" in result.message


def test_loop_rule_failure_carried_to_result() -> None:
    result, _ = run(
        [JOB, answer(text("The compound is safe: "), ref("O1", "n_examined"))],
        QUESTIONS["Q6"],
    )
    assert result.status is LoopStatus.ANSWERED
    assert result.verdict is not None and not result.verdict.ok
    assert result.rendered is None


def test_loop_model_sees_only_short_ids() -> None:
    result, script = run([JOB, INCIDENCE, answer(text("Examined: "), ref("O1", "n_examined"))])
    shown = str(script.calls[2]["messages"][-1]["content"][0]["content"])
    assert '"id": "O1"' in shown
    assert result.ledger.observations[0].obs_id not in shown


def test_loop_declined_and_truncated_end_the_loop() -> None:
    declined = {"stop_reason": "refusal", "content": [], "usage": {}}
    result, _ = run([declined])
    assert result.status is LoopStatus.DECLINED and result.rendered is None
    cut = {"stop_reason": "max_tokens", "content": [text("x")], "usage": {}}
    result, _ = run([JOB, cut])
    assert result.status is LoopStatus.TRUNCATED and result.calls == 2


def test_loop_exposes_prompt_version_and_schema_hash() -> None:
    result, _ = run([JOB])
    assert result.prompt_version == PROMPT_VERSION
    assert result.tool_schema_sha256 == schema_hash()
    assert all(definition["strict"] for definition in tool_definitions())
    assert "run_job" in PROMPT


def test_loop_incidence_screen_hidden_and_default_applies() -> None:
    definition = next(d for d in tool_definitions() if d["name"] == "incidence")
    assert "screen" not in definition["input_schema"]["properties"]
    assert "screen" not in definition["input_schema"]["required"]
    result, _ = run([JOB, INCIDENCE, answer(text("Examined: "), ref("O1", "n_examined"))])
    incidence = result.ledger.observations[0]
    assert incidence.kind == "incidence_screen"


def test_loop_text_only_end_turn_is_declined() -> None:
    chatter = {"stop_reason": "end_turn", "content": [text("Let me think.")], "usage": {}}
    result, script = run([JOB, chatter])
    assert result.status is LoopStatus.DECLINED and result.rendered is None
    assert result.message == "the model declined" and len(script.calls) == 2


def test_loop_tool_exception_returns_to_the_model_and_counts() -> None:
    bad = use("run_job", {"kind": "validate"})  # a valid string the job runner does not know
    result, script = run([bad, JOB, INCIDENCE, answer(text("Examined: "), ref("O1", "n_examined"))])
    assert result.steps[0].error and "unknown job kind" in result.steps[0].error
    feedback = script.calls[1]["messages"][-1]["content"][0]
    assert feedback["is_error"] is True and "tool error" in feedback["content"]
    assert result.calls == 4
    assert result.status is LoopStatus.ANSWERED


def test_loop_failed_run_job_does_not_unlock_other_tools() -> None:
    bad = use("run_job", {"kind": "validate"})
    result, _ = run([bad, INCIDENCE, bad])
    assert result.steps[1].error and "first tool call must be run_job" in result.steps[1].error
    assert result.status is LoopStatus.CAPPED and result.calls == MAX_CALLS
