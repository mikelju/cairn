"""Generic workflow evals: every case file in workflow_cases/ names a workflow and its drafts.

A case gives sections and the verify rules that must fail (none when it must pass), checked
against the ledger the workflow gathers. A workflow without pauses also runs its whole graph
against its recordings, with no pause and no model call beyond the draft.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from cairn.gateway import DEFAULT_MODEL, LLMGateway, Mode
from cairn.recording import ReplayClient, recorded_model
from cairn.workflow import build_graph, draft_key, gather_state, load_workflow, verify_final

CASES = Path(__file__).parent / "workflow_cases"
FIXTURES = Path(__file__).parents[1] / "fixtures" / "recordings"
REAL = Path(__file__).parents[2] / "recordings"
FILES = sorted(CASES.glob("*.json"))
CASE_PARAMS = [
    pytest.param(file.stem, case, id=f"{file.stem}-{case['name']}")
    for file in FILES
    for case in json.loads(file.read_text("utf-8"))
]
NO_PAUSE = [file.stem for file in FILES if not load_workflow(file.stem).pauses]


@pytest.mark.parametrize(("name", "case"), CASE_PARAMS)
def test_workflow_eval_case_fails_exactly_its_rules(name: str, case: dict[str, Any]) -> None:
    workflow = load_workflow(name)
    state = {**gather_state(workflow), "sections": case["sections"]}
    verdict = verify_final(state, workflow)
    assert verdict.rules == case["expect_rules"], [str(f) for f in verdict.failures]


@pytest.mark.parametrize("name", NO_PAUSE)
@pytest.mark.parametrize("directory", [FIXTURES, REAL], ids=["fixture", "real"])
def test_workflow_eval_full_graph_runs_without_pause(
    name: str, directory: Path, tmp_path: Path
) -> None:
    workflow = load_workflow(name)
    if not (directory / f"{workflow.recording.lower()}.json").is_file():
        pytest.skip("no recording in this folder")
    model = recorded_model(directory, workflow.recording, DEFAULT_MODEL)
    client = ReplayClient.load(directory, draft_key(model, workflow))
    gateway = LLMGateway(Mode.REPLAY, client=client)
    config: Any = {"configurable": {"thread_id": "t1"}}

    async def scenario() -> None:
        async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "w.db")) as saver:
            graph = build_graph(gateway, model, saver, workflow)
            await graph.ainvoke({"author": "Author A"}, config)
            snapshot = await graph.aget_state(config)
            assert snapshot.next == ()
            assert snapshot.values["final"]["ok"], snapshot.values["final"]["failures"]
            assert "judge" not in snapshot.values
            assert client.position == 1

    asyncio.run(scenario())
