"""Per-page contract over every real state: format line, one language."""

import html as htmllib
import re
from functools import cache

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web.i18n import CATALOGUES
from screens import REAL_RECORDINGS, STATE_MARKERS, rendered_state

LANGS = ("es", "en")
# Every screen state with its real data (the draft screen with a thread), one full page each.
SCREEN_STATES = list(STATE_MARKERS)
MIN_LENGTH = 12  # shorter catalogue values are generic words that data may legitimately repeat


def _main(page: str) -> str:
    """What a visitor reads in <main>: tags, scripts and templates dropped, entities decoded."""
    found = re.search(r"<main.*?</main>", page, re.S)
    body = found.group(0) if found else page
    body = re.sub(r"<(script|style|template)\b.*?</\1>", " ", body, flags=re.S)
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", body)).split())


@cache
def _extra_pages(lang: str) -> dict[str, str]:
    """Ask with answers, a live refusal and a highlight page, as the app renders them."""
    import os

    saved = {k: os.environ.get(k) for k in ("CAIRN_RECORDINGS", "CAIRN_ACCESS_CODE")}
    os.environ["CAIRN_RECORDINGS"] = str(REAL_RECORDINGS)
    os.environ["CAIRN_ACCESS_CODE"] = "s3cret"
    try:
        with TestClient(create_app()) as client:
            pages = {
                "ask": client.get(f"/ask?lang={lang}").text,
                "ask_q2": client.post(f"/ask/run?lang={lang}", data={"question": "Q2"}).text,
                "ask_q6": client.post(f"/ask/run?lang={lang}", data={"question": "Q6"}).text,
                "ask_g2": client.post(f"/ask/run?lang={lang}", data={"question": "G2"}).text,
                "live_refusal": client.post(
                    f"/explore/live?lang={lang}", data={"question": "Q?", "code": "wrong"}
                ).text,
            }
            link = re.search(r'href="(/highlight/[^"]+)"', pages["ask_g2"])
            assert link, "the G2 answer links no highlighted page"
            pages["highlight"] = client.get(f"{link.group(1)}?lang={lang}").text
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return pages


@cache
def _screen_page(name: str, lang: str) -> str:
    return rendered_state(name, lang)


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
    pages = {name: _screen_page(name, lang) for name in SCREEN_STATES}
    pages.update(_extra_pages(lang))
    foreign = _foreign_values(lang)
    assert len(foreign) > 100
    leaks = []
    for name, page in pages.items():
        # The draft sheet is the English document in both UIs (its footer is the English
        # footer_note), so it is cut out; everything around it must stay in one language.
        text = _main(re.sub(r'<article class="sheet".*?</article>', " ", page, flags=re.S))
        # D4/D13: the recorded prose and the draft always show the study terms in English
        # (as the study records them); only the English term names are allowed there, in
        # the draft states, and every other text of the page still has to be one language.
        allowed = name.startswith("draft") and lang == "es"
        leaks += [
            (name, key)
            for key, literal in foreign
            if literal in text and not (allowed and key.startswith("term_"))
        ]
    assert not leaks, leaks
