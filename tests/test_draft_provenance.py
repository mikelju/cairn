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
)
from test_ask_provenance import _parse, _squash


def _decided(client: TestClient, lang: str) -> None:
    client.cookies.set("cairn_lang", lang)
    client.get("/decide")
    # The reviewer's Decide button records and confirms each sex in one step.
    for sex, related, adverse in (("F", "20", "200"), ("M", "400", "400")):
        client.post(
            "/decide/choose",
            data={"actor": "reviewer", "sex": sex, "related": related, "adverse": adverse},
        )


def _draft(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, lang: str) -> tuple[str, list[Part]]:
    """The decided draft page and the prose parts (draft_parts) the sheet was written from."""
    page, prose, _every = _draft_all(monkeypatch, tmp_path, lang)
    return page, prose


def _draft_all(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, lang: str
) -> tuple[str, list[Part], list[Part]]:
    """The page, the prose parts and every tagged part the sheet used (tables repeat tags)."""
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    prose: list[Part] = []
    every: list[Part] = []
    real_prose, real_every = provenance.draft_parts, provenance.provenance_parts

    def spy_prose(*args: object) -> list[Part]:
        prose.extend(found := real_prose(*args))  # type: ignore[arg-type]
        return found

    def spy_every(*args: object) -> list[Part]:
        every.extend(found := real_every(*args))  # type: ignore[arg-type]
        return found

    with TestClient(create_app()) as client:
        _decided(client, lang)
        monkeypatch.setattr(provenance, "draft_parts", spy_prose)
        monkeypatch.setattr(provenance, "provenance_parts", spy_every)
        page = client.get("/draft?actor=reviewer").text
    return page, prose, every


# Digits the sheet may show outside every tag: numbered headings and the Ref. column
# (D1 to D11), both fixed text written in code. The References list is cut out first
# because it names the guidance documents by their published title.
FIXED_NUMBERING = re.compile(r"<h[23]>[\d.]+\s|<td>D\d+</td>")
DETAILS_EDGE = re.compile(r"<details\b|</details>")


def _strip_tags(html: str) -> str:
    """The text of the draft sheet with every provenance tag and the fixed numbering removed."""
    body = html.split('<article class="sheet"', 1)[1].split("</article>")[0]
    body = body.split("<h2>References</h2>")[0]
    while (tag := re.search(r'<details class="prov ', body)) is not None:
        depth, pos = 0, tag.start()
        for found in DETAILS_EDGE.finditer(body, pos):
            depth += 1 if found.group().startswith("<d") else -1
            if depth == 0:
                body = body[:pos] + " " + body[found.end() :]
                break
    return unescape(re.sub(r"<[^>]+>", " ", FIXED_NUMBERING.sub("<x>", body)))


