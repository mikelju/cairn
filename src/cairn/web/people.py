"""Screens 3 and 4: thin HTMX handlers over the thread API functions (no model call here)."""

import json
import re
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastmcp import Client
from markupsafe import Markup, escape

from cairn.content import QuoteRef, Sentence, Text, ValueRef
from cairn.decisions import EXAMPLE, KEY_FINDING, Decision, apply_decisions, finding_key
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
from cairn.web import i18n, provenance
from cairn.web.provenance import DecisionInfo, TextPart, stray_digits, tag_counts
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
from cairn.workflow import (
    build_ledger,
    draft_key,
    final_ledger,
    sections_of,
    shown_facts,
    verify_final,
)

people = APIRouter()
EMPTY_SLOT = re.compile(r"\[((?:D\d+|NOAEL-[FM]): no decision yet)\]")


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


ROLE_KEYS: dict[str, str] = {AUTHOR: "role_author", REVIEWER: "role_reviewer"}


def _decision_info(state: Any, t: dict[str, str]) -> dict[str, DecisionInfo]:
    """Who decided each slot: the author for a recorded decision, the reviewer for a NOAEL."""

    def info(who: str) -> DecisionInfo:
        return DecisionInfo(who, t[ROLE_KEYS[who]])

    found = {d["dec_id"]: info(d["actor"]) for d in state.get("decisions", [])}
    return {**found, "NOAEL-F": info(REVIEWER), "NOAEL-M": info(REVIEWER)}


def _body(state: Any, t: dict[str, str]) -> dict[str, Any]:
    """The final draft as tagged parts, the legend kinds used and the counts line."""
    parts = provenance.draft_parts(
        sections_of(state), final_ledger(state), _decision_info(state, t)
    )
    counts = tag_counts(parts)
    kinds = [k for k in ("data", "quote", "decision") if counts[k]]
    line = t["draft_counts"].format(
        numbers=counts["data"],
        ai=len(stray_digits(parts)),
        decisions=counts["decision"],
        quotes=counts["quote"],
    )
    words = len("".join(p.text for p in parts).split())
    return {"parts": parts, "kinds": kinds, "counts_line": line, "words": words}


def _incidence(state: Any, sex: str) -> list[tuple[float, int, int]]:
    """Dose, affected and examined animals of the key finding for one sex, from the Observation."""
    for observation in build_ledger(state).observations:
        if not observation.kind.startswith("incidence"):
            continue
        for row in observation.values["findings"]:
            if f"{row['tissue']} {row['finding']}" == KEY_FINDING and row["sex"] == sex:
                return [(g["dose"], g["affected"] or 0, g["examined"] or 0) for g in row["groups"]]
    return []


def _decide_context(state: Any, view: dict[str, Any], t: dict[str, str]) -> dict[str, Any]:
    """What /decide draws: the incidence table, one block per sex and the example list."""
    given = {d["dec_id"]: d for d in view["decisions"]}
    slots = {s["slot"]: s for s in view["slots"]}
    sexes = []
    for sex in ("F", "M"):
        slot = next(s for s in view["slots"] if s["finding"] == KEY_FINDING and s["sex"] == sex)
        decision = given.get(slot["slot"])
        confirmed = sex in view["confirmed"]
        noael = view["noael"][sex]["dose"]
        sexes.append(
            {
                "sex": sex,
                "name": t["s1_sex_" + sex].capitalize(),
                "doses": [f"{d:g}" for d in slot["doses"] if d > 0],
                "decided": decision is not None,
                "adverse": "" if decision is None else _decision_line(decision, sex, t),
                "confirmed": confirmed,
                "noael": (
                    t["undecided"]
                    if not confirmed
                    else t["s4_not_set"]
                    if noael is None
                    else f"{noael:g} mg/kg"
                ),
            }
        )
    rows = [
        [f"{r[0]}", *[f"{a}/{n}" for _, a, n in r[1]]]
        for r in ((t["s1_sex_" + sex], _incidence(state, sex)) for sex in ("F", "M"))
    ]
    doses = [d for d, _, _ in _incidence(state, "F")]
    heads = [t["s4_th_sex"], *[t["s4_control"] if d == 0 else f"{d:g}" for d in doses]]
    examples = [
        [
            t[finding_key(s["finding"])],
            t["s1_sex_" + s["sex"]],
            _label(EXAMPLE[s["sex"], s["finding"]][1], t),
            t["s4_ex_tag"],
        ]
        for s in slots.values()
        if s["finding"] != KEY_FINDING
    ]
    return {
        "thread": view["thread_id"],
        "sexes": sexes,
        "inc_heads": heads,
        "inc_rows": rows,
        "examples": examples,
        "both_confirmed": all(x["confirmed"] for x in sexes),
    }


