"""Bounded wait for RUNNING over a fake service: no AWS and no real sleeps."""

from typing import Any

from cairn.wait_running import wait_running


def run(states: list[dict[str, Any]], tries: int = 5) -> tuple[bool, list[float], int]:
    seq = iter(states)
    sleeps: list[float] = []
    calls = 0

    def fetch() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return next(seq)

    ok = wait_running(fetch, tries=tries, interval=7, sleep=sleeps.append, log=lambda _: None)
    return ok, sleeps, calls


def test_wait_passes_after_deploying() -> None:
    ok, sleeps, calls = run([{"state": "DEPLOYING"}, {"state": "DEPLOYING"}, {"state": "RUNNING"}])
    assert ok
    assert calls == 3
    assert sleeps == [7, 7]


def test_wait_ignores_running_while_next_deployment_pending() -> None:
    ok, _, calls = run(
        [
            {"state": "RUNNING", "nextDeployment": {"state": "ACTIVATING"}},
            {"state": "RUNNING"},
        ]
    )
    assert ok
    assert calls == 2


def test_wait_fails_after_all_tries() -> None:
    ok, sleeps, calls = run([{"state": "DEPLOYING"}] * 3, tries=3)
    assert not ok
    assert calls == 3
    assert len(sleeps) == 2


def test_wait_fails_fast_on_failed_deployment() -> None:
    ok, _, calls = run([{"state": "DEPLOYING", "nextDeployment": {"state": "FAILED"}}])
    assert not ok
    assert calls == 1


def test_wait_fails_fast_on_disabled_service() -> None:
    ok, _, calls = run([{"state": "DISABLED"}])
    assert not ok
    assert calls == 1
