"""JSON API for the nonclinical-summary workflow: start, record decisions, confirm, approve.

The actor comes in each request (two simulated demo users); the API, not the page, refuses
self-approval. Recording decisions only updates the checkpoint and recomputes: no model call.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, NoReturn

from fastapi import APIRouter, HTTPException, Request
from langgraph.types import Command
from pydantic import BaseModel

from cairn import audit
from cairn.decisions import Decision, apply_decisions, enumerate_slots
from cairn.gateway import DEFAULT_MODEL, LLMGateway, Mode
from cairn.observation import current_snapshot
from cairn.recording import RECORDINGS_DIR, ReplayClient, recorded_model, recording_path
from cairn.workflow import State, build_graph, build_ledger, draft_key, verify_final

Actor = Literal["A. Author", "R. Reviewer"]
AUTHOR: Actor = "A. Author"
REVIEWER: Actor = "R. Reviewer"
threads = APIRouter(prefix="/api/threads")


_locks: dict[str, asyncio.Lock] = {}


def _lock(thread_id: str) -> asyncio.Lock:
    """One lock per thread: the check of the pause and the write or resume happen together."""
    return _locks.setdefault(thread_id, asyncio.Lock())


class DecisionIn(BaseModel):
    dec_id: str
    treatment_related_from: float | None = None
    adverse_from: float | None = None


class Record(BaseModel):
    actor: Actor
    decisions: list[DecisionIn]


class Confirm(BaseModel):
    actor: Actor
    confirmed: list[Literal["F", "M"]]


class Approve(BaseModel):
    actor: Actor


def _graph(request: Request) -> Any:
    directory = RECORDINGS_DIR
    model = recorded_model(directory, "DRAFT", DEFAULT_MODEL)
    client = ReplayClient.load(directory, draft_key(model))
    return build_graph(LLMGateway(Mode.REPLAY, client=client), model, request.app.state.saver)


def _config(thread_id: str) -> Any:
    return {"configurable": {"thread_id": thread_id}}


async def _load(request: Request, thread_id: str) -> tuple[Any, Any, State, str]:
    graph = _graph(request)
    snapshot = await graph.aget_state(_config(thread_id))
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="thread not found")
    waiting = snapshot.next[0] if snapshot.next else "done"
    return graph, _config(thread_id), snapshot.values, waiting


def _view(thread_id: str, state: State, waiting: str) -> dict[str, Any]:
    ledger = build_ledger(state)
    decisions = [Decision.model_validate(d) for d in state.get("decisions", [])]
    noaels = apply_decisions(ledger, decisions, frozenset(state.get("confirmed", [])))
    verdict = verify_final(state)
    return {
        "thread_id": thread_id,
        "author": state.get("author"),
        "waiting": waiting,
        "slots": [
            {"slot": s.slot, "finding": s.finding, "sex": s.sex, "doses": list(s.doses)}
            for s in enumerate_slots(ledger)
        ],
        "decisions": state.get("decisions", []),
        "confirmed": state.get("confirmed", []),
        "noael": {sex: {"dose": n.dose, "flags": n.flags} for sex, n in noaels.items()},
        "final": {
            "ok": verdict.ok,
            "text": verdict.text,
            "failures": [str(f) for f in verdict.failures],
        },
        "approved_by": state.get("approved_by"),
    }


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _log(request: Request, thread_id: str, actor: str, action: str, **payload: Any) -> None:
    await audit.append(request.app.state.saver.conn, thread_id, _now(), actor, action, payload)


async def _refuse(
    request: Request, thread_id: str, actor: str, step: str, status: int, detail: str
) -> NoReturn:
    """Chain the refusal, then answer with it."""
    await _log(request, thread_id, actor, "refused", step=step, status=status, reason=detail)
    raise HTTPException(status_code=status, detail=detail)


def _at(waiting: str, expected: str) -> None:
    if waiting != expected:
        raise HTTPException(status_code=409, detail=f"thread is at {waiting}, not {expected}")


@threads.post("", status_code=201)
async def start(request: Request) -> dict[str, Any]:
    thread_id = uuid.uuid4().hex
    graph = _graph(request)
    async with _lock(thread_id):
        await graph.ainvoke({"author": AUTHOR}, _config(thread_id))
        draft = json.loads(recording_path(RECORDINGS_DIR, "DRAFT").read_text(encoding="utf-8"))
        await _log(
            request,
            thread_id,
            AUTHOR,
            "thread_started",
            snapshot_sha256=current_snapshot(),
            draft_model=draft.get("model"),
            draft_recorded=draft.get("date"),
        )
    _, _, state, waiting = await _load(request, thread_id)
    return _view(thread_id, state, waiting)


@threads.get("/{thread_id}")
async def get_thread(request: Request, thread_id: str) -> dict[str, Any]:
    _, _, state, waiting = await _load(request, thread_id)
    return _view(thread_id, state, waiting)


@threads.post("/{thread_id}/decisions")
async def record_decisions(request: Request, thread_id: str, body: Record) -> dict[str, Any]:
    """Store the decisions in the checkpoint; the NOAEL and the verdict are recomputed, no model."""
    async with _lock(thread_id):
        return await _record(request, thread_id, body)


async def _record(request: Request, thread_id: str, body: Record) -> dict[str, Any]:
    graph, config, state, waiting = await _load(request, thread_id)
    _at(waiting, "await_decisions")
    slots = {s.slot: s for s in enumerate_slots(build_ledger(state))}
    now = _now()
    records = []
    for item in body.decisions:
        if item.dec_id not in slots:
            raise HTTPException(status_code=422, detail=f"unknown slot {item.dec_id}")
        slot = slots[item.dec_id]
        given = (item.treatment_related_from, item.adverse_from)
        if any(d is not None and d not in slot.doses for d in given):
            raise HTTPException(status_code=422, detail=f"dose not in {list(slot.doses)}")
        if 0 in given:
            raise HTTPException(status_code=422, detail="the control dose is not a finding dose")
        if item.adverse_from is not None and item.treatment_related_from is None:
            raise HTTPException(status_code=422, detail="adverse without treatment-related")
        if None not in given and item.treatment_related_from > item.adverse_from:  # type: ignore[operator]
            raise HTTPException(status_code=422, detail="treatment-related after adverse")
        records.append(
            Decision(
                dec_id=slot.slot,
                finding=slot.finding,
                sex=slot.sex,
                treatment_related_from=item.treatment_related_from,
                adverse_from=item.adverse_from,
                actor=body.actor,
                ts=now,
            ).model_dump()
        )
    await graph.aupdate_state(config, {"decisions": records, "confirmed": []})
    await _log(request, thread_id, body.actor, "decisions_recorded", decisions=records)
    _, _, state, waiting = await _load(request, thread_id)
    return _view(thread_id, state, waiting)


@threads.post("/{thread_id}/confirm")
async def confirm(request: Request, thread_id: str, body: Confirm) -> dict[str, Any]:
    """A reviewer confirms the NOAEL of each listed sex; resumes only if the text then verifies."""
    async with _lock(thread_id):
        return await _confirm(request, thread_id, body)


async def _confirm(request: Request, thread_id: str, body: Confirm) -> dict[str, Any]:
    graph, config, state, waiting = await _load(request, thread_id)
    _at(waiting, "await_decisions")
    if body.actor != REVIEWER or body.actor == state.get("author"):
        await _refuse(
            request, thread_id, body.actor, "confirm", 403, "Only the reviewer confirms a NOAEL."
        )
    state = {**state, "confirmed": list(body.confirmed)}
    if not verify_final(state).ok:
        await _refuse(request, thread_id, body.actor, "confirm", 409, "verify_final is not green")
    resume = {"decisions": state.get("decisions", []), "confirmed": state["confirmed"]}
    await graph.ainvoke(Command(resume=resume), config)
    _, _, state, waiting = await _load(request, thread_id)
    await _log(request, thread_id, body.actor, "noael_confirmed", confirmed=state["confirmed"])
    final = state["final"]
    await _log(
        request,
        thread_id,
        "system",
        "verify_final",
        ok=final["ok"],
        failures=len(final["failures"]),
    )
    return _view(thread_id, state, waiting)


@threads.post("/{thread_id}/approve")
async def approve(request: Request, thread_id: str, body: Approve) -> dict[str, Any]:
    async with _lock(thread_id):
        return await _approve(request, thread_id, body)


async def _approve(request: Request, thread_id: str, body: Approve) -> dict[str, Any]:
    graph, config, state, waiting = await _load(request, thread_id)
    _at(waiting, "await_approval")
    if body.actor == state.get("author"):
        await _refuse(
            request,
            thread_id,
            body.actor,
            "approve",
            403,
            "Authors cannot approve their own draft.",
        )
    if not state.get("final", {}).get("ok"):
        await _refuse(request, thread_id, body.actor, "approve", 409, "verify_final is not green")
    await graph.ainvoke(Command(resume={"approved_by": body.actor}), config)
    await _log(request, thread_id, body.actor, "approved")
    _, _, state, waiting = await _load(request, thread_id)
    return _view(thread_id, state, waiting)


@threads.get("/{thread_id}/audit/verify")
async def verify_audit(request: Request, thread_id: str) -> dict[str, Any]:
    """Read-only: check the thread's chain and say whether it is intact."""
    chain = await audit.entries(request.app.state.saver.conn, thread_id)
    if not chain:
        raise HTTPException(status_code=404, detail="thread not found")
    check = audit.verify_chain(chain)
    return {"ok": check.ok, "count": check.count, "first_broken": check.first_broken}


async def load_view(request: Request, thread_id: str) -> tuple[State, str, dict[str, Any]]:
    """State, the step it waits at, and the JSON view: for server-rendered pages."""
    _, _, state, waiting = await _load(request, thread_id)
    return state, waiting, _view(thread_id, state, waiting)
