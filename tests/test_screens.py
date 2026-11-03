"""C2-C6 and C13 of change 004: four screens, one menu, redirects, a folded Inside panel."""

import os
import re
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.web.i18n import COOKIE
from screens import LANGS, REAL_RECORDINGS, STATE_MARKERS, rendered_state

SCREENS = ("/study", "/ask", "/decide", "/draft")
MENU = {
    "es": ["El estudio", "Pregúntale", "Decides tú", "El borrador"],
    "en": ["The study", "Ask it", "You decide", "The draft"],
}
COUNTER = {"es": "Paso {n} de 4", "en": "Step {n} of 4"}
NEXT = {"es": "Siguiente", "en": "Next"}
UNDECIDED = {"es": "sin decidir", "en": "not decided yet"}
REDIRECTS = {
    "/step/1": "/study",
    "/step/2": "/ask",
    "/step/3": "/ask",
    "/step/4": "/decide",
    "/step/5": "/draft",
    "/step/6": "/draft",
    "/step/7": "/draft",
    "/explore": "/ask",
}


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    mp = pytest.MonkeyPatch()
    mp.setenv("CAIRN_THREADS_DB", str(tmp_path_factory.mktemp("db") / "threads.db"))
    with TestClient(create_app()) as c:
        yield c
    mp.undo()


@pytest.fixture(autouse=True)
def _clean(client: TestClient) -> None:
    client.cookies.clear()


