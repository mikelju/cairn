"""Web pages: landing page, steps 1 and 2 and /healthz, rendered with Jinja2 and local HTMX."""

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cairn import __version__, retrieval
from cairn.content import Text, ValueRef
from cairn.gateway import DEFAULT_MODEL, LLMGateway, Mode
from cairn.guidelines import load_manifest
from cairn.highlight import IMAGES_DIR, cited_page, highlights_by_sentence
from cairn.ingest import build_report, load_study
from cairn.jobs import JobRunner
from cairn.loop import PROMPT_VERSION, STUDY_TOOLS, LoopResult, LoopStatus, ask, schema_hash
from cairn.passages import normalize_whitespace, stored_passages
from cairn.questions import QUESTIONS, STEP2_QUESTIONS
from cairn.recording import (
    RECORDINGS_DIR,
    RecordingKey,
    ReplayClient,
    StaleRecording,
    recorded_model,
    total_cost,
)
from cairn.render import quotations
from cairn.validate import RULE_AUC, RULE_CONC, validate_study
from cairn.web import i18n
from cairn.web.threads import threads

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
router = APIRouter()
STEP_COUNT = 7


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
    shell = i18n.context(request, context.get("current"))
    base = {"steps": range(1, STEP_COUNT + 1), "footer": footer, **shell, **context}
    return templates.TemplateResponse(request, name, base)


