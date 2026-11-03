"""Screens 3 and 4: thin HTMX handlers over the thread API functions (no model call here)."""

import json
import re
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastmcp import Client
from markupsafe import Markup, escape

from cairn.content import QuoteRef, Text, ValueRef
from cairn.decisions import EXAMPLE, Decision, apply_decisions
from cairn.gateway import DEFAULT_MODEL
from cairn.judge import (
    EXAMPLE_OBS,
    EXAMPLE_SENTENCE,
    JUDGE_MODEL,
    KAPPA_PATH,
    NOT_JUDGED,
    replay_judge,
)
from cairn.recording import RECORDINGS_DIR, ReplayClient, recorded_model, total_cost
from cairn.render import render
from cairn.verify import RULE_REASONS
from cairn.web import _page as page
from cairn.web import i18n, templates
from cairn.web.threads import (
    AUTHOR,
    REVIEWER,
    Actor,
    Approve,
    Confirm,
    DecisionIn,
    Record,
    approve,
    confirm,
    get_thread,
    load_view,
    record_decisions,
    start,
    verify_audit,
)
from cairn.workflow import build_ledger, draft_key, sections_of, shown_facts, verify_final

people = APIRouter()
EMPTY_SLOT = re.compile(r"\[((?:D\d+|NOAEL-[FM]): no decision yet)\]")


def _choice(dose: float | None) -> str:
    return "none" if dose is None else f"{dose:g}"


def _dose(value: str) -> float | None:
    if value == "none":
        return None
    try:
        return float(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"bad dose {value!r}") from None


def _actor(actor: str) -> Actor:
    if actor not in (AUTHOR, REVIEWER):
        raise HTTPException(status_code=422, detail="unknown actor")
    return actor


COOKIE = "cairn_thread"
COOKIE_MAX_AGE = 60 * 60 * 24


def _current(actor: str) -> RedirectResponse:
    """After a 409: the page for the state the thread is really in, not the raw JSON."""
    return RedirectResponse(f"/draft?actor={actor}", status_code=303)


def _remember(response: Response, thread: str) -> Response:
    response.set_cookie(COOKIE, thread, max_age=COOKIE_MAX_AGE, samesite="lax", path="/")
    return response


async def _session_thread(request: Request, explicit: str | None = None) -> str:
    """The visitor's thread: the query or form value, else the cookie, else a new one."""
    for candidate in (explicit, request.cookies.get(COOKIE)):
        if not candidate:
            continue
        try:
            await get_thread(request, candidate)
        except HTTPException as missing:
            if missing.status_code != 404:
                raise
        else:
            return candidate
    return str((await start(request))["thread_id"])


async def _draft(request: Request, thread: str) -> Markup:
    """The draft with the decisions placed so far; an empty slot is a dashed box."""
    state = (await load_view(request, thread))[0]
    ledger = build_ledger(state)
    decisions = [Decision.model_validate(d) for d in state.get("decisions", [])]
    apply_decisions(ledger, decisions, frozenset(state.get("confirmed", [])))
    text = str(escape(render(sections_of(state), ledger)))
    return Markup(EMPTY_SLOT.sub(r'<span class="slot">\1</span>', text))


def _select(name: str, label: str, doses: list[str], chosen: str, t: dict[str, str]) -> Markup:
    options = [("", t["s4_choose"]), ("none", t["s4_none"]), *[(d, d) for d in doses]]
    body = "".join(
        Markup('<option value="{}"{}>{}</option>').format(
            v, Markup(" selected" if v == chosen else ""), t
        )
        for v, t in options
    )
    return Markup('<select name="{}" aria-label="{}">{}</select>').format(name, label, Markup(body))


async def _fragment(request: Request, view: dict[str, Any]) -> dict[str, Any]:
    """What a dropdown change recomputes, and what the page needs to draw its rows."""
    given = {d["dec_id"]: d for d in view["decisions"]}
    rows = [
        {
            **s,
            "doses": [f"{d:g}" for d in s["doses"] if d > 0],
            "t": _choice(given[s["slot"]]["treatment_related_from"]) if s["slot"] in given else "",
            "a": _choice(given[s["slot"]]["adverse_from"]) if s["slot"] in given else "",
        }
        for s in view["slots"]
    ]
    t = i18n.context(request)["t"]
    table = [
        [
            r["finding"],
            r["sex"],
            _select(
                "t_" + r["slot"],
                f"{t['s4_th_related']} {r['finding']} {r['sex']}",
                r["doses"],
                r["t"],
                t,
            ),
            _select(
                "a_" + r["slot"],
                f"{t['s4_th_adverse']} {r['finding']} {r['sex']}",
                r["doses"],
                r["a"],
                t,
            ),
        ]
        for r in rows
    ]
    return {
        "thread": view["thread_id"],
        "rows": table,
        "noael": view["noael"],
        "complete": len(given) == len(view["slots"]),
        "draft": await _draft(request, view["thread_id"]),
    }


@people.get("/decide", response_class=HTMLResponse)
async def decide(request: Request, thread: str | None = None) -> Response:
    thread = await _session_thread(request, thread)
    view = await get_thread(request, thread)
    fragment = await _fragment(request, view)
    response = page(request, "decide.html", current=3, actor=AUTHOR, **fragment)
    return _remember(response, thread)


