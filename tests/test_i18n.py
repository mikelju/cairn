"""UI string catalogue: same keys in both locales, and the toggle switches the shell strings."""

import re

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
    for key in ("role", "footer_note", "step_1", "step_7", "nav_steps"):
        assert ES[key] in page
    assert EN["role"] not in page and EN["footer_note"] not in page


def test_toggle_switches_the_shell_strings_and_persists_by_cookie() -> None:
    with TestClient(create_app()) as client:
        english = client.get("/?lang=en")
        assert english.cookies.get(COOKIE) == "en"
        for key in ("role", "footer_note", "step_1", "step_7", "nav_steps"):
            assert EN[key] in english.text
        assert ES["role"] not in english.text and ES["footer_note"] not in english.text
        follow_up = client.get("/step/1").text  # no query parameter: the cookie decides
        assert '<html lang="en">' in follow_up and EN["role"] in follow_up
        client.get("/step/1?lang=es")
        assert '<html lang="es">' in client.get("/step/2").text


def test_toggle_links_keep_the_page_and_the_query() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/step/2?x=abc&y=R.+Reviewer&lang=es").text
    links = re.findall(r'<a href="([^"]+)" hreflang="(\w+)"', page)
    assert {code for _, code in links} == {"es", "en"}
    for href, code in links:
        assert href.startswith("/step/2?") and "x=abc" in href and f"lang={code}" in href
    assert re.search(r'hreflang="es" lang="es" aria-current="true"', page)


def test_unknown_locale_falls_back_to_the_default() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/?lang=fr")
    assert '<html lang="es">' in response.text and COOKIE not in response.cookies


def test_the_redirect_from_step_4_keeps_the_chosen_locale() -> None:
    with TestClient(create_app()) as client:
        page = client.get("/step/4?lang=en").text
    assert '<html lang="en">' in page and "Acting as:" in page
