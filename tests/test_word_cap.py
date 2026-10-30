import os
import re
import sqlite3
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from cairn import app as app_module
from cairn.app import create_app
from cairn.web.i18n import CATALOGUES, COOKIE

STEP_WORD_CAP = 93
REAL_RECORDINGS = Path(__file__).resolve().parent / "fixtures" / "recordings_real_shape"
STALE_NOTICE = "stale recording"
SENTENCE_WORD_CAP = 25


# Rendered-page counter (plan "Counting rule"): what a visitor reads inside <main>.
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "wbr"}
DROPPED_TAGS = {"script", "style", "template"}


class _MainCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.words = 0
        self.lede = ""
        self.stack: list[tuple[str, bool, bool]] = []  # tag, hides its text, is the lede
        self.in_main = False

    def _hidden(self) -> bool:
        return any(hide for _, hide, _ in self.stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in VOID_TAGS:
            return
        values = dict(attrs)
        if tag == "main":
            self.in_main = True
        hide = tag in DROPPED_TAGS
        if tag == "tbody" and self.in_main and not self._hidden():
            self.words += 1
            hide = True
        if self.stack and self.stack[-1][0] == "details-closed" and tag != "summary":
            hide = True
        name = tag
        if tag == "details":
            name = "details" if "open" in values else "details-closed"
        is_lede = "lede" in (values.get("class") or "").split()
        self.stack.append((name, hide, is_lede))

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        names = (tag, "details-closed") if tag == "details" else (tag,)
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] in names:
                del self.stack[index:]
                break
        if tag == "main":
            self.in_main = False

    def handle_data(self, data: str) -> None:
        if not self.in_main or self._hidden():
            return
        words = data.split()
        self.words += len(words)
        if any(lede for _, _, lede in self.stack):
            self.lede += " " + data


def rendered_words(html: str) -> int:
    """Words in the rendered <main>; a tbody is one word, a closed details its summary."""
    counter = _MainCounter()
    counter.feed(html)
    return counter.words


def rendered_lede(html: str) -> str:
    counter = _MainCounter()
    counter.feed(html)
    return " ".join(counter.lede.split())


def rendered_problems(html: str) -> list[str]:
    problems = []
    if rendered_words(html) > STEP_WORD_CAP:
        problems.append("step words")
    lede = rendered_lede(html)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", lede) if s]
    if len(sentences) != 1 or len(lede.split()) > SENTENCE_WORD_CAP:
        problems.append("lede")
    return problems


def with_result(page: str, fragment: str) -> str:
    """The GET page with the POST fragment inside #result, as HTMX places it."""
    empty = re.compile(r'(<div id="result"[^>]*>)</div>')
    placed, count = empty.subn(lambda m: f"{m.group(1)}{fragment}</div>", page)
    assert count == 1, "no empty #result element to place the fragment in"
    return placed


def open_toggle(html: str) -> str:
    """Mark the model-text disclosure open, as a visitor does."""
    labels = "|".join(re.escape(c["disc_model_text"]) for c in CATALOGUES.values())
    closed = re.compile(rf'<details class="pill">(?=<summary class="pill">(?:{labels}))')
    opened, count = closed.subn('<details class="pill" open>', html, count=1)
    assert count == 1, "no closed model-text toggle to open"
    return opened


BROKEN_STATES = {"step6_broken", "step7_broken", "step7_mismatch"}


def _literal(text: str) -> str:
    """The fixed text of a catalogue value: up to its first placeholder."""
    return text.split("{")[0]


def _chain(label: str):  # type: ignore[no-untyped-def]
    """The step 7 chain row: "{n} entries, verified" without the number."""
    return lambda t: _literal(t["s7_chain_value"].split("{n}")[1].replace("{state}", t[label]))


