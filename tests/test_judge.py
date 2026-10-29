"""The judge: verdicts, refusals, replay only, never blocking, kappa, and the record command."""

import asyncio
import fnmatch
import hashlib
import json
import re
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from typer.testing import CliRunner

from cairn import audit, judge, live
from cairn.app import create_app
from cairn.cli import app
from cairn.decisions import EXAMPLE, enumerate_slots, example_decisions
from cairn.gateway import DEFAULT_MODEL, LLMGateway, Mode
from cairn.judge import EXAMPLE_SENTENCE
from cairn.judge_cases import CASES_PATH as CASES
from cairn.judge_cases import load_cases
from cairn.recording import ReplayClient, recording_path
from cairn.render import render_sentence
from cairn.workflow import (
    build_graph,
    build_ledger,
    draft_key,
    draft_sections,
    final_ledger,
    final_sentences,
    gather_state,
    sections_of,
)

FIXTURES = Path(__file__).parent / "fixtures" / "recordings"
AUTHOR, REVIEWER = "A. Author", "R. Reviewer"


def reply(
    verdict: str = "overstated",
    category: str = "causal",
    reason: str = "It claims cause.",
    stop: str = "tool_use",
) -> dict[str, Any]:
    block = {
        "type": "tool_use",
        "id": "t1",
        "name": "judge_verdict",
        "input": {"verdict": verdict, "category": category, "reason": reason},
    }
    return {
        "stop_reason": stop,
        "content": [block],
        "usage": {"input_tokens": 1000, "output_tokens": 100},
    }


class Fake:
    """A client that answers every call with one reply."""

    def __init__(self, response: dict[str, Any]):
        self.response = response
        self.calls: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


def ask(response: dict[str, Any]) -> dict[str, str]:
    gateway = LLMGateway(Mode.RECORD, client=Fake(response))
    return judge.judge_sentence(gateway, "A sentence.", "facts")


def test_judge_returns_one_structured_verdict_from_another_model() -> None:
    fake = Fake(reply())
    result = judge.judge_sentence(LLMGateway(Mode.RECORD, client=fake), "A sentence.", "facts")
    assert (result["verdict"], result["category"], result["reason"]) == (
        "overstated",
        "causal",
        "It claims cause.",
    )
    sent = fake.calls[0]
    assert sent["tool_choice"] == {"type": "tool", "name": "judge_verdict"}
    assert sent["tools"][0]["strict"] is True
    assert "A sentence." in sent["messages"][0]["content"]
    assert judge.JUDGE_MODEL != DEFAULT_MODEL


def test_judge_drops_a_reason_with_a_digit_and_keeps_the_verdict() -> None:
    result = ask(reply(reason="It says 10 of 10."))
    assert (result["verdict"], result["category"], result["reason"]) == ("overstated", "causal", "")


@pytest.mark.parametrize(
    "response",
    [
        reply(stop="refusal"),
        reply(stop="max_tokens"),
        {**reply(), "content": []},
        reply(verdict="maybe"),
        reply(category="other"),
    ],
    ids=["refusal", "truncated", "no tool", "bad verdict", "bad category"],
)
def test_judge_gives_not_judged_rather_than_a_verdict(response: dict[str, Any]) -> None:
    result = ask(response)
    assert result["verdict"] == judge.NOT_JUDGED
    assert result["category"] == result["reason"] == ""


def test_judge_replay_without_a_recording_is_not_judged(tmp_path: Path) -> None:
    result = judge.replay_judge(tmp_path, "Never recorded.", "facts")
    assert result["verdict"] == judge.NOT_JUDGED and result["id"].startswith("J-")


def save_recording(directory: Path, sentence: str, facts: str, response: dict[str, Any]) -> None:
    key = judge.judge_key(sentence, facts)
    data = {
        "source": "fixture",
        "question_id": key.question_id,
        "prompt_version": key.prompt_version,
        "tool_schema_sha256": key.tool_schema_sha256,
        "model": key.model,
        "calls": [{"response": response}],
    }
    recording_path(directory, key.question_id).write_text(json.dumps(data), encoding="utf-8")


def test_judge_replay_serves_the_recording_and_goes_stale_with_the_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_recording(tmp_path, "A sentence.", "facts", reply())
    assert judge.replay_judge(tmp_path, "A sentence.", "facts")["verdict"] == "overstated"
    assert judge.replay_judge(tmp_path, "Another.", "facts")["verdict"] == judge.NOT_JUDGED
    client = ReplayClient.load(tmp_path, judge.judge_key("A sentence.", "facts"))
    assert client.recording["prompt_version"] == judge.JUDGE_PROMPT_VERSION
    monkeypatch.setattr(judge, "JUDGE_PROMPT_VERSION", "judge-2")
    assert judge.replay_judge(tmp_path, "A sentence.", "facts")["verdict"] == judge.NOT_JUDGED
    monkeypatch.undo()
    monkeypatch.setitem(judge.JUDGE_TOOL, "description", "changed")
    assert judge.replay_judge(tmp_path, "A sentence.", "facts")["verdict"] == judge.NOT_JUDGED


