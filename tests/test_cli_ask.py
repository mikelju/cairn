"""Laptop commands over a fake client: no network, no AWS, no credentials."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from cairn import live
from cairn.cli import app
from cairn.gateway import MODEL_PROFILES
from cairn.loop import STUDY_TOOLS, tool_definitions
from cairn.questions import QUESTIONS

runner = CliRunner()


class Script:
    def __init__(self, replies: list[dict[str, Any]]):
        self.replies = replies
        self.calls: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.replies[min(len(self.calls), len(self.replies)) - 1]


def use(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    block = {"type": "tool_use", "id": "t1", "name": name, "input": arguments}
    usage = {"input_tokens": 100, "output_tokens": 10}
    return {"stop_reason": "tool_use", "content": [block], "usage": usage}


ANSWER = use(
    "write_answer",
    {
        "sentences": [
            {
                "parts": [
                    {"type": "text", "text": "Examined: "},
                    {"type": "ref", "obs_id": "O1", "field": "n_examined"},
                ]
            }
        ]
    },
)
REPLIES = [use("run_job", {"kind": "validate_study"}), use("incidence", {}), ANSWER]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Script:
    script = Script(REPLIES)
    monkeypatch.setattr(live, "make_client", lambda mode: script)
    return script


def test_record_writes_file_then_ask_replays_it(fake: Script, tmp_path: Path) -> None:
    done = runner.invoke(app, ["record", "Q2", "--recordings", str(tmp_path)])
    assert done.exit_code == 0, done.output
    assert "ceiling:" in done.output
    assert (tmp_path / "q2.json").is_file()
    saved = json.loads((tmp_path / "q2.json").read_text(encoding="utf-8"))
    assert saved["source"] == "bedrock" and saved["region"].startswith("eu-")
    fake.calls.clear()
    replay = runner.invoke(app, ["ask", "Q2", "--recordings", str(tmp_path)])
    assert replay.exit_code == 0, replay.output
    assert "status: answered" in replay.output
    assert "rules fired: []" in replay.output
    assert "Examined: " in replay.output
    assert fake.calls == []  # replay never touches the client


def test_ask_replay_missing_recording_and_free_text(tmp_path: Path) -> None:
    missing = runner.invoke(app, ["ask", "Q2", "--recordings", str(tmp_path)])
    assert missing.exit_code == 1 and "stale recording" in missing.output
    free = runner.invoke(app, ["ask", "anything goes", "--recordings", str(tmp_path)])
    assert free.exit_code == 2


def test_ask_live_uses_the_client(fake: Script) -> None:
    done = runner.invoke(app, ["ask", "My own question", "--live"])
    assert done.exit_code == 0, done.output
    assert fake.calls[0]["messages"][0]["content"] == "My own question"


def test_record_rejects_free_text_and_stops_at_budget(
    fake: Script, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert runner.invoke(app, ["record", "free text"]).exit_code == 2
    report = live.record_questions(["Q2", "Q6"], tmp_path, "opus-5-5", budget=1.0, spent=0.5)
    assert report.saved == [] and "stopped before Q2" in report.stopped
    assert live.record_ceiling("opus-5-5", 2) < live.BUDGET_USD


class Failing:
    """Fails for one profile with a 400, a rejection and a quota error, answers the others."""

    def __init__(self) -> None:
        self.messages = self
        self.n = 0

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.n += 1
        if self.n == 1:
            error = RuntimeError("tools.0.strict: schema not supported")
            error.status_code = 400  # type: ignore[attr-defined]
            raise error
        if self.n == 2:
            return {"stop_reason": "refusal", "content": [], "usage": {"input_tokens": 5}}
        if self.n == 3:
            error = RuntimeError("Too many requests")
            error.status_code = 429  # type: ignore[attr-defined]
            raise error
        text = {"type": "text", "text": "ok"}
        return {"stop_reason": "end_turn", "content": [text], "usage": {"input_tokens": 5}}


def test_smoke_writes_evidence_and_survives_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(live, "make_client", lambda mode: Failing())
    out = tmp_path / "evidence" / "bedrock-smoke.json"
    done = runner.invoke(app, ["smoke", "--output", str(out)])
    assert done.exit_code == 0, done.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [p["model"] for p in data["profiles"]] == list(MODEL_PROFILES)
    first = data["profiles"][0]["calls"]
    assert "400" in str(first[0]["status_code"]) and first[0]["error"]
    assert first[1]["refusal"] is True
    assert first[2]["quota_error"] is True
    assert all(len(p["calls"]) == 3 for p in data["profiles"])


def test_smoke_question_sends_the_real_strict_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = Script([use("run_job", {"kind": "validate_study"})])
    monkeypatch.setattr(live, "make_client", lambda mode: script)
    live.smoke(tmp_path / "s.json")
    assert script.calls[0]["tools"] == tool_definitions()


def test_no_web_module_imports_the_live_client() -> None:
    root = Path(__file__).parents[1] / "src" / "cairn"
    web = [*(root / "web").rglob("*.py"), root / "app.py"]
    for path in web:
        text = path.read_text(encoding="utf-8")
        assert "cairn.live" not in text and "from cairn import live" not in text, path
        assert "build_client" not in text and "AnthropicBedrock" not in text, path


def _walk(node: Any, path: str = "") -> list[str]:
    problems: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            if node.get("additionalProperties") is not False:
                problems.append(f"{path}: additionalProperties is not false")
            if sorted(node.get("required", [])) != sorted(node.get("properties", {})):
                problems.append(f"{path}: not all properties are required")
        for key in ("default", "title", "oneOf", "discriminator"):
            if key in node:
                problems.append(f"{path}: has {key}")
        if node.get("additionalProperties") is True:
            problems.append(f"{path}: open object")
        for key, value in node.items():
            problems += _walk(value, f"{path}/{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            problems += _walk(item, f"{path}/{index}")
    return problems


def test_tool_schemas_are_strict_compatible() -> None:
    definitions = tool_definitions()
    assert [d["name"] for d in definitions][:-1] == list(STUDY_TOOLS)
    for definition in definitions:
        assert definition["strict"] is True
        assert _walk(definition["input_schema"], definition["name"]) == []
    run_job = definitions[0]["input_schema"]["properties"]
    assert "params" not in run_job and QUESTIONS