# Per state: catalogue entries the page must show, and entries it must not (a fall-through fails).
# An entry is a catalogue key, or a function of the catalogue for a computed marker.
STATE_MARKERS: dict[str, tuple[tuple, tuple]] = {  # type: ignore[type-arg]
    "landing": (("land_cta",), ()),
    "step1_before": (("s1_run",), ("s1_th_rule",)),
    "step1_after": (("s1_tile_q",), ("s1_tile_inj",)),
    "step1_injected": (("s1_tile_inj",), ()),
    "step1_duplicate": (("s1_tile_q",), ("s1_tile_inj",)),
    "step1_dose": (("s1_tile_q",), ("s1_tile_inj",)),
    "step2_before": (("s2_ask",), ("exp_rules",)),
    "step2_q2": (("exp_rules",), ("fmt_refusal_h",)),
    "step2_q2_open": (("exp_rules", "disc_model_text"), ()),
    "step2_q6": (("fmt_refusal_h",), ()),
    "step3": (("s3_lede",), ()),
    "step4_empty": (("s4_example",), ()),
    "step4_filled": (("s4_example",), ()),
    "step5": (("s5_lede",), ("s5_refused",)),
    "step5_refused": (("s5_refused",), ()),
    "step6": (("s6_chain_ok",), ("s6_chain_broken",)),
    "step6_broken": (("s6_chain_broken",), ("s6_chain_ok",)),
    "step7": (("s7_same", _chain("s7_verified")), ("s7_differ", _chain("s7_broken"))),
    "step7_broken": (("s7_same", _chain("s7_broken")), ("s7_differ", _chain("s7_verified"))),
    "step7_mismatch": (("s7_differ", _chain("s7_verified")), ("s7_same",)),
}


def _marker_text(entry, t: dict[str, str]) -> str:  # type: ignore[no-untyped-def]
    return entry(t) if callable(entry) else _literal(t[entry])


def assert_expected_page(name: str, html: str) -> None:
    """The state renders the page it names, so a state that falls through to another fails here."""
    lang = re.search(r'<html lang="(\w+)"', html)
    t = CATALOGUES[lang.group(1) if lang else "es"]
    present, absent = STATE_MARKERS[name]
    text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
    for entry in present:
        marker = _marker_text(entry, t)
        assert marker and marker in text, f"{name} does not render {marker!r}"
    for entry in absent:
        marker = _marker_text(entry, t)
        assert marker and marker not in text, f"{name} renders {marker!r}"


def rendered_state(name: str, lang: str | None = None) -> str:
    html = _rendered_state_unchecked(name, lang)
    assert_expected_page(name, html)
    return html


def _rendered_state_unchecked(name: str, lang: str | None = None) -> str:
    # Step 2 states always replay the real-shape fixtures, whatever the cwd or the environment say.
    saved = os.environ.get("CAIRN_RECORDINGS")
    os.environ["CAIRN_RECORDINGS"] = str(REAL_RECORDINGS)
    try:
        if name in BROKEN_STATES:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                db = Path(tmp) / "threads.db"
                os.environ["CAIRN_THREADS_DB"] = str(db)
                try:
                    return _rendered_state(name, lang, db)
                finally:
                    del os.environ["CAIRN_THREADS_DB"]
        return _rendered_state(name, lang)
    finally:
        if saved is None:
            del os.environ["CAIRN_RECORDINGS"]
        else:
            os.environ["CAIRN_RECORDINGS"] = saved


