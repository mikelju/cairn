"""Steps 4 and 5: thin HTMX handlers over the thread API functions (no model call here)."""

import re
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from markupsafe import Markup, escape

from cairn.decisions import EXAMPLE, Decision, apply_decisions
from cairn.gateway import DEFAULT_MODEL
from cairn.recording import RECORDINGS_DIR, ReplayClient, recorded_model, total_cost
from cairn.render import render
from cairn.verify import RULE_REASONS
from cairn.web import _page as page
from cairn.web import templates
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
)
from cairn.workflow import build_ledger, draft_key, sections_of, verify_final

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


def _current(thread: str, actor: str) -> RedirectResponse:
    """After a 409: the page for the state the thread is really in, not the raw JSON."""
    return RedirectResponse(f"/step/5?thread={thread}&actor={actor}", status_code=303)


async def _draft(request: Request, thread: str) -> Markup:
    """The draft with the decisions placed so far; an empty slot is a dashed box."""
    state = (await load_view(request, thread))[0]
    ledger = build_ledger(state)
    decisions = [Decision.model_validate(d) for d in state.get("decisions", [])]
    apply_decisions(ledger, decisions, frozenset(state.get("confirmed", [])))
    text = str(escape(render(sections_of(state), ledger)))
    return Markup(EMPTY_SLOT.sub(r'<span class="slot">\1</span>', text))


def _select(name: str, label: str, doses: list[str], chosen: str) -> Markup:
    options = [("", "choose"), ("none", "none"), *[(d, d) for d in doses]]
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
    table = [
        [
            r["finding"],
            r["sex"],
            _select(
                "t_" + r["slot"],
                f"Treatment-related from {r['finding']} {r['sex']}",
                r["doses"],
                r["t"],
            ),
            _select(
                "a_" + r["slot"], f"Adverse from {r['finding']} {r['sex']}", r["doses"], r["a"]
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


@people.get("/step/4", response_class=HTMLResponse)
async def step4(request: Request, thread: str | None = None) -> Response:
    if thread is None:
        view = await start(request)
        return RedirectResponse(f"/step/4?thread={view['thread_id']}", status_code=303)
    view = await get_thread(request, thread)
    return page(request, "step4.html", current=4, actor=AUTHOR, **await _fragment(request, view))


@people.post("/step/4/decide", response_class=HTMLResponse)
async def step4_decide(request: Request) -> HTMLResponse:
    form = await request.form()
    if "thread" not in form:
        raise HTTPException(status_code=422, detail="thread is required")
    thread = str(form["thread"])
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
            status_code=204, headers={"HX-Redirect": _current(thread, AUTHOR).headers["location"]}
        )
    return templates.TemplateResponse(request, "step4_result.html", await _fragment(request, view))


@people.post("/step/4/example")
async def step4_example(request: Request, thread: Annotated[str, Form()]) -> RedirectResponse:
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
        return _current(thread, AUTHOR)
    return RedirectResponse(f"/step/4?thread={thread}", status_code=303)


@people.post("/step/4/confirm")
async def step4_confirm(
    request: Request, thread: Annotated[str, Form()], actor: Annotated[str, Form()]
) -> RedirectResponse:
    who = _actor(actor)
    try:
        await confirm(request, thread, Confirm(actor=who, confirmed=["F", "M"]))
    except HTTPException as refusal:
        if refusal.status_code != 409:
            raise
        return _current(thread, who)
    return RedirectResponse(f"/step/5?thread={thread}&actor={actor}", status_code=303)


async def _step5(request: Request, thread: str, actor: str, error: str = "") -> Response:
    state, waiting, view = await load_view(request, thread)
    if waiting == "await_decisions":
        return RedirectResponse(f"/step/4?thread={thread}", status_code=303)
    model = recorded_model(RECORDINGS_DIR, "DRAFT", DEFAULT_MODEL)
    recording = ReplayClient.load(RECORDINGS_DIR, draft_key(model)).recording
    cost = total_cost(recording)
    latency = sum(float(call.get("latency_s", 0.0)) for call in recording["calls"])
    failed = set(verify_final(state).rules)
    return page(
        request,
        "step5.html",
        current=5,
        actor=actor,
        thread=thread,
        error=error,
        text=view["final"]["text"],
        approved_by=view["approved_by"],
        meta=(
            f"{recording['date']} | {recording['region']} | {recording['model']} | "
            f"{latency:.1f} s | " + ("cost n/a" if cost is None else f"{cost:.2f} USD")
        ),
        checks=[
            [f"{n} {reason}", "fail" if n in failed else "pass"]
            for n, reason in RULE_REASONS.items()
        ],
    )


@people.get("/step/5", response_class=HTMLResponse)
async def step5(request: Request, thread: str | None = None, actor: str = REVIEWER) -> Response:
    if thread is None:
        return RedirectResponse("/step/4", status_code=303)
    return await _step5(request, thread, _actor(actor))


@people.post("/step/5/approve", response_class=HTMLResponse)
async def step5_approve(
    request: Request, thread: Annotated[str, Form()], actor: Annotated[str, Form()]
) -> Response:
    who = _actor(actor)
    error = ""
    try:
        await approve(request, thread, Approve(actor=who))
    except HTTPException as refusal:
        if refusal.status_code == 409:
            return _current(thread, who)
        if refusal.status_code != 403:
            raise
        error = f"403 · {refusal.detail} Enforced by the API, not the UI"
    return await _step5(request, thread, who, error)
