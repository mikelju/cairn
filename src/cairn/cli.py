"""Command line: the same registry tools as MCP and REST."""

import json
from typing import Annotated, Any

import typer
import uvicorn
from pydantic import ValidationError

from cairn.canonical import canonical_json
from cairn.tools import argument_problems, result_sha256
from cairn.tools import call_tool as registry_call

app = typer.Typer(help="Cairn: traceable agentic demo for drug safety science.")


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a tool; bad arguments end the command with a plain message and a non-zero exit."""
    try:
        return registry_call(name, arguments)
    except ValidationError as error:
        typer.echo(f"error: {argument_problems(error)}", err=True)
        raise typer.Exit(2) from error


def _emit(result: dict[str, Any], show_hash: bool) -> None:
    if show_hash:
        typer.echo(result_sha256(result))
    else:
        typer.echo(canonical_json(result).decode("utf-8"))


@app.command("run-job")
def run_job_command(
    kind: str,
    params: Annotated[str, typer.Option(help="JSON object with job parameters")] = "{}",
    hash_only: Annotated[bool, typer.Option("--hash", help="Print only the result hash")] = False,
) -> None:
    """Run a job and print its result as canonical JSON."""
    _emit(call_tool("run_job", {"kind": kind, "params": json.loads(params)}), hash_only)


@app.command("study-design")
def study_design_command(
    hash_only: Annotated[bool, typer.Option("--hash", help="Print only the result hash")] = False,
) -> None:
    """Print the study design as canonical JSON."""
    _emit(call_tool("study_design", {}), hash_only)


@app.command("incidence")
def incidence_command(
    full: Annotated[bool, typer.Option("--full", help="All findings, not only the screen")] = False,
    hash_only: Annotated[bool, typer.Option("--hash", help="Print only the result hash")] = False,
) -> None:
    """Print histopathology incidence as canonical JSON."""
    _emit(call_tool("incidence", {"screen": not full}), hash_only)


@app.command("body-weight-change")
def body_weight_change_command(
    sex: str = "F",
    population: str = "main_and_recovery",
    hash_only: Annotated[bool, typer.Option("--hash", help="Print only the result hash")] = False,
) -> None:
    """Print the body weight change by dose group as canonical JSON."""
    _emit(call_tool("body_weight_change", {"sex": sex, "population": population}), hash_only)


@app.command("tk-summary")
def tk_summary_command(
    sex: str = "M",
    dose: float = 20.0,
    day: float = 1.0,
    hash_only: Annotated[bool, typer.Option("--hash", help="Print only the result hash")] = False,
) -> None:
    """Print the toxicokinetic AUCtau summary as canonical JSON."""
    _emit(call_tool("tk_summary", {"sex": sex, "dose": dose, "day": day}), hash_only)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:  # pragma: no cover
    """Serve the web app, REST API and MCP endpoint."""
    uvicorn.run("cairn.app:create_app", factory=True, host=host, port=port)
