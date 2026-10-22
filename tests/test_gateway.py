"""Gateway tests over a fake client: no network, no AWS."""

from typing import Any

import pytest

from cairn import gateway
from cairn.gateway import GatewayError, LLMGateway, Mode, Status


class FakeMessages:
    def __init__(self, response: dict[str, Any]):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response: dict[str, Any]):
        self.messages = FakeMessages(response)


def reply(stop_reason: str, content: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "stop_reason": stop_reason,
        "content": content or [{"type": "text", "text": "hi"}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def test_gateway_config_client_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_bedrock(**kwargs: Any) -> str:
        seen.update(kwargs)
        return "client"

    monkeypatch.setattr(gateway, "AnthropicBedrock", fake_bedrock)
    assert str(gateway.build_client(Mode.LIVE)) == "client"
    assert seen == {"aws_region": "eu-west-1", "timeout": 45, "max_retries": 0}


def test_gateway_config_profile_prefix() -> None:
    assert set(gateway.MODEL_PROFILES) == {"opus-4-6", "sonnet-4-6"}
    assert all(p.startswith("eu.anthropic.") for p in gateway.MODEL_PROFILES.values())


def test_gateway_config_no_stream_and_auto_tool_choice() -> None:
    client = FakeClient(reply("end_turn"))
    gw = LLMGateway(Mode.LIVE, client=client)
    gw.create("opus-4-6", [{"role": "user", "content": "q"}], tools=[{"name": "t"}])
    call = client.messages.calls[0]
    assert "stream" not in call
    assert call["model"] == "eu.anthropic.claude-opus-4-6-v1"
    assert call["tool_choice"] == {"type": "auto"}


@pytest.mark.parametrize("mode", [Mode.RECORD, Mode.LIVE])
def test_gateway_config_outside_eu_raises(mode: Mode) -> None:
    with pytest.raises(GatewayError):
        gateway.build_client(mode, region="us-east-1")
    with pytest.raises(GatewayError):
        LLMGateway(mode, client=FakeClient(reply("end_turn")), region="us-east-1")


def test_gateway_config_replay_builds_no_client() -> None:
    assert gateway.build_client(Mode.REPLAY, region="us-east-1") is None
    with pytest.raises(GatewayError):
        LLMGateway(Mode.REPLAY).create("opus-4-6", [])


def test_gateway_config_mode_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAIRN_LLM_MODE", raising=False)
    assert gateway.mode_from_env() is Mode.REPLAY
    monkeypatch.setenv("CAIRN_LLM_MODE", "record")
    assert gateway.mode_from_env() is Mode.RECORD
    monkeypatch.setenv("CAIRN_LLM_MODE", "bogus")
    with pytest.raises(GatewayError):
        gateway.mode_from_env()


def test_gateway_config_unknown_model() -> None:
    gw = LLMGateway(Mode.LIVE, client=FakeClient(reply("end_turn")))
    with pytest.raises(GatewayError):
        gw.create("nope", [])


def test_gateway_ok_passes_content_and_usage() -> None:
    gw = LLMGateway(Mode.LIVE, client=FakeClient(reply("tool_use", [{"type": "tool_use"}])))
    result = gw.create("sonnet-4-6", [])
    assert result.status is Status.OK
    assert result.content == [{"type": "tool_use"}]
    assert (result.input_tokens, result.output_tokens) == (10, 5)


def test_gateway_refusal_is_declined_without_content() -> None:
    gw = LLMGateway(Mode.LIVE, client=FakeClient(reply("refusal")))
    result = gw.create("opus-4-6", [])
    assert result.status is Status.DECLINED
    assert result.message == "the model declined"
    assert result.content == []


def test_gateway_truncated_discards_content() -> None:
    gw = LLMGateway(Mode.LIVE, client=FakeClient(reply("max_tokens")))
    result = gw.create("opus-4-6", [])
    assert result.status is Status.TRUNCATED
    assert result.content == []


def test_gateway_refusal_unknown_stop_reason_is_error() -> None:
    gw = LLMGateway(Mode.LIVE, client=FakeClient(reply("pause_turn")))
    with pytest.raises(GatewayError):
        gw.create("opus-4-6", [])


def test_gateway_reads_pydantic_like_response() -> None:
    class Model:
        def model_dump(self) -> dict[str, Any]:
            return reply("end_turn")

    class Messages:
        def create(self, **kwargs: Any) -> Model:
            return Model()

    class Client:
        messages = Messages()

    result = LLMGateway(Mode.LIVE, client=Client()).create("opus-4-6", [])
    assert result.status is Status.OK


def test_echo_block_drops_fields_bedrock_rejects() -> None:
    from cairn.gateway import echo_block

    raw: dict[str, object] = {
        "type": "tool_use",
        "id": "t1",
        "name": "x",
        "input": {},
        "toolset_name": None,
        "caller": None,
    }
    assert echo_block(raw) == {"type": "tool_use", "id": "t1", "name": "x", "input": {}}
    assert echo_block({"type": "text", "text": "hi", "citations": None}) == {
        "type": "text",
        "text": "hi",
    }
