import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cairn import jobs
from cairn.app import create_app


def test_post_job_reaches_done_and_get_returns_report_with_inputs_hash() -> None:
    with TestClient(create_app()) as client:
        created = client.post("/jobs", json={"kind": "validate_study"})
        assert created.status_code == 202
        job = created.json()
        assert set(job) == {"job_id", "kind", "inputs_sha256", "status", "outputs"}
        assert job["kind"] == "validate_study"
        assert len(job["inputs_sha256"]) == 64
        for _ in range(100):
            body = client.get(f"/jobs/{job['job_id']}").json()
            if body["status"] in ("done", "failed"):
                break
            time.sleep(0.1)
        assert body["status"] == "done"
        assert body["inputs_sha256"] == job["inputs_sha256"]
        assert body["outputs"]["report"]["quarantine"]["total"] == 12


def test_same_inputs_give_same_inputs_hash() -> None:
    with TestClient(create_app()) as client:
        a = client.post("/jobs", json={"kind": "validate_study"}).json()
        b = client.post("/jobs", json={"kind": "validate_study"}).json()
        assert a["job_id"] != b["job_id"]
        assert a["inputs_sha256"] == b["inputs_sha256"]


def test_unknown_kind_and_unknown_job() -> None:
    with TestClient(create_app()) as client:
        assert client.post("/jobs", json={"kind": "nope"}).status_code == 422
        assert client.get("/jobs/missing").status_code == 404


def test_failed_job_reports_the_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(kind: str, params: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(jobs, "execute", boom)
    with TestClient(create_app()) as client:
        job = client.post("/jobs", json={"kind": "validate_study"}).json()
        for _ in range(100):
            body = client.get(f"/jobs/{job['job_id']}").json()
            if body["status"] in ("done", "failed"):
                break
            time.sleep(0.05)
        assert body["status"] == "failed"
        assert body["outputs"] == {"error": "boom"}


def test_execute_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="broken"):
        jobs.execute("broken", {})
