"""C2-C6 of change 004: four screens, one menu, old routes redirect, nothing is lost on the way."""

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app

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
    client.post("/decide/example", follow_redirects=False)
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
