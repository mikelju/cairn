"""Recording tests: replay, stale checks, a record round trip and file metadata. No network."""

import json
from pathlib import Path
from typing import Any

import pytest

from cairn.gateway import LLMGateway, Mode
from cairn.pricing import call_cost
from cairn.recording import (
    RecordingClient,
    RecordingKey,
    ReplayClient,
    StaleRecording,
    metadata_problems,
    tool_schema_hash,
    total_cost,
)

FIXTURES = Path(__file__).parent / "fixtures" / "recordings"
TOOLS = [{"name": "run_job", "input_schema": {"type": "object"}}]


class FakeMessages:
    def create(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 1000, "output_tokens": 200},
        }


class FakeClient:
    messages = FakeMessages()


def make_key(**changes: str) -> RecordingKey:
    fields = {
        "question_id": "Q9",
        "prompt_version": "v1",
        "tool_schema_sha256": tool_schema_hash(TOOLS),
        "model": "opus-4-6",
    }
    fields.update(changes)
    return RecordingKey(**fields)


def record(directory: Path) -> Path:
    client = RecordingClient(FakeClient(), make_key(), region="eu-west-1")
    LLMGateway(Mode.RECORD, client=client).create("opus-4-6", [{"role": "user", "content": "q"}])
    return client.save(directory)


def test_replay_fixture_serves_stored_call() -> None:
    key = RecordingKey("QFIX", "fixture-1", "fixture", "opus-4-6")
    gateway = LLMGateway(Mode.REPLAY, client=ReplayClient.load(FIXTURES, key))
    result = gateway.create("opus-4-6", [])
    assert result.content[0]["text"] == "fixture reply"


def test_replay_stale_missing_file(tmp_path: Path) -> None:
    with pytest.raises(StaleRecording, match="stale recording: run make record"):
        ReplayClient.load(tmp_path, make_key())


@pytest.mark.parametrize(
    "change",
    [{"prompt_version": "v2"}, {"tool_schema_sha256": "other"}, {"model": "sonnet-4-6"}],
    ids=["prompt_version", "tool_schema", "model"],
)
def test_replay_stale_changed_key(tmp_path: Path, change: dict[str, str]) -> None:
    record(tmp_path)
    ReplayClient.load(tmp_path, make_key())
    with pytest.raises(StaleRecording, match="stale recording: run make record"):
        ReplayClient.load(tmp_path, make_key(**change))


def test_replay_stale_more_calls_than_recorded(tmp_path: Path) -> None:
    record(tmp_path)
    client = ReplayClient.load(tmp_path, make_key())
    gateway = LLMGateway(Mode.REPLAY, client=client)
    gateway.create("opus-4-6", [])
    with pytest.raises(StaleRecording):
        gateway.create("opus-4-6", [])


def test_record_round_trip(tmp_path: Path) -> None:
    path = record(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["source"] == "bedrock"
    assert data["region"] == "eu-west-1"
    assert data["calls"][0]["cost_usd"] == pytest.approx(call_cost("opus-4-6", 1000, 200))
    assert metadata_problems(data, require_bedrock=True) == []
    replayed = LLMGateway(Mode.REPLAY, client=ReplayClient(data)).create("opus-4-6", [])
    assert replayed.content == [{"type": "text", "text": "ok"}]
    assert total_cost(data) == pytest.approx(0.01)


def test_tool_schema_hash_is_stable_and_sensitive() -> None:
    assert tool_schema_hash(TOOLS) == tool_schema_hash([dict(reversed(TOOLS[0].items()))])
    assert tool_schema_hash(TOOLS) != tool_schema_hash([{"name": "other"}])


def test_pricing_cost() -> None:
    assert call_cost("sonnet-4-6", 1_000_000, 1_000_000) == pytest.approx(18.0)
    with pytest.raises(KeyError):
        call_cost("unknown", 1, 1)


def test_metadata_rejects_fixture_and_non_eu_as_real() -> None:
    fixture = json.loads((FIXTURES / "qfix.json").read_text(encoding="utf-8"))
    assert metadata_problems(fixture, require_bedrock=False) == []
    assert "source is not bedrock" in metadata_problems(fixture, require_bedrock=True)
    assert total_cost(fixture) is None
    broken = {"source": "bedrock", "region": "us-east-1", "calls": [{}]}
    problems = metadata_problems(broken, require_bedrock=True)
    assert "region is not an EU region" in problems
    assert "missing model" in problems
    assert "call 0 missing cost_usd" in problems
    assert "no calls" in metadata_problems({}, require_bedrock=False)


REAL_DIR = Path(__file__).parents[1] / "recordings"
REAL_FILES = sorted(REAL_DIR.glob("*.json")) if REAL_DIR.is_dir() else []


@pytest.mark.parametrize("path", REAL_FILES or [None], ids=lambda p: getattr(p, "name", "none"))
def test_recordings_metadata_real_files(path: Path | None) -> None:
    if path is None:
        return  # no real recordings yet: increment 8 adds them
    data = json.loads(path.read_text(encoding="utf-8"))
    assert metadata_problems(data, require_bedrock=True) == []


def test_replay_stale_real_q2_q6_under_the_current_prompt() -> None:
    """Increment 14 re-records Q2 and Q6; until then the real files are stale under question-6."""
    from cairn import live
    from cairn.loop import PROMPT_VERSION

    for name in ("q2.json", "q6.json"):
        data = json.loads((REAL_DIR / name).read_text(encoding="utf-8"))
        assert data["prompt_version"] != PROMPT_VERSION
    for question in ("Q2", "Q6"):
        with pytest.raises(StaleRecording):
            live.ask_replay(question, REAL_DIR, "opus-4-6")


def test_every_fixture_matches_the_current_prompt_version_and_schema_hash() -> None:
    from cairn.loop import PROMPT_VERSION, schema_hash

    for folder in (FIXTURES, FIXTURES.parent / "recordings_real_shape"):
        for path in sorted(folder.glob("q*.json")):
            if path.name == "qfix.json":
                continue  # the loop-independent stand-in has its own version
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["source"] == "fixture", path
            assert data["prompt_version"] == PROMPT_VERSION, path
            assert data["tool_schema_sha256"] == schema_hash(), path
