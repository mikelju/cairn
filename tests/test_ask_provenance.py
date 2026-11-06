"""Change 004 C8 and C10 on /ask: every tag matches its source and the page carries one legend."""

import re
from html import unescape
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from cairn import web
from cairn.app import create_app
from cairn.questions import QUESTIONS
from cairn.web import i18n
from cairn.web.provenance import DataTag, DecisionTag, QuoteTag, TextPart
from screens import LANGS, STATE_MARKERS, main_copy, rendered_state

QUESTION_IDS = (*QUESTIONS, *web.ASK_QUERIES)
STATUS_WORDS = ("REAL", "RECORDED", "SIMULATED", "COMPUTED AT BUILD")
KINDS = {"data", "decision", "quote"}


class _Tags(HTMLParser):
    """Every provenance tag: its kind, chip text, body text and the cell marked as used."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[dict[str, str]] = []
        self.legend: list[str] = []
        self._depth = 0
        self._where = ""
        self._hit = False
        self._links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "details" and "prov" in classes:
            kind = next(c.removeprefix("prov-") for c in classes if c.startswith("prov-"))
            self.tags.append({"kind": kind, "chip": "", "body": "", "hit": "", "links": ""})
            self._depth = 1
            self._links = []
        elif self._depth:
            if tag == "details":
                self._depth += 1
            if tag == "summary" and self._depth == 1:
                self._where = "chip"
            if "prov-body" in classes:
                self._where = "body"
            if tag == "td" and "hit" in classes:
                self._hit = True
            if tag == "a" and values.get("href"):
                self._links.append(values["href"] or "")
                self.tags[-1]["links"] = " ".join(self._links)
        elif tag == "span" and "prov-key" in classes:
            self.legend.append(next(c.removeprefix("prov-") for c in classes if c != "prov-key"))

    def handle_endtag(self, tag: str) -> None:
        if not self._depth:
            return
        if tag == "summary" and self._depth == 1:
            self._where = ""
        if tag == "td":
            self._hit = False
        if tag == "details":
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._depth:
            return
        if self._where == "chip":
            self.tags[-1]["chip"] += data
        elif self._where == "body":
            self.tags[-1]["body"] += " " + data
            if self._hit:
                self.tags[-1]["hit"] += data


def _parse(html: str) -> _Tags:
    parser = _Tags()
    parser.feed(html)
    return parser


def _squash(text: str) -> str:
    return " ".join(unescape(text).split())


def _answer(question: str, lang: str = "en") -> str:
    with TestClient(create_app()) as client:
        return client.post(f"/ask/run?lang={lang}", data={"question": question}).text


def _expected(question: str) -> list[DataTag | QuoteTag | DecisionTag]:
    if question in web.ASK_QUERIES:
        context = web._query_context(question)
    else:
        context = web._step2_context(question, web._recordings_dir(), i18n.CATALOGUES["en"])
    return [p for p in context["parts"] if not isinstance(p, TextPart)]


@pytest.mark.parametrize("question", QUESTION_IDS)
def test_every_tag_shows_its_chip_and_its_source(question: str) -> None:
    html = _answer(question)
    shown = _parse(html).tags
    expected = _expected(question)
    assert [t["kind"] for t in shown] == [p.kind for p in expected]
    for tag, part in zip(shown, expected, strict=True):
        assert _squash(tag["chip"]) == _squash(part.text)
        body = _squash(tag["body"])
        if isinstance(part, DataTag):
            assert _squash(tag["hit"]) == part.text
            for fact in (part.tool, part.column, part.population):
                assert fact in body
        elif isinstance(part, QuoteTag):
            for fact in (part.guideline, part.section, str(part.page)):
                assert fact in body
            assert part.link in tag["links"]
            assert (part.highlight in tag["links"]) if part.highlight else True
        else:
            assert isinstance(part, DecisionTag)
            assert part.who in body and part.value in body and "/decide" in tag["links"]


@pytest.mark.parametrize("lang", ["en", "es"])
@pytest.mark.parametrize("question", QUESTION_IDS)
def test_the_legend_names_exactly_the_kinds_the_answer_uses(question: str, lang: str) -> None:
    parsed = _parse(_answer(question, lang))
    used = {t["kind"] for t in parsed.tags}
    assert used <= KINDS
    assert set(parsed.legend) == used and len(parsed.legend) == len(used)


def test_every_kind_is_shown_with_a_label_in_both_locales() -> None:
    for catalogue in i18n.CATALOGUES.values():
        assert all(catalogue[f"prov_legend_{kind}"] for kind in KINDS)


def _outside_panel(html: str) -> str:
    html = re.sub(r'<details class="inside">.*?</details>', "", html, flags=re.S)
    html = html.split('<div id="inside-trace" hx-swap-oob="true">')[0]
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


@pytest.mark.parametrize("lang", ["en", "es"])
def test_ask_shows_no_status_badge_outside_the_inside_panel(lang: str) -> None:
    with TestClient(create_app()) as client:
        page = client.get(f"/ask?lang={lang}").text
    main = page.split("<main", 1)[1].split("</main>", 1)[0]
    pieces = [(_outside_panel(main), "page")]
    pieces += [(_outside_panel(_answer(q, lang)), q) for q in QUESTION_IDS]
    for text, name in pieces:
        assert not [w for w in STATUS_WORDS if re.search(rf"\b{w}\b", text)], name
    assert 'class="badge' not in re.sub(
        r'<details class="inside">.*?</details>', "", main, flags=re.S
    )


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("state", list(STATE_MARKERS))
def test_no_status_badge_in_any_screen_outside_the_inside_panel(state: str, lang: str) -> None:
    """C10: the landing and the four screens, in every state, keep status labels in Inside only."""
    html = rendered_state(state, lang)
    # no Inside on /study (E58, D24)
    no_panel = state == "landing" or state.startswith("study_")
    assert ("<main" in html and "inside" in html) or no_panel
    text = main_copy(html)
    assert not [w for w in STATUS_WORDS if re.search(rf"\b{w}\b", text)], (state, lang)
    main = html.split("<main", 1)[1].split("</main>", 1)[0]
    outside = re.sub(r'<details class="inside">.*?</details>', "", main, flags=re.S)
    assert 'class="badge' not in outside, (state, lang)