def _decision_line(decision: dict[str, Any], sex: str, t: dict[str, str]) -> str:
    name = t["s1_sex_" + sex].capitalize()
    return t["s4_chosen"].format(
        sex=name,
        related=_label(decision["treatment_related_from"], t),
        adverse=_label(decision["adverse_from"], t),
    )


def _label(dose: float | None, t: dict[str, str]) -> str:
    return t["s4_none"] if dose is None else f"{dose:g}"


@people.get("/decide", response_class=HTMLResponse)
async def decide(request: Request, thread: str | None = None) -> Response:
    return await _decide_page(request, await _session_thread(request, thread))


async def _decide_page(
    request: Request, thread: str, error: str = "", status: int = 200
) -> Response:
    state, _, view = await load_view(request, thread)
    context = _decide_context(state, view, i18n.context(request)["t"])
    response = page(request, "decide.html", current=3, actor=AUTHOR, error=error, **context)
    response.status_code = status
    return _remember(response, thread)


REFUSALS = {
    "unknown sex": "decide_err_sex",
    "choose both related and adverse": "decide_err_both",
    "adverse cannot be below treatment-related": "decide_err_order",
    "adverse needs a treatment-related dose": "decide_err_need",
    "dose not in the study": "decide_err_dose",
}


@people.post("/decide/choose")
async def decide_choose(
    request: Request,
    sex: Annotated[str, Form()] = "",
    adverse: Annotated[str, Form()] = "",
    related: Annotated[str, Form()] = "",
    thread: Annotated[str | None, Form()] = None,
) -> Response:
    """Record the visitor's two choices for one sex; a refusal is a one-line message, not JSON."""
    thread = await _session_thread(request, thread)
    try:
        return await _choose(request, thread, sex, adverse, related)
    except HTTPException as refusal:
        if refusal.status_code != 422:
            raise
        t = i18n.context(request)["t"]
        raw = str(refusal.detail)
        key = "decide_err_dose" if raw.startswith("bad dose") else REFUSALS.get(raw, "")
        detail = t.get(key, raw)
        return await _decide_page(request, thread, t["decide_error"].format(detail=detail), 422)


