from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pytest

from cairn import ingest
from cairn.fetch import DOMAINS, VENDORED_DIR, load_manifest, snapshot_hash
from cairn.send import normalise_zeros
from cairn.validate import RULE_AUC, validate_study


@pytest.fixture(scope="module")
def study() -> tuple[dict[str, pd.DataFrame], dict[str, int], str]:
    return ingest.load_study()


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return ingest.ingest(db_path=tmp_path_factory.mktemp("db") / "cairn.duckdb")


def test_loads_exactly_eight_domains_and_snapshot_is_stable(
    study: tuple[dict[str, pd.DataFrame], dict[str, int], str],
) -> None:
    frames, _, snapshot = study
    assert sorted(frames) == sorted(DOMAINS)
    assert len(frames) == 8
    assert snapshot == snapshot_hash(load_manifest())
    assert ingest.load_study(VENDORED_DIR)[2] == snapshot


def test_zero_normalisation() -> None:
    frame = pd.DataFrame({"a": [1e-80, -1e-80, 0.5, 0.0]})
    assert normalise_zeros(frame) == {"a": 2}
    assert frame["a"].tolist() == [0.0, 0.0, 0.5, 0.0]
    assert normalise_zeros(frame) == {}


def test_expected_data_facts(report: dict[str, Any]) -> None:
    assert report["auc"]["AUCIFO"] == {"negative": 10, "quantified": 16}
    assert report["auc"]["AUCTAU"] == {"negative": 2, "quantified": 36}
    assert report["quarantine"]["total"] == 12
    assert report["quarantine"]["by_rule"] == {RULE_AUC: 12}
    assert report["concentrations"] == {"quantified": 226, "negative": 0}
    assert report["age"]["animals_checked"] == 124
    assert report["age"]["animals_mismatching"] == 124
    assert report["age"]["dm_age_values"] == [0.0]
    assert report["terminology"] == {"value": "SEND Terminology 2013-012-20", "well_formed": False}
    assert len(report["deaths"]) == 1
    death = report["deaths"][0]
    assert (death["usubjid"], death["day"]) == ("PDS2014-0119", 3.0)
    assert "Vehicle" in death["group"]
    assert death["group"].endswith("TK")
    assert report["xpt_zeros_normalised"] == {"DM.AGE": 124, "PC.PCTPTNUM": 18}
    assert set(report["structure_failures"].values()) == {0}
    assert report["integrity"]["duplicate_usubjid"] == 0


def test_naive_mean_with_and_without_the_bad_value(report: dict[str, Any]) -> None:
    naive = report["naive_mean_auctau"]
    assert naive["with_quarantined"]["n"] == 3
    assert round(naive["with_quarantined"]["mean"]) == 2821
    assert naive["without_quarantined"]["n"] == 2
    assert round(naive["without_quarantined"]["mean"]) == 15956


def test_quarantine_is_absent_from_domains_present_in_quarantine_and_unchanged(
    study: tuple[dict[str, pd.DataFrame], dict[str, int], str], tmp_path: Path
) -> None:
    frames, zeros, _ = study
    validation = validate_study(frames, zeros)
    db = tmp_path / "cairn.duckdb"
    ingest.write_database(validation, db, "snap")
    pp = ingest.read_table(db, "pp")
    quarantine = ingest.read_table(db, "quarantine")
    assert len(pp) == len(frames["PP"]) - 12
    assert len(quarantine) == 12
    assert set(quarantine["rule"]) == {RULE_AUC}
    original = frames["PP"]
    for _, row in quarantine.iterrows():
        assert original.loc[row["source_row"], "PPSTRESN"] == row["value"]
        assert row["value"] < 0
        assert not ((pp["USUBJID"] == row["usubjid"]) & (pp["PPSTRESN"] == row["value"])).any()


def test_database_opens_read_only(report: dict[str, Any], tmp_path: Path) -> None:
    db = tmp_path / "ro.duckdb"
    frames, zeros, _ = ingest.load_study()
    ingest.write_database(validate_study(frames, zeros), db, "snap")
    connection = duckdb.connect(str(db), read_only=True)
    with pytest.raises(duckdb.Error):
        connection.execute("CREATE TABLE x (a INTEGER)")
    connection.close()


def test_main_writes_the_database(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "out.duckdb"
    assert ingest.main([str(db)]) == 0
    assert db.exists()
    assert "pp_auc_positive" in capsys.readouterr().out


def test_ingestion_is_deterministic(report: dict[str, Any], tmp_path: Path) -> None:
    again = ingest.ingest(db_path=tmp_path / "again.duckdb")
    assert again["report_sha256"] == report["report_sha256"]
