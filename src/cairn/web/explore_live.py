"""Live Explore: one free question behind the access code and the daily cap (phase 06, O1 and O2).

This is the only web module that reaches Bedrock (decision D8 reversed for this one route).
Without the code, with a wrong code, over the length limit or at the cap it makes no model call.
"""

import hmac
import math
import os
import threading
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from cairn import live
from cairn.gateway import DEFAULT_MODEL, REGION
from cairn.loop import LoopStatus
from cairn.pricing import call_cost
from cairn.tools import LIVE_SEARCH
from cairn.web import i18n, result_context, templates

explore_live = APIRouter()
MAX_QUESTION_CHARS = 500
DEFAULT_CAP_USD = 2.0
_spend: dict[date, float] = {}
_busy = threading.Lock()


def utc_today() -> date:
    return datetime.now(UTC).date()


def daily_cap() -> float:
    try:
        cap = float(os.environ.get("CAIRN_LIVE_CAP_USD", DEFAULT_CAP_USD))
    except ValueError:
        return DEFAULT_CAP_USD
    return cap if math.isfinite(cap) and cap >= 0 else DEFAULT_CAP_USD


def code_ok(code: str) -> bool:
    """Constant-time comparison with CAIRN_ACCESS_CODE; no code configured means no live."""
    expected = os.environ.get("CAIRN_ACCESS_CODE", "")
    return bool(expected) and hmac.compare_digest(code.encode(), expected.encode())


def spent_today() -> float:
    return _spend.get(utc_today(), 0.0)


def _add_spend(amount: float) -> None:
    today = utc_today()
    for day in [d for d in _spend if d != today]:  # keep only the current UTC day
        del _spend[day]
    _spend[today] = _spend.get(today, 0.0) + amount


def _refused(request: Request, key: str, **values: object) -> HTMLResponse:
    """A refusal in the visitor's language: `key` names a catalogue message."""
    shell = i18n.context(request)
    message = shell["t"][key].format(**values)
    return templates.TemplateResponse(
        request, "explore_refused.html", {**shell, "refused": message}
    )


@explore_live.post("/explore/live", response_class=HTMLResponse)
def explore_ask_live(
    request: Request,
    question: Annotated[str, Form()],
    code: Annotated[str, Form()] = "",
) -> HTMLResponse:
    question = question.strip()
    if not code_ok(code):
        return _refused(request, "live_need_code")
    if not question or len(question) > MAX_QUESTION_CHARS:
        return _refused(request, "live_length", n=MAX_QUESTION_CHARS)
    if spent_today() >= daily_cap():
        return _refused(request, "live_budget")
    if not _busy.acquire(blocking=False):
        return _refused(request, "live_busy")
    try:
        if spent_today() >= daily_cap():  # a question that just finished may have used it up
            return _refused(request, "live_budget")
        gateway: live.SpendGateway | None = None
        token = LIVE_SEARCH.set(True)
        try:
            gateway = live.spend_gateway()
            result = live.ask_live(question, DEFAULT_MODEL, gateway)
        except Exception as error:  # a timeout or a Bedrock error: count what the calls cost
            _add_spend(gateway.spent if gateway else 0.0)
            return _refused(request, "live_failed", error=type(error).__name__)
        finally:
            LIVE_SEARCH.reset(token)
        cost = call_cost(DEFAULT_MODEL, result.input_tokens, result.output_tokens)
        _add_spend(cost)
    finally:
        _busy.release()
    meta = (
        f"{utc_today().isoformat()} | {REGION} | {DEFAULT_MODEL} | "
        f"{result.latency_s:.1f} s | {cost:.2f} USD"
    )
    context = result_context(result, "REAL", meta)
    if result.status is not LoopStatus.ANSWERED:  # shown as is, never as an answer
        context["text"] = None
    return templates.TemplateResponse(
        request, "explore_answer.html", {**i18n.context(request), "r": context}
    )
