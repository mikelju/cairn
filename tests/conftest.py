"""Shared fixtures: the app's DuckDB file is built once when it is missing."""

import pytest

from cairn.ingest import DEFAULT_DB, ingest


@pytest.fixture(scope="session", autouse=True)
def app_database() -> None:
    if not DEFAULT_DB.exists():
        ingest()
