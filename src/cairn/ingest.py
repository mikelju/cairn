"""Ingest the pinned SEND snapshot, validate it and write the read-only DuckDB file."""

import json
import sys
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from cairn.canonical import canonical_sha256
from cairn.fetch import REPO_ROOT, VENDORED_DIR, load_manifest, verify_dir
from cairn.send import read_study
from cairn.validate import Validation, mean_auctau, validate_study

DEFAULT_DB = REPO_ROOT / "data" / "build" / "cairn.duckdb"
NAIVE_MEAN: tuple[str, float, float] = ("M", 20.0, 1.0)


def build_report(
    frames: dict[str, pd.DataFrame], validation: Validation, snapshot: str
) -> dict[str, Any]:
    """Join the validation report with the snapshot hash and the naive means, all by code."""
    report = dict(validation.report)
    report["snapshot_sha256"] = snapshot
    report["naive_mean_auctau"] = {
        "group": {"sex": NAIVE_MEAN[0], "dose": NAIVE_MEAN[1], "day": NAIVE_MEAN[2]},
        "with_quarantined": mean_auctau(frames, *NAIVE_MEAN),
        "without_quarantined": mean_auctau(validation.clean, *NAIVE_MEAN),
    }
    report["quarantine"] = {
        **report["quarantine"],
        "rows": validation.quarantine.drop(columns=["row_json"]).to_dict(orient="records"),
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def write_database(validation: Validation, path: Path, snapshot: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    connection = duckdb.connect(str(path))
    try:
        for domain, frame in validation.clean.items():
            connection.register("source", frame)
            connection.execute(f'CREATE TABLE "{domain.lower()}" AS SELECT * FROM source')
            connection.unregister("source")
        connection.register("source", validation.quarantine)
        connection.execute("CREATE TABLE quarantine AS SELECT * FROM source")
        connection.unregister("source")
        connection.execute("CREATE TABLE build (snapshot_sha256 VARCHAR)")
        connection.execute("INSERT INTO build VALUES (?)", [snapshot])
    finally:
        connection.close()


def read_table(path: Path, name: str) -> pd.DataFrame:
    """Read one table from the DuckDB file, always read-only."""
    connection = duckdb.connect(str(path), read_only=True)
    try:
        return connection.execute(f'SELECT * FROM "{name}"').df()
    finally:
        connection.close()


def load_study(
    directory: Path = VENDORED_DIR,
) -> tuple[dict[str, pd.DataFrame], dict[str, int], str]:
    """Verify the files against the manifest and read them; return frames, zeros, snapshot."""
    snapshot = verify_dir(load_manifest(), directory)
    frames, zeros = read_study(directory)
    return frames, zeros, snapshot


def ingest(directory: Path = VENDORED_DIR, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    frames, zeros, snapshot = load_study(directory)
    validation = validate_study(frames, zeros)
    write_database(validation, db_path, snapshot)
    return build_report(frames, validation, snapshot)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    db_path = Path(args[0]) if args else DEFAULT_DB
    report = ingest(db_path=db_path)
    print(f"Wrote {db_path}")
    print(json.dumps(report["quarantine"]["by_rule"], sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
