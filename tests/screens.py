"""Render the landing and the four screens in every state a visitor can reach, in both languages."""

import os
import re
import sqlite3
import tempfile
from functools import cache
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from cairn import app as app_module
from cairn.app import create_app
from cairn.web.i18n import CATALOGUES, COOKIE

REAL_RECORDINGS = Path(__file__).resolve().parent / "fixtures" / "recordings_real_shape"
STALE_NOTICE = "stale recording"
LANGS = ("es", "en")
SWITCHES = {"study_injected": "negative", "study_duplicate": "duplicate", "study_dose": "dose"}


def _literal(text: str) -> str:
    """The fixed text of a catalogue value: up to its first placeholder."""
    return text.split("{")[0]


# Per state: catalogue entries the page must show, and entries it must not (a fall-through fails).
STATE_MARKERS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "landing": (("land_cta",), ()),
    "study_before": (("s1_run",), ("s1_th_rule",)),
    "study_after": (("s1_tile_q",), ("s1_tile_inj",)),
    "study_injected": (("s1_tile_inj",), ()),
    "study_duplicate": (("s1_tile_q",), ("s1_tile_inj",)),
    "study_dose": (("s1_tile_q",), ("s1_tile_inj",)),
    "ask_before": (("s2_ask",), ("exp_rules",)),
    "ask_q2": (("exp_rules",), ("fmt_refusal_h",)),
    "ask_q2_open": (("exp_rules", "disc_model_text"), ()),
    "ask_q6": (("fmt_refusal_h",), ()),
    "ask_explore_q2": (("exp_rules",), ("fmt_refusal_h",)),
    "ask_explore_q6": (("fmt_refusal_h",), ()),
    "decide_empty": (("s4_example",), ()),
    "decide_filled": (("s4_example",), ()),
    "decide_confirmed": (("s4_example",), ()),
    "draft_empty": (("undecided",), ("s5_approved",)),
    "draft_confirmed": (("s5_lede", "s6_chain_ok"), ("s5_refused", "s5_approved")),
    "draft_rejected": (("s5_refused",), ("s5_approved",)),
    "draft_approved": (("s5_approved", "s6_chain_ok", "s7_same"), ("s5_refused", "s7_differ")),
    "draft_broken": (("s6_chain_broken", "s7_same"), ("s6_chain_ok", "s7_differ")),
    "draft_mismatch": (("s7_differ",), ("s7_same",)),
}


def assert_expected_page(name: str, html: str) -> None:
    """The state renders the page it names, so a state that falls through to another fails here."""
    lang = re.search(r'<html lang="(\w+)"', html)
    t = CATALOGUES[lang.group(1) if lang else "es"]
    present, absent = STATE_MARKERS[name]
    text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
    for key in present:
        marker = _literal(t[key])
        assert marker and marker in text, f"{name} does not render {marker!r}"
    for key in absent:
        marker = _literal(t[key])
        assert marker and marker not in text, f"{name} renders {marker!r}"


OOB_TRACE = '<div id="inside-trace" hx-swap-oob="true">'


def with_result(page: str, fragment: str, target: str = "result") -> str:
    """The GET page with the POST fragment inside its target element, as HTMX places it.

    An out-of-band trace block goes where HTMX puts it: into the Inside panel's empty slot.
    """
    if OOB_TRACE in fragment:
        fragment, rest = fragment.split(OOB_TRACE)
        trace = rest[: rest.rindex("</div>")]
        slot = '<div id="inside-trace"></div>'
        assert page.count(slot) == 1, "no empty #inside-trace slot in the page"
        page = page.replace(slot, f'<div id="inside-trace">{trace}</div>')
    empty = re.compile(rf'(<div [^>]*id="{target}"[^>]*>)</div>')
    placed, count = empty.subn(lambda m: f"{m.group(1)}{fragment}</div>", page)
    assert count == 1, f"no empty #{target} element to place the fragment in"
    return placed


def open_toggle(html: str) -> str:
    """Mark the model-text disclosure open, as a visitor does."""
    labels = "|".join(re.escape(c["disc_model_text"]) for c in CATALOGUES.values())
    closed = re.compile(rf'<details class="pill">(?=<summary class="pill">(?:{labels}))')
    opened, count = closed.subn('<details class="pill" open>', html, count=1)
    assert count == 1, "no closed model-text toggle to open"
    return opened


def _break_chain(db: Path, thread: str) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE audit SET actor = 'X' WHERE thread_id = ? AND seq = 3", (thread,))


def _ask(client: TestClient, name: str) -> str:
    page = client.get("/ask").text
    if name == "ask_before":
        return page
    question = "Q6" if name.endswith("q6") else "Q2"
    if name.startswith("ask_explore_"):
        result = client.post("/explore/run", data={"question": question}).text
        target = "answer-explore"
    else:
        result = client.post("/ask/run", data={"question": question}).text
        target = "result"
    assert STALE_NOTICE not in result, f"{name} rendered a stale recording"
    if name == "ask_q2_open":
        result = open_toggle(result)
    return with_result(page, result, target)


def _render(client: TestClient, db: Path, name: str) -> str:
    if name == "landing":
        return client.get("/").text
    if name.startswith("study_"):
        page = client.get("/study").text
        if name == "study_before":
            return page
        data = {"switch": SWITCHES[name]} if name in SWITCHES else None
        return with_result(page, client.post("/study/run", data=data).text)
    if name.startswith("ask_"):
        return _ask(client, name)
    if name == "decide_empty":
        return client.get("/decide").text
    if name == "draft_empty":
        return client.get("/draft").text
    client.get("/decide")
    thread = client.cookies.get("cairn_thread")
    assert thread, "the decide screen starts no thread"
    client.post("/decide/example")
    if name == "decide_filled":
        return client.get("/decide").text
    client.post("/decide/confirm", data={"actor": "R. Reviewer"})
    if name in ("decide_confirmed", "draft_confirmed"):
        return client.get("/decide" if name == "decide_confirmed" else "/draft").text
    if name == "draft_rejected":
        refused = client.post("/draft/approve", data={"actor": "A. Author"})
        assert "Authors cannot approve their own draft" in refused.text
        return refused.text
    if name == "draft_broken":
        _break_chain(db, thread)
    client.post("/draft/approve", data={"actor": "R. Reviewer"})
    if name == "draft_mismatch":
        other = {"content_sha256": "x" * 64}
        with mock.patch.object(app_module, "call_tool", lambda tool, args: other):
            return client.get("/draft").text
    assert name in ("draft_approved", "draft_broken"), f"unknown state {name}"
    return client.get("/draft").text


@cache
def _all_states(lang: str) -> dict[str, str]:
    """Every state in one language: one app and database, cookies cleared per scenario."""
    saved = {k: os.environ.get(k) for k in ("CAIRN_RECORDINGS", "CAIRN_THREADS_DB")}
    os.environ["CAIRN_RECORDINGS"] = str(REAL_RECORDINGS)
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = Path(tmp) / "threads.db"
            os.environ["CAIRN_THREADS_DB"] = str(db)
            with TestClient(create_app()) as client:
                pages = {}
                for name in STATE_MARKERS:
                    client.cookies.clear()
                    client.cookies.set(COOKIE, lang)
                    pages[name] = _render(client, db, name)
                return pages
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def rendered_state(name: str, lang: str | None = None) -> str:
    html = _all_states(lang or "es")[name]
    assert_expected_page(name, html)
    return html
