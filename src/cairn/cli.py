"""Command line: the registry tools (also over MCP and REST); ask, record and smoke are CLI only."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import uvicorn
from pydantic import ValidationError

from cairn import live, passages, retrieval, weights
from cairn.canonical import canonical_json
from cairn.gateway import DEFAULT_MODEL, MODEL_PROFILES, GatewayError
from cairn.recording import RECORDINGS_DIR, StaleRecording, recorded_model
from cairn.tools import argument_problems, result_sha256
from cairn.tools import call_tool as registry_call

app = typer.Typer(help="Cairn: traceable agentic demo for drug safety science.")
guidance_app = typer.Typer(help="Guideline passages for guidance retrieval.")
app.add_typer(guidance_app, name="guidance")


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


def _known_model(model: str) -> str:
    """Return the model or end the command before any ceiling is computed."""
    if model not in MODEL_PROFILES:
        typer.echo(f"error: unknown model: {model} (known: {', '.join(MODEL_PROFILES)})", err=True)
        raise typer.Exit(2)
    return model


@app.command("ask")
def ask_command(
    question: Annotated[str, typer.Argument(help="Question ID (Q2, Q6) or free text with --live")],
    live_mode: Annotated[bool, typer.Option("--live", help="Call Bedrock")] = False,
    model: Annotated[
        str | None, typer.Option(help="Model key; replay reads it from the file")
    ] = None,
    recordings: Path = RECORDINGS_DIR,
) -> None:
    """Answer a question: replay a recording, or call the model with --live."""
    question_id, text = live.question_text(question)
    if model is not None:
        _known_model(model)
    try:
        if live_mode:
            chosen = model or DEFAULT_MODEL
            typer.echo(f"ceiling: {live.record_ceiling(chosen, 1):.2f} USD")
            result = live.ask_live(text, chosen)
        elif question_id:
            chosen = model or recorded_model(recordings, question_id, DEFAULT_MODEL)
            result = live.ask_replay(question_id, recordings, chosen)
        else:
            typer.echo("error: replay needs a question ID (Q2, Q6); use --live", err=True)
            raise typer.Exit(2)
    except typer.Exit:
        raise
    except (StaleRecording, GatewayError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error
    except Exception as error:  # SDK errors (403, timeout, throttling) end as a plain message
        typer.echo(f"error: {type(error).__name__}: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"status: {result.status.value}")
    if result.message:
        typer.echo(result.message)
    if result.rendered:
        typer.echo(result.rendered)
    if result.verdict is not None:
        typer.echo(f"rules fired: {result.verdict.rules}")


@app.command("record")
def record_command(
    questions: Annotated[list[str], typer.Argument(help="Question IDs, for example Q2 Q6")],
    model: str = DEFAULT_MODEL,
    recordings: Path = RECORDINGS_DIR,
) -> None:
    """Record questions against Bedrock (laptop only); stops before 10 USD."""
    _known_model(model)
    ids = [live.question_text(q)[0] for q in questions]
    if not all(ids):
        typer.echo("error: record takes question IDs (Q2, Q6)", err=True)
        raise typer.Exit(2)
    typer.echo(f"ceiling: {live.record_ceiling(model, len(ids)):.2f} USD of {live.BUDGET_USD:.2f}")
    report = live.record_questions(ids, recordings, model)
    for question_id, outcome in report.outcomes.items():
        typer.echo(f"{question_id}: {outcome}")
    for path in report.saved:
        typer.echo(f"saved {path}")
    for question_id in report.unsaved:
        typer.echo(f"not saved: {question_id} (the file is left as it was)")
    typer.echo(f"spent: {report.spent:.4f} USD")
    if report.stopped:
        typer.echo(report.stopped, err=report.stopped.startswith("error:"))
    if report.stopped or report.unsaved:
        raise typer.Exit(1)


@app.command("smoke")
def smoke_command(output: Path = live.SMOKE_PATH) -> None:
    """Send question, draft and judge prompts to each profile (laptop only)."""
    typer.echo(f"ceiling: {live.smoke_ceiling():.2f} USD of {live.BUDGET_USD:.2f}")
    evidence = live.smoke(output)
    typer.echo(f"wrote {output}; spent {evidence['total_cost_usd']:.4f} USD")


@guidance_app.command("build")
def guidance_build_command(
    output: Path = passages.PASSAGES_PATH,
    calibration: Path = retrieval.CALIBRATION_PATH,
    passages_only: bool = False,
) -> None:
    """Rebuild the generated guidance files: passages, then the calibration scores and threshold.

    The second step embeds and reranks (needs the weights: run `cairn guidance weights` once).
    """
    count = passages.write_passages(output)
    typer.echo(f"wrote {output}: {count} passages")
    if passages_only:
        return
    index = retrieval.build_index(output)
    calibration.write_text(retrieval.calibrate(index, calibration), encoding="utf-8", newline="\n")
    typer.echo(f"wrote {calibration}: threshold {retrieval.load_threshold(calibration):.4f}")


@guidance_app.command("weights")
def guidance_weights_command() -> None:  # pragma: no cover
    """Download the pinned model weights into CAIRN_MODELS and verify every SHA-256."""
    models = weights.models_dir()
    try:
        done = weights.download_weights(models)
    except weights.WeightsError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    for name, relative, size in done:
        typer.echo(f"{name} {relative} {size} bytes ok")
    typer.echo(f"weights verified in {models}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:  # pragma: no cover
    """Serve the web app, REST API and MCP endpoint."""
    uvicorn.run("cairn.app:create_app", factory=True, host=host, port=port)
