"""Same result hash for run_job and study_design over MCP, REST and the CLI."""

import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import anyio
import pytest
import uvicorn
from mcp import Client
from typer.testing import CliRunner

from cairn.app import create_app
from cairn.cli import app as cli_app
from cairn.tools import REGISTRY, call_tool, result_sha256

CASES: list[tuple[str, dict[str, Any]]] = [
    ("run_job", {"kind": "validate_study", "params": {}}),
    ("study_design", {}),
    ("incidence", {"screen": True}),
    ("body_weight_change", {"sex": "F", "population": "main_and_recovery"}),
    ("tk_summary", {"sex": "M", "dose": 20.0, "day": 1.0}),
]


@pytest.fixture(scope="module")
def server_url() -> Iterator[str]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


async def mcp_call(url: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(f"{url}/mcp") as client:
        result = await client.call_tool(name, arguments)
    assert not result.is_error
    assert result.structured_content is not None
    return dict(result.structured_content)


def rest_call(url: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    import httpx

    response = httpx.post(f"{url}/api/tools/{name}", json=arguments, timeout=60)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def cli_hash(name: str, arguments: dict[str, Any]) -> str:
    if name == "run_job":
        args = ["run-job", arguments["kind"], "--hash"]
    elif name == "incidence":
        args = ["incidence", "--hash"]
    elif name == "body_weight_change":
        args = ["body-weight-change", "--sex", "F", "--hash"]
    elif name == "tk_summary":
        args = ["tk-summary", "--sex", "M", "--dose", "20", "--day", "1", "--hash"]
    else:
        args = ["study-design", "--hash"]
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0
    return result.stdout.strip()


@pytest.mark.parametrize(("name", "arguments"), CASES)
def test_registry_same_hash_over_mcp_rest_and_cli(
    server_url: str, name: str, arguments: dict[str, Any]
) -> None:
    direct = result_sha256(call_tool(name, arguments))
    over_mcp = result_sha256(anyio.run(mcp_call, server_url, name, arguments))
    over_rest = result_sha256(rest_call(server_url, name, arguments))
    assert over_mcp == over_rest == cli_hash(name, arguments) == direct


def test_registry_has_exactly_the_registered_tools() -> None:
    assert sorted(REGISTRY) == [
        "body_weight_change",
        "incidence",
        "run_job",
        "study_design",
        "tk_summary",
    ]


def test_study_design_content() -> None:
    design = call_tool("study_design", {})
    assert design["values"]["study_id"] == "PDS2014"
    assert sum(group["animals"] for group in design["values"]["groups"]) == 124
    assert {group["dose"] for group in design["values"]["groups"]} >= {0.0, 20.0}


def test_cli_prints_json_without_hash_flag() -> None:
    result = CliRunner().invoke(cli_app, ["study-design"])
    assert result.exit_code == 0
    assert '"study_id":"PDS2014"' in result.stdout


def test_rest_rejects_unknown_tool_and_bad_arguments(server_url: str) -> None:
    import httpx

    assert httpx.post(f"{server_url}/api/tools/nope", json={}).status_code == 404
    assert httpx.post(f"{server_url}/api/tools/incidence", json={"bogus": 1}).status_code == 422


BAD_ARGUMENTS: list[tuple[str, dict[str, Any]]] = [
    ("body_weight_change", {"sex": "F", "population": "tk"}),
    ("body_weight_change", {"sex": "F", "population": "all"}),
    ("body_weight_change", {"sex": "X", "population": "main"}),
    ("tk_summary", {"sex": "Q"}),
    ("incidence", {"screen": "maybe"}),
]
BAD_CLI: list[list[str]] = [
    ["body-weight-change", "--population", "tk"],
    ["body-weight-change", "--population", "tk_satellites"],
    ["body-weight-change", "--sex", "X"],
    ["tk-summary", "--sex", "Q"],
]


@pytest.mark.parametrize(("name", "arguments"), BAD_ARGUMENTS)
def test_validation_rejects_bad_arguments_over_mcp_and_rest(
    server_url: str, name: str, arguments: dict[str, Any]
) -> None:
    import httpx

    response = httpx.post(f"{server_url}/api/tools/{name}", json=arguments, timeout=60)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)

    async def rejected() -> bool:
        async with Client(f"{server_url}/mcp") as client:
            try:
                result = await client.call_tool(name, arguments)
            except Exception:
                return True
        return bool(result.is_error)

    assert anyio.run(rejected)


@pytest.mark.parametrize("arguments", BAD_CLI)
def test_validation_rejects_tk_and_bad_values_on_the_cli(arguments: list[str]) -> None:
    result = CliRunner().invoke(cli_app, arguments)
    assert result.exit_code != 0
    assert "error:" in result.output
    assert "Traceback" not in result.output
