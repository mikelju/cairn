"""The Observation contract and read-only DuckDB access (C2)."""

import duckdb
import pytest

from cairn.canonical import canonical_sha256
from cairn.fetch import file_sha256
from cairn.ingest import DEFAULT_DB
from cairn.observation import Observation, connect, query
from cairn.tools import call_tool


def test_observation_study_design_has_valid_fields() -> None:
    result = call_tool("study_design", {})
    observation = Observation.model_validate(result)
    assert observation.kind == "study_design"
    assert observation.population == "all animals"
    assert observation.n_examined == 124
    assert observation.tool.name == "study_design"
    assert observation.sql.startswith("SELECT tx.SETCD")
    assert len(observation.source_rows) == len(observation.values["groups"])
    assert observation.values["study_id"] == "PDS2014"
    assert len(observation.snapshot_sha256) == 64


def test_observation_study_design_same_hash_on_two_runs() -> None:
    first, second = call_tool("study_design", {}), call_tool("study_design", {})
    assert first["content_sha256"] == second["content_sha256"]
    body = {
        key: first[key]
        for key in (
            "kind",
            "population",
            "n_examined",
            "values",
            "sql",
            "source_rows",
            "tool",
            "snapshot_sha256",
        )
    }
    assert canonical_sha256(body) == first["content_sha256"]


def test_tools_duckdb_read_only() -> None:
    before = file_sha256(DEFAULT_DB)
    connection = connect()
    try:
        with pytest.raises(duckdb.Error):
            connection.execute("CREATE TABLE intruder (x INTEGER)")
        with pytest.raises(duckdb.Error):
            connection.execute("DELETE FROM dm")
    finally:
        connection.close()
    assert query("SELECT count(*) AS n FROM dm") == [{"n": 124}]
    assert file_sha256(DEFAULT_DB) == before
