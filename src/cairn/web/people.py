"""Screens 3 and 4: thin HTMX handlers over the thread API functions (no model call here)."""

import json
import re
from dataclasses import dataclass
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastmcp import Client
from markupsafe import Markup
from pydantic import TypeAdapter

from cairn.content import DecisionRef, QuoteRef, Sentence, Text, ValueRef
from cairn.decisions import (
    EXAMPLE,
    EXAMPLE_ACTOR,
    KEY_FINDING,
    finding_key,
)
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
from cairn.verify import RULE_REASONS
from cairn.web import _page as page
from cairn.web import _recordings_dir, _step2_context, i18n, provenance
from cairn.web.i18n import CATALOGUES
from cairn.web.provenance import (
    DataTag,
    DecisionInfo,
    DecisionTag,
    Part,
    QuoteTag,
    TextPart,
    number_tags,
    stray_numbers,
    tag_counts,
)
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
    NONCLINICAL_SUMMARY,
    build_ledger,
    draft_key,
    final_ledger,
    sections_of,
    shown_facts,
    verify_final,
)

people = APIRouter()
HOLE = re.compile(r"\[?((?:D\d+|NOAEL-[FM]): no decision yet)\]?")


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


ROLE_KEYS: dict[str, str] = {AUTHOR: "role_author", REVIEWER: "role_reviewer"}
SHORT_ROLES: dict[str, str] = {"author": AUTHOR, "reviewer": REVIEWER}


def _decision_info(state: Any, t: dict[str, str]) -> dict[str, DecisionInfo]:
    """Who decided each slot: the author for a recorded decision, the reviewer for a NOAEL."""

    def info(who: str) -> DecisionInfo:
        if who == EXAMPLE_ACTOR:
            return DecisionInfo(t["prov_example"], t["role_example"])
        return DecisionInfo(who, t[ROLE_KEYS[who]])

    found = {d["dec_id"]: info(d["actor"]) for d in state.get("decisions", [])}
    return {**found, "NOAEL-F": info(REVIEWER), "NOAEL-M": info(REVIEWER)}


@dataclass(frozen=True)
class Hole:
    """A decision nobody has taken yet: shown yellow on the sheet, never filled in."""

    text: str
    kind: str = "hole"


def _marked(part: Part) -> Part | Hole:
    found = HOLE.fullmatch(part.text) if isinstance(part, DecisionTag) else None
    return Hole(found.group(1)) if found else part


def _tags(parts: list[Part], column: str) -> list[DataTag]:
    return [p for p in parts if isinstance(p, DataTag) and p.column == column]


def _first(parts: list[Part], column: str) -> DataTag | None:
    return next(iter(_tags(parts, column)), None)


def _word(tag: DataTag | None, capital: bool = False) -> str:
    """A controlled term as the plain English word, as the sentence shows it."""
    if tag is None:
        return ""
    word = provenance.plain_terms([tag], CATALOGUES["en"])[0].text
    return word[:1].upper() + word[1:] if capital else word


def _listed(tags: list[DataTag], unit: str = "") -> list[Part]:
    """The tags as 'a, b and c', then the unit."""
    out: list[Part] = []
    for i, tag in enumerate(tags):
        if i:
            out.append(TextPart(" and " if i == len(tags) - 1 else ", "))
        out.append(tag)
    return [*out, TextPart(f" {unit}")] if unit and out else out


def _mean_rows(parts: list[Part]) -> list[tuple[str, DataTag]]:
    """Each mean with the label the sentence gives it (including or excluding the quarantine)."""
    rows: list[tuple[str, DataTag]] = []
    for i, part in enumerate(parts[:-1]):
        after = parts[i + 1].text.lower() if isinstance(parts[i + 1], TextPart) else ""
        found = sorted((after.find(w), w) for w in ("including", "excluding") if w in after)
        if isinstance(part, DataTag) and part.column == "mean" and found:
            rows.append((f"{found[0][1].capitalize()} the quarantined value", part))
    return rows


def _by_section(state: Any) -> dict[str, list[Sentence]]:
    adapter = TypeAdapter(list[Sentence])
    saved = state.get("sections", {})
    return {n: adapter.validate_python(saved.get(n, [])) for n in NONCLINICAL_SUMMARY.sections}


NOAEL_HEADINGS = {"NOAEL-F": "Females", "NOAEL-M": "Males"}


