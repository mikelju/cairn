"""The Observation contract and read-only access to the app's DuckDB file."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
from pydantic import BaseModel

from cairn.canonical import canonical_sha256
from cairn.fetch import load_manifest, snapshot_hash
from cairn.ingest import DEFAULT_DB

TOOL_VERSION = "1"
NOT_EXAMINED = "not examined"

# Shared SQL fragment: one row per animal with its sex, dose and population flags.
ANIMALS_SQL = """animal AS (
  SELECT dm.USUBJID AS usubjid, dm.SEX AS sex, dm.SETCD AS setcd,
         CAST(dose.TXVAL AS DOUBLE) AS dose,
         COALESCE(tk.TXVAL, '') = 'TK' AS is_tk,
         dm.ARM ILIKE '%with recovery%' AS is_recovery
  FROM dm
  JOIN tx dose ON dose.SETCD = dm.SETCD AND dose.TXPARMCD = 'TRTDOS'
  LEFT JOIN tx tk ON tk.SETCD = dm.SETCD AND tk.TXPARMCD = 'TKDESC'
)"""


class ToolInfo(BaseModel):
    name: str
    version: str


class Observation(BaseModel):
    obs_id: str
    kind: str
    population: str
    n_examined: int | None
    values: dict[str, Any]
    sql: str
    source_rows: list[dict[str, Any]]
    content_sha256: str
    tool: ToolInfo
    snapshot_sha256: str


@lru_cache(maxsize=1)
def current_snapshot() -> str:
    return snapshot_hash(load_manifest())


def connect(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open the app's DuckDB file read-only; every tool goes through here."""
    return duckdb.connect(str(path or DEFAULT_DB), read_only=True)


def query(sql: str, path: Path | None = None) -> list[dict[str, Any]]:
    """Run one fixed SQL statement and return its rows as dicts."""
    connection = connect(path)
    try:
        cursor = connection.execute(sql)
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    finally:
        connection.close()


def build_observation(
    *,
    tool: str,
    kind: str,
    population: str,
    n_examined: int | None,
    values: dict[str, Any],
    sql: str,
    source_rows: list[dict[str, Any]],
) -> Observation:
    """Assemble an Observation; the hash covers everything except the hash and the ID."""
    body: dict[str, Any] = {
        "kind": kind,
        "population": population,
        "n_examined": n_examined,
        "values": values,
        "sql": sql,
        "source_rows": source_rows,
        "tool": {"name": tool, "version": TOOL_VERSION},
        "snapshot_sha256": current_snapshot(),
    }
    digest = canonical_sha256(body)
    return Observation(obs_id=f"{tool}-{digest[:12]}", content_sha256=digest, **body)
