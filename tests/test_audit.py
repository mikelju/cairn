"""The audit chain: building, the events of the API walkthrough, tampering on a copy, SEC-002."""

import copy
import hashlib
import itertools
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient

from cairn import audit
from cairn.app import create_app
from cairn.decisions import EXAMPLE
from cairn.ingest import DEFAULT_DB
from cairn.observation import StaleBuild, check_build, current_snapshot
from cairn.web.threads import threads
from cairn.workflow import gather_state

AUTHOR, REVIEWER = "A. Author", "R. Reviewer"


def start(client: TestClient) -> dict[str, Any]:
    reply = client.post("/api/threads", json={"author": AUTHOR})
    assert reply.status_code == 201
    body: dict[str, Any] = reply.json()
    return body


def example(slot: dict[str, Any]) -> tuple[float | None, float | None]:
    return EXAMPLE[slot["sex"], slot["finding"]]


def form(thread: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "dec_id": s["slot"],
            "treatment_related_from": example(s)[0],
            "adverse_from": example(s)[1],
        }
        for s in thread["slots"]
    ]


def decide(client: TestClient, thread: dict[str, Any], decisions: list[dict[str, Any]]) -> Any:
    path = f"/api/threads/{thread['thread_id']}"
    client.post(f"{path}/decisions", json={"actor": AUTHOR, "decisions": decisions})
    return client.post(f"{path}/confirm", json={"actor": REVIEWER, "confirmed": ["F", "M"]})


def approve(client: TestClient, thread: dict[str, Any], actor: str) -> Any:
    return client.post(f"/api/threads/{thread['thread_id']}/approve", json={"actor": actor})


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "threads.db"
    monkeypatch.setenv("CAIRN_THREADS_DB", str(path))
    return path


@pytest.fixture
def client(db_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def build_chain(count: int = 5) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    previous = audit.ZEROS
    for seq in range(1, count + 1):
        entry = audit.make_entry(
            seq, f"2026-10-28T10:00:0{seq}Z", "A. Author", "x", {"n": seq}, previous
        )
        chain.append(entry)
        previous = entry["hash"]
    return chain


def stored(db_path: Path, thread_id: str) -> list[tuple[Any, ...]]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT * FROM audit WHERE thread_id = ? ORDER BY seq", (thread_id,)
        ).fetchall()


def test_audit_chain_links_and_is_deterministic() -> None:
    chain = build_chain()
    assert chain[0]["prev_hash"] == "0" * 64
    for before, after in itertools.pairwise(chain):
        assert after["prev_hash"] == before["hash"]
    body = {k: v for k, v in chain[2].items() if k != "hash"}
    assert chain[2]["hash"] == audit.entry_hash(body)
    assert chain == build_chain()  # same inputs and timestamps, same hashes
    assert audit.verify_chain(chain) == audit.Check(True, 5)
    assert audit.verify_chain([]) == audit.Check(True, 0)


def edit(field: str, value: Any) -> Any:
    def apply(chain: list[dict[str, Any]]) -> None:
        chain[2][field] = value

    return apply


def swap(chain: list[dict[str, Any]]) -> None:
    chain[1], chain[2] = chain[2], chain[1]


def insert(chain: list[dict[str, Any]]) -> None:
    extra = audit.make_entry(3, "2026-10-28T10:00:09Z", "X", "forged", {}, chain[1]["hash"])
    chain.insert(2, extra)


CASES = {
    "edit seq": (edit("seq", 9), 9),
    "edit ts": (edit("ts", "2027-01-01T00:00:00Z"), 3),
    "edit actor": (edit("actor", "R. Reviewer"), 3),
    "edit action": (edit("action", "approved"), 3),
    "edit payload": (edit("payload", {"n": 99}), 3),
    "edit prev_hash": (edit("prev_hash", "f" * 64), 3),
    "edit hash": (edit("hash", "f" * 64), 3),
    "delete": (lambda chain: chain.pop(2), 4),
    "swap": (swap, 3),
    "insert": (insert, 3),
}


