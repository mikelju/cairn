"""The offline smoke check (`cairn.offline_check`) runs against the app the way the container runs it."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cairn import offline_check
from cairn.app import create_app


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