async def _choose(
    request: Request, thread: str, sex: str, adverse: str, related: str
) -> RedirectResponse:
    _, _, view = await load_view(request, thread)
    if sex not in ("F", "M"):
        raise HTTPException(status_code=422, detail="unknown sex")
    if not related or not adverse:
        raise HTTPException(status_code=422, detail="choose both related and adverse")
    dose = _dose(adverse)
    related_from = _dose(related)
    if related_from is not None and dose is not None and related_from > dose:
        raise HTTPException(status_code=422, detail="adverse cannot be below treatment-related")
    if related_from is None and dose is not None:
        raise HTTPException(status_code=422, detail="adverse needs a treatment-related dose")
    mine = next(s for s in view["slots"] if s["finding"] == KEY_FINDING and s["sex"] == sex)
    if any(x is not None and x not in mine["doses"] for x in (dose, related_from)):
        raise HTTPException(status_code=422, detail="dose not in the study")
    items = {
        d["dec_id"]: DecisionIn(
            dec_id=d["dec_id"],
            treatment_related_from=d["treatment_related_from"],
            adverse_from=d["adverse_from"],
        )
        for d in view["decisions"]
    }
    for s in view["slots"]:
        if s["finding"] != KEY_FINDING and s["slot"] not in items:
            example_related, example_adverse = EXAMPLE[s["sex"], s["finding"]]
            items[s["slot"]] = DecisionIn(
                dec_id=s["slot"],
                treatment_related_from=example_related,
                adverse_from=example_adverse,
            )
    items[mine["slot"]] = DecisionIn(
        dec_id=mine["slot"], treatment_related_from=related_from, adverse_from=dose
    )
    try:
        await record_decisions(
            request, thread, Record(actor=AUTHOR, decisions=list(items.values()))
        )
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
    sex: Annotated[str, Form()] = "",
) -> RedirectResponse:
    who = _actor(actor)
    thread = await _session_thread(request, thread)
    if sex not in ("", "F", "M"):
        raise HTTPException(status_code=422, detail="unknown sex")
    sexes: list[Literal["F", "M"]] = [sex] if sex else ["F", "M"]  # type: ignore[list-item]
    try:
        await confirm(request, thread, Confirm(actor=who, confirmed=sexes))
    except HTTPException as refusal:
        if refusal.status_code != 409:
            raise
        return _remember(_current(who), thread)  # type: ignore[return-value]
    if (await get_thread(request, thread))["waiting"] == "await_decisions":
        return _remember(RedirectResponse("/decide", status_code=303), thread)  # type: ignore[return-value]
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


STEP7_LINKS = [("s7_link_rest", "/docs")]
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
        body=_body(state, t),
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
        flagged=sum(r["verdict"] == "overstated" for r in view["judge"]),
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


def _landing_sentence(state: Any) -> list[provenance.Part]:
    """The body-weight sentence of the draft, rendered by code; every digit sits in a tag.

    The recorded draft has no such sentence yet, so the code composes it from the first
    body-weight Observation: text and references only, placed by the same renderer.
    """
    ledger = final_ledger(state)
    for section in sections_of(state):
        parts = provenance.provenance_parts(section, ledger)
        data = [p for p in parts if not isinstance(p, TextPart)]
        if data and all(getattr(p, "tool", "") == "body_weight_change" for p in data):
            return parts
    obs_id = next(i for i in ledger.ids if ledger.get(i).kind == "body_weight_change")

    def ref(field: str) -> ValueRef:
        return ValueRef(obs_id=obs_id, field=field)

    sentence = Sentence(
        parts=[
            Text(text="Mean body weight on day "),
            ref("day"),
            Text(text=" at "),
            ref("groups.1.dose"),
            Text(text=" mg/kg was "),
            ref("groups.1.mean_day29_g"),
            Text(text=" g, "),
            ref("groups.1.percent_lower_than_control"),
            Text(text=" percent lower than control."),
        ]
    )
    return provenance.provenance_parts(sentence, ledger)


@people.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> Response:
    """The result first: one real draft sentence with its numbers marked, then one button."""
    thread = await _session_thread(request)
    parts = _landing_sentence((await load_view(request, thread))[0])
    t = i18n.context(request)["t"]
    counts = t["land_counts"].format(numbers=tag_counts(parts)["data"], ai=len(stray_digits(parts)))
    if i18n.context(request)["locale"] == "es":
        counts += " | " + t["land_english"]
    response = page(request, "landing.html", current=0, parts=parts, counts_line=counts)
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
        error = t["s5_refused"]
    page_response = await _draft_page(request, thread, who, error)
    if error:
        page_response.status_code = 403  # the API's refusal stays a 403; the page says it plainly
    return page_response
