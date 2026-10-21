"""FastAPI application: jobs endpoints now, tools and web pages in later increments."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from cairn.jobs import Job, JobRunner
from cairn.tools import REGISTRY, call_tool


class JobRequest(BaseModel):
    kind: str
    params: dict[str, Any] = Field(default_factory=dict)


def create_app() -> FastAPI:
    mcp = FastMCP("Cairn")
    for tool in REGISTRY.values():
        mcp.tool(tool)
    mcp_app = mcp.http_app(path="/mcp")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        app.state.runner = JobRunner()
        async with mcp_app.lifespan(app):
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

    @app.post("/api/tools/run_job")
    async def api_run_job(request: JobRequest) -> dict[str, Any]:
        return call_tool("run_job", request.model_dump())

    @app.post("/api/tools/study_design")
    async def api_study_design() -> dict[str, Any]:
        return call_tool("study_design", {})

    app.mount("/", mcp_app)
    return app