def _rendered_state(name: str, lang: str | None = None, db: Path | None = None) -> str:
    with TestClient(create_app()) as client:
        if lang:
            client.cookies.set(COOKIE, lang)
        if name == "landing":
            return client.get("/").text
        if name == "step3":
            return client.get("/step/3").text
        if name.startswith(("step4", "step5", "step6", "step7")):
            return _people_state(client, name, db)
        if name.startswith("step2_"):
            page = client.get("/step/2").text
            if name == "step2_before":
                return page
            question = "Q6" if name == "step2_q6" else "Q2"
            result = client.post("/step/2/run", data={"question": question}).text
            assert STALE_NOTICE not in result, f"{name} rendered a stale recording"
            if name == "step2_q2_open":
                result = open_toggle(result)
            return with_result(page, result)
        page = client.get("/step/1").text
        if name == "step1_before":
            return page
        switches = {
            "step1_injected": "negative",
            "step1_duplicate": "duplicate",
            "step1_dose": "dose",
        }
        data = {"switch": switches[name]} if name in switches else None
        return with_result(page, client.post("/step/1/run", data=data).text)


def _people_state(client: TestClient, name: str, db: Path | None = None) -> str:
    """Steps 4 and 5 as a visitor sees them: empty, with the example filled, and after the 403."""
    thread = client.post("/api/threads").json()["thread_id"]
    if name == "step4_empty":
        return client.get(f"/step/4?thread={thread}").text
    client.post("/step/4/example", data={"thread": thread})
    if name == "step4_filled":
        return client.get(f"/step/4?thread={thread}").text
    client.post("/step/4/confirm", data={"thread": thread, "actor": "R. Reviewer"})
    if name == "step5":
        return client.get(f"/step/5?thread={thread}").text
    if name == "step6":
        return client.get(f"/step/6?thread={thread}").text
    if name == "step6_broken":
        assert db is not None
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE audit SET actor = 'X' WHERE thread_id = ? AND seq = 3", (thread,))
        return client.get(f"/step/6?thread={thread}").text
    if name == "step7":
        client.post("/step/5/approve", data={"thread": thread, "actor": "R. Reviewer"})
        return client.get(f"/step/7?thread={thread}").text
    if name == "step7_broken":
        assert db is not None
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE audit SET actor = 'X' WHERE thread_id = ? AND seq = 3", (thread,))
        client.post("/step/5/approve", data={"thread": thread, "actor": "R. Reviewer"})
        return client.get(f"/step/7?thread={thread}").text
    if name == "step7_mismatch":
        client.post("/step/5/approve", data={"thread": thread, "actor": "R. Reviewer"})
        other = {"content_sha256": "x" * 64}
        with mock.patch.object(app_module, "call_tool", lambda tool, args: other):
            return client.get(f"/step/7?thread={thread}").text
    assert name == "step5_refused", f"unknown people state {name}"
    refused = client.post("/step/5/approve", data={"thread": thread, "actor": "A. Author"})
    assert "Authors cannot approve their own draft" in refused.text
    return refused.text


def _page(body: str, lede: str = "One short sentence.") -> str:
    lede_p = f'<p class="lede">{lede}</p>'
    return f"<header>chrome words</header><main>{lede_p}{body}</main><footer>more chrome</footer>"


def test_rendered_counter_ignores_header_and_footer() -> None:
    assert rendered_words(_page("<p>a b c</p>")) == 3 + 3


def test_rendered_counter_fails_an_over_cap_main_area() -> None:
    body = "<p>" + " ".join(["word"] * STEP_WORD_CAP) + "</p>"
    assert rendered_problems(_page(body)) == ["step words"]


def test_rendered_counter_counts_a_table_body_as_one_word() -> None:
    rows = "<tr><td>" + " ".join(["cell"] * 50) + "</td></tr>" * 3
    table = f"<table><thead><tr><th>Rule Animal</th></tr></thead><tbody>{rows}</tbody></table>"
    assert rendered_words(_page(table, lede="Lede.")) == 1 + 2 + 1


def test_rendered_counter_counts_a_closed_details_by_its_summary() -> None:
    inner = "<p>" + " ".join(["hidden"] * 40) + "</p>"
    closed = f"<details><summary>Show more</summary>{inner}</details>"
    opened = f"<details open><summary>Show more</summary>{inner}</details>"
    assert rendered_words(_page(closed, lede="Lede.")) == 1 + 2
    assert rendered_words(_page(opened, lede="Lede.")) == 1 + 2 + 40


