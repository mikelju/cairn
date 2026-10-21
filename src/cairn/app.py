"""FastAPI application: jobs endpoints now, tools and web pages in later increments."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from cairn.jobs import Job, JobRunner


class JobRequest(BaseModel):
    kind: str
    params: dict[str, Any] = Field(default_factory=dict)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        app.state.runner = JobRunner()
        yield

    app = FastAPI(title="Cairn", lifespan=lifespan)

    @app.post("/jobs", status_code=202)
    async def post_job(request: JobRequest) -> Job:
        try:
            job: Job = app.state.runner.submit(request.kind, request.params)
            return job
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str) -> Job:
        job: Job | None = app.state.runner.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    return app