@people.post("/decide/set", response_class=HTMLResponse)
async def decide_set(request: Request) -> HTMLResponse:
    form = await request.form()
    thread = await _session_thread(request, str(form["thread"]) if "thread" in form else None)
    items = []
    for slot in (await get_thread(request, thread))["slots"]:
        t, a = str(form.get("t_" + slot["slot"], "")), str(form.get("a_" + slot["slot"], ""))
        if t and a:
            items.append(
                DecisionIn(
                    dec_id=slot["slot"], treatment_related_from=_dose(t), adverse_from=_dose(a)
                )
            )
    try:
        view = await record_decisions(request, thread, Record(actor=AUTHOR, decisions=items))
    except HTTPException as refusal:
        if refusal.status_code != 409:
            raise
        return HTMLResponse(
            status_code=204, headers={"HX-Redirect": _current(AUTHOR).headers["location"]}
        )
    fragment = await _fragment(request, view)
    response = templates.TemplateResponse(
        request, "decide_result.html", {**i18n.context(request), **fragment}
    )
    return _remember(response, thread)  # type: ignore[return-value]


@people.post("/decide/example")
async def decide_example(
    request: Request, thread: Annotated[str | None, Form()] = None
) -> RedirectResponse:
    thread = await _session_thread(request, thread)
    slots = (await get_thread(request, thread))["slots"]
    items = [
        DecisionIn(
            dec_id=s["slot"],
            treatment_related_from=EXAMPLE[s["sex"], s["finding"]][0],
            adverse_from=EXAMPLE[s["sex"], s["finding"]][1],
        )
        for s in slots
    ]
    try:
        await record_decisions(request, thread, Record(actor=AUTHOR, decisions=items))
    except HTTPException as refusal:
        if refusal.status_code != 409:
            raise
        return _remember(_current(AUTHOR), thread)  # type: ignore[return-value]
    return _remember(RedirectResponse("/decide", status_code=303), thread)  # type: ignore[return-value]


