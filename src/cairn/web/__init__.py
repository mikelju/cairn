"""Web pages: landing page, step 1 and /healthz, rendered with Jinja2 and local HTMX."""

import os
import subprocess
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cairn import __version__
from cairn.ingest import build_report, load_study
from cairn.jobs import JobRunner
from cairn.validate import RULE_AUC, RULE_CONC, validate_study

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
router = APIRouter()
ROLE = "Study toxicologist"
STEPS = ["Validate", "Design", "Explore", "Analyse", "Draft", "Check", "Review"]


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


def mount_web(app: FastAPI) -> None:
    app.state.commit = _commit()
    app.state.snapshot = load_study()[2]
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    app.include_router(router)
