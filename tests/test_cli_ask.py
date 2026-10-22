"""Laptop commands over a fake client: no network, no AWS, no credentials."""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from cairn import live
from cairn.cli import app
from cairn.gateway import DEFAULT_MODEL, MAX_TOKENS, MODEL_PROFILES
from cairn.loop import STUDY_TOOLS, tool_definitions
from cairn.pricing import call_cost
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
    report = live.record_questions(["Q2", "Q6"], tmp_path, "opus-4-6", budget=1.0, spent=0.5)
    assert report.saved == [] and "stopped before Q2" in report.stopped
    assert live.record_ceiling("opus-4-6", 2) < live.BUDGET_USD


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


class Raising:
    """Answers the first calls from a script, then fails like the SDK would."""

    def __init__(self, replies: list[dict[str, Any]], fail_after: int, error: Exception):
        self.script = Script(replies)
        self.messages = self
        self.fail_after = fail_after
        self.error = error

    def create(self, **kwargs: Any) -> dict[str, Any]:
        if len(self.script.calls) >= self.fail_after:
            raise self.error
        return self.script.create(**kwargs)


def _prior(tmp_path: Path) -> Path:
    path = tmp_path / "q2.json"
    path.write_text("previous recording", encoding="utf-8")
    return path


def test_record_does_not_overwrite_on_truncated_capped_or_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prior = _prior(tmp_path)
    cut = {"stop_reason": "max_tokens", "content": [], "usage": {"input_tokens": 5}}
    for client in (Script([cut]), Script([REPLIES[0]]), Raising([], 0, RuntimeError("403 denied"))):
        monkeypatch.setattr(live, "make_client", lambda mode, client=client: client)
        done = runner.invoke(app, ["record", "Q2", "--recordings", str(tmp_path)])
        assert done.exit_code == 1, done.output
        assert "not saved: Q2" in done.output or "error:" in done.output
        assert "spent:" in done.output
        assert prior.read_text(encoding="utf-8") == "previous recording"


def test_record_prints_each_status_and_saves_a_declined_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    refusal = {"stop_reason": "refusal", "content": [], "usage": {"input_tokens": 5}}
    monkeypatch.setattr(live, "make_client", lambda mode: Script([refusal]))
    done = runner.invoke(app, ["record", "Q6", "--recordings", str(tmp_path)])
    assert done.exit_code == 0, done.output
    assert "Q6: declined" in done.output
    assert (tmp_path / "q6.json").is_file()


def test_record_midway_error_keeps_saved_files_and_reports_spending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = Raising(REPLIES, 3, RuntimeError("Too many requests"))
    monkeypatch.setattr(live, "make_client", lambda mode: client)
    done = runner.invoke(app, ["record", "Q2", "Q6", "--recordings", str(tmp_path)])
    assert done.exit_code == 1, done.output
    assert (tmp_path / "q2.json").is_file() and not (tmp_path / "q6.json").exists()
    assert "Q2: answered" in done.output and "saved" in done.output
    assert "error: Q6: RuntimeError: Too many requests" in done.output
    assert "spent:" in done.output


def test_ask_live_sdk_error_is_a_plain_message(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Raising([], 0, RuntimeError("403 not available"))
    monkeypatch.setattr(live, "make_client", lambda mode: client)
    done = runner.invoke(app, ["ask", "My own question", "--live"])
    assert done.exit_code == 1
    assert "error: RuntimeError: 403 not available" in done.output
    assert "Traceback" not in done.output


def test_unknown_model_is_a_plain_error_before_any_ceiling() -> None:
    for args in (["ask", "Q2", "--live"], ["ask", "Q2"], ["record", "Q2"]):
        done = runner.invoke(app, [*args, "--model", "x"])
        assert done.exit_code == 2, done.output
        assert "error: unknown model: x" in done.output
        assert "ceiling" not in done.output and not isinstance(done.exception, KeyError)


def test_replay_reads_the_model_from_the_recording(
    fake: Script, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    done = runner.invoke(
        app, ["record", "Q2", "--model", "sonnet-4-6", "--recordings", str(tmp_path)]
    )
    assert done.exit_code == 0, done.output
    replay = runner.invoke(app, ["ask", "Q2", "--recordings", str(tmp_path)])
    assert replay.exit_code == 0 and "status: answered" in replay.output, replay.output


def test_ceiling_uses_the_gateway_token_limit(fake: Script, tmp_path: Path) -> None:
    assert live.CEILING_OUTPUT_TOKENS == MAX_TOKENS
    runner.invoke(app, ["ask", "My own question", "--live"])
    assert fake.calls[0]["max_tokens"] == MAX_TOKENS
    expected = call_cost("opus-4-6", live.CEILING_INPUT_TOKENS, MAX_TOKENS)
    assert live.call_ceiling("opus-4-6") == pytest.approx(expected)


def test_smoke_keeps_only_the_error_type_and_masks_account_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class AccessDenied(Exception):
        status_code = 403

    message = "User: arn:aws:sts::123456789012:assumed-role/dev/x is not authorized"
    client = Raising([], 0, AccessDenied(message))
    monkeypatch.setattr(live, "make_client", lambda mode: client)
    out = tmp_path / "smoke.json"
    done = runner.invoke(app, ["smoke", "--output", str(out)])
    assert done.exit_code == 0, done.output
    text = out.read_text(encoding="utf-8")
    assert "123456789012" not in text and "arn:aws" not in text
    call = json.loads(text)["profiles"][0]["calls"][0]
    assert call["error"] == "AccessDenied" and call["status_code"] == 403
    assert live.mask_account_ids("a 123456789012 b 12345") == "a [masked] b 12345"


def test_one_source_for_the_default_model_and_the_recordings_folder() -> None:
    root = Path(__file__).parents[1] / "src" / "cairn"
    for path in root.rglob("*.py"):
        if path.name not in ("gateway.py", "pricing.py"):
            assert '"opus-4-6"' not in path.read_text(encoding="utf-8"), path
        if path.name != "recording.py":
            assert 'Path("recordings")' not in path.read_text(encoding="utf-8"), path
    assert DEFAULT_MODEL in MODEL_PROFILES