def _sheet(state: Any, t: dict[str, str]) -> dict[str, Any]:
    """The draft as a document: sections from the recorded draft, tables from the same tags.

    Every figure on the sheet is a tag (study value, quotation or decision); the headings and
    references are fixed text. Counts come from the tags shown, so they match the page.
    """
    ledger, info, sections = final_ledger(state), _decision_info(state, t), _by_section(state)
    shown: list[Part | Hole] = []

    def show(parts: list[Part]) -> list[Part | Hole]:
        marked = [_marked(p) for p in parts]
        shown.extend(marked)
        return marked

    def prose(sentences: list[Sentence]) -> list[Part | Hole]:
        return show(provenance.draft_parts(sentences, ledger, info))

    def raw(name: str) -> list[Part]:
        return [p for s in sections[name] for p in provenance.provenance_parts(s, ledger, info)]

    design = raw("design")
    study, animals = _tags(design, "study_id")[:1], _tags(design, "n_examined")[:1]
    unit = next((x.text for x in _tags(design, "dose_unit")), "")
    doses = _listed(_tags(design, "dose"), unit)
    strain, kind = _word(_first(design, "strain")), _word(_first(design, "species"))
    species = f"{strain} {kind}".strip()
    route = _word(_first(design, "route"), capital=True)
    meta = [
        ("Study", show(list(study)), "Species", [TextPart(species)]),
        ("Route", [TextPart(route)], "Animals", show(list(animals))),
        ("Dose levels", show(doses), "Status", [TextPart("Draft for review")]),
    ]
    parameters = [
        ("Animals", show([*animals, TextPart(f" {kind}")] if animals else [])),
        ("Route of administration", [TextPart(route)]),
        ("Dose levels", show(doses)),
    ]
    decisions = []
    for sentence in sections["findings"]:
        for tag in provenance.provenance_parts(sentence, ledger, info):
            if isinstance(tag, DecisionTag):
                decisions.append((tag.slot, show([tag])))
    tk = raw("tk")
    heads = _tags(tk, "test")[:1]
    means = [(label, show([tag])) for label, tag in _mean_rows(tk)]
    notes = sections["tk"][1:]
    noael = []
    guidelines: list[str] = []
    for number, sentence in enumerate(sections["noael"], 1):
        parts = provenance.draft_parts([sentence], ledger, info)
        cut = next((i for i, p in enumerate(parts) if isinstance(p, QuoteTag)), len(parts))
        guidelines += [p.guideline for p in parts[cut:] if isinstance(p, QuoteTag)]
        slot = next((p.slot for p in sentence.parts if isinstance(p, DecisionRef)), "")
        noael.append(
            {
                "heading": f"4.{number} {NOAEL_HEADINGS.get(slot, slot)}",
                "text": show(parts[:cut]),
                "quote": show(parts[cut:]),
            }
        )
    # The prose is placed before counting: every tag shown on the sheet is in the counts line.
    intro, tk_intro = prose(sections["design"]), prose(sections["tk"][:1])
    tk_notes = [prose([s]) for s in notes]
    tags = [p for p in shown if not isinstance(p, Hole)]
    counts = tag_counts(tags)
    example = sum(getattr(p, "who", "") == t["prov_example"] for p in tags)
    line = t["draft_counts"].format(
        numbers=number_tags(tags),
        ai=stray_numbers(tags),
        decisions=counts["decision"] - example,
        example=example,
        quotes=counts["quote"],
    )
    return {
        "meta": meta,
        "parameters": parameters,
        "decisions": decisions,
        "intro": intro,
        "tk_intro": tk_intro,
        "tk_head": _word(heads[0]) if heads else "",
        "tk_means": means,
        "tk_notes": tk_notes,
        "noael": noael,
        "guidelines": list(dict.fromkeys(guidelines)),
        "footer": CATALOGUES["en"]["footer_note"],
        "holes": any(isinstance(p, Hole) for p in shown),
        "counts_line": line,
    }


def _incidence(state: Any, sex: str) -> list[tuple[float, int, int]]:
    """Dose, affected and examined animals of the key finding for one sex, from the Observation."""
    for observation in build_ledger(state).observations:
        if not observation.kind.startswith("incidence"):
            continue
        for row in observation.values["findings"]:
            if f"{row['tissue']} {row['finding']}" == KEY_FINDING and row["sex"] == sex:
                return [(g["dose"], g["affected"] or 0, g["examined"] or 0) for g in row["groups"]]
    return []


