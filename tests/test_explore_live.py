"""Live Explore (phase 06, increment 1): fake client only, never Bedrock."""

import hmac
import threading
import time
from datetime import date
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from cairn import live, retrieval, tools
from cairn.app import create_app
from cairn.gateway import DEFAULT_MODEL
from cairn.pricing import call_cost
from cairn.web import explore_live

LIVE_RUN = {
    "stop_reason": "tool_use",
    "content": [
        {"type": "tool_use", "id": "t1", "name": "run_job", "input": {"kind": "validate_study"}}
    ],
    "usage": {"input_tokens": 1000, "output_tokens": 100},
}
LIVE_ANSWER = {
    "stop_reason": "tool_use",
    "content": [
        {
            "type": "tool_use",
            "id": "t2",
            "name": "write_answer",
            "input": {"sentences": [{"parts": [{"type": "text", "text": "No data."}]}]},
        }
    ],
    "usage": {"input_tokens": 1000, "output_tokens": 100},
}


class LiveFake:
    def __init__(self, replies: list[Any]):
        self.replies = replies
        self.calls = 0
        self.messages = self

    def create(self, **kwargs: Any) -> Any:
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def live_box(monkeypatch: pytest.MonkeyPatch) -> LiveFake:
    fake = LiveFake([LIVE_RUN, LIVE_ANSWER])
    monkeypatch.setattr(live, "make_client", lambda mode: fake)
    monkeypatch.setenv("CAIRN_ACCESS_CODE", "s3cret")
    monkeypatch.delenv("CAIRN_LIVE_CAP_USD", raising=False)
    explore_live._spend.clear()
    return fake


def ask_box(code: str, question: str = "How many animals?") -> str:
    with TestClient(create_app()) as client:
        return client.post("/explore/live", data={"question": question, "code": code}).text


def test_explore_live_refuses_without_code_wrong_code_or_long_question(live_box: LiveFake) -> None:
    for code, question in (("", "q"), ("wrong", "q"), ("s3cret", "x" * 501), ("s3cret", " ")):
        page = ask_box(code, question)
        assert "Recorded questions" in page and "s3cret" not in page
    assert live_box.calls == 0


