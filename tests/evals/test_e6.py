"""E6: people decide through the API, offline: pauses, 403, 409, idempotent resume, forms."""

import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cairn.app import create_app
from cairn.decisions import EXAMPLE
from cairn.gateway import LLMGateway
from cairn.workflow import build_graph

AUTHOR, REVIEWER = "A. Author", "R. Reviewer"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("CAIRN_THREADS_DB", str(tmp_path / "threads.db"))
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def model_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Counts model calls from now on; the start of a thread is the only one that may make one."""
    calls: list[int] = []
    create = LLMGateway.create

    def counting(self: LLMGateway, *args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return create(self, *args, **kwargs)

    monkeypatch.setattr(LLMGateway, "create", counting)
    return calls


def start(client: TestClient) -> dict[str, Any]:
    reply = client.post("/api/threads", json={"author": AUTHOR})
    assert reply.status_code == 201
    body: dict[str, Any] = reply.json()
    return body


def form(thread: dict[str, Any], rule: Any) -> list[dict[str, Any]]:
    """One decision per slot; `rule(slot)` gives (treatment-related from, adverse from)."""
    return [
        {"dec_id": s["slot"], "treatment_related_from": rule(s)[0], "adverse_from": rule(s)[1]}
        for s in thread["slots"]
    ]


def example(slot: dict[str, Any]) -> tuple[float | None, float | None]:
    return EXAMPLE[slot["sex"], slot["finding"]]


def decide(
    client: TestClient, thread: dict[str, Any], rule: Any, confirmed: Any = ("F", "M")
) -> Any:
    path = f"/api/threads/{thread['thread_id']}"
    recorded = client.post(
        f"{path}/decisions", json={"actor": AUTHOR, "decisions": form(thread, rule)}
    )
    assert recorded.status_code == 200
    return client.post(f"{path}/confirm", json={"actor": REVIEWER, "confirmed": list(confirmed)})


def approve(client: TestClient, thread: dict[str, Any], actor: str) -> Any:
    return client.post(f"/api/threads/{thread['thread_id']}/approve", json={"actor": actor})


def test_api_start_pauses_at_decisions_with_slots(client: TestClient) -> None:
    thread = start(client)
    assert thread["waiting"] == "await_decisions"
    assert thread["author"] == AUTHOR
    assert [s["slot"] for s in thread["slots"]][:2] == ["D1", "D2"]
    assert thread["final"]["ok"] is False  # empty slots fail rule 2
    assert client.get("/api/threads/nope").status_code == 404


def test_api_decisions_example_set_recomputes_with_no_model_call(
    client: TestClient, model_calls: list[int]
) -> None:
    thread = start(client)
    path = f"/api/threads/{thread['thread_id']}"
    first = client.post(
        f"{path}/decisions", json={"actor": AUTHOR, "decisions": form(thread, example)}
    ).json()
    assert first["waiting"] == "await_decisions"
    assert (first["noael"]["F"]["dose"], first["noael"]["M"]["dose"]) == (20.0, 200.0)
    assert first["noael"]["M"]["flags"]  # incomplete examination is flagged for confirmation
    changed = client.post(
        f"{path}/decisions",
        json={"actor": AUTHOR, "decisions": form(thread, lambda s: (None, None))},
    ).json()
    assert changed["noael"]["F"]["dose"] == changed["noael"]["M"]["dose"] == 400.0
    assert model_calls == [1]  # the draft at start, nothing after


def test_api_confirm_example_set_reaches_approval_green(
    client: TestClient, model_calls: list[int]
) -> None:
    done = decide(client, start(client), example)
    assert done.status_code == 200
    body = done.json()
    assert body["waiting"] == "await_approval"
    assert body["final"]["ok"], body["final"]["failures"]
    assert "NOAEL, females: 20 mg/kg/day" in body["final"]["text"]
    assert "NOAEL, males: 200 mg/kg/day" in body["final"]["text"]
    assert model_calls == [1]  # the draft at start, nothing after


def test_api_confirm_is_reviewer_only(client: TestClient) -> None:
    thread = start(client)
    path = f"/api/threads/{thread['thread_id']}"
    client.post(f"{path}/decisions", json={"actor": AUTHOR, "decisions": form(thread, example)})
    reply = client.post(f"{path}/confirm", json={"actor": AUTHOR, "confirmed": ["F", "M"]})
    assert reply.status_code == 403


def test_api_409_confirm_with_an_unfilled_slot(client: TestClient) -> None:
    thread = start(client)
    path = f"/api/threads/{thread['thread_id']}"
    some = form(thread, example)[:-1]
    client.post(f"{path}/decisions", json={"actor": AUTHOR, "decisions": some})
    reply = client.post(f"{path}/confirm", json={"actor": REVIEWER, "confirmed": ["F", "M"]})
    assert reply.status_code == 409
    assert client.get(path).json()["waiting"] == "await_decisions"


def test_api_403_author_cannot_approve_own_draft(client: TestClient) -> None:
    thread = start(client)
    decide(client, thread, example)
    assert approve(client, thread, AUTHOR).status_code == 403
    assert client.get(f"/api/threads/{thread['thread_id']}").json()["waiting"] == "await_approval"
    done = approve(client, thread, REVIEWER)
    assert done.status_code == 200
    assert done.json()["waiting"] == "done"
    assert done.json()["approved_by"] == REVIEWER


def test_api_409_when_the_thread_is_not_at_that_pause(client: TestClient) -> None:
    thread = start(client)
    assert approve(client, thread, REVIEWER).status_code == 409  # still at decisions
    decide(client, thread, example)
    path = f"/api/threads/{thread['thread_id']}"
    again = client.post(f"{path}/decisions", json={"actor": AUTHOR, "decisions": []})
    assert again.status_code == 409  # decisions are closed once confirmed


def test_api_409_approve_when_verify_final_is_not_green(client: TestClient) -> None:
    thread = start(client)
    decide(client, thread, example)
    saver = client.app.state.saver  # type: ignore[attr-defined]
    graph = build_graph(None, "m", saver)  # type: ignore[arg-type]
    broken = {"final": {"ok": False, "text": "", "failures": ["x"]}}
    assert client.portal is not None
    config = {"configurable": {"thread_id": thread["thread_id"]}}
    client.portal.call(graph.aupdate_state, config, broken)
    assert approve(client, thread, REVIEWER).status_code == 409


def test_resume_idempotent(client: TestClient, model_calls: list[int]) -> None:
    thread = start(client)
    path = f"/api/threads/{thread['thread_id']}"
    first = decide(client, thread, example)
    assert first.status_code == 200
    saver = client.app.state.saver  # type: ignore[attr-defined]
    before = (client.get(path).json(), saver.conn.total_changes)
    again = client.post(f"{path}/confirm", json={"actor": REVIEWER, "confirmed": ["F", "M"]})
    assert again.status_code == 409
    assert (client.get(path).json(), saver.conn.total_changes) == before
    assert approve(client, thread, REVIEWER).status_code == 200
    assert approve(client, thread, REVIEWER).status_code == 409
    assert model_calls == [1]  # the draft at start, nothing after


def only(**adverse: float | None) -> Any:
    """A form rule: the adverse onset by sex; every finding treatment-related from that dose."""

    def rule(slot: dict[str, Any]) -> tuple[float | None, float | None]:
        dose = adverse.get(slot["sex"])
        return (dose, dose)

    return rule


@pytest.mark.parametrize(
    ("rule", "females", "males"),
    [
        (only(F=20.0), None, 400.0),  # lowest treated dose adverse: not established
        (only(M=200.0), 400.0, 20.0),
        (only(F=400.0, M=400.0), 200.0, 200.0),
        (only(), 400.0, 400.0),  # nothing adverse: the highest dose tested
    ],
)
def test_api_form_combinations_use_the_noael_rule_with_no_model_call(
    client: TestClient,
    model_calls: list[int],
    rule: Any,
    females: float | None,
    males: float | None,
) -> None:
    done = decide(client, start(client), rule)
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["waiting"] == "await_approval"
    assert body["final"]["ok"], body["final"]["failures"]
    assert (body["noael"]["F"]["dose"], body["noael"]["M"]["dose"]) == (females, males)
    if females is None:
        assert "NOAEL, females: not established" in body["final"]["text"]
    assert model_calls == [1]  # the draft at start, nothing after


def _twice(client: TestClient, path: str, body: dict[str, Any]) -> list[int]:
    with ThreadPoolExecutor(2) as pool:
        return sorted(pool.map(lambda _: client.post(path, json=body).status_code, range(2)))


def test_api_concurrent_confirm_and_approve_succeed_once(client: TestClient) -> None:
    thread = start(client)
    path = f"/api/threads/{thread['thread_id']}"
    client.post(f"{path}/decisions", json={"actor": AUTHOR, "decisions": form(thread, example)})
    assert _twice(client, f"{path}/confirm", {"actor": REVIEWER, "confirmed": ["F", "M"]}) == [
        200,
        409,
    ]
    assert _twice(client, f"{path}/approve", {"actor": REVIEWER}) == [200, 409]


def test_api_author_is_always_the_author(client: TestClient) -> None:
    reply = client.post("/api/threads", json={"author": REVIEWER})
    thread = reply.json()
    assert thread["author"] == AUTHOR
    path = f"/api/threads/{thread['thread_id']}"
    client.post(f"{path}/decisions", json={"actor": AUTHOR, "decisions": form(thread, example)})
    mine = client.post(f"{path}/confirm", json={"actor": AUTHOR, "confirmed": ["F", "M"]})
    assert mine.status_code == 403
    theirs = client.post(f"{path}/confirm", json={"actor": REVIEWER, "confirmed": ["F", "M"]})
    assert theirs.status_code == 200
    assert approve(client, thread, AUTHOR).status_code == 403


@pytest.mark.parametrize(
    "dose", [1e9, -20.0, float("nan"), 30.0], ids=["huge", "negative", "nan", "not-a-dose"]
)
def test_api_422_for_a_dose_the_slot_does_not_have(client: TestClient, dose: float) -> None:
    thread = start(client)
    path = f"/api/threads/{thread['thread_id']}"
    for field in ("adverse_from", "treatment_related_from"):
        bad = form(thread, example)
        bad[0][field] = dose
        body = json.dumps({"actor": AUTHOR, "decisions": bad}, allow_nan=True)
        reply = client.post(
            f"{path}/decisions", content=body, headers={"content-type": "application/json"}
        )
        assert reply.status_code == 422
    assert client.get(path).status_code == 200


def test_api_422_when_treatment_related_comes_after_adverse(client: TestClient) -> None:
    thread = start(client)
    path = f"/api/threads/{thread['thread_id']}"
    bad = form(thread, example)
    doses = sorted(d for d in thread["slots"][0]["doses"] if d > 0)
    bad[0].update(treatment_related_from=doses[-1], adverse_from=doses[0])
    reply = client.post(f"{path}/decisions", json={"actor": AUTHOR, "decisions": bad})
    assert reply.status_code == 422


def test_api_422_for_adverse_without_treatment_related_and_for_the_control_dose(
    client: TestClient,
) -> None:
    thread = start(client)
    path = f"/api/threads/{thread['thread_id']}"
    dose = max(thread["slots"][0]["doses"])
    cases = [(None, dose), (0, dose), (dose, 0), (0, 0)]
    for treatment_related, adverse in cases:
        bad = form(thread, example)
        bad[0].update(treatment_related_from=treatment_related, adverse_from=adverse)
        reply = client.post(f"{path}/decisions", json={"actor": AUTHOR, "decisions": bad})
        assert reply.status_code == 422, (treatment_related, adverse)
