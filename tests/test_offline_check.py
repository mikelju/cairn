"""The offline smoke check (`cairn.offline_check`) runs against the app as the container does."""

from __future__ import annotations

import importlib
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from email.message import Message
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from cairn import offline_check
from cairn.app import create_app


def _http_error(path: str, status: int, body: bytes) -> HTTPError:
    """What `urllib.request.urlopen` raises for a 4xx or 5xx answer."""
    return HTTPError(offline_check.BASE + path, status, "error", Message(), BytesIO(body))


class _Server:
    """Stands in for the uvicorn subprocess."""

    def terminate(self) -> None:
        self.terminated = True


@pytest.fixture
def run_check(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., int]]:
    """Run `offline_check.main()` with its HTTP layer served by the app's TestClient."""
    with TestClient(create_app()) as client:

        def run(override: Callable[[str], tuple[int, bytes] | None] = lambda path: None) -> int:
            @contextmanager
            def urlopen(target: Any) -> Iterator[SimpleNamespace]:
                if isinstance(target, str):
                    path, data = target.removeprefix(offline_check.BASE), None
                else:
                    path = target.full_url.removeprefix(offline_check.BASE)
                    data = target.data
                forced = override(path)
                if forced is not None and forced[0] >= 400:  # urllib raises on 4xx and 5xx
                    raise _http_error(path, forced[0], forced[1])
                if forced is not None:
                    yield SimpleNamespace(status=forced[0], read=lambda: forced[1])
                    return
                response = (
                    client.get(path)
                    if data is None
                    else client.post(
                        path,
                        content=data,
                        headers={"content-type": "application/x-www-form-urlencoded"},
                    )
                )
                if response.status_code >= 400:
                    raise _http_error(path, response.status_code, response.content)
                yield SimpleNamespace(status=response.status_code, read=lambda: response.content)

            monkeypatch.setattr(
                offline_check,
                "http",
                SimpleNamespace(
                    urlopen=urlopen,
                    Request=lambda url, data: SimpleNamespace(full_url=url, data=data),
                ),
            )
            monkeypatch.setattr(
                offline_check, "subprocess", SimpleNamespace(Popen=lambda command: _Server())
            )
            monkeypatch.setattr(
                offline_check,
                "socket",
                SimpleNamespace(
                    socket=lambda: SimpleNamespace(connect_ex=lambda address: 0),
                ),
            )
            return offline_check.main()

        yield run


def test_offline_check_passes_against_the_app(
    run_check: Callable[..., int], capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_check() == 0
    out = capsys.readouterr().out
    assert "/step/3 200" in out
    assert "PNG" in out
    assert "POST /step/2/run 200 RECORDED" in out
    assert "steps 4-6: reviewer approves ok" in out


def test_offline_check_fails_without_a_highlight_link(run_check: Callable[..., int]) -> None:
    assert run_check(lambda path: (200, b"<html></html>") if path == "/step/3" else None) == 1


def test_offline_check_fails_without_a_png(run_check: Callable[..., int]) -> None:
    def override(path: str) -> tuple[int, bytes] | None:
        if path.startswith("/highlights/"):
            return 200, b"not an image"
        return None

    assert run_check(override) == 1


def test_offline_check_fails_when_the_highlight_page_has_no_image(
    run_check: Callable[..., int],
) -> None:
    def override(path: str) -> tuple[int, bytes] | None:
        return (200, b"<html></html>") if path.startswith("/highlight/") else None

    assert run_check(override) == 1


def test_offline_check_fails_when_step_2_is_not_recorded(run_check: Callable[..., int]) -> None:
    def override(path: str) -> tuple[int, bytes] | None:
        return (200, b"no marker") if path == "/step/2/run" else None

    assert run_check(override) == 1


@pytest.mark.parametrize("route", ["/healthz", "/explore", "/step/1"])
def test_offline_check_fails_when_a_route_does_not_answer_200(
    run_check: Callable[..., int], capsys: pytest.CaptureFixture[str], route: str
) -> None:
    assert run_check(lambda path: (500, b"boom") if path == route else None) == 1
    assert f"{route} 500" in capsys.readouterr().out


def test_offline_check_fails_when_the_author_is_not_refused(run_check: Callable[..., int]) -> None:
    assert run_check(lambda path: (200, b"approved") if path == "/step/5/approve" else None) == 1


def test_offline_check_fails_when_step_6_has_no_verified_chain(
    run_check: Callable[..., int],
) -> None:
    assert run_check(lambda path: (200, b"no chain") if path.startswith("/step/6") else None) == 1


def test_offline_check_fails_when_the_image_lacks_the_kappa_file(
    run_check: Callable[..., int], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(offline_check, "KAPPA_PATH", tmp_path / "missing.json")
    assert run_check() == 1


def test_offline_check_fails_when_no_sentence_is_judged(
    run_check: Callable[..., int], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = tmp_path / "recordings"
    shutil.copytree("recordings", folder, ignore=shutil.ignore_patterns("j-*.json"))
    for name in ("cairn.web.people", "cairn.web.threads"):
        monkeypatch.setattr(importlib.import_module(name), "RECORDINGS_DIR", folder)
    assert run_check() == 1