def test_explore_live_is_off_without_a_configured_code(
    live_box: LiveFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CAIRN_ACCESS_CODE")
    assert "Recorded questions" in ask_box("")
    assert live_box.calls == 0


def test_explore_live_answers_with_real_badge_and_never_shows_the_code(live_box: LiveFake) -> None:
    page = ask_box("s3cret")
    assert 'class="badge real"' in page and "opus-4-6" in page and "USD" in page
    assert "No data." in page and "s3cret" not in page
    assert live_box.calls == 2


def test_explore_live_shows_a_cut_or_a_failure_as_is(live_box: LiveFake) -> None:
    partial = LIVE_ANSWER["content"]
    live_box.replies = [{"stop_reason": "max_tokens", "content": partial, "usage": {}}]
    page = ask_box("s3cret")
    assert "cut off" in page and "No data." not in page
    live_box.calls = 0
    live_box.replies = [{"stop_reason": "refusal", "content": [], "usage": {}}]
    declined = ask_box("s3cret")
    assert "declined" in declined and "No data." not in declined
    live_box.replies = [TimeoutError("slow")]
    assert "The live call failed (TimeoutError)" in ask_box("s3cret")


def test_explore_live_box_shows_only_with_a_code(
    live_box: LiveFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(create_app()) as client:
        assert "/explore/live" in client.get("/explore").text
        monkeypatch.delenv("CAIRN_ACCESS_CODE")
        assert "/explore/live" not in client.get("/explore").text


def test_live_cap_blocks_at_the_cap_and_reopens_next_utc_day(
    live_box: LiveFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAIRN_LIVE_CAP_USD", "0.01")
    assert 'class="badge real"' in ask_box("s3cret")  # two calls, about 0.0165 USD
    calls = live_box.calls
    assert "daily live budget" in ask_box("s3cret")
    assert live_box.calls == calls
    monkeypatch.setattr(explore_live, "utc_today", lambda: date(2099, 1, 2))
    assert 'class="badge real"' in ask_box("s3cret")


def test_live_cap_counts_a_failed_call_and_refuses_a_second_question_while_one_runs(
    live_box: LiveFake,
) -> None:
    live_box.replies = [RuntimeError("x")]
    ask_box("s3cret")
    assert explore_live.spent_today() > 0
    explore_live._spend.clear()
    live_box.calls = 0
    assert explore_live._busy.acquire(blocking=False)
    try:
        assert "Another live question is running" in ask_box("s3cret")
        assert live_box.calls == 0
    finally:
        explore_live._busy.release()


def test_live_cap_compares_the_code_in_constant_time(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[bytes, bytes]] = []
    real = hmac.compare_digest

    def spy(a: bytes, b: bytes) -> bool:
        seen.append((a, b))
        return real(a, b)

    monkeypatch.setattr(hmac, "compare_digest", spy)
    monkeypatch.setenv("CAIRN_ACCESS_CODE", "abc")
    assert explore_live.code_ok("abc") and not explore_live.code_ok("abd")
    assert len(seen) == 2


def test_live_index_builds_once_under_concurrent_first_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[int] = []

    def slow_build() -> object:
        built.append(1)
        time.sleep(0.05)
        return object()

    monkeypatch.setattr(retrieval, "build_index", slow_build)
    monkeypatch.setattr(tools, "_index", None)
    found: list[object] = []
    workers = [threading.Thread(target=lambda: found.append(tools._live_index())) for _ in range(6)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert len(built) == 1 and len({id(i) for i in found}) == 1


def test_live_index_loads_the_reranker_once(monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[int] = []

    class Ranker:
        def rerank(self, query: str, texts: list[str], batch_size: int = 1) -> list[float]:
            return [1.0 for _ in texts]

    def slow_load(models: object) -> Ranker:
        time.sleep(0.05)
        loads.append(1)
        return Ranker()

    monkeypatch.setattr(retrieval, "_load_reranker", slow_load)
    index = retrieval.Index([], None, np.zeros(0), None, texts={})
    monkeypatch.setattr(index, "search", lambda query, limit=0: [])
    workers = [threading.Thread(target=lambda: index.rerank("q")) for _ in range(6)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert len(loads) == 1


def test_live_cap_default_and_bad_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAIRN_LIVE_CAP_USD", "oops")
    assert explore_live.daily_cap() == 2.0


def test_live_cap_counts_the_spend_of_calls_made_before_a_failure(live_box: LiveFake) -> None:
    live_box.replies = [LIVE_RUN, LIVE_RUN, TimeoutError("slow")]
    ask_box("s3cret")
    real = 2 * call_cost(DEFAULT_MODEL, 1000, 100)
    assert explore_live.spent_today() == pytest.approx(real + live.call_ceiling(DEFAULT_MODEL))
    assert live_box.calls == 3


def test_live_cap_is_checked_again_once_the_lock_is_held(live_box: LiveFake) -> None:
    class Lock:  # another question finishes and uses the budget while this one waits
        def acquire(self, blocking: bool = True) -> bool:
            explore_live._add_spend(5.0)
            return True

        def release(self) -> None:
            pass

    explore_live._busy = Lock()  # type: ignore[assignment]
    try:
        assert "daily live budget" in ask_box("s3cret")
    finally:
        explore_live._busy = threading.Lock()
    assert live_box.calls == 0


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-1"])
def test_live_cap_ignores_a_non_finite_or_negative_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CAIRN_LIVE_CAP_USD", value)
    assert explore_live.daily_cap() == 2.0


def test_live_question_reaches_the_search_tool_with_the_live_flag(
    live_box: LiveFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    guidance = retrieval.Guidance(
        query="x", abstained=True, best_score=0.0, threshold=1.0, message="none", hits=[]
    )

    def fake_search(index: object, query: str) -> retrieval.Guidance:
        seen.append(query)
        return guidance

    monkeypatch.setattr(tools, "_live_index", lambda: "index")
    monkeypatch.setattr(retrieval, "search_guidance", fake_search)
    monkeypatch.setenv("CAIRN_LLM_MODE", "replay")
    search = {"type": "tool_use", "id": "s", "name": "search_guidance", "input": {"query": "x"}}
    live_box.replies = [LIVE_RUN, {**LIVE_RUN, "content": [search]}, LIVE_ANSWER]
    ask_box("s3cret")
    assert seen == ["x"]