JUDGE_PROMPT_SHA256 = "64726a535bfa50cf700b38c9bc1578669c1c0fc78cec9022a3dd00ccbf47e70c"


def test_judge_prompt_is_pinned_to_its_version() -> None:
    raw = (Path(judge.__file__).parent / "prompts" / "judge.md").read_bytes()
    digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    assert (judge.JUDGE_PROMPT_VERSION, digest) == ("judge-1", JUDGE_PROMPT_SHA256), (
        "judge prompt changed: bump JUDGE_PROMPT_VERSION and re-record"
    )


@pytest.mark.parametrize(
    ("labels", "predictions", "expected"),
    [
        (["a", "a", "b", "b"], ["a", "a", "b", "b"], 1.0),
        (["a", "a", "b", "b"], ["a", "b", "b", "b"], 0.5),  # 0.75 agree, 0.5 by chance
        (["a", "b", "a", "b"], ["a", "a", "b", "b"], 0.0),  # agreement is chance alone
        (["a", "a", "b", "b"], ["b", "b", "a", "a"], -1.0),
        (["a", "a", "a", "a"], ["a", "a", "a", "a"], 1.0),  # one class only
    ],
)
def test_kappa_on_hand_computed_examples(
    labels: list[str], predictions: list[str], expected: float
) -> None:
    assert judge.kappa(labels, predictions) == pytest.approx(expected)


