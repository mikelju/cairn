"""Web pages: landing page, steps 1 and 2 and /healthz, rendered with Jinja2 and local HTMX."""

import json
import os
import subprocess
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cairn import __version__
from cairn.content import Text
from cairn.gateway import DEFAULT_MODEL, LLMGateway, Mode
from cairn.ingest import build_report, load_study
from cairn.jobs import JobRunner
from cairn.loop import PROMPT_VERSION, STUDY_TOOLS, LoopResult, LoopStatus, ask, schema_hash
from cairn.questions import QUESTIONS
from cairn.recording import (
    RECORDINGS_DIR,
    RecordingKey,
    ReplayClient,
    StaleRecording,
    recorded_model,
    total_cost,
)
from cairn.validate import RULE_AUC, RULE_CONC, validate_study

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
router = APIRouter()
ROLE = "Study toxicologist"
STEPS = ["Validate", "Ask", "Explore", "Analyse", "Draft", "Check", "Review"]


def _commit() -> str:
    baked = os.environ.get("CAIRN_COMMIT", "").strip()
    if baked:
        return baked
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=HERE,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:,.0f}"


def _page(request: Request, name: str, **context: Any) -> HTMLResponse:
    footer = {
        "version": __version__,
        "commit": request.app.state.commit,
        "snapshot": request.app.state.snapshot,
    }
    base = {"role": ROLE, "steps": STEPS, "footer": footer, **context}
    return templates.TemplateResponse(request, name, base)


def _result(report: dict[str, Any], injected: bool) -> dict[str, Any]:
    naive = report["naive_mean_auctau"]
    rows = report["quarantine"]["rows"]
    return {
        "injected": injected,
        "total": report["quarantine"]["total"],
        "rows": [r for r in rows if r["rule"] == RULE_AUC],
        "fired": [r for r in rows if r["rule"] == RULE_CONC],
        "with_bad": _number(naive["with_quarantined"]["mean"]),
        "n_with": naive["with_quarantined"]["n"],
        "without_bad": _number(naive["without_quarantined"]["mean"]),
        "n_without": naive["without_quarantined"]["n"],
    }