@pytest.mark.parametrize("lang", ["en", "es"])
def test_every_tag_on_the_draft_matches_its_source(
    lang: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page, prose, every = _draft_all(monkeypatch, tmp_path, lang)
    shown = _parse(page).tags
    # The sheet repeats a tag in the meta table, the parameters, the decisions and the TK
    # table, so each shown tag is matched with the source tag that has the same kind and chip.
    sources: dict[tuple[str, str], list[Part]] = {}
    for part in every:
        if not isinstance(part, TextPart):
            sources.setdefault((part.kind, _squash(part.text)), []).append(part)

    def matches(tag: dict[str, str], part: Part) -> bool:
        body = _squash(tag["body"])
        if isinstance(part, DataTag):
            return _squash(tag["hit"]) == part.text and all(
                f in body for f in (part.tool, part.column, part.population)
            )
        if isinstance(part, QuoteTag):
            facts = (part.guideline, part.section, str(part.page))
            return all(f in body for f in facts) and part.link in tag["links"]
        assert isinstance(part, DecisionTag)
        return (
            bool(part.who) and part.who in body and part.value in body and "/decide" in tag["links"]
        )

    assert shown
    for tag in shown:
        candidates = sources[(tag["kind"], _squash(tag["chip"]))]
        assert any(matches(tag, c) for c in candidates), tag["chip"]
    # Every tag of the prose sentences is on the sheet.
    on_sheet = {(t["kind"], _squash(t["chip"])) for t in shown}
    wanted = {(p.kind, _squash(p.text)) for p in prose if not isinstance(p, TextPart)}
    assert wanted and wanted <= on_sheet


@pytest.mark.parametrize("lang", ["en", "es"])
def test_the_decided_sheet_uses_all_three_kinds_and_has_only_the_one_line_legend(
    lang: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The Step4 sheet has no per-kind legend: only "Draft in English." (and the yellow key).
    page, _parts = _draft(monkeypatch, tmp_path, lang)
    parsed = _parse(page)
    assert {t["kind"] for t in parsed.tags} == {"data", "quote", "decision"}
    assert parsed.legend == [] and "prov-legend" not in page
    note = re.search(r'<p class="meta sheet-note">(.*?)</p>', page, re.S)
    assert note is not None and _squash(re.sub(r"<[^>]+>", "", note.group(1))) == (
        "Draft in English." if lang == "en" else "Borrador en inglés."
    )
    assert 'class="hl"' not in page.split('<article class="sheet"', 1)[1]  # nothing pending


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
    # The References list is the only place the guidance titles (with numbers) are written.
    refs = page.split("<h2>References</h2>", 1)[1].split("</article>")[0]
    assert refs.count("<li>") >= 1


@pytest.mark.parametrize(("lang", "tail"), [("en", "by the AI"), ("es", "por la IA")])
def test_the_counts_line_equals_the_rendered_tags(
    lang: str, tail: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page, _parts, every = _draft_all(monkeypatch, tmp_path, lang)
    shown = _parse(page).tags
    # The sheet repeats tags in its tables; the line counts each figure, quotation and decision
    # once, ids such as PDS2014 are not numbers and the preloaded examples are not people.
    figures = {
        (_squash(t["chip"]), _squash(t["body"]))
        for t in shown
        if t["kind"] == "data" and re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?", t["chip"].strip())
    }
    assert len(figures) > 0 and len(figures) < sum(t["kind"] == "data" for t in shown)
    outside = _strip_tags(page)
    for word in FIXED_DIGIT_WORDS:
        outside = outside.replace(word, "")
    stray = len(re.findall(r"\d+(?:[.,]\d+)*", outside))
    line = _squash(re.search(r'<p class="meta prov-counts">(.*?)</p>', page, re.S).group(1))  # type: ignore[union-attr]
    numbers = [int(n) for n in re.findall(r"\d+", line)]
    slots = [p for p in every if isinstance(p, DecisionTag)]
    example = {p.slot for p in slots if p.who in ("Preloaded example", "Ejemplo precargado")}
    people = {p.slot for p in slots if p.who and p.slot not in example}
    assert example and people
    quotes = {_squash(t["body"]) for t in shown if t["kind"] == "quote"}
    assert numbers == [len(figures), stray, len(people), len(example), len(quotes)]
    assert tail in line


@pytest.mark.parametrize("lang", ["en", "es"])
def test_ask_shows_sex_and_species_as_english_words_not_chips(lang: str) -> None:
    with TestClient(create_app()) as client:
        page = client.post(f"/ask/run?lang={lang}", data={"question": "Q3"}).text
    chips = [t["chip"] for t in _parse(page).tags if t["kind"] == "data"]
    assert chips and all(re.search(r"\d", c) for c in chips), chips
    assert not {"F", "M", "RAT"} & {c.strip() for c in chips}
    plain = " ".join(unescape(re.sub(r"<[^>]+>", " ", page)).split())
    assert "In female rat from the main study" in plain  # recorded prose is English in both UIs
    assert not re.search(r"\b(?:hembra|macho|rata)\b", plain)


@pytest.mark.parametrize("lang", ["en", "es"])
def test_draft_shows_sex_and_species_as_english_words_not_chips(
    lang: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page, parts = _draft(monkeypatch, tmp_path, lang)
    chips = [t["chip"] for t in _parse(page).tags if t["kind"] == "data"]
    assert not {"F", "M", "RAT"} & {c.strip() for c in chips}
    text = "".join(p.text for p in parts if isinstance(p, TextPart))
    assert "Sprague-Dawley rats were" in text and "oral gavage" in text
    assert not re.search(r"\b(?:F|M|RAT)\b", text)


def test_a_refused_choice_is_an_html_page_with_a_plain_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    with TestClient(create_app()) as client:
        for lang, message in (("en", "choose both"), ("es", "elige la dosis")):
            client.cookies.set("cairn_lang", lang)
            reply = client.post(
                "/decide/choose", data={"actor": "reviewer", "sex": "F", "adverse": "200"}
            )
            assert reply.status_code == 422
            assert reply.headers["content-type"].startswith("text/html")
            assert message in reply.text and '{"detail"' not in reply.text
            assert 'class="callout' in reply.text or "callout" in reply.text


@pytest.mark.parametrize(
    ("lang", "label", "rules", "judge", "differ", "refusal"),
    [
        (
            "en",
            "Draft in English.",
            "Rules: 8/8 passed.",
            "Judge: 1/16 flagged; a person reviews.",
            "Rules check numbers and quotations; the judge reads meaning.",
            "The author cannot sign; another person signs.",
        ),
        (
            "es",
            "Borrador en inglés.",
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
