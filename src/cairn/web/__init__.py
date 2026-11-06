"""Web pages: landing page, steps 1 and 2 and /healthz, rendered with Jinja2 and local HTMX."""

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cairn import __version__, retrieval
from cairn.content import Text, ValueRef
from cairn.decisions import finding_key
from cairn.gateway import DEFAULT_MODEL, LLMGateway, Mode
from cairn.guidelines import load_manifest
from cairn.highlight import IMAGES_DIR, cited_page, highlights_by_sentence
from cairn.ingest import NAIVE_MEAN, build_report, load_study
from cairn.jobs import JobRunner
from cairn.loop import PROMPT_VERSION, STUDY_TOOLS, LoopResult, LoopStatus, ask, schema_hash
from cairn.passages import normalize_whitespace, stored_passages
from cairn.questions import QUESTIONS
from cairn.recording import (
    RECORDINGS_DIR,
    RecordingKey,
    ReplayClient,
    StaleRecording,
    recorded_model,
    total_cost,
)
from cairn.render import quotations
from cairn.validate import RULE_AUC, RULE_CONC, auctau_rows, validate_study
from cairn.web import i18n
from cairn.web.provenance import (
    DataTag,
    Part,
    QuoteTag,
    SourceTable,
    TextPart,
    plain_terms,
    provenance_parts,
)
from cairn.web.threads import threads

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
router = APIRouter()
SCREENS = ((1, "/study"), (2, "/ask"), (3, "/decide"), (4, "/draft"))


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
    keep = {k: str(context[k]) for k in ("thread", "actor") if context.get(k)}
    shell = i18n.context(request, context.get("current"), keep)
    base = {"steps": SCREENS, "screens": SCREENS, "footer": footer, **shell, **context}
    return templates.TemplateResponse(request, name, base)


@lru_cache(maxsize=1)
def _study_facts() -> dict[str, Any]:
    """What the study is, read from the data: animal count, doses and the AUC unit."""
    frames, _, _ = load_study()
    tx, pp = frames["TX"], frames["PP"]
    doses = sorted({float(v) for v in tx.loc[tx["TXPARMCD"] == "TRTDOS", "TXVAL"]})
    unit = str(pp.loc[pp["PPTESTCD"] == "AUCTAU", "PPSTRESU"].dropna().iloc[0])
    dosing = str(frames["TS"].loc[frames["TS"]["TSPARMCD"] == "DOSDUR", "TSVAL"].iloc[0])
    return {
        "days": int(dosing.strip("PD")),
        "animals": len(frames["DM"]),
        "doses": ", ".join(f"{d:g}" for d in doses),
        "n_doses": len(doses),
        "unit": unit,
    }


MEASURES = {
    "AUCTAU": "s1_m_auctau",
    "AUCIFO": "s1_m_aucifo",
    RULE_CONC: "s1_m_conc",
    "dm_usubjid_unique": "s1_m_dup",
    "dm_setcd_in_tx": "s1_m_set",
}


def _shown(value: Any, unit: Any) -> str:
    if isinstance(value, str):
        return value if value.isdigit() else "-"
    text = f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return f"{text} {unit}" if unit else text


def _row(r: dict[str, Any]) -> dict[str, Any]:
    day = r.get("visit_day")
    return {
        "animal": r["usubjid"],
        "measure": MEASURES[r["test"] if r["rule"] == RULE_AUC else r["rule"]],
        "day": "-" if day is None else int(day),
        "value": _shown(r["value"], r.get("unit")),
        "rule": r["rule"],
    }


