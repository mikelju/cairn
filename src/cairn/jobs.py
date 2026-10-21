"""Jobs: the Job contract and an in-process asyncio runner for validate_study."""

import asyncio
import uuid
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel

from cairn.canonical import canonical_sha256
from cairn.ingest import build_report, load_study
from cairn.validate import validate_study

JobStatus = Literal["queued", "running", "done", "failed"]
KINDS = ("validate_study",)


class Job(BaseModel):
    job_id: str
    kind: str
    inputs_sha256: str
    status: JobStatus
    outputs: dict[str, Any] | None = None


@lru_cache(maxsize=1)
def _snapshot() -> str:
    return load_study()[2]


def inputs_hash(kind: str, params: dict[str, Any]) -> str:
    """One hash for what a job reads: its kind, parameters and the pinned data snapshot."""
    return canonical_sha256({"kind": kind, "params": params, "snapshot_sha256": _snapshot()})


def run_validate_study(params: dict[str, Any]) -> dict[str, Any]:
    frames, zeros, snapshot = load_study()
    validation = validate_study(frames, zeros)
    return {"report": build_report(frames, validation, snapshot)}


def execute(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"unknown job kind: {kind}")
    return run_validate_study(params)


class JobRunner:
    """Holds jobs in memory and runs each one as an asyncio task."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def submit(self, kind: str, params: dict[str, Any]) -> Job:
        if kind not in KINDS:
            raise ValueError(f"unknown job kind: {kind}")
        job = Job(
            job_id=uuid.uuid4().hex,
            kind=kind,
            inputs_sha256=inputs_hash(kind, params),
            status="queued",
        )
        self.jobs[job.job_id] = job
        self.tasks[job.job_id] = asyncio.create_task(self._run(job, params))
        return job

    async def _run(self, job: Job, params: dict[str, Any]) -> None:
        job.status = "running"
        try:
            job.outputs = await asyncio.to_thread(execute, job.kind, params)
            job.status = "done"
        except Exception as error:
            job.outputs = {"error": str(error)}
            job.status = "failed"

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)