def _result(
    report: dict[str, Any], injected: bool, extra: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    naive = report["naive_mean_auctau"]
    rows = report["quarantine"]["rows"]
    extra = extra or []
    return {
        "injected": injected,
        "reported": bool(extra),
        "total": report["quarantine"]["total"],
        "rows": [r for r in rows if r["rule"] == RULE_AUC],
        "fired": [r for r in rows if r["rule"] == RULE_CONC] + extra,
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


RULE_UNIQUE = "dm_usubjid_unique"
RULE_SET = "dm_setcd_in_tx"
UNKNOWN_SET = "99"


def _duplicate_id(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Copy the frames and repeat the first animal of DM; the source files stay untouched."""
    dm = frames["DM"]
    row = dm.iloc[[0]].copy()
    row.index = pd.Index([int(str(dm.index.max())) + 1])
    return {**frames, "DM": pd.concat([dm, row])}


def _unknown_dose(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Copy the frames and move the first animal to a treatment set that TX does not define."""
    dm = frames["DM"].copy()
    dm.loc[dm.index[0], "SETCD"] = UNKNOWN_SET
    return {**frames, "DM": dm}


SWITCHES = {"negative": _inject, "duplicate": _duplicate_id, "dose": _unknown_dose}


def _integrity_rows(
    report: dict[str, Any], frames: dict[str, pd.DataFrame]
) -> list[dict[str, Any]]:
    """The DM integrity rules that fired in the report, as quarantine rows (never corrected)."""
    dm, integrity = frames["DM"], report["integrity"]
    rows = []
    if integrity["duplicate_usubjid"]:
        animal = str(dm.loc[dm["USUBJID"].duplicated(keep="first"), "USUBJID"].iloc[0])
        rows.append({"rule": RULE_UNIQUE, "usubjid": animal, "test": "DM", "value": "repeated"})
    if integrity["dm_setcd_missing_in_tx"]:
        bad = dm[~dm["SETCD"].isin(frames["TX"]["SETCD"])]
        rows.append(
            {
                "rule": RULE_SET,
                "usubjid": str(bad["USUBJID"].iloc[0]),
                "test": "SETCD",
                "value": str(bad["SETCD"].iloc[0]),
            }
        )
    return rows


def _revalidate(switch: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    frames, zeros, snapshot = load_study()
    frames = SWITCHES[switch](frames)
    report = build_report(frames, validate_study(frames, zeros), snapshot)
    return report, _integrity_rows(report, frames)


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
async def step1_run(request: Request, switch: Annotated[str, Form()] = "none") -> HTMLResponse:
    extra: list[dict[str, Any]] = []
    if switch not in (*SWITCHES, "none"):
        raise HTTPException(status_code=422, detail="unknown switch")
    if switch != "none":
        report, extra = _revalidate(switch)
    else:
        runner: JobRunner = request.app.state.runner
        job = runner.submit("validate_study", {})
        await runner.tasks[job.job_id]
        report = (runner.jobs[job.job_id].outputs or {})["report"]
    return templates.TemplateResponse(
        request, "step1_result.html", {"r": _result(report, switch == "negative", extra)}
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
        "".join(
            part.text
            if isinstance(part, Text)
            else _marker(part.field if isinstance(part, ValueRef) else "quote")
            for part in s.parts
        )
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
        # Incidence source rows are the affected animals; n is the examined count.
        label = "affected" if o.kind.startswith("incidence") else "animals"
        evidence.append(
            {
                "tool": o.tool.name,
                "population": o.population,
                "n": "n/a" if o.n_examined is None else str(o.n_examined),
                "sources": f"{len(ids)} {label}, from {ids[0]}" if ids else "none",
            }
        )
    return evidence


def _highlighted(sentence_id: str) -> list[dict[str, Any]]:
    return highlights_by_sentence().get(sentence_id, [])


def _all_highlights() -> list[dict[str, Any]]:
    return [e for entries in highlights_by_sentence().values() for e in entries]


def _with_highlight(quote: dict[str, Any]) -> dict[str, Any]:
    """Add the viewer link when the build highlighted the first quoted sentence."""
    first = quote["sentence_ids"][0]
    return {**quote, "highlight": f"/highlight/{first}" if _highlighted(first) else ""}


def _step2_context(question_id: str, directory: Path) -> dict[str, Any]:
    model = recorded_model(directory, question_id, DEFAULT_MODEL)
    key = RecordingKey(question_id, PROMPT_VERSION, schema_hash(), model)
    client = ReplayClient.load(directory, key)
    recording = client.recording
    result = ask(QUESTIONS[question_id], LLMGateway(Mode.REPLAY, client=client), model)
    cost = total_cost(recording)
    latency = sum(float(call.get("latency_s", 0.0)) for call in recording["calls"])
    fixture = recording.get("source") == "fixture"
    meta = (
        f"{recording['date']} | {recording['region']} | {recording['model']} | "
        f"{latency:.1f} s | " + ("cost n/a" if cost is None else f"{cost:.2f} USD")
    )
    return result_context(result, "FIXTURE" if fixture else "RECORDED", meta)


def _answer_kind(result: LoopResult, has_table: bool) -> str:
    """Why the answer looks as it does: refusal, quotations, table with text, or text only."""
    if result.status is not LoopStatus.ANSWERED:
        return "refusal"
    if quotations(result.sentences):
        return "quotes"
    return "table" if has_table else "text"


def result_context(result: LoopResult, badge: str, meta: str) -> dict[str, Any]:
    """The template data of one answered, declined or rejected question, recorded or live."""
    verdict = result.verdict
    doses, rows = _screen(result)
    trace = " -> ".join(step.tool for step in result.steps if step.tool in STUDY_TOOLS)
    return {
        "badge": badge,
        "meta": meta,
        "kind": _answer_kind(result, bool(rows)),
        "trace": trace,
        "calls": len(trace.split(" -> ")) if trace else 0,
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
        "quotes": [_with_highlight(q) for q in quotations(result.sentences)]
        if result.rendered
        else [],
    }


@router.get("/step/2", response_class=HTMLResponse)
async def step2(request: Request) -> HTMLResponse:
    badge = _step2_badge(_recordings_dir())
    return _page(request, "step2.html", current=2, questions=STEP2_QUESTIONS, page_badge=badge)


@router.post("/step/2/run", response_class=HTMLResponse)
def step2_run(request: Request, question: Annotated[str, Form()]) -> HTMLResponse:
    if question not in QUESTIONS:
        raise HTTPException(status_code=422, detail="unknown question")
    try:
        context = _step2_context(question, _recordings_dir())
    except StaleRecording as error:
        return templates.TemplateResponse(
            request, "step2_result.html", {**i18n.context(request), "stale": str(error)}
        )
    return templates.TemplateResponse(
        request, "step2_result.html", {**i18n.context(request), "r": context}
    )


SHOWN_HITS = 3
NS_QUERIES = "nonclinical-summary"


def _rank(value: int | None) -> str:
    return "-" if value is None else str(value)


def _step3_context() -> dict[str, Any]:
    """The two fixed workflow queries from the build-time cache, with the quotation check.

    A quotation is the first stored sentence of a shown passage; it counts as verbatim on the cited
    page when the build located exactly that text on a page of the passage.
    """
    guidelines = load_manifest()["guidelines"]
    passages = stored_passages()
    queries, quotes, verbatim = [], [], 0
    for fixed in retrieval.load_fixed_queries():
        if fixed["used_by"] != NS_QUERIES:
            continue
        rows: list[list[str]] = []
        folded: list[list[str]] = []
        for number, hit in enumerate(retrieval.cached_guidance(fixed["query"]).hits, start=1):
            passage = passages[hit.passage_id]
            title = guidelines[passage.doc]["title"]
            row = [
                " ".join(title.split()[:2]),
                passage.section,
                str(passage.page_start),
                _rank(hit.lexical_rank),
                _rank(hit.semantic_rank),
                _rank(hit.fused_rank),
            ]
            (rows if number <= SHOWN_HITS else folded).append(row)
            if number > SHOWN_HITS:
                continue
            sentence = passage.sentences[0]
            page = cited_page(passage, sentence.sentence_id)
            base = guidelines[passage.doc]["page_link_base"]
            marks = _highlighted(sentence.sentence_id)
            if any(
                normalize_whitespace(m["text"]) == normalize_whitespace(sentence.text)
                and passage.page_start <= m["page"] <= passage.page_end
                for m in marks
            ):
                verbatim += 1
            quotes.append(
                {
                    "id": fixed["id"],
                    "text": sentence.text,
                    "cite": " ".join([*row[:2], str(page)]),
                    "highlight": f"/highlight/{sentence.sentence_id}" if marks else "",
                    "link": f"{base}#page={page}",
                }
            )
        queries.append({"id": fixed["id"], "query": fixed["query"], "rows": rows, "folded": folded})
    return {"queries": queries, "quotes": quotes, "verbatim": verbatim}


@router.get("/step/3", response_class=HTMLResponse)
async def step3(request: Request) -> HTMLResponse:
    return _page(request, "step3.html", current=3, r=_step3_context())


@router.get("/highlight/{sentence_id}", response_class=HTMLResponse)
async def highlight_view(request: Request, sentence_id: str) -> HTMLResponse:
    entries = _highlighted(sentence_id)
    if not entries:
        raise HTTPException(status_code=404, detail="no highlighted page for this sentence")
    passage = stored_passages()[entries[0]["passage_id"]]
    return _page(
        request,
        "highlight.html",
        current=0,
        pages=entries,
        sentence=next(s.text for s in passage.sentences if s.sentence_id == sentence_id),
    )


@router.get("/highlights/{name}")
async def highlight_image(name: str) -> FileResponse:
    known = {Path(str(e["image"])).name for e in _all_highlights()}
    if name not in known:
        raise HTTPException(status_code=404, detail="unknown highlight")
    return FileResponse(IMAGES_DIR / name, media_type="image/png")


EXPLORE_STAGES = (("Q1", "Q2", "Q3", "Q5"), ("Q4", "Q6", "Q7", "Q8"), ("G1", "G2", "G3"))


@lru_cache(maxsize=4)
def _card_kinds(directory: Path) -> dict[str, str]:
    """The answer format of every recorded question, read from the recordings themselves."""
    kinds: dict[str, str] = {}
    for question_id in QUESTIONS:
        try:
            kinds[question_id] = _step2_context(question_id, directory)["kind"]
        except StaleRecording:
            kinds[question_id] = "text"
    return kinds


@router.get("/explore", response_class=HTMLResponse)
async def explore(request: Request) -> HTMLResponse:
    directory = _recordings_dir()
    badge = _step2_badge(directory)
    live = bool(os.environ.get("CAIRN_ACCESS_CODE"))
    kinds = _card_kinds(directory)
    stages = [[(q, kinds[q]) for q in group] for group in EXPLORE_STAGES]
    return _page(request, "explore.html", current=0, stages=stages, page_badge=badge, live=live)


@router.post("/explore/run", response_class=HTMLResponse)
def explore_run(request: Request, question: Annotated[str, Form()]) -> HTMLResponse:
    if question not in QUESTIONS:
        raise HTTPException(status_code=422, detail="unknown question")
    try:
        context = _step2_context(question, _recordings_dir())
    except StaleRecording as error:
        return templates.TemplateResponse(
            request, "explore_answer.html", {**i18n.context(request), "stale": str(error)}
        )
    return templates.TemplateResponse(
        request, "explore_answer.html", {**i18n.context(request), "r": context}
    )


def mount_web(app: FastAPI) -> None:
    from cairn.web.explore_live import explore_live
    from cairn.web.people import people  # imports this module's helpers, so it loads late

    app.add_middleware(i18n.LocaleCookie)
    app.state.commit = _commit()
    app.state.snapshot = load_study()[2]
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    app.include_router(router)
    app.include_router(people)
    app.include_router(explore_live)
    app.include_router(threads)
