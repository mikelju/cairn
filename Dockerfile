# syntax=docker/dockerfile:1
# Lightsail runs linux/amd64: docker build --platform linux/amd64 -t cairn .
FROM python:3.12-slim AS weights
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy CAIRN_MODELS=/models
WORKDIR /w
# Own cached layer (decision O1): the pinned weights are downloaded and SHA-256 checked here, so only
# a change to pyproject.toml, uv.lock, the pin file or these modules downloads them again.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/cairn/__init__.py src/cairn/weights.py src/cairn/passages.py src/cairn/guidelines.py src/cairn/fetch.py src/cairn/canonical.py ./src/cairn/
COPY data/guidance/weights.json ./data/guidance/weights.json
RUN PYTHONPATH=/w/src .venv/bin/python -c "from cairn import weights; [print(*f) for f in weights.download_weights(weights.models_dir())]"

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY data/manifest.json ./data/manifest.json
COPY data/pds2014 ./data/pds2014
COPY recordings ./recordings
COPY workflows ./workflows
COPY data/judge ./data/judge
COPY data/guidelines ./data/guidelines
COPY data/guidance ./data/guidance
# The cryptography<=46.0.3 constraint in pyproject.toml is already pinned in uv.lock; linux x86_64 wheels exist.
RUN uv sync --frozen --no-dev
# The DuckDB file is built here, from the vendored XPT snapshot: no network at runtime.
RUN .venv/bin/python -m cairn.ingest
# Guidance check: a fresh retrieval of every cached query must match the committed cache (at most one
# near-tied passage differs, scores within the cross-platform tolerances); the build fails otherwise. Only the build loads the reranker.
COPY --from=weights /models /models
RUN CAIRN_MODELS=/models .venv/bin/cairn guidance check

FROM python:3.12-slim
WORKDIR /app
RUN useradd --system --no-create-home cairn
COPY --from=build /app /app
# Not read at request time (replay uses the precomputed cache); kept for the live box of phase 06.
COPY --from=weights /models /models
ARG COMMIT=unknown
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 CAIRN_MODELS=/models CAIRN_COMMIT=$COMMIT
USER cairn
EXPOSE 8000
CMD ["uvicorn", "cairn.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