def test_rendered_counter_counts_options_and_drops_scripts() -> None:
    body = "<select><option>Q1 first</option><option>Q2</option></select><script>x y z</script>"
    assert rendered_words(_page(body, lede="Lede.")) == 1 + 3


def test_rendered_lede_must_be_one_short_sentence() -> None:
    assert rendered_problems(_page("")) == []
    assert rendered_problems(_page("", lede="One. Two.")) == ["lede"]
    assert rendered_problems(_page("", lede=" ".join(["word"] * 26) + ".")) == ["lede"]
    assert rendered_problems(_page("", lede=" ".join(["word"] * 25) + ".")) == []


def test_result_fragment_lands_inside_the_result_element() -> None:
    page = _page('<div id="result"></div>')
    assert rendered_words(with_result(page, "<p>a b</p>")) == rendered_words(page) + 2


@pytest.mark.parametrize(
    "state",
    [
        "landing",
        "step1_before",
        "step1_after",
        "step1_injected",
        "step1_duplicate",
        "step1_dose",
        "step2_before",
        "step2_q2",
        "step2_q2_open",
        "step2_q6",
        "step3",
        "step4_empty",
        "step4_filled",
        "step5",
        "step5_refused",
        "step6",
        "step6_broken",
        "step7",
        "step7_broken",
        "step7_mismatch",
    ],
)
def test_word_cap_rendered(state: str) -> None:
    html = rendered_state(state)
    print(state, rendered_words(html), rendered_lede(html))
    assert rendered_problems(html) == [], state


@pytest.mark.parametrize("lang", ["es", "en"])
@pytest.mark.parametrize(
    "state",
    [
        "step1_before",
        "step1_after",
        "step1_injected",
        "step1_duplicate",
        "step1_dose",
        "step2_before",
        "step2_q2",
        "step2_q2_open",
        "step2_q6",
        "step3",
        "step4_empty",
        "step4_filled",
        "step5",
        "step5_refused",
        "step6",
        "step6_broken",
        "step7",
        "step7_broken",
        "step7_mismatch",
    ],
)
def test_steps_1_to_7_are_within_the_cap_in_both_locales(state: str, lang: str) -> None:
    html = rendered_state(state, lang)
    print(state, lang, rendered_words(html))
    assert f'<html lang="{lang}"' in html
    assert rendered_problems(html) == [], (state, lang)


def test_with_result_fails_when_there_is_no_result_element() -> None:
    with pytest.raises(AssertionError):
        with_result(_page("<p>no result here</p>"), "<p>a b</p>")


def test_open_toggle_fails_when_there_is_no_closed_toggle() -> None:
    with pytest.raises(AssertionError):
        open_toggle("<p>stale recording: run make record</p>")
    assert '<details class="pill" open>' in open_toggle(
        '<details class="pill"><summary class="pill">Show model text · 2 words</summary></details>'
    )


@pytest.mark.parametrize("state", ["step2_q2", "step2_q2_open", "step2_q6"])
def test_step2_states_replay_the_real_recordings_whatever_the_environment_says(
    state: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CAIRN_RECORDINGS", str(tmp_path))  # an empty folder: would be stale
    monkeypatch.chdir(tmp_path)  # and no relative "recordings" folder here either
    html = rendered_state(state, "en")
    assert STALE_NOTICE not in html
    assert os.environ["CAIRN_RECORDINGS"] == str(tmp_path)  # restored afterwards
    assert "Rules fired:" in html


@pytest.mark.parametrize("lang", ["es", "en"])
def test_landing_is_within_the_cap_in_both_locales(lang: str) -> None:
    with TestClient(create_app()) as client:
        html = client.get(f"/?lang={lang}").text
    print("landing", lang, rendered_words(html))
    assert rendered_problems(html) == [], lang
