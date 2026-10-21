"""The model gateway: one place that builds the Bedrock client and reads every reply."""

import os
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from anthropic import AnthropicBedrock

REGION = "eu-west-1"
TIMEOUT_SECONDS = 45
MAX_RETRIES = 0

# EU inference profile IDs. Provisional: increment 7 (smoke test) confirms them.
MODEL_PROFILES: dict[str, str] = {
    "opus-5-5": "eu.anthropic.claude-opus-5-5",
    "sonnet-5-5": "eu.anthropic.claude-sonnet-5-5",
    "opus-4-8": "eu.anthropic.claude-opus-4-8",
}


class Mode(StrEnum):
    REPLAY = "replay"
    RECORD = "record"
    LIVE = "live"


class GatewayError(Exception):
    """A gateway failure: bad mode, region outside the EU, or an unknown stop reason."""


class Status(StrEnum):
    OK = "ok"
    DECLINED = "declined"
    TRUNCATED = "truncated"


@dataclass
class GatewayResult:
    """One model reply after the stop reason was read; content is empty unless status is ok."""

    status: Status
    stop_reason: str
    content: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    region: str = ""
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    message: str = ""


def mode_from_env() -> Mode:
    """Read CAIRN_LLM_MODE; replay is the default."""
    raw = os.environ.get("CAIRN_LLM_MODE", "replay").strip().lower()
    try:
        return Mode(raw)
    except ValueError:
        raise GatewayError(f"unknown CAIRN_LLM_MODE: {raw}") from None


def check_region(mode: Mode, region: str) -> None:
    if mode is not Mode.REPLAY and not region.startswith("eu-"):
        raise GatewayError(f"{mode.value} mode needs an EU region, got {region}")


def build_client(mode: Mode, region: str = REGION) -> AnthropicBedrock | None:
    """Build the Bedrock client for record or live; replay builds none."""
    check_region(mode, region)
    if mode is Mode.REPLAY:
        return None
    return AnthropicBedrock(aws_region=region, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)


def as_dict(value: Any) -> Any:
    """Turn an SDK model into plain data; dicts pass through."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


class LLMGateway:
    """Calls messages.create (never streaming) and reads stop_reason before any content."""

    def __init__(self, mode: Mode | None = None, client: Any = None, region: str = REGION):
        self.mode = mode or mode_from_env()
        check_region(self.mode, region)
        self.region = region
        self.client = client if client is not None else build_client(self.mode, region)

    def create(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> GatewayResult:
        if self.client is None:
            raise GatewayError("no client: replay needs a recording client")
        if model not in MODEL_PROFILES:
            raise GatewayError(f"unknown model: {model}")
        kwargs: dict[str, Any] = {
            "model": MODEL_PROFILES[model],
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or {"type": "auto"}
        started = time.monotonic()
        response = as_dict(self.client.messages.create(**kwargs))
        latency = time.monotonic() - started
        stop_reason = response.get("stop_reason")
        usage = as_dict(response.get("usage") or {})
        result = GatewayResult(
            status=Status.OK,
            stop_reason=str(stop_reason),
            model=model,
            region=self.region,
            latency_s=latency,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
        if stop_reason == "refusal":
            result.status = Status.DECLINED
            result.message = "the model declined"
        elif stop_reason == "max_tokens":
            result.status = Status.TRUNCATED
            result.message = "the model output was cut off and discarded"
        elif stop_reason in ("tool_use", "end_turn"):
            result.content = [as_dict(block) for block in response.get("content") or []]
        else:
            raise GatewayError(f"unexpected stop_reason: {stop_reason}")
        return result
