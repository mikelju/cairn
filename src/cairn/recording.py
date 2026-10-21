"""Recordings of model calls: one JSON per question, replayed offline, written by record mode."""

import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from cairn.canonical import canonical_sha256
from cairn.gateway import MODEL_PROFILES, as_dict
from cairn.pricing import call_cost

RECORDINGS_DIR = Path("recordings")
STALE_MESSAGE = "stale recording: run make record"
CALL_FIELDS = ("latency_s", "input_tokens", "output_tokens", "cost_usd", "response")
BEDROCK_FIELDS = ("question_id", "prompt_version", "tool_schema_sha256", "model", "region", "date")


class StaleRecording(Exception):
    """The recording is missing, or one part of its key differs from the request."""

    def __init__(self, detail: str = ""):
        super().__init__(f"{STALE_MESSAGE} ({detail})" if detail else STALE_MESSAGE)


def tool_schema_hash(tools: list[dict[str, Any]]) -> str:
    """Canonical SHA-256 of the tool definitions sent to the model."""
    return canonical_sha256(tools)


@dataclass(frozen=True)
class RecordingKey:
    question_id: str
    prompt_version: str
    tool_schema_sha256: str
    model: str


def recording_path(directory: Path, question_id: str) -> Path:
    return directory / f"{question_id.lower()}.json"


def load_recording(directory: Path, key: RecordingKey) -> dict[str, Any]:
    """Load the recording for a key or raise StaleRecording."""
    path = recording_path(directory, key.question_id)
    if not path.is_file():
        raise StaleRecording(f"missing {path.name}")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    for name in ("question_id", "prompt_version", "tool_schema_sha256", "model"):
        # A fixture is a hand-written stand-in, so it carries no real model to compare.
        if name == "model" and data.get("source") == "fixture":
            continue
        if data.get(name) != getattr(key, name):
            raise StaleRecording(f"changed {name}")
    return data


class _Messages:
    def __init__(self, owner: Any):
        self.owner = owner

    def create(self, **kwargs: Any) -> dict[str, Any]:
        result: dict[str, Any] = self.owner.handle(kwargs)
        return result


class ReplayClient:
    """A client that serves the stored calls in order; the gateway cannot tell it apart."""

    def __init__(self, recording: dict[str, Any]):
        self.recording = recording
        self.position = 0
        self.messages = _Messages(self)

    @classmethod
    def load(cls, directory: Path, key: RecordingKey) -> "ReplayClient":
        return cls(load_recording(directory, key))

    def handle(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        calls = self.recording["calls"]
        if self.position >= len(calls):
            raise StaleRecording("more calls than recorded")
        call = calls[self.position]
        self.position += 1
        response: dict[str, Any] = call["response"]
        return response


class RecordingClient:
    """Wraps a real client, forwards every call and keeps what is needed to replay it."""

    def __init__(self, client: Any, key: RecordingKey, region: str):
        self.client = client
        self.key = key
        self.region = region
        self.calls: list[dict[str, Any]] = []
        self.messages = _Messages(self)

    def handle(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        response = as_dict(self.client.messages.create(**kwargs))
        latency = time.monotonic() - started
        usage = as_dict(response.get("usage") or {})
        tokens_in = int(usage.get("input_tokens", 0))
        tokens_out = int(usage.get("output_tokens", 0))
        self.calls.append(
            {
                "latency_s": round(latency, 3),
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "cost_usd": call_cost(self.key.model, tokens_in, tokens_out),
                "response": response,
            }
        )
        return response  # type: ignore[no-any-return]

    def save(self, directory: Path, source: str = "bedrock") -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = recording_path(directory, self.key.question_id)
        data = {
            "source": source,
            "question_id": self.key.question_id,
            "prompt_version": self.key.prompt_version,
            "tool_schema_sha256": self.key.tool_schema_sha256,
            "model": self.key.model,
            "model_profile": MODEL_PROFILES.get(self.key.model, ""),
            "region": self.region,
            "date": date.today().isoformat(),
            "calls": self.calls,
        }
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path


def total_cost(recording: dict[str, Any]) -> float | None:
    """Sum of the call costs, or None when the recording carries no cost (a fixture)."""
    costs = [call.get("cost_usd") for call in recording["calls"]]
    if not costs or any(cost is None for cost in costs):
        return None
    return float(sum(costs))


def metadata_problems(data: dict[str, Any], require_bedrock: bool) -> list[str]:
    """List what is wrong with a recording file; empty means it is acceptable."""
    problems = [f"missing {name}" for name in BEDROCK_FIELDS if not data.get(name)]
    calls = data.get("calls")
    if not calls:
        problems.append("no calls")
    for index, call in enumerate(calls or []):
        problems += [f"call {index} missing {n}" for n in CALL_FIELDS if n not in call]
    if require_bedrock:
        if data.get("source") != "bedrock":
            problems.append("source is not bedrock")
        if not str(data.get("region", "")).startswith("eu-"):
            problems.append("region is not an EU region")
        if total_cost(data) is None:
            problems.append("cost missing")
    return problems