def _result(
    report: dict[str, Any], injected: bool, extra: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    naive = report["naive_mean_auctau"]
    # one list for every count shown: the injected exposure (the newest source row) comes first
    top = max(
        (q["source_row"] for q in report["quarantine"]["rows"] if q["domain"] == "PP"), default=-1
    )
    held = sorted(
        report["quarantine"]["rows"],
        key=lambda q: not (injected and q["domain"] == "PP" and q["source_row"] == top),
    )
    rows = [_row(q) for q in held]
    return {
        **_study_facts(),
        "injected": injected,
        "total": len(rows),
        "rows": rows,
        "reported": [_row(q) for q in extra or []],
        "group": naive["group"],
        "with_bad": _number(naive["with_quarantined"]["mean"]),
        "n_with": naive["with_quarantined"]["n"],
        "without_bad": _number(naive["without_quarantined"]["mean"]),
        "n_without": naive["without_quarantined"]["n"],
        "injected_animal": rows[0]["animal"] if injected and rows else "",
        "injected_value": rows[0]["value"] if injected and rows else "",
    }


INJECTED_AUC = -50000.0


def _inject(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Copy the frames and add one negative AUCtau to the mean group; the sources stay untouched."""
    pp = frames["PP"]
    chosen = auctau_rows(frames, *NAIVE_MEAN)
    row = pp.loc[[chosen.index[chosen["PPSTRESN"] > 0][0]]].copy()
    row["PPSTRESN"] = INJECTED_AUC
    row.index = pd.Index([int(str(pp.index.max())) + 1])
    return {**frames, "PP": pd.concat([pp, row])}


def _figure(rows: pd.DataFrame, population: str, t: dict[str, str]) -> dict[str, Any]:
    """One mean with the AUCtau values it comes from, as a provenance tag."""
    group = t["s1_group"].format(
        sex=t["s1_sex_" + NAIVE_MEAN[0]], dose=int(NAIVE_MEAN[1]), day=int(NAIVE_MEAN[2])
    )
    pairs = zip(rows["USUBJID"], rows["PPSTRESN"], strict=True)
    values = [[str(a), _number(float(v))] for a, v in pairs]
    tag = DataTag(
        text=_number(float(rows["PPSTRESN"].mean())),
        tool="validate_study",
        column=t["s1_m_auctau"],
        population=f"{group}, {population}",
        table=SourceTable([t["s1_th_animal"], t["s1_m_auctau"]], values, (-1, -1)),
        source_rows=[],
        source_row_count=0,
    )
    return {"tag": tag, "n": len(rows)}


def _means(switch: str, t: dict[str, str]) -> dict[str, Any]:
    """The mean AUCtau of the group with every value and with the plausible ones only."""
    frames, zeros, _ = load_study()
    if switch == "negative":
        frames = _inject(frames)
    clean = validate_study(frames, zeros).clean
    return {
        "all": _figure(auctau_rows(frames, *NAIVE_MEAN), t["s1_row_all"], t),
        "plausible": _figure(auctau_rows(clean, *NAIVE_MEAN), t["s1_row_ok"], t),
    }


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


async def _study_page(request: Request, switch: str) -> HTMLResponse:
    """The whole study screen, with its result rendered on the server for the chosen switch."""
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
    injected = switch == "negative"
    result = _result(report, injected, extra)
    result["means"] = _means(switch if injected else "none", i18n.context(request, 1)["t"])
    return _page(request, "study.html", current=1, r=result, **_study_facts())


@router.get("/study", response_class=HTMLResponse)
async def study(request: Request) -> HTMLResponse:
    return await _study_page(request, "none")


@router.post("/study/run", response_class=HTMLResponse)
async def study_run(request: Request, switch: Annotated[str, Form()] = "none") -> HTMLResponse:
    return await _study_page(request, switch)


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
                "fkey": finding_key(f"{f['tissue']} {f['finding']}"),
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


def _evidence(result: LoopResult) -> list[dict[str, object]]:
    evidence = []
    for o in result.ledger.observations:
        ids = sorted({str(row["usubjid"]) for row in o.source_rows if "usubjid" in row})
        # Incidence source rows are the affected animals; n is the examined count.
        label = "ev_affected" if o.kind.startswith("incidence") else "ev_animals"
        evidence.append(
            {
                "tool": o.tool.name,
                "population": o.population,
                "n": "n/a" if o.n_examined is None else str(o.n_examined),
                "count": len(ids),
                "label": label,
                "first": ids[0] if ids else "",
            }
        )
    return evidence


def _highlighted(sentence_id: str) -> list[dict[str, Any]]:
    return highlights_by_sentence().get(sentence_id, [])


def _all_highlights() -> list[dict[str, Any]]:
    return [e for entries in highlights_by_sentence().values() for e in entries]


def _step2_context(
    question_id: str, directory: Path, t: dict[str, str] | None = None
) -> dict[str, Any]:
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
        f"{latency:.1f} s | "
        + ((t or i18n.CATALOGUES["en"])["s5_cost_na"] if cost is None else f"{cost:.2f} USD")
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
        "rules": ", ".join(str(r) for r in verdict.rules) if verdict and verdict.rules else "",
        "message_key": "exp_declined" if result.message == "the model declined" else "",
        "written": _written(result),
        "doses": doses,
        "rows": rows,
        "rule": next(
            (o.values["screen_rule"] for o in result.ledger.observations if o.kind == SCREEN_KIND),
            "",
        ),
        "evidence": _evidence(result),
        "parts": _answer_parts(result) if result.rendered else [],
    }


def _answer_parts(result: LoopResult) -> list[Part]:
    """The answer sentences as text and provenance tags, one space between sentences.

    The recorded prose is English, so its terms (sex, species, route) are English words too.
    """
    parts: list[Part] = []
    for sentence in result.sentences:
        if parts:
            parts.append(TextPart(" "))
        parts.extend(provenance_parts(sentence, result.ledger))
    return plain_terms(parts, i18n.CATALOGUES["en"])


def _kinds(parts: list[Part]) -> list[str]:
    """The tag kinds present in the parts, in legend order."""
    present = {p.kind for p in parts if not isinstance(p, TextPart)}
    return [k for k in ("data", "decision", "quote") if k in present]


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
        own: list[dict[str, Any]] = []
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
            literal = any(
                normalize_whitespace(m["text"]) == normalize_whitespace(sentence.text)
                and passage.page_start <= m["page"] <= passage.page_end
                for m in marks
            )
            verbatim += literal
            quote = {
                "id": fixed["id"],
                "guideline": title,
                "section": passage.section,
                "page": page,
                "sentence_id": sentence.sentence_id,
                "verbatim": literal,
                "text": sentence.text,
                "cite": " ".join([*row[:2], str(page)]),
                "highlight": f"/highlight/{sentence.sentence_id}" if marks else "",
                "link": f"{base}#page={page}",
            }
            quotes.append(quote)
            own.append(quote)
        queries.append(
            {
                "id": fixed["id"],
                "query": fixed["query"],
                "rows": rows,
                "folded": folded,
                "quotes": own,
            }
        )
    return {
        "queries": queries,
        "quotes": quotes,
        "verbatim": verbatim,
        "guidelines": len(guidelines),
    }


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


# One list on screen 2: the first group is visible, the rest sits in a closed disclosure (C14 cap).
ASK_FIRST = ("Q2", "Q6")
ASK_MORE = ("Q1", "Q3", "Q4", "Q5", "Q7", "Q8", "G1", "G2", "G3", "NS1", "NS2")
ASK_QUERIES = ("NS1", "NS2")  # the two fixed guideline queries, answered from the build-time cache
ASK_TRICKS = frozenset({"Q4", "Q6", "Q7", "Q8"})  # requests the system must decline


def _query_context(question_id: str) -> dict[str, Any]:
    """A fixed guideline query as an answer: its cached quotations, with the page they cite."""
    query = next(q for q in _step3_context()["queries"] if q["id"] == question_id)
    parts: list[Part] = []
    for q in query["quotes"]:
        if parts:
            parts.append(TextPart(" "))
        parts.append(
            QuoteTag(
                text=f"{q['text']} ({q['cite']})",
                guideline=q["guideline"],
                section=q["section"],
                page=q["page"],
                citation=q["cite"],
                sentence_ids=[q["sentence_id"]],
                highlight=q["highlight"],
                link=q["link"],
            )
        )
    return {
        "badge": "RECORDED",
        "meta": query["query"],
        "kind": "quotes",
        "trace": "search_guidance",
        "calls": 1,
        "status": "answered",
        "message": "",
        "answered": True,
        "text": " ",
        "failures": [],
        "rules": "",
        "message_key": "",
        "written": "",
        "doses": [],
        "rows": [],
        "rule": "",
        "evidence": [],
        "parts": parts,
    }


@router.get("/ask", response_class=HTMLResponse)
async def ask_page(request: Request) -> HTMLResponse:
    return _page(
        request,
        "ask.html",
        current=2,
        first=ASK_FIRST,
        more=ASK_MORE,
        tricks=ASK_TRICKS,
        live=bool(os.environ.get("CAIRN_ACCESS_CODE")),
        page_badge=_step2_badge(_recordings_dir()),
    )


@router.post("/ask/run", response_class=HTMLResponse)
def ask_run(request: Request, question: Annotated[str, Form()]) -> HTMLResponse:
    """The recorded answer of any question of the list: study, guideline query or trick."""
    if question not in QUESTIONS and question not in ASK_QUERIES:
        raise HTTPException(status_code=422, detail="unknown question")
    shell = i18n.context(request)
    try:
        if question in ASK_QUERIES:
            context = _query_context(question)
        else:
            context = _step2_context(question, _recordings_dir(), shell["t"])
    except StaleRecording as error:
        return templates.TemplateResponse(
            request, "ask_answer.html", {**shell, "stale": str(error)}
        )
    context = {
        **context,
        "id": question,
        "trick": question in ASK_TRICKS,
        "kinds": _kinds(context["parts"]),
    }
    return templates.TemplateResponse(request, "ask_answer.html", {**shell, "r": context})


REDIRECTS = {1: "/study", 2: "/ask", 3: "/ask", 4: "/decide", 5: "/draft", 6: "/draft", 7: "/draft"}


def _redirect(request: Request, target: str) -> RedirectResponse:
    query = request.url.query
    return RedirectResponse(f"{target}?{query}" if query else target, status_code=303)


@router.get("/step/{number}")
async def old_step(request: Request, number: int) -> RedirectResponse:
    if number not in REDIRECTS:
        raise HTTPException(status_code=404, detail="no such step")
    return _redirect(request, REDIRECTS[number])


@router.get("/explore")
async def old_explore(request: Request) -> RedirectResponse:
    return _redirect(request, "/ask")


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
