"""Workflow tests: pauses, resume and the draft replay against fixture and real recording."""

import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from cairn.content import DecisionRef, Text
from cairn.decisions import enumerate_slots, example_decisions
from cairn.gateway import DEFAULT_MODEL, LLMGateway, Mode
from cairn.recording import ReplayClient, recorded_model
from cairn.workflow import (
    NONCLINICAL_SUMMARY,
    SECTIONS,
    State,
    build_graph,
    build_ledger,
    draft_key,
    sections_of,
    verify_final,
)

FIXTURES = Path(__file__).parent / "fixtures" / "recordings"
REAL = Path(__file__).parents[1] / "recordings"
DRAFTS = [FIXTURES, *([REAL] if (REAL / "draft.json").is_file() else [])]
CONFIG: Any = {"configurable": {"thread_id": "t1"}}


def replay_gateway(directory: Path) -> tuple[LLMGateway, str]:
    model = recorded_model(directory, "DRAFT", DEFAULT_MODEL)
    client = ReplayClient.load(directory, draft_key(model))
    return LLMGateway(Mode.REPLAY, client=client), model


def example_resume(state: State) -> dict[str, Any]:
    slots = enumerate_slots(build_ledger(state))
    decisions = example_decisions(slots, "Reviewer A", "2026-10-27T10:00:00Z")
    return {"decisions": [d.model_dump() for d in decisions], "confirmed": ["F", "M"]}


async def run_to_end(directory: Path, db: Path) -> tuple[State, LLMGateway]:
    gateway, model = replay_gateway(directory)
    async with AsyncSqliteSaver.from_conn_string(str(db)) as saver:
        graph = build_graph(gateway, model, saver)
        await graph.ainvoke({"author": "Author A"}, CONFIG)
        state = (await graph.aget_state(CONFIG)).values
        await graph.ainvoke(Command(resume=example_resume(state)), CONFIG)
        await graph.ainvoke(Command(resume={"approved_by": "Approver B"}), CONFIG)
        final: State = (await graph.aget_state(CONFIG)).values
        return final, gateway


def test_workflow_stops_at_both_pauses_and_resume_makes_no_model_call(tmp_path: Path) -> None:
    async def scenario() -> None:
        gateway, model = replay_gateway(FIXTURES)
        async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "w.db")) as saver:
            graph = build_graph(gateway, model, saver)
            await graph.ainvoke({"author": "Author A"}, CONFIG)
            snapshot = await graph.aget_state(CONFIG)
            assert snapshot.next == ("await_decisions",)
            assert snapshot.values["author"] == "Author A"
            client: Any = gateway.client
            assert client.position == 1  # the draft is the only model call
            await graph.ainvoke(None, CONFIG)  # re-invoke without a resume value
            assert (await graph.aget_state(CONFIG)).next == ("await_decisions",)
            assert client.position == 1
            state = snapshot.values
            await graph.ainvoke(Command(resume=example_resume(state)), CONFIG)
            snapshot = await graph.aget_state(CONFIG)
            assert snapshot.next == ("await_approval",)
            assert snapshot.values["final"]["ok"], snapshot.values["final"]["failures"]
            await graph.ainvoke(Command(resume={"approved_by": "Approver B"}), CONFIG)
            snapshot = await graph.aget_state(CONFIG)
            assert snapshot.next == ()
            assert snapshot.values["approved_by"] == "Approver B"
            assert client.position == 1

    asyncio.run(scenario())


def test_workflow_pauses_are_steps_of_the_workflow() -> None:
    assert set(NONCLINICAL_SUMMARY.pauses) <= set(NONCLINICAL_SUMMARY.steps)


@pytest.mark.parametrize("directory", DRAFTS, ids=lambda d: d.parent.name + "/" + d.name)
def test_workflow_draft_replay(directory: Path, tmp_path: Path) -> None:
    state, _ = asyncio.run(run_to_end(directory, tmp_path / "w.db"))
    assert list(state["sections"]) == list(SECTIONS)
    slots = enumerate_slots(build_ledger(state))
    assert len(state["sections"]["findings"]) == len(slots)
    sentences = sections_of(state)
    model_text = "".join(p.text for s in sentences for p in s.parts if isinstance(p, Text))
    assert not any(char.isdigit() for char in model_text)
    refs = [p.slot for s in sentences for p in s.parts if isinstance(p, DecisionRef)]
    expected = [s.slot for s in slots] + [f"NOAEL-{sex}" for sex in sorted({s.sex for s in slots})]
    assert sorted(refs) == sorted(expected)
    assert verify_final(state).ok
    assert state["final"]["ok"]
    assert "NOAEL, females: 20 mg/kg/day" in state["final"]["text"]


def test_verify_final_is_pure_and_unconfirmed_noael_fails(tmp_path: Path) -> None:
    state, _ = asyncio.run(run_to_end(FIXTURES, tmp_path / "w.db"))
    before = json.dumps(state, sort_keys=True, default=str)
    assert verify_final({**state, "confirmed": ["F"]}).rules == [2]
    assert verify_final({**state, "decisions": []}).rules == [2]
    assert json.dumps(state, sort_keys=True, default=str) == before


def test_record_draft_saves_a_verified_recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cairn import live

    reply = json.loads((FIXTURES / "draft.json").read_text(encoding="utf-8"))["calls"][0][
        "response"
    ]

    class Fake:
        class messages:
            @staticmethod
            def create(**kwargs: Any) -> dict[str, Any]:
                assert kwargs["tool_choice"] == {"type": "tool", "name": "write_draft"}
                return {**reply, "usage": {"input_tokens": 1000, "output_tokens": 500}}

    monkeypatch.setattr(live, "make_client", lambda mode: Fake)
    path = live.record_draft(tmp_path, "opus-4-6")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert (
        path.name == "draft.json" and saved["source"] == "bedrock" and saved["calls"][0]["cost_usd"]
    )


PROMPT_SHA256 = "2e9f9a6734308df57a2ed1d6c5ae0ff6c5ddd9aaaa4ee205b85a16438fdede2a"


def test_draft_prompt_is_pinned_to_its_version() -> None:
    from cairn import workflow

    raw = (Path(workflow.__file__).parent / "prompts" / "draft.md").read_bytes()
    digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    assert (workflow.DRAFT_PROMPT_VERSION, digest) == ("draft-1", PROMPT_SHA256), (
        "draft prompt changed: bump DRAFT_PROMPT_VERSION and re-record"
    )


def test_record_draft_command_fails_when_the_cost_passes_the_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from cairn import live
    from cairn.cli import app

    reply = json.loads((FIXTURES / "draft.json").read_text(encoding="utf-8"))["calls"][0][
        "response"
    ]

    def client(tokens: int) -> Any:
        class Fake:
            class messages:
                @staticmethod
                def create(**kwargs: Any) -> dict[str, Any]:
                    return {**reply, "usage": {"input_tokens": tokens, "output_tokens": tokens}}

        return Fake

    args = ["record-draft", "--recordings", str(tmp_path)]
    monkeypatch.setattr(live, "make_client", lambda mode: client(1000))
    cheap = CliRunner().invoke(app, args)
    assert cheap.exit_code == 0 and re.search(r"^cost: 0\.\d{4} USD$", cheap.output, re.M), cheap.output
    monkeypatch.setattr(live, "make_client", lambda mode: client(10**8))
    dear = CliRunner().invoke(app, args)
    assert dear.exit_code == 1 and "passes the ceiling" in dear.output
