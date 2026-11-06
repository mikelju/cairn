"""Key copy of the approved canvas, in both locales (change 004 C14 as amended by D23).

There is no word cap per screen or per sentence; each screen checks that its canvas text is present.
"""

import os
import re
from html import unescape
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web.i18n import CATALOGUES
from screens import STALE_NOTICE, assert_expected_page, rendered_state, with_result


def _text(html: str) -> str:
    main = html.split("<main", 1)[1].split("</main>", 1)[0]
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", main)).split())


@pytest.mark.parametrize("lang", ["es", "en"])
def test_landing_shows_the_key_copy_of_the_canvas(lang: str) -> None:
    cat = CATALOGUES[lang]
    html = rendered_state("landing", lang)
    text = _text(html)
    for key in ("land_title", "land_goal", "land_steps", "land_example", "land_example_note"):
        assert cat[key] in text, (lang, key)
    assert cat["land_cta"] in text
    assert cat["land_counts"].split("{ai}")[1] in text  # ends with the click hint
    assert cat["role"] in html and cat["footer_note"] in html


def test_landing_copy_matches_the_canvas_in_spanish() -> None:
    text = _text(rendered_state("landing", "es"))
    assert "Una IA redacta el informe no clínico de un estudio público" in text
    assert "Ejemplo fragmento del borrador, en inglés" in text
    assert "Ver cómo se hace" in text


def test_live_states_prove_the_live_box_is_present() -> None:
    plain = rendered_state("ask_before", "en")
    with pytest.raises(AssertionError, match="Your question"):
        assert_expected_page("ask_live_before", plain)
    live = rendered_state("ask_live_before", "en")
    assert 'action="/explore/live"' in live or 'hx-post="/explore/live"' in live
    assert 'hx-post="/explore/live"' not in plain and 'action="/explore/live"' not in plain


def test_with_result_fails_when_there_is_no_result_element() -> None:
    with pytest.raises(AssertionError):
        with_result("<main><p>no result here</p></main>", "<p>a b</p>")


@pytest.mark.parametrize("state", ["ask_q2", "ask_q6"])
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
def test_header_has_the_fixed_role_and_the_language_switch_and_no_acting_as(lang: str) -> None:
    cat = CATALOGUES[lang]
    with TestClient(create_app()) as client:
        for path in ("/", "/decide", "/draft"):
            page = client.get(f"{path}?lang={lang}").text
            header = page.split("<header", 1)[1].split("</header>", 1)[0]
            assert f'<span class="role">{cat["role"]}</span>' in header, (path, lang)
            assert 'hreflang="es"' in header and 'hreflang="en"' in header
            assert "Acting as" not in page and "Actuando como" not in page
