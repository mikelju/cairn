"""Render the landing and the four screens in every state a visitor can reach, in both languages."""

import os
import re
import sqlite3
import tempfile
from functools import cache
from html import unescape
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
    # The study screen renders its result on the server: the GET page already holds the means.
    "study_before": (
        ("s1_lede", "s1_card_h", "s1_gone_h", "s1_effect", "s1_break", "s1_lbl_all", "s1_lbl_ok"),
        ("s1_note", "s1_undo", "s1_reported", "s1_injected_tag"),
    ),
    "study_after": (
        ("s1_lede", "s1_card_h", "s1_gone_h", "s1_break", "s1_lbl_all", "s1_lbl_ok"),
        ("s1_note", "s1_undo", "s1_reported", "s1_injected_tag"),
    ),
    "study_injected": (
        ("s1_gone_h", "s1_note", "s1_undo", "s1_injected_tag", "s1_lbl_all", "s1_lbl_ok"),
        ("s1_break", "s1_reported"),
    ),
    "study_duplicate": (("s1_gone_h", "s1_reported", "s1_break"), ("s1_note", "s1_undo")),
    "study_dose": (("s1_gone_h", "s1_reported", "s1_break"), ("s1_note", "s1_undo")),
    "ask_before": (("s2_lede", "q_Q1", "ask_col_answer"), ("trick_Q6",)),
    "ask_q2": (("ask_col_answer", "ask_col_ai"), ("trick_Q6",)),
    "ask_q6": (("trick_Q6",), ()),
    "ask_g2": (("exp_official",), ("trick_Q6",)),
    # With an access code configured (as on AWS) the live question box is part of the page.
    "ask_live_before": (
        ("s2_lede", "q_Q1", "exp_live_q", "exp_live_code", "exp_live_go", "live_wait"),
        ("trick_Q6",),
    ),
    "ask_live_q2": (
        ("ask_col_answer", "exp_live_q", "exp_live_code", "exp_live_go", "live_wait"),
        ("trick_Q6",),
    ),
    # E60: one Decide button per sex, no Confirm button; the reviewer's Decide also confirms.
    "decide_empty": (("s4_decide", "disc_examples", "s4_role_label"), ("s4_confirm",)),
    "decide_filled": (("s4_decide", "disc_examples"), ("s4_confirm",)),
    "decide_confirmed": (("s4_decide", "disc_examples"), ("s4_confirm",)),
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
    text = " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())
    for key in present:
        marker = _literal(t[key])
        assert marker and marker in text, f"{name} does not render {marker!r}"
    for key in absent:
        marker = _literal(t[key])
        assert marker and marker not in text, f"{name} renders {marker!r}"


def with_result(page: str, fragment: str, target: str = "result") -> str:
    """The GET page with the POST fragment replacing the content of its target, as HTMX swaps it."""
    opener = re.search(rf'<div [^>]*id="{target}"[^>]*>', page)
    assert opener is not None, f"no #{target} element to place the fragment in"
    depth = 1
    for found in re.finditer(r"<div\b|</div>", page[opener.end() :]):
        depth += 1 if found.group() == "<div" else -1
        if depth == 0:
            end = opener.end() + found.start()
            return page[: opener.end()] + fragment + page[end:]
    raise AssertionError(f"#{target} is never closed")


def _break_chain(db: Path, thread: str) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE audit SET actor = 'X' WHERE thread_id = ? AND seq = 3", (thread,))


def _ask(client: TestClient, name: str) -> str:
    page = client.get("/ask").text
    if name == "ask_before":  # the GET page already holds the recorded answer to Q2
        return page
    question = {"ask_q6": "Q6", "ask_g2": "G2"}.get(name, "Q2")
    result = client.post("/ask/run", data={"question": question}).text
    assert STALE_NOTICE not in result, f"{name} rendered a stale recording"
    return with_result(page, result, "result")


def decide_both(client: TestClient) -> None:
    """The reviewer decides both sexes on the key finding.

    The Decide button records and confirms in one step for the reviewer; the author is refused.
    """
    client.post(
        "/decide/choose",
        data={"actor": "reviewer", "sex": "F", "related": "20", "adverse": "200"},
    )
    client.post(
        "/decide/choose",
        data={"actor": "reviewer", "sex": "M", "related": "400", "adverse": "400"},
    )


def _render(client: TestClient, db: Path, name: str) -> str:
    if name == "landing":
        return client.get("/").text
    if name.startswith("study_"):
        if name in SWITCHES:  # the POST answers with the whole screen, result included
            return client.post("/study/run", data={"switch": SWITCHES[name]}).text
        return client.get("/study").text
    if name.startswith("ask_live_"):
        with mock.patch.dict(os.environ, {"CAIRN_ACCESS_CODE": "test-code-not-real"}):
            return _ask(client, name.replace("live_", "", 1))
    if name.startswith("ask_"):
        return _ask(client, name)
    if name == "decide_empty":
        return client.get("/decide").text
    if name == "draft_empty":
        return client.get("/draft").text
    client.get("/decide")
    thread = client.cookies.get("cairn_thread")
    assert thread, "the decide screen starts no thread"
    decide_both(client)
    if name == "decide_filled":
        return client.get("/decide?actor=reviewer").text  # the Reviewer role of the selector
    if name in ("decide_confirmed", "draft_confirmed"):
        return client.get("/decide" if name == "decide_confirmed" else "/draft").text
    if name == "draft_rejected":
        refused = client.post("/draft/approve", data={"actor": "A. Author"})
        assert refused.status_code == 403
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


def _drop(html: str, opener: re.Pattern[str], tag: str) -> str:
    """Remove every element that starts like `opener`, matching nested tags of the same name."""
    while (start := opener.search(html)) is not None:
        depth, end = 0, len(html)
        for found in re.finditer(rf"<{tag}\b|</{tag}>", html[start.start() :]):
            depth += 1 if found.group().startswith("<" + tag) else -1
            if depth == 0:
                end = start.start() + found.end()
                break
        html = html[: start.start()] + " " + html[end:]
    return html


def main_copy(html: str, prose: bool = True) -> str:
    """The text of <main> outside the Inside panel; prose=False also drops tags and answer units."""
    main = html.split("<main", 1)[1].split("</main>", 1)[0]
    main = _drop(main, re.compile(r'<details class="inside"'), "details")
    if not prose:
        main = _drop(main, re.compile(r'<details class="prov '), "details")
        for tag in ("div", "blockquote", "p"):
            main = _drop(main, re.compile(rf'<{tag} class="[^"]*\banswer-unit\b'), tag)
        # The draft sheet is the English document itself (headings, DRAFT, References), not UI copy.
        main = _drop(main, re.compile(r'<article class="sheet"'), "article")
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", main)).split())
