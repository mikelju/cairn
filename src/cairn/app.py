"""FastAPI application: jobs, REST tool endpoints, the MCP endpoint and the web pages."""

import os
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException
from fastmcp import FastMCP
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, Field, ValidationError

from cairn import audit
from cairn.jobs import Job, JobRunner
from cairn.observation import check_build
from cairn.retrieval import StaleRetrievalCache
from cairn.tools import REGISTRY, argument_problems, call_tool
from cairn.web import mount_web


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
        check_build()  # SEC-002: refuse to start on a stale or unstamped DuckDB build
        app.state.runner = JobRunner()
        threads_db = os.environ.get("CAIRN_THREADS_DB", ":memory:")
        async with AsyncSqliteSaver.from_conn_string(threads_db) as saver, mcp_app.lifespan(app):
            app.state.saver = saver
            await audit.init(saver.conn)
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

    @app.post("/api/tools/{name}")
    def api_tool(
        name: str, arguments: Annotated[dict[str, Any] | None, Body()] = None
    ) -> dict[str, Any]:
        if name not in REGISTRY:
            raise HTTPException(status_code=404, detail="unknown tool")
        try:
            return call_tool(name, arguments or {})
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=argument_problems(error)) from error
        except StaleRetrievalCache as error:
            detail = f"query not in the replay cache: {error}"
            raise HTTPException(status_code=422, detail=detail) from error

    mount_web(app)
    app.mount("/", mcp_app)
    return app