def _text(fragment: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", fragment).split())


def _menu(html: str) -> list[tuple[str, str, bool]]:
    nav = re.search(r'<nav class="steps".*?</nav>', html, re.S)
    assert nav, "no menu"
    return [
        (m.group(2), _text(m.group(3)).lstrip("0123456789 "), "aria-current" in m.group(1))
        for m in re.finditer(r'<a([^>]*href="([^"]+)"[^>]*)>(.*?)</a>', nav.group(0), re.S)
    ]


def _screen_nav(html: str) -> list[tuple[str, str]]:
    block = re.search(r'<p class="btn-row screen-nav">(.*?)</p>', html, re.S)
    assert block, "no screen-nav"
    return [
        (m.group(1), re.sub(r"&[lr]arr;", "", _text(m.group(2))).strip())
        for m in re.finditer(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', block.group(1), re.S)
    ]


def _main(html: str) -> str:
    main = re.search(r"<main.*?</main>", html, re.S)
    assert main
    return main.group(0)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_c2_menu_counter_and_next(client: TestClient, lang: str) -> None:
    for i, path in enumerate(SCREENS, start=1):
        html = client.get(path, params={"lang": lang}).text
        menu = _menu(html)
        assert [label for _, label, _ in menu] == MENU[lang]
        assert [href for href, _, _ in menu] == list(SCREENS)
        assert COUNTER[lang].format(n=i) in html
        assert "<ol" not in _main(html)
        nav = _screen_nav(html)
        nexts = [href for href, label in nav if label == NEXT[lang]]
        if i < 4:
            assert nexts == [SCREENS[i]]
        else:
            assert nexts == [] and len(nav) == 1
        assert ('<a class="btn-primary"' in html) == (i < 4)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_c3_redirects_keep_lang(client: TestClient, lang: str) -> None:
    for old, new in REDIRECTS.items():
        reply = client.get(old, params={"lang": lang}, follow_redirects=False)
        assert reply.status_code == 303, old
        assert reply.headers["location"] == f"{new}?lang={lang}", old


def test_c3_crawler_finds_no_dead_or_old_links(client: TestClient) -> None:
    seen: set[str] = set()
    queue = ["/", *SCREENS]
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        reply = client.get(path)
        assert reply.status_code < 400, (path, reply.status_code)
        if "text/html" not in reply.headers.get("content-type", ""):
            continue
        refs = re.findall(r'(?:href|action)="([^"]*)"', reply.text)
        actions = re.findall(r'action="([^"]*)"', reply.text)
        for ref in refs:
            if ref.startswith(("http", "#", "mailto:")) or not ref:
                continue
            assert not ref.startswith(("/step/", "/explore")), (path, ref)
            if ref in actions:
                posted = client.post(ref, follow_redirects=False)  # exists: not 404/405/5xx
                assert posted.status_code not in (404, 405) and posted.status_code < 500, (
                    path,
                    ref,
                    posted.status_code,
                )
            else:
                queue.append(ref)
    assert set(SCREENS) <= seen


def test_c4_menu_navigation_keeps_thread_and_decisions(client: TestClient) -> None:
    client.get("/decide")
    cookie = client.cookies.get("cairn_thread")
    assert cookie
    client.post("/decide/choose", data={"sex": "F", "adverse": "200"}, follow_redirects=False)
    before = client.get("/draft").text
    for path in ("/study", "/ask", "/draft"):
        html = client.get(path).text
        assert path in [href for href, _, _ in _menu(html)]
    after = client.get("/draft").text
    assert client.cookies.get("cairn_thread") == cookie
    assert _main(after) == _main(before)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_c5_next_links_reach_draft_and_empty_draft_says_undecided(
    client: TestClient, lang: str
) -> None:
    path = "/study"
    for _ in range(3):
        html = client.get(path, params={"lang": lang}).text
        path = next(h for h, label in _screen_nav(html) if label == NEXT[lang])
    assert path == "/draft"
    draft = client.get(path, params={"lang": lang})
    assert draft.status_code == 200
    assert UNDECIDED[lang] in draft.text


@pytest.mark.parametrize("lang", ["es", "en"])
def test_c6_one_current_page_per_screen(client: TestClient, lang: str) -> None:
    for path in SCREENS:
        html = client.get(path, params={"lang": lang}).text
        assert html.count('aria-current="page"') == 1
        current = [href for href, _, cur in _menu(html) if cur]
        assert current == [path]
    assert 'aria-current="page"' not in client.get("/", params={"lang": lang}).text


# C13: technical detail is folded into one closed Inside panel per screen.
INSIDE_STATES = {
    "/study": "study_after",
    "/ask": "ask_q2",
    "/decide": "decide_filled",
    "/draft": "draft_approved",
}
# Catalogue keys of the detail that lives only inside the panel, per state.
INSIDE_ONLY = {
    "study_after": ("inside_prod_h", "s1_prod_lead", "s1_prod"),
    "ask_q2": ("inside_prod_h", "exp_prod", "exp_trace", "exp_en_live"),
    "decide_filled": ("inside_prod_h", "s4_prod"),
    "draft_approved": (
        "inside_prod_h",
        "s5_prod",
        "s6_prod",
        "s6_chain_note",
        "s5_judge_h",
        "s6_chain_h",
        "s7_doors_h",
        "s7_same",
        "s7_th_hash",
        "footer_build",
    ),
}
REMOVED_KEYS = (
    "disc_ranking",
    "disc_lower_ranks",
    "disc_trace",
    "disc_checks",
    "disc_production",
    "unit_calls",
    "exp_prod_label",
    "s_path_label",
    "s3_th_guideline",
    "s3_th_section",
    "s3_th_page",
    "s3_prod",
    *(f"s{n}_path_{i}" for n in (1, 2, 3, 4) for i in (1, 2, 3)),
    *(f"exp_path_{i}" for i in (1, 2, 3, 4)),
)
INSIDE = re.compile(r'<details class="inside">.*?</details>', re.S)


@pytest.mark.parametrize("lang", ["es", "en"])
@pytest.mark.parametrize("screen", SCREENS)
def test_c13_one_closed_inside_panel_holds_the_technical_detail(screen: str, lang: str) -> None:
    from cairn.web.i18n import CATALOGUES

    state = INSIDE_STATES[screen]
    html = rendered_state(state, lang)
    t = CATALOGUES[lang]
    assert html.count('<details class="inside"') == 1
    assert '<details class="inside">' in html and '<details class="inside" open' not in html
    panel = INSIDE.search(html)
    assert panel and t["inside"] in panel.group(0).split("</summary>")[0]
    outside = html.replace(panel.group(0), "")
    for key in INSIDE_ONLY[state]:
        marker = t[key].split("{")[0]
        assert marker in panel.group(0), f"{state}: {marker!r} is not inside the panel"
        assert marker not in outside, f"{state}: {marker!r} leaks into main copy"
    for word in ("Lex", "Sem", "Fused"):
        assert f"<th>{word}</th>" not in html


def test_c13_removed_keys_are_gone_from_templates_and_catalogues() -> None:
    from pathlib import Path

    from cairn.web import i18n

    web = Path(i18n.__file__).parent
    sources = "\n".join(p.read_text(encoding="utf-8") for p in (web / "templates").glob("*.html"))
    sources += (web / "i18n.py").read_text(encoding="utf-8")
    for key in REMOVED_KEYS:
        assert f'"{key}"' not in sources and f"t.{key}" not in sources, key
        assert all(key not in c for c in i18n.CATALOGUES.values()), key


# C18: no link to the repository, and every link the demo renders resolves.
EXTERNAL_ALLOWED = {
    "www.fda.gov": "official FDA guideline PDF in data/guidelines; HTTP 200 when added",
    "database.ich.org": "official ICH guideline PDFs in data/guidelines; HTTP 200 when added",
}
HREF = re.compile(r'<a\b[^>]*?\bhref="([^"]*)"')
ID = re.compile(r'\bid="([^"]+)"')


def _crawl(lang: str) -> int:
    """Check every link of every page and fragment in one language; return how many were checked."""
    saved = {k: os.environ.get(k) for k in ("CAIRN_RECORDINGS", "CAIRN_THREADS_DB")}
    os.environ["CAIRN_RECORDINGS"] = str(REAL_RECORDINGS)
    checked = 0
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            os.environ["CAIRN_THREADS_DB"] = str(Path(tmp) / "threads.db")
            with TestClient(create_app()) as client:
                client.cookies.set(COOKIE, lang)
                pages = {
                    path: client.get(path).text
                    for path in ("/", "/study", "/ask", "/decide", "/draft")
                }
                pages["/no-such-page"] = client.get("/no-such-page").text
                pages["/study/run"] = client.post("/study/run").text
                for question in ("Q2", "Q6", "G2", "NS1"):
                    pages[f"/ask/run {question}"] = client.post(
                        "/ask/run", data={"question": question}
                    ).text
                for name in STATE_MARKERS:
                    pages[name] = rendered_state(name, lang)
                for html in list(pages.values()):
                    for href in HREF.findall(html):
                        if href.startswith("/highlight/") and href not in pages:
                            pages[href] = client.get(href).text
                for name, html in pages.items():
                    ids = set(ID.findall(html))
                    for href in HREF.findall(html):
                        where = f"{lang} {name}: {href}"
                        assert "github.com" not in href, where
                        checked += 1
                        if href.startswith("#"):
                            assert href[1:] in ids, f"dead anchor {where}"
                        elif href.startswith(("http://", "https://")):
                            assert href.split("/")[2] in EXTERNAL_ALLOWED, (
                                f"unlisted external {where}"
                            )
                        else:
                            reply = client.get(href.split("#")[0], follow_redirects=True)
                            assert reply.status_code == 200, f"{reply.status_code} {where}"
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return checked


def test_every_link_resolves_and_none_points_to_the_repository() -> None:
    """C18: no github.com href, internal hrefs answer 200, anchors have ids, externals listed."""
    for lang in LANGS:
        assert _crawl(lang) > 50