@pytest.mark.parametrize("name", CASES)
def test_audit_tamper_is_detected_on_a_copy(name: str) -> None:
    chain = build_chain()
    original = copy.deepcopy(chain)
    tampered = copy.deepcopy(chain)
    mutate, broken = CASES[name]
    mutate(tampered)
    check = audit.verify_chain(tampered)
    assert not check.ok
    assert check.first_broken == broken
    assert chain == original  # the stored chain is untouched


def test_audit_tamper_truncated_tail_shows_only_against_a_known_head() -> None:
    chain = build_chain()
    head = chain[-1]["hash"]
    cut = chain[:3]
    assert audit.verify_chain(cut).ok  # the stated limit: a cut tail is not seen without a head
    check = audit.verify_chain(cut, head)
    assert not check.ok and check.first_broken == 4
    assert audit.verify_chain(chain, head).ok


def test_audit_events_follow_the_walkthrough(client: TestClient, db_path: Path) -> None:
    thread = start(client)
    assert approve(client, thread, REVIEWER).status_code == 409  # wrong step: changes nothing
    assert decide(client, thread, form(thread)[:-1]).status_code == 409  # slot unfilled
    assert decide(client, thread, form(thread)).status_code == 200
    assert approve(client, thread, AUTHOR).status_code == 403
    assert approve(client, thread, REVIEWER).status_code == 200
    rows = stored(db_path, thread["thread_id"])
    assert [(r[1], r[3], r[4]) for r in rows] == [
        (1, AUTHOR, "thread_started"),
        (2, AUTHOR, "decisions_recorded"),
        (3, REVIEWER, "refused"),
        (4, AUTHOR, "decisions_recorded"),
        (5, REVIEWER, "noael_confirmed"),
        (6, "system", "verify_final"),
        (7, AUTHOR, "refused"),
        (8, REVIEWER, "approved"),
    ]
    assert "snapshot_sha256" in rows[0][5]


def test_api_audit_verify_full_walkthrough_and_unknown_thread(
    client: TestClient, db_path: Path
) -> None:
    thread = start(client)
    decide(client, thread, form(thread))
    approve(client, thread, REVIEWER)
    path = f"/api/threads/{thread['thread_id']}/audit/verify"
    assert client.get(path).json() == {"ok": True, "count": 5, "first_broken": None}
    assert client.get("/api/threads/nope/audit/verify").status_code == 404
    audit_routes = [r.path for r in threads.routes if "audit" in r.path]  # type: ignore[attr-defined]
    assert audit_routes == ["/api/threads/{thread_id}/audit/verify"]
    assert [r.methods for r in threads.routes if "audit" in r.path] == [{"GET"}]  # type: ignore[attr-defined]
    # editing a stored entry outside the API makes verify report it
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE audit SET actor = 'X' WHERE thread_id = ? AND seq = 3", (thread["thread_id"],)
        )
    assert client.get(path).json() == {"ok": False, "count": 5, "first_broken": 3}


def test_snapshot_mismatch_fails_gather_and_real_build_passes(tmp_path: Path) -> None:
    check_build()  # the real build
    assert gather_state()["observations"][0]["snapshot_sha256"] == current_snapshot()
    stale = tmp_path / "stale.duckdb"
    shutil.copy(DEFAULT_DB, stale)
    with duckdb.connect(str(stale)) as connection:
        connection.execute("UPDATE build SET snapshot_sha256 = 'other'")
    with pytest.raises(StaleBuild, match="not the pinned"):
        check_build(stale)
    with duckdb.connect(str(stale)) as connection:
        connection.execute("DROP TABLE build")
    with pytest.raises(StaleBuild):
        check_build(stale)


def test_snapshot_gather_refuses_a_changed_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cairn.observation.current_snapshot", lambda: hashlib.sha256(b"x").hexdigest()
    )
    with pytest.raises(StaleBuild):
        gather_state()