def _inject(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Copy the frames and add one negative concentration; the source files stay untouched."""
    pc = frames["PC"]
    row = pc[pc["PCSTRESN"] > 0].iloc[[0]].copy()
    row["PCSTRESN"] = -1.0
    row.index = pd.Index([int(str(pc.index.max())) + 1])
    return {**frames, "PC": pd.concat([pc, row])}


def _revalidate_injected() -> dict[str, Any]:
    frames, zeros, snapshot = load_study()
    frames = _inject(frames)
    return build_report(frames, validate_study(frames, zeros), snapshot)


@router.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return _page(request, "landing.html", current=0)


@router.get("/step/1", response_class=HTMLResponse)
async def step1(request: Request) -> HTMLResponse:
    return _page(request, "step1.html", current=1)


@router.post("/step/1/run", response_class=HTMLResponse)
async def step1_run(request: Request, inject: Annotated[str | None, Form()] = None) -> HTMLResponse:
    injected = inject == "on"
    if injected:
        report = _revalidate_injected()
    else:
        runner: JobRunner = request.app.state.runner
        job = runner.submit("validate_study", {})
        await runner.tasks[job.job_id]
        report = (runner.jobs[job.job_id].outputs or {})["report"]
    return templates.TemplateResponse(
        request, "step1_result.html", {"r": _result(report, injected)}
    )


SCREEN_KIND = "incidence_screen"


def _recordings_dir() -> Path:
    return Path(os.environ.get("CAIRN_RECORDINGS", str(RECORDINGS_DIR)))


def _step2_badge(directory: Path) -> str:
    """FIXTURE if any readable recording is hand-written, RECORDED if there are any, else NONE."""
    sources = []
    for path in directory.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            sources.append(data.get("source"))
    if not sources:
        return "NONE"
    return "FIXTURE" if "fixture" in sources else "RECORDED"


def _marker(field: str) -> str:
    """A marker for a reference: the last field name, with no digit."""
    last = field.rsplit(".", 1)[-1]
    return "[" + "".join(ch for ch in last if not ch.isdigit()).strip("_") + "]"


def _written(result: LoopResult) -> str:
    return " ".join(
        "".join(part.text if isinstance(part, Text) else _marker(part.field) for part in s.parts)
        for s in result.sentences
    )


def _screen(result: LoopResult) -> tuple[list[str], list[dict[str, Any]]]:
    """The screening table from the last incidence Observation: dose headers and printed rows."""
    for observation in reversed(result.ledger.observations):
        if observation.kind != SCREEN_KIND:
            continue
        findings = observation.values["findings"]
        doses = [f"{g['dose']:g}" for g in findings[0]["groups"]] if findings else []
        rows = [
            {
                "sex": f["sex"],
                "tissue": f["tissue"],
                "finding": f["finding"],
                "cells": [
                    f"{g['affected']}/{g['examined']}" if g["examined"] else "not examined"
                    for g in f["groups"]
                ],
            }
            for f in findings
        ]
        return doses, rows
    return [], []


def _evidence(result: LoopResult) -> list[dict[str, str]]:
    evidence = []
    for o in result.ledger.observations:
        ids = sorted({str(row["usubjid"]) for row in o.source_rows if "usubjid" in row})
        evidence.append(
            {
                "tool": o.tool.name,
                "population": o.population,
                "n": "n/a" if o.n_examined is None else str(o.n_examined),
                "sources": f"{len(ids)} animals, from {ids[0]}" if ids else "none",
            }
        )
    return evidence


def _step2_context(question_id: str, directory: Path) -> dict[str, Any]:
    model = recorded_model(directory, question_id, DEFAULT_MODEL)
    key = RecordingKey(question_id, PROMPT_VERSION, schema_hash(), model)
    client = ReplayClient.load(directory, key)
    recording = client.recording
    result = ask(QUESTIONS[question_id], LLMGateway(Mode.REPLAY, client=client), model)
    verdict = result.verdict
    cost = total_cost(recording)
    latency = sum(float(call.get("latency_s", 0.0)) for call in recording["calls"])
    fixture = recording.get("source") == "fixture"
    doses, rows = _screen(result)
    trace = " -> ".join(step.tool for step in result.steps if step.tool in STUDY_TOOLS)
    return {
        "badge": "FIXTURE" if fixture else "RECORDED",
        "meta": (
            f"{recording['date']} | {recording['region']} | {recording['model']} | "
            f"{latency:.1f} s | " + ("cost n/a" if cost is None else f"{cost:.2f} USD")
        ),
        "trace": trace,
        "status": result.status.value,
        "message": result.message,
        "answered": result.status is LoopStatus.ANSWERED,
        "text": result.rendered,
        "failures": [str(f) for f in verdict.failures] if verdict else [],
        "rules": ", ".join(str(r) for r in verdict.rules) if verdict and verdict.rules else "none",
        "written": _written(result),
        "doses": doses,
        "rows": rows,
        "rule": next(
            (o.values["screen_rule"] for o in result.ledger.observations if o.kind == SCREEN_KIND),
            "",
        ),
        "evidence": _evidence(result),
    }


@router.get("/step/2", response_class=HTMLResponse)
async def step2(request: Request) -> HTMLResponse:
    badge = _step2_badge(_recordings_dir())
    return _page(request, "step2.html", current=2, questions=QUESTIONS, page_badge=badge)


@router.post("/step/2/run", response_class=HTMLResponse)
def step2_run(request: Request, question: Annotated[str, Form()]) -> HTMLResponse:
    if question not in QUESTIONS:
        raise HTTPException(status_code=422, detail="unknown question")
    try:
        context = _step2_context(question, _recordings_dir())
    except StaleRecording as error:
        return templates.TemplateResponse(request, "step2_result.html", {"stale": str(error)})
    return templates.TemplateResponse(request, "step2_result.html", {"r": context})


def mount_web(app: FastAPI) -> None:
    app.state.commit = _commit()
    app.state.snapshot = load_study()[2]
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    app.include_router(router)
