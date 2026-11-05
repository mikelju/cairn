"""Change 004 C8, C9 and C10 on /draft, and the friendly refusal on /decide."""

import re
from html import unescape
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web import provenance
from cairn.web.provenance import (
    FIXED_DIGIT_WORDS,
    DataTag,
    DecisionTag,
    Part,
    QuoteTag,
    TextPart,
    stray_digits,
    tag_counts,
)
from test_ask_provenance import _parse, _squash


def _decided(client: TestClient, lang: str) -> None:
    client.cookies.set("cairn_lang", lang)
    client.get("/decide")
    client.post("/decide/choose", data={"sex": "F", "related": "20", "adverse": "200"})
    client.post("/decide/choose", data={"sex": "M", "related": "400", "adverse": "400"})
    client.post("/decide/confirm", data={"actor": "R. Reviewer"})


def _draft(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, lang: str) -> tuple[str, list[Part]]:
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    shown: list[list[Part]] = []
    real = provenance.draft_parts

    def spy(*args: object) -> list[Part]:
        shown.append(real(*args))  # type: ignore[arg-type]
        return shown[-1]

    monkeypatch.setattr(provenance, "draft_parts", spy)
    with TestClient(create_app()) as client:
        _decided(client, lang)
        page = client.get("/draft?actor=R.%20Reviewer").text
    return page, shown[-1]


def _strip_tags(html: str) -> str:
    """The text of the draft body with every provenance tag removed."""
    body = html.split('<div class="card answer"><p class="answer-unit">', 1)[1].split(
        '<p class="prov-legend">'
    )[0]
    while (tag := re.search(r'<details class="prov ', body)) is not None:
        depth, pos = 0, tag.start()
        for found in re.finditer(r"<details\b|</details>", body[pos:]):
            depth += 1 if found.group().startswith("<d") else -1
            if depth == 0:
                body = body[:pos] + " " + body[pos + found.end() :]
                break
    return unescape(re.sub(r"<[^>]+>", " ", body))


@pytest.mark.parametrize("lang", ["en", "es"])
def test_every_tag_on_the_draft_matches_its_source(
    lang: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page, parts = _draft(monkeypatch, tmp_path, lang)
    shown = _parse(page).tags
    expected = [p for p in parts if not isinstance(p, TextPart)]
    assert expected and [t["kind"] for t in shown] == [p.kind for p in expected]
    for tag, part in zip(shown, expected, strict=True):
        assert _squash(tag["chip"]) == _squash(part.text)
        body = _squash(tag["body"])
        if isinstance(part, DataTag):
            assert _squash(tag["hit"]) == part.text
            assert all(f in body for f in (part.tool, part.column, part.population))
        elif isinstance(part, QuoteTag):
            assert all(f in body for f in (part.guideline, part.section, str(part.page)))
            assert part.link in tag["links"]
        else:
            assert isinstance(part, DecisionTag)
            assert part.who and part.who in body and part.value in body
            assert "/decide" in tag["links"]


@pytest.mark.parametrize("lang", ["en", "es"])
def test_the_draft_legend_names_exactly_the_kinds_used(
    lang: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page, _parts = _draft(monkeypatch, tmp_path, lang)
    parsed = _parse(page)
    used = {t["kind"] for t in parsed.tags}
    assert used == {"data", "quote", "decision"}
    assert set(parsed.legend) == used and len(parsed.legend) == len(used)


@pytest.mark.parametrize("lang", ["en", "es"])
def test_without_tags_the_draft_has_no_digit_but_the_fixed_words(
    lang: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page, parts = _draft(monkeypatch, tmp_path, lang)
    plain = _strip_tags(page)
    for word in FIXED_DIGIT_WORDS:
        plain = plain.replace(word, "")
    assert not re.search(r"\d", plain), plain
    assert stray_digits(parts) == ""


@pytest.mark.parametrize(("lang", "tail"), [("en", "by the AI"), ("es", "por la IA")])
def test_the_counts_line_equals_the_rendered_tags(
    lang: str, tail: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page, parts = _draft(monkeypatch, tmp_path, lang)
    counts = tag_counts(parts)
    shown = _parse(page).tags
    for kind in counts:
        assert counts[kind] == sum(t["kind"] == kind for t in shown)
    with_digits = sum(t["kind"] == "data" and bool(re.search(r"\d", t["chip"])) for t in shown)
    assert 0 < with_digits < counts["data"]  # names and units are data tags without a number
    outside = _strip_tags(page)
    for word in FIXED_DIGIT_WORDS:
        outside = outside.replace(word, "")
    stray = len(re.findall(r"\d+(?:[.,]\d+)*", outside))
    line = _squash(re.search(r'<p class="meta prov-counts">(.*?)</p>', page, re.S).group(1))  # type: ignore[union-attr]
    numbers = [int(n) for n in re.findall(r"\d+", line)]
    example = sum(
        getattr(p, "who", "") in ("Preloaded example", "Ejemplo precargado") for p in parts
    )
    assert example > 0
    assert numbers == [with_digits, stray, counts["decision"] - example, example, counts["quote"]]
    assert tail in line


def test_a_refused_choice_is_an_html_page_with_a_plain_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    with TestClient(create_app()) as client:
        for lang, message in (("en", "choose both"), ("es", "elige la dosis")):
            client.cookies.set("cairn_lang", lang)
            reply = client.post("/decide/choose", data={"sex": "F", "adverse": "200"})
            assert reply.status_code == 422
            assert reply.headers["content-type"].startswith("text/html")
            assert message in reply.text and '{"detail"' not in reply.text
            assert 'class="callout' in reply.text or "callout" in reply.text


@pytest.mark.parametrize(
    ("lang", "label", "rules", "judge", "differ", "refusal"),
    [
        (
            "en",
            "Show draft in English",
            "Rules: 8/8 passed.",
            "Judge: 1/16 flagged; a person reviews.",
            "Rules check numbers and quotations; the judge reads meaning.",
            "The author cannot sign; another person signs.",
        ),
        (
            "es",
            "Ver borrador en inglés",
            "Reglas: 8/8 superadas.",
            "Juez: 1/16 marcadas; revisión humana.",
            "Reglas miran números y citas; el juez, el sentido.",
            "Quien redacta no puede firmar; firma otra persona.",
        ),
    ],
)
def test_draft_explains_its_checks_and_refuses_the_author_plainly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lang: str,
    label: str,
    rules: str,
    judge: str,
    differ: str,
    refusal: str,
) -> None:
    """C16 and C12 with the real judge recordings: the recovery flag is explained, not hidden."""
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    with TestClient(create_app()) as client:
        _decided(client, lang)
        page = client.get("/draft").text
        main = page[page.index("<main") : page.index("</main>")]
        before_panel = main[: main.index('class="inside"')] if 'class="inside"' in main else main
        for line in (label, rules, judge, differ):
            assert line in unescape(before_panel), line
        refused = client.post("/draft/approve", data={"actor": "A. Author"})
        assert refused.status_code == 403
        assert refusal in refused.text
        assert "(403)" not in refused.text and "Rechazado" not in refused.text
        signed = client.post("/draft/approve", data={"actor": "R. Reviewer"})
        assert signed.status_code == 200 and refusal not in signed.text
