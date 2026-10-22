# syntax=docker/dockerfile:1
# Lightsail runs linux/amd64: docker build --platform linux/amd64 -t cairn .
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY data/manifest.json ./data/manifest.json
COPY data/pds2014 ./data/pds2014
COPY recordings ./recordings
# The cryptography<=46.0.3 constraint in pyproject.toml is already pinned in uv.lock; linux x86_64 wheels exist.
RUN uv sync --frozen --no-dev
# The DuckDB file is built here, from the vendored XPT snapshot: no network at runtime.
RUN .venv/bin/python -m cairn.ingest

FROM python:3.12-slim
WORKDIR /app
RUN useradd --system --no-create-home cairn
COPY --from=build /app /app
ARG COMMIT=unknown
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 CAIRN_COMMIT=$COMMIT
USER cairn
EXPOSE 8000
CMD ["uvicorn", "cairn.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