def _decide_context(
    state: Any, view: dict[str, Any], t: dict[str, str], change: str = ""
) -> dict[str, Any]:
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
                "decided": decision is not None and sex != change,
                "adverse": "" if decision is None else _decision_line(decision, sex, t),
                "related_pick": _pick(decision, "treatment_related_from"),
                "adverse_pick": _pick(decision, "adverse_from"),
                "confirmed": confirmed,
                "noael": (
                    t["undecided"]
                    if not confirmed
                    else t["s4_not_set"]
                    if noael is None
                    else f"{noael:g} mg/kg/day"
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
        "started": any(d["actor"] != EXAMPLE_ACTOR for d in view["decisions"]),
        "both_confirmed": all(x["confirmed"] for x in sexes),
    }


def _decision_line(decision: dict[str, Any], sex: str, t: dict[str, str]) -> str:
    name = t["s1_sex_" + sex].capitalize()
    return t["s4_chosen"].format(
        sex=name,
        related=_label(decision["treatment_related_from"], t),
        adverse=_label(decision["adverse_from"], t),
    )


def _pick(decision: dict[str, Any] | None, field: str) -> str:
    """The radio value that a recorded decision selects; empty when nothing is recorded."""
    if decision is None:
        return ""
    return "none" if decision[field] is None else f"{decision[field]:g}"


def _role(actor: str) -> Actor:
    """The role of the screen: the reviewer by name or short key, otherwise the author."""
    return REVIEWER if actor in ("reviewer", REVIEWER) else AUTHOR


def _label(dose: float | None, t: dict[str, str]) -> str:
    return t["s4_none"] if dose is None else f"{dose:g}"


@people.get("/decide", response_class=HTMLResponse)
async def decide(
    request: Request, thread: str | None = None, change: str = "", actor: str = AUTHOR
) -> Response:
    return await _decide_page(
        request, await _session_thread(request, thread), change=change, actor=_role(actor)
    )


async def _decide_page(
    request: Request,
    thread: str,
    error: str = "",
    status: int = 200,
    change: str = "",
    actor: str = AUTHOR,
) -> Response:
    state, _, view = await load_view(request, thread)
    context = _decide_context(state, view, i18n.context(request)["t"], change)
    response = page(request, "decide.html", current=3, actor=actor, error=error, **context)
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
    actor: Annotated[str, Form()] = AUTHOR,
) -> Response:
    """The Decide button: the reviewer records one sex and confirms it; the author is refused."""
    who = _role(actor)
    thread = await _session_thread(request, thread)
    t = i18n.context(request)["t"]
    try:
        if who == AUTHOR:
            if sex not in ("F", "M"):
                raise HTTPException(status_code=422, detail="unknown sex")
            try:  # the refusal and its audit entry belong to confirm
                await confirm(request, thread, Confirm(actor=AUTHOR, confirmed=[sex]))  # type: ignore[list-item]
            except HTTPException as refusal:
                if refusal.status_code == 409:
                    return _remember(_current(AUTHOR), thread)
                if refusal.status_code != 403:
                    raise
                return await _decide_page(request, thread, t["decide_err_author"], 403, actor=who)
            return await _decide_page(request, thread, actor=who)
        if stale := await _choose(request, thread, sex, adverse, related):
            return stale
        try:
            await confirm(request, thread, Confirm(actor=REVIEWER, confirmed=[sex]))  # type: ignore[list-item]
        except HTTPException as refusal:
            if refusal.status_code != 409:
                raise
            if refusal.detail != "verify_final is not green":
                return _remember(_current(REVIEWER), thread)
            reason = t["confirm_err_verify"]
            error = t["confirm_error"].format(detail=reason)
            return await _decide_page(request, thread, error, 409, actor=who)
        return await _decide_page(request, thread, actor=who)
    except HTTPException as refusal:
        if refusal.status_code != 422:
            raise
        raw = str(refusal.detail)
        key = "decide_err_dose" if raw.startswith("bad dose") else REFUSALS.get(raw, "")
        detail = t.get(key, raw)
        error = t["decide_error"].format(detail=detail)
        return await _decide_page(request, thread, error, 422, actor=who)


async def _choose(
    request: Request, thread: str, sex: str, adverse: str, related: str
) -> Response | None:
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
            example=d["actor"] == EXAMPLE_ACTOR,
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
                example=True,
            )
    items[mine["slot"]] = DecisionIn(
        dec_id=mine["slot"], treatment_related_from=related_from, adverse_from=dose
    )
    try:
        await record_decisions(
            request, thread, Record(actor=REVIEWER, decisions=list(items.values()))
        )
    except HTTPException as refusal:
        if refusal.status_code != 409:
            raise
        return _remember(_current(REVIEWER), thread)
    return None