@people.post("/decide/confirm")
async def decide_confirm(
    request: Request,
    actor: Annotated[str, Form()],
    thread: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    who = _actor(actor)
    thread = await _session_thread(request, thread)
    try:
        await confirm(request, thread, Confirm(actor=who, confirmed=["F", "M"]))
    except HTTPException as refusal:
        if refusal.status_code != 409:
            raise
    return _remember(_current(who), thread)  # type: ignore[return-value]


async def _undecided(request: Request, thread: str, view: dict[str, Any], actor: str) -> Response:
    """The draft page while the decisions are still open: gaps stay visible, nothing is invented."""
    t = i18n.context(request)["t"]
    noael = [
        [
            f"{t['draft_noael']} {sex}",
            f"{n['dose']:g} mg/kg/day"
            if sex in view["confirmed"] and n["dose"] is not None
            else t["undecided"],
        ]
        for sex, n in view["noael"].items()
    ]
    response = page(
        request,
        "draft.html",
        current=4,
        actor=actor,
        thread=thread,
        undecided=True,
        noael=noael,
        text=await _draft(request, thread),
    )
    return _remember(response, thread)


def _judge_meta() -> str:
    """The kappa and n come from the calibration result file; absent until it is recorded."""
    try:
        result = json.loads(KAPPA_PATH.read_text(encoding="utf-8"))
        calibration = f"n={result['n']} | kappa {result['kappa']:.2f}"
    except (OSError, ValueError, KeyError):
        calibration = "n n/a | kappa n/a"
    return f"{JUDGE_MODEL} | {calibration}"


def _judge_rows(results: list[dict[str, str]], state: Any, t: dict[str, str]) -> list[list[Any]]:
    """Each warning, one row for the sentences not judged, then the EXAMPLE overstated sentence."""
    example = replay_judge(
        RECORDINGS_DIR, EXAMPLE_SENTENCE, shown_facts(build_ledger(state), EXAMPLE_OBS)
    )
    rows: list[list[Any]] = [
        [r["sentence"], f"{t['s5_warning']} {r['category']}", r["reason"]]
        for r in results
        if r["verdict"] == "overstated"
    ]
    unjudged = sum(r["verdict"] == NOT_JUDGED for r in results)
    if unjudged:  # one row, so the panel stays on one screen whatever the decisions
        rows.append([f"{unjudged} {t['s5_unjudged']}", NOT_JUDGED, t["s5_no_recording"]])
    verdict = (
        f"{t['s5_warning']} {example['category']}"
        if example["verdict"] == "overstated"
        else example["verdict"]
    )
    badge = Markup('<span class="badge example">EXAMPLE</span>')
    rows.append([badge + " " + EXAMPLE_SENTENCE, verdict, example["reason"]])
    return rows


REPO = "https://github.com/mikelju/cairn"
STEP7_LINKS = [
    ("s7_link_memo", f"{REPO}/commit/7897d079c8665301821fe0e0faffdfd988b6ce82"),
    ("s7_link_pr", f"{REPO}/pull/6"),
    ("s7_link_rest", "/docs"),
    ("s7_link_mcp", "/mcp"),
]
PRODUCTION_KEYS = ["identity", "audit", "model", "sign"]


async def _two_doors(request: Request) -> tuple[str, str]:
    """The same tool called over MCP and over REST: the content hash of each Observation.

    REST goes through the app's own HTTP route, in process, so a broken route shows as a failure.
    """
    async with Client(request.app.state.mcp) as client:
        over_mcp = (await client.call_tool("study_design", {})).structured_content or {}
    transport = httpx.ASGITransport(app=request.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://cairn") as http:
        reply = await http.post("/api/tools/study_design", json={})
    over_rest = reply.json().get("content_sha256") if reply.status_code == 200 else None
    return str(over_mcp["content_sha256"]), str(over_rest or f"HTTP {reply.status_code}")


async def _draft_page(request: Request, thread: str, actor: str, error: str = "") -> Response:
    state, waiting, view = await load_view(request, thread)
    if waiting == "await_decisions":
        return await _undecided(request, thread, view, actor)
    t = i18n.context(request)["t"]
    model = recorded_model(RECORDINGS_DIR, "DRAFT", DEFAULT_MODEL)
    recording = ReplayClient.load(RECORDINGS_DIR, draft_key(model)).recording
    cost = total_cost(recording)
    latency = sum(float(call.get("latency_s", 0.0)) for call in recording["calls"])
    failed = {f.rule: f.reason for f in verify_final(state).failures}
    chain = await verify_audit(request, thread)
    parts = [p for s in sections_of(state) for p in s.parts]
    by_model = sum(c.isdigit() for p in parts if isinstance(p, Text) for c in p.text)
    over_mcp, over_rest = await _two_doors(request)
    session = [
        [
            t["s7_draft"],
            f"{latency:.1f} s, " + (t["s5_cost_na"] if cost is None else f"{cost:.2f} USD"),
        ],
        [
            t["s7_rules"],
            t["s7_rules_value"].format(a=len(RULE_REASONS) - len(failed), b=len(RULE_REASONS)),
        ],
        [
            t["s7_chain"],
            t["s7_chain_value"].format(
                n=chain["count"], state=t["s7_verified"] if chain["ok"] else t["s7_broken"]
            ),
        ],
        [t["s7_approval"], view["approved_by"] or t["s7_not_yet"]],
    ]
    response = page(
        request,
        "draft.html",
        current=4,
        actor=actor,
        thread=thread,
        undecided=False,
        error=error,
        text=view["final"]["text"],
        approved_by=view["approved_by"],
        meta=(
            f"{recording['date']} | {recording['region']} | {recording['model']} | "
            f"{latency:.1f} s | " + (t["s5_cost_na"] if cost is None else f"{cost:.2f} USD")
        ),
        passed=len(RULE_REASONS) - len(failed),
        rule_total=len(RULE_REASONS),
        judge_meta=_judge_meta(),
        judge_rows=_judge_rows(view["judge"], state, t),
        judged=sum(r["verdict"] != NOT_JUDGED for r in view["judge"]),
        total=len(view["judge"]),
        rules=[
            [n, t["s6_fired"] if n in failed else t["s6_passed"], failed.get(n, reason)]
            for n, reason in RULE_REASONS.items()
        ],
        fired=len(failed),
        entries=chain["count"],
        chain=(
            t["s6_chain_ok"]
            if chain["ok"]
            else t["s6_chain_broken"].format(n=chain["first_broken"])
        ),
        chain_ok=chain["ok"],
        session=session,
        numbers=sum(isinstance(p, ValueRef) for p in parts),
        by_model=by_model,
        quotes=sum(isinstance(p, QuoteRef) for p in parts),
        decisions=len(view["decisions"]),
        doors=[["MCP", over_mcp[:16]], ["REST", over_rest[:16]]],
        same=over_mcp == over_rest,
        links=[(t[key], href) for key, href in STEP7_LINKS],
        production=[
            [t[f"s7_p_{k}"], t[f"s7_p_{k}_demo"], t[f"s7_p_{k}_prod"]] for k in PRODUCTION_KEYS
        ],
    )
    return _remember(response, thread)


@people.get("/draft", response_class=HTMLResponse)
async def draft(request: Request, thread: str | None = None, actor: str = REVIEWER) -> Response:
    thread = await _session_thread(request, thread)
    return await _draft_page(request, thread, _actor(actor))


@people.post("/draft/approve", response_class=HTMLResponse)
async def draft_approve(
    request: Request,
    actor: Annotated[str, Form()],
    thread: Annotated[str | None, Form()] = None,
) -> Response:
    who = _actor(actor)
    thread = await _session_thread(request, thread)
    error = ""
    try:
        await approve(request, thread, Approve(actor=who))
    except HTTPException as refusal:
        if refusal.status_code == 409:
            return _remember(_current(who), thread)
        if refusal.status_code != 403:
            raise
        t = i18n.context(request)["t"]
        error = t["s5_refused"].format(detail=refusal.detail)
    return await _draft_page(request, thread, who, error)
