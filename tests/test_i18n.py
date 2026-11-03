"""UI string catalogue: same keys in both locales, and the toggle switches the shell strings."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web.i18n import COOKIE, EN, ES


def test_catalogues_have_the_same_keys() -> None:
    assert EN.keys() == ES.keys()
    assert all(EN[key] and ES[key] for key in EN)


def test_default_locale_is_spanish_and_the_shell_reads_the_catalogue() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/").text
    assert '<html lang="es">' in page
    for key in ("role", "footer_note", "step_1", "step_4", "nav_steps"):
        assert ES[key] in page
    assert EN["role"] not in page and EN["footer_note"] not in page


def test_toggle_switches_the_shell_strings_and_persists_by_cookie() -> None:
    with TestClient(create_app()) as client:
        english = client.get("/?lang=en")
        assert english.cookies.get(COOKIE) == "en"
        for key in ("role", "footer_note", "step_1", "step_4", "nav_steps"):
            assert EN[key] in english.text
        assert ES["role"] not in english.text and ES["footer_note"] not in english.text
        follow_up = client.get("/study").text  # no query parameter: the cookie decides
        assert '<html lang="en">' in follow_up and EN["role"] in follow_up
        client.get("/study?lang=es")
        assert '<html lang="es">' in client.get("/ask").text


def test_toggle_links_keep_the_page_and_the_query() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/ask?x=abc&y=R.+Reviewer&lang=es").text
    links = re.findall(r'<a href="([^"]+)" hreflang="(\w+)"', page)
    assert {code for _, code in links} == {"es", "en"}
    for href, code in links:
        assert href.startswith("/ask?") and "x=abc" in href and f"lang={code}" in href
    assert re.search(r'hreflang="es" lang="es" aria-current="true"', page)


def test_unknown_locale_falls_back_to_the_default() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/?lang=fr")
    assert '<html lang="es">' in response.text and COOKIE not in response.cookies


def test_the_redirect_from_a_retired_step_keeps_the_chosen_locale() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/step/4?lang=en").text
    assert '<html lang="en">' in page and "Acting as:" in page


FIXTURES = Path(__file__).parent / "fixtures" / "recordings"
REAL = Path(__file__).parent / "fixtures" / "recordings_real_shape"


def _run(path: str, question: str, folder: Path, mp: pytest.MonkeyPatch, lang: str) -> str:
    mp.setenv("CAIRN_RECORDINGS", str(folder))
    with TestClient(create_app()) as client:
        client.cookies.set(COOKIE, lang)
        return client.post(path, data={"question": question}).text


def test_toggle_on_a_post_page_keeps_the_thread() -> None:
    with TestClient(create_app()) as client:
        client.cookies.set(COOKIE, "en")
        client.get("/decide")
        thread = client.cookies.get("cairn_thread")
        assert thread
        client.post("/decide/example")
        client.post("/decide/confirm", data={"actor": "R. Reviewer"})
        refused = client.post("/draft/approve", data={"actor": "A. Author"}).text
        links = re.findall(r'href="(/draft\?[^"]*lang=[^"]*)"', refused)
        assert links
        assert all(client.get(link).status_code == 200 for link in links)
        assert client.cookies.get("cairn_thread") == thread  # the thread travels in the cookie


def test_landing_secondary_link_needs_no_thread() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/?lang=en").text
    assert 'class="btn-secondary" href="/ask"' in page


def test_highlight_page_reads_the_catalogue() -> None:
    from cairn.highlight import load_highlights

    entry = load_highlights()[0]
    with TestClient(create_app()) as client:
        client.cookies.set(COOKIE, "es")
        page = client.get(f"/highlight/{entry['sentence_id']}").text
    assert ES["hl_official"] in page and ES["hl_back"] in page
    assert "official page" not in page and "back to Ask it" not in page


def test_generated_ui_words_follow_the_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    declined = _run("/ask/run", "Q6", REAL, monkeypatch, "es")
    assert ES["trick_Q6"] in declined and EN["trick_Q6"] not in declined
    answered = _run("/ask/run", "Q2", FIXTURES, monkeypatch, "es")
    assert ES["ev_from"] in answered and ", from " not in answered
    assert "cost n/a" not in answered and "Reglas aplicadas: none" not in answered


def test_empty_pills_are_not_rendered(monkeypatch: pytest.MonkeyPatch) -> None:
    for path in ("/ask/run",):
        page = _run(path, "Q6", REAL, monkeypatch, "es")
        assert "· 0 " not in page


def test_explore_survives_an_unreadable_recording(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for path in FIXTURES.glob("*.json"):
        (tmp_path / path.name).write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("CAIRN_RECORDINGS", str(tmp_path))
    with TestClient(create_app()) as client:
        assert client.get("/ask").status_code == 200