def test_judge_summary_counts_only() -> None:
    results = [
        {"verdict": "supported"},
        {"verdict": "overstated"},
        {"verdict": judge.NOT_JUDGED},
    ]
    assert judge.summary(results) == {"sentences": 3, "judged": 2, "warnings": 1}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The API with its draft and judge recordings in a temporary folder."""
    folder = tmp_path / "recordings"
    folder.mkdir()
    shutil.copy(FIXTURES / "draft.json", folder / "draft.json")
    monkeypatch.setattr(sys.modules["cairn.web.threads"], "RECORDINGS_DIR", folder)
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    with TestClient(create_app()) as test_client:
        test_client.folder = folder  # type: ignore[attr-defined]
        yield test_client


def walk(client: TestClient) -> dict[str, Any]:
    """Start, record the example decisions and confirm; returns the thread at approval."""
    thread = client.post("/api/threads", json={"author": AUTHOR}).json()
    path = f"/api/threads/{thread['thread_id']}"
    decisions = [
        {
            "dec_id": s["slot"],
            "treatment_related_from": EXAMPLE[s["sex"], s["finding"]][0],
            "adverse_from": EXAMPLE[s["sex"], s["finding"]][1],
        }
        for s in thread["slots"]
    ]
    client.post(f"{path}/decisions", json={"actor": AUTHOR, "decisions": decisions})
    done = client.post(f"{path}/confirm", json={"actor": REVIEWER, "confirmed": ["F", "M"]})
    assert done.status_code == 200
    body: dict[str, Any] = done.json()
    return body


def filled_state() -> Any:
    state = gather_state()
    model = "opus-4-6"
    replay = ReplayClient.load(FIXTURES, draft_key(model))
    state["sections"] = draft_sections(state, LLMGateway(Mode.REPLAY, client=replay), model)
    slots = enumerate_slots(build_ledger(state))
    state["decisions"] = [d.model_dump() for d in example_decisions(slots, "A", "2026-10-28")]
    state["confirmed"] = ["F", "M"]
    return state


def example_facts() -> dict[str, str]:
    """Each final sentence of the example walkthrough with the facts the judge is shown."""
    return dict(final_sentences(filled_state()))


def test_judge_warns_never_blocks(client: TestClient) -> None:
    unjudged = walk(client)
    assert {j["verdict"] for j in unjudged["judge"]} == {judge.NOT_JUDGED}  # no recordings yet
    sentences = [j["sentence"] for j in unjudged["judge"]]
    assert " ".join(sentences) == unjudged["final"]["text"]
    facts = example_facts()
    folder = client.folder  # type: ignore[attr-defined]
    save_recording(folder, sentences[0], facts[sentences[0]], reply("overstated", "causal"))
    save_recording(folder, sentences[1], facts[sentences[1]], reply("supported", "none", "Fine."))
    body = walk(client)
    verdicts = [j["verdict"] for j in body["judge"]]
    assert verdicts[:2] == ["overstated", "supported"]
    assert set(verdicts[2:]) == {judge.NOT_JUDGED}
    assert body["final"]["ok"] and body["final"] == unjudged["final"]  # a warning changes nothing
    done = client.post(f"/api/threads/{body['thread_id']}/approve", json={"actor": REVIEWER})
    assert done.status_code == 200 and done.json()["approved_by"] == REVIEWER
    saver = client.app.state.saver  # type: ignore[attr-defined]
    assert client.portal is not None
    rows = client.portal.call(audit.entries, saver.conn, body["thread_id"])
    judged = next(r for r in rows if r["action"] == "judge_run")
    assert judged["actor"] == judge.JUDGE_MODEL
    assert judged["payload"] == {"sentences": len(verdicts), "judged": 2, "warnings": 1}
    assert audit.verify_chain(rows).ok


def test_judge_node_skips_a_draft_that_fails_the_rules(tmp_path: Path) -> None:
    async def run() -> list[dict[str, str]]:
        replay = ReplayClient.load(FIXTURES, draft_key("opus-4-6"))
        async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "w.db")) as saver:
            graph = build_graph(
                LLMGateway(Mode.REPLAY, client=replay), "opus-4-6", saver, judge_dir=FIXTURES
            )
            config: Any = {"configurable": {"thread_id": "t"}}
            await graph.ainvoke({"author": "A"}, config)
            await graph.ainvoke(Command(resume={"decisions": [], "confirmed": []}), config)
            values = (await graph.aget_state(config)).values
            assert values["final"]["ok"] is False
            judged: list[dict[str, str]] = values["judge"]
            return judged

    assert asyncio.run(run()) == []


def stub_client(recording_labels: dict[str, str]) -> Any:
    """A Bedrock stand-in that judges by the label of the case whose sentence it is shown."""

    class Client:
        class messages:
            @staticmethod
            def create(**kwargs: Any) -> dict[str, Any]:
                text = kwargs["messages"][0]["content"]
                verdict = next((v for s, v in recording_labels.items() if s in text), "supported")
                return reply(verdict, "causal" if verdict == "overstated" else "none")

    return Client


def labels_of(cases: list[dict[str, Any]]) -> dict[str, str]:
    return {c["sentence"]: "supported" if c["label"] == "faithful" else "overstated" for c in cases}


def test_record_judge_saves_within_the_ceiling_and_writes_kappa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = live.judge_inputs(CASES, FIXTURES)
    assert len(inputs.cases) == 24 and len(inputs.items) > 24
    assert EXAMPLE_SENTENCE in [sentence for sentence, _ in inputs.items]
    monkeypatch.setattr(live, "make_client", lambda mode: stub_client(labels_of(inputs.cases)))
    result = tmp_path / "e5_result.json"
    report = live.record_judge(inputs, tmp_path, result_path=result)
    assert report.saved == len(inputs.items) and not report.stopped
    assert report.kappa == pytest.approx(1.0)
    saved = json.loads(result.read_text(encoding="utf-8"))
    assert (saved["n"], saved["kappa"], saved["judge"]) == (24, 1.0, "sonnet-4-6")
    one = json.loads(next(tmp_path.glob("j-*.json")).read_text(encoding="utf-8"))
    assert (
        one["source"] == "bedrock" and one["region"] == "eu-west-1" and one["calls"][0]["cost_usd"]
    )
    stopped = live.record_judge(inputs, tmp_path, result_path=result, budget=report.spent)
    assert "ceiling would pass" in stopped.stopped and stopped.saved == 0


def test_record_judge_command_prints_the_ceiling_first_and_the_spend_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = load_cases(CASES)
    monkeypatch.setattr(live, "make_client", lambda mode: stub_client(labels_of(cases)))
    shutil.copy(FIXTURES / "draft.json", tmp_path / "draft.json")
    args = ["record-judge", "--recordings", str(tmp_path), "--result", str(tmp_path / "r.json")]
    done = CliRunner().invoke(app, args)
    assert done.exit_code == 0, done.output
    lines = done.output.splitlines()
    assert re.fullmatch(r"ceiling: \d+\.\d{2} USD more for \d+ sentences, .*", lines[0])
    assert any(re.fullmatch(r"spent: \d\.\d{4} USD", line) for line in lines)
    assert any(line.startswith("kappa: 1.0000") for line in lines)
    wrong = {c["sentence"]: "supported" for c in cases}  # a judge that never warns
    monkeypatch.setattr(live, "make_client", lambda mode: stub_client(wrong))
    low = CliRunner().invoke(app, args)
    assert low.exit_code == 1 and "kappa: 0.0000" in low.output


def test_record_judge_has_no_model_option_and_the_judge_always_uses_its_own() -> None:
    refused = CliRunner().invoke(app, ["record-judge", "--model", "opus-4-6"])
    assert refused.exit_code == 2  # unknown option: a recording cannot use the drafter's model


def test_one_recording_pattern_matches_the_files_a_judge_recording_is_saved_as(
    tmp_path: Path,
) -> None:
    name = recording_path(tmp_path, judge.item_id("A sentence.", "facts")).name
    assert fnmatch.fnmatch(name, judge.RECORDING_PATTERN)
    assert not fnmatch.fnmatch("draft.json", judge.RECORDING_PATTERN)


def test_the_kappa_file_is_found_from_the_repo_root_not_the_working_directory() -> None:
    assert judge.KAPPA_PATH.is_absolute()
    assert Path(__file__).parents[1] / "data" / "judge" / "e5_result.json" == judge.KAPPA_PATH


def test_final_sentences_are_checked_on_the_ledger_verify_final_uses() -> None:
    state = filled_state()
    ledger = final_ledger(state)
    assert [text for text, _ in final_sentences(state)] == [
        render_sentence(s, ledger) for s in sections_of(state)
    ]
