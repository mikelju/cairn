"""Disclosures are pill buttons that name their content and size; reading cues; no help panel."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web import templates
from cairn.web.i18n import CATALOGUES
from test_word_cap import rendered_state

WEB = Path(__file__).resolve().parents[1] / "src" / "cairn" / "web"
REAL_RECORDINGS = Path(__file__).resolve().parent / "fixtures" / "recordings_real_shape"
SUMMARY = re.compile(r"<summary([^>]*)>(.*?)</summary>", re.S)
GENERIC = {"details", "more", "show", "detalles", "más", "mas", "ver", "mostrar"}
HELP_MARKERS = (
    "aside.explain",
    'class="explain"',
    "How to read this page",
    "Cómo leer esta página",
)
REAL_STATES = (
    "step1_after",
    "step5_refused",
    "step6",
    "step7",
    "step6_broken",
    "step7_broken",
    "step7_mismatch",
)


def _pages(lang: str, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("CAIRN_RECORDINGS", str(REAL_RECORDINGS))
    pages: dict[str, str] = {}
    with TestClient(create_app()) as client:
        client.get(f"/?lang={lang}")
        thread = client.post("/api/threads").json()["thread_id"]
        for name in ("/", "/explore", "/step/1", "/step/2", "/step/3"):
            pages[name] = client.get(name).text
        pages["q2"] = client.post("/step/2/run", data={"question": "Q2"}).text
        pages["q6"] = client.post("/step/2/run", data={"question": "Q6"}).text
        client.post("/step/4/example", data={"thread": thread})
        pages["/step/4"] = client.get(f"/step/4?thread={thread}").text
        pages["step4_fragment"] = client.post(
            "/step/4/decide", data={"thread": thread, "t_x": "1", "a_x": "1"}
        ).text
        client.post("/step/4/confirm", data={"thread": thread, "actor": "R. Reviewer"})
        pages["/step/5"] = client.get(f"/step/5?thread={thread}").text
    # Steps that need a real thread or a run: the same states the word-cap tests render.
    for state in REAL_STATES:
        pages[state] = rendered_state(state, lang)
    return pages


@pytest.mark.parametrize("lang", ["es", "en"])
def test_every_rendered_summary_is_a_pill_that_names_content_and_size(
    lang: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    pages = _pages(lang, monkeypatch)
    seen = 0
    for name, html in pages.items():
        for attrs, text in SUMMARY.findall(html):
            seen += 1
            label = re.sub(r"<[^>]+>", "", text).strip()
            assert 'class="pill"' in attrs, (lang, name, label)
            match = re.fullmatch(r"(\S+) (.+?) · (\d+) (\S+)", label)
            assert match, (lang, name, label)
            assert match.group(1).lower() in {"ver", "show"}, (lang, name, label)
            assert match.group(2).lower() not in GENERIC, (lang, name, label)
            other = CATALOGUES["en" if lang == "es" else "es"]
            assert not any(v in label for k, v in other.items() if k.startswith("disc_")), (
                lang,
                name,
                label,
            )
    assert seen >= 8


@pytest.mark.parametrize("lang", ["es", "en"])
def test_the_disclosure_labels_come_from_the_active_catalogue(
    lang: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = _pages(lang, monkeypatch)["/step/3"]
    assert CATALOGUES[lang]["disc_lower_ranks"] in html
    assert CATALOGUES[lang]["disc_quotes"] in html


def test_the_catalogue_has_a_label_and_a_unit_for_every_disclosure() -> None:
    used = set(
        re.findall(
            r'disclosure\("(\w+)", [^,]+, "(\w+)"',
            "".join(p.read_text(encoding="utf-8") for p in (WEB / "templates").glob("*.html")),
        )
    )
    assert used
    for catalogue in CATALOGUES.values():
        for key, unit in used:
            assert catalogue[f"disc_{key}"] and "|" in catalogue[f"unit_{unit}"]


def test_no_template_uses_a_bare_details_or_summary() -> None:
    for path in (WEB / "templates").glob("*.html"):
        text = path.read_text(encoding="utf-8")
        if path.name == "_components.html":
            continue
        assert "<details" not in text and "<summary" not in text, path.name


def test_no_help_panel_exists_anywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    sources = [p for p in (WEB / "templates").glob("*.html")] + [WEB / "static" / "cairn.css"]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert not any(m in text for m in HELP_MARKERS) and "aside" not in text, path.name
    for lang in ("es", "en"):
        for name, html in _pages(lang, monkeypatch).items():
            assert not any(m in html for m in HELP_MARKERS) and "<aside" not in html, name


def test_the_reading_path_and_cue_components_render_numbered_stages() -> None:
    template = templates.env.from_string(
        '{% import "_components.html" as a with context %}'
        '{{ a.reading_path(["One", "Two", "Three"], "Path") }}{{ a.cue(2) }}'
    )
    html = template.render(t=CATALOGUES["en"])
    assert html.count("<li>") == 3 and '<ol class="path" aria-label="Path">' in html
    assert [int(n) for n in re.findall(r'class="cue solid"[^>]*>(\d)<', html)] == [1, 2, 3]
    assert '<span class="cue" aria-hidden="true">2</span>' in html


def test_the_new_controls_have_a_visible_focus_outline() -> None:
    css = (WEB / "static" / "cairn.css").read_text(encoding="utf-8")
    assert re.search(r"summary:focus-visible", css)
    assert "outline: var(--border-focus) solid var(--color-accent)" in css
