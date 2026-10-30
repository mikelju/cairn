"""Per-page contract over every real state: reading path, format line, one language."""

import html as htmllib
import re
from functools import cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web.i18n import CATALOGUES
from test_word_cap import STATE_MARKERS, rendered_state

REAL_RECORDINGS = Path(__file__).resolve().parent / "fixtures" / "recordings_real_shape"
LANGS = ("es", "en")
# Every step state with its real data (steps 6 and 7 with a thread), one full page each.
STEP_STATES = [name for name in STATE_MARKERS if name != "landing"]
MIN_LENGTH = 12  # shorter catalogue values are generic words that data may legitimately repeat


def _main(page: str) -> str:
    """What a visitor reads in <main>: tags, scripts and templates dropped, entities decoded."""
    found = re.search(r"<main.*?</main>", page, re.S)
    body = found.group(0) if found else page
    body = re.sub(r"<(script|style|template)\b.*?</\1>", " ", body, flags=re.S)
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", body)).split())


@cache
def _extra_pages(lang: str) -> dict[str, str]:
    """Explore with answers, a live refusal and a highlight page, as the app renders them."""
    import os

    saved = {k: os.environ.get(k) for k in ("CAIRN_RECORDINGS", "CAIRN_ACCESS_CODE")}
    os.environ["CAIRN_RECORDINGS"] = str(REAL_RECORDINGS)
    os.environ["CAIRN_ACCESS_CODE"] = "s3cret"
    try:
        with TestClient(create_app()) as client:
            pages = {
                "explore": client.get(f"/explore?lang={lang}").text,
                "explore_q2": client.post(
                    f"/explore/run?lang={lang}", data={"question": "Q2"}
                ).text,
                "explore_q6": client.post(
                    f"/explore/run?lang={lang}", data={"question": "Q6"}
                ).text,
                "explore_g2": client.post(
                    f"/explore/run?lang={lang}", data={"question": "G2"}
                ).text,
                "live_refusal": client.post(
                    f"/explore/live?lang={lang}", data={"question": "Q?", "code": "wrong"}
                ).text,
            }
            step3 = client.get(f"/step/3?lang={lang}").text
            link = re.search(r'href="(/highlight/[^"]+)"', step3)
            assert link, "step 3 links no highlighted page"
            pages["highlight"] = client.get(f"{link.group(1)}?lang={lang}").text
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return pages


@cache
def _step_page(name: str, lang: str) -> str:
    return rendered_state(name, lang)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("name", ["landing", *STEP_STATES])
def test_every_step_page_shows_its_reading_path(name: str, lang: str) -> None:
    page = _step_page(name, lang)
    assert re.search(r'<ol class="path" aria-label="[^"]+">(?:<li>.*?</li>){2,}</ol>', page), name


@pytest.mark.parametrize("lang", LANGS)
def test_explore_shows_its_reading_path(lang: str) -> None:
    page = _extra_pages(lang)["explore"]
    assert re.search(r'<ol class="path" aria-label="[^"]+">(?:<li>.*?</li>){2,}</ol>', page)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("question", ["Q2", "Q6"])
def test_step2_answer_has_exactly_one_non_empty_format_line(
    question: str, lang: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAIRN_RECORDINGS", str(REAL_RECORDINGS))
    with TestClient(create_app()) as client:
        body = client.post(f"/step/2/run?lang={lang}", data={"question": question}).text
    lines = re.findall(r'<p class="format-line[^"]*">(.*?)</p>', body, re.S)
    assert body.count('class="format-line') == 1 and len(lines) == 1, (question, lang)
    assert re.sub(r"<[^>]+>", "", lines[0]).strip(), (question, lang)
    assert re.search(r"<b>[^<]+</b>", lines[0]), (question, lang)


def _foreign_values(lang: str) -> list[tuple[str, str]]:
    """Other-locale catalogue texts that identify that locale.

    The literal text up to the first placeholder, only when it is long enough to be
    specific and does not also occur as any value of this locale's catalogue.
    All-capital values are status badges (REAL, RECORDED, COMPUTED AT BUILD), which are
    English labels on every page by design, so they are skipped.
    """
    own = {v for v in CATALOGUES[lang].values()}
    other = CATALOGUES["en" if lang == "es" else "es"]
    values = []
    for key, value in other.items():
        literal = " ".join(value.split("{")[0].split())
        if len(literal) >= MIN_LENGTH and literal not in own and not literal.isupper():
            values.append((key, literal))
    return values


@pytest.mark.parametrize("lang", LANGS)
def test_no_page_shows_text_from_the_other_locale(lang: str) -> None:
    pages = {name: _step_page(name, lang) for name in ["landing", *STEP_STATES]}
    pages.update(_extra_pages(lang))
    foreign = _foreign_values(lang)
    assert len(foreign) > 100
    leaks = []
    for name, page in pages.items():
        text = _main(page)
        leaks += [(name, key) for key, literal in foreign if literal in text]
    assert not leaks, leaks
