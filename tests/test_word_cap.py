import os
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from screens import STALE_NOTICE, STATE_MARKERS, open_toggle, rendered_state, with_result

WORD_CAP = 60  # change 004 C14: every state of every page
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
        unit = "answer-unit" in (values.get("class") or "").split()
        in_closed = bool(self.stack) and self.stack[-1][0] == "details-closed" and tag != "summary"
        if (tag == "tbody" or unit) and self.in_main and not self._hidden() and not in_closed:
            self.words += 1
            hide = True
        if in_closed:
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


def rendered_problems(html: str, cap: int = WORD_CAP) -> list[str]:
    problems = []
    if rendered_words(html) > cap:
        problems.append("step words")
    lede = rendered_lede(html)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", lede) if s]
    if len(sentences) != 1 or len(lede.split()) > SENTENCE_WORD_CAP:
        problems.append("lede")
    return problems


def _page(body: str, lede: str = "One short sentence.") -> str:
    lede_p = f'<p class="lede">{lede}</p>'
    return f"<header>chrome words</header><main>{lede_p}{body}</main><footer>more chrome</footer>"


def test_rendered_counter_ignores_header_and_footer() -> None:
    assert rendered_words(_page("<p>a b c</p>")) == 3 + 3


def test_rendered_counter_fails_an_over_cap_main_area() -> None:
    body = "<p>" + " ".join(["word"] * WORD_CAP) + "</p>"
    assert rendered_problems(_page(body)) == ["step words"]


def test_rendered_counter_counts_a_table_body_as_one_word() -> None:
    rows = "<tr><td>" + " ".join(["cell"] * 50) + "</td></tr>" * 3
    table = f"<table><thead><tr><th>Rule Animal</th></tr></thead><tbody>{rows}</tbody></table>"
    assert rendered_words(_page(table, lede="Lede.")) == 1 + 2 + 1


def test_rendered_counter_counts_an_answer_unit_as_one_word() -> None:
    text = " ".join(["ans"] * 50)
    unit = f'<article class="answer-panel"><p class="answer-unit">{text}</p><p>one two three</p></article>'
    assert rendered_words(_page(unit, lede="Lede.")) == 1 + 1 + 3  # the sibling is counted


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


@pytest.mark.parametrize("state", list(STATE_MARKERS))
def test_word_cap_rendered(state: str) -> None:
    html = rendered_state(state)
    print(state, rendered_words(html), rendered_lede(html))
    assert rendered_problems(html, WORD_CAP) == [], state


@pytest.mark.parametrize("lang", ["es", "en"])
@pytest.mark.parametrize("state", list(STATE_MARKERS))
def test_screens_are_within_the_cap_in_both_locales(state: str, lang: str) -> None:
    html = rendered_state(state, lang)
    print(state, lang, rendered_words(html))
    assert f'<html lang="{lang}"' in html
    assert rendered_problems(html, WORD_CAP) == [], (state, lang)


def test_with_result_fails_when_there_is_no_result_element() -> None:
    with pytest.raises(AssertionError):
        with_result(_page("<p>no result here</p>"), "<p>a b</p>")


def test_open_toggle_fails_when_there_is_no_closed_toggle() -> None:
    with pytest.raises(AssertionError):
        open_toggle("<p>stale recording: run make record</p>")
    assert '<details class="pill" open>' in open_toggle(
        '<details class="pill"><summary class="pill">Show model text · 2 words</summary></details>'
    )


@pytest.mark.parametrize("state", ["ask_q2", "ask_q2_open", "ask_q6"])
def test_ask_states_replay_the_real_recordings_whatever_the_environment_says(
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
    assert rendered_problems(html, WORD_CAP) == [], lang