@people.post("/decide/confirm", response_model=None)
async def decide_confirm(
    request: Request,
    actor: Annotated[str, Form()],
    thread: Annotated[str | None, Form()] = None,
    sex: Annotated[str, Form()] = "",
) -> Response:
    who = _actor(actor)
    thread = await _session_thread(request, thread)
    if sex not in ("", "F", "M"):
        raise HTTPException(status_code=422, detail="unknown sex")
    sexes: list[Literal["F", "M"]] = [sex] if sex else ["F", "M"]  # type: ignore[list-item]
    t = i18n.context(request)["t"]
    _, waiting, view = await load_view(request, thread)
    if waiting == "await_decisions":
        keyed = {s["slot"]: s["sex"] for s in view["slots"] if s["finding"] == KEY_FINDING}
        decided = {keyed[d["dec_id"]] for d in view["decisions"] if d["dec_id"] in keyed}
        if missing := [x for x in sexes if x not in decided]:
            names = " / ".join(t["s1_sex_" + x] for x in missing)
            reason = t["confirm_err_undecided"].format(sex=names)
            return await _decide_page(
                request, thread, t["confirm_error"].format(detail=reason), 409
            )
    try:
        await confirm(request, thread, Confirm(actor=who, confirmed=sexes))
    except HTTPException as refusal:
        if refusal.status_code != 409:
            raise
        if refusal.detail == "verify_final is not green":
            reason = t["confirm_err_verify"]
            return await _decide_page(
                request, thread, t["confirm_error"].format(detail=reason), 409
            )
        return _remember(_current(who), thread)
    if (await get_thread(request, thread))["waiting"] == "await_decisions":
        return _remember(RedirectResponse("/decide", status_code=303), thread)
    return _remember(_current(who), thread)


@people.post("/restart")
async def restart(request: Request) -> Response:
    """Start over: a new thread replaces the one in the cookie."""
    thread = str((await start(request))["thread_id"])
    return _remember(RedirectResponse("/decide", status_code=303), thread)


def _noael_rows(view: dict[str, Any], t: dict[str, str]) -> list[list[str]]:
    """The NOAEL of each sex as the rule gives it once confirmed, else 'not decided yet'."""
    return [
        [
            f"{t['draft_noael']} {sex}",
            f"{n['dose']:g} mg/kg/day"
            if sex in view["confirmed"] and n["dose"] is not None
            else t["undecided"],
        ]
        for sex, n in view["noael"].items()
    ]


async def _undecided(request: Request, thread: str, view: dict[str, Any], actor: str) -> Response:
    """The draft page while the decisions are still open: gaps stay visible, nothing is invented."""
    t = i18n.context(request)["t"]
    state = (await load_view(request, thread))[0]
    response = page(
        request,
        "draft.html",
        current=4,
        actor=actor,
        thread=thread,
        undecided=True,
        noael=_noael_rows(view, t),
        sheet=_sheet(state, t),
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
        sheet=_sheet(state, t),
        noael=_noael_rows(view, t),
        flags=[r["reason"] for r in view["judge"] if r["verdict"] == "overstated"],
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


def _landing_sentence(t: dict[str, str]) -> list[provenance.Part]:
    """The first clause of the recorded body-weight answer (Q3 of /ask), same parts as there."""
    parts: list[provenance.Part] = _step2_context(LANDING_QUESTION, _recordings_dir(), t)["parts"]
    for i, part in enumerate(parts):
        if isinstance(part, TextPart) and ";" in part.text:
            head = part.text.split(";", 1)[0]
            return [*parts[:i], TextPart(head + " ...")]
    return parts


LANDING_QUESTION = "Q3"  # the recorded body-weight answer of /ask


@people.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> Response:
    """The result first: one real draft sentence with its numbers marked, then one button."""
    thread = await _session_thread(request)
    t = i18n.context(request)["t"]
    parts = _landing_sentence(t)
    counts = t["land_counts"].format(numbers=number_tags(parts), ai=stray_numbers(parts))
    response = page(request, "landing.html", current=0, parts=parts, counts_line=counts)
    return _remember(response, thread)


@people.get("/draft", response_class=HTMLResponse)
async def draft(request: Request, thread: str | None = None, actor: str = REVIEWER) -> Response:
    thread = await _session_thread(request, thread)
    return await _draft_page(request, thread, _actor(SHORT_ROLES.get(actor, actor)))


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
