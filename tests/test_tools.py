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
    else:
        args = ["study-design", "--hash"]
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0
    return result.stdout.strip()


@pytest.mark.parametrize(("name", "arguments"), CASES)
def test_same_hash_over_mcp_rest_and_cli(
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
