"""Smoke test for the four-screen wiring: every screen answers and the thread follows the visitor."""

import re

from fastapi.testclient import TestClient

from cairn.app import create_app


def test_four_screens_and_thread_cookie(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    with TestClient(create_app()) as client:
        for lang in ("es", "en"):
            for path in ("/", "/study", "/ask", "/decide", "/draft"):
                reply = client.get(path, params={"lang": lang})
                assert reply.status_code == 200, (lang, path, reply.status_code)
        for number, target in {1: "/study", 3: "/ask", 4: "/decide", 7: "/draft"}.items():
            old = client.get(f"/step/{number}?lang=en", follow_redirects=False)
            assert old.status_code == 303 and old.headers["location"] == f"{target}?lang=en"
        assert client.get("/explore", follow_redirects=False).headers["location"] == "/ask"

        client.cookies.clear()
        fresh = client
        thread = fresh.get("/draft").text
        assert "not decided yet" in thread or "sin decidir" in thread
        cookie = fresh.cookies.get("cairn_thread")
        assert cookie
        assert fresh.post("/decide/example", follow_redirects=False).status_code == 303
        confirm = fresh.post("/decide/confirm", data={"actor": "R. Reviewer"}, follow_redirects=False)
        assert confirm.headers["location"].startswith("/draft")
        assert fresh.get("/study").status_code == 200
        done = fresh.get("/draft")
        assert done.status_code == 200 and "undecided" not in done.text
        assert re.search(r"A\. Author", done.text)
        assert fresh.cookies.get("cairn_thread") == cookie
