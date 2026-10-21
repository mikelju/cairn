"""Validate the SEND domains: pandera structure, cross rules and quarantine.

Rows that fail a row rule are flagged and moved to the quarantine table, never corrected.
Everything here works on in-memory frames so it can be re-run on a modified copy.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
import pandera.errors

from cairn.send import SCHEMAS

RULE_AUC = "pp_auc_positive"
RULE_CONC = "pc_concentration_positive"
TERMINOLOGY_PATTERN = re.compile(r"^SEND Terminology \d{4}-\d{2}-\d{2}$")
QUARANTINE_COLUMNS = [
    "rule",
    "domain",
    "source_row",
    "usubjid",
    "test",
    "value",
    "unit",
    "visit_day",
    "row_json",
]


@dataclass
class Validation:
    clean: dict[str, pd.DataFrame]
    quarantine: pd.DataFrame
    report: dict[str, Any]


def _number(value: Any) -> float | None:
    return None if pd.isna(value) else float(value)


def _row_json(row: pd.Series) -> str:
    values = {str(k): (_number(v) if isinstance(v, float) else v) for k, v in row.items()}
    return json.dumps(values, sort_keys=True, allow_nan=False)


def _flag(
    frame: pd.DataFrame, domain: str, mask: pd.Series, rule: str, test: str, value: str, unit: str
) -> list[dict[str, Any]]:
    rows = []
    for index, row in frame[mask].iterrows():
        rows.append(
            {
                "rule": rule,
                "domain": domain,
                "source_row": int(str(index)),
                "usubjid": str(row["USUBJID"]),
                "test": str(row[test]),
                "value": _number(row[value]),
                "unit": str(row[unit]),
                "visit_day": _number(row["VISITDY"]),
                "row_json": _row_json(row),
            }
        )
    return rows


def _structure(frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    failures: dict[str, int] = {}
    for domain, schema in SCHEMAS.items():
        try:
            schema.validate(frames[domain], lazy=True)
            failures[domain] = 0
        except pandera.errors.SchemaErrors as error:
            failures[domain] = len(error.failure_cases)
    return failures


def _ts_value(ts: pd.DataFrame, code: str) -> str | None:
    values = ts.loc[ts["TSPARMCD"] == code, "TSVAL"]
    return str(values.iloc[0]) if len(values) else None


def _age_check(dm: pd.DataFrame, ts: pd.DataFrame) -> dict[str, Any]:
    text = _ts_value(ts, "AGETXT") or ""
    match = re.match(r"^(\d+)-(\d+)", text)
    low, high = (int(match.group(1)), int(match.group(2))) if match else (None, None)
    ages = dm["AGE"]
    if low is None or high is None:
        bad = pd.Series(True, index=dm.index)
    else:
        bad = ~ages.between(low, high)
    return {
        "ts_age_text": text,
        "animals_checked": len(dm),
        "animals_mismatching": int(bad.sum()),
        "dm_age_values": sorted({float(a) for a in ages.dropna()}),
    }


def _deaths(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    ds, dm, tx = frames["DS"], frames["DM"], frames["TX"]
    deaths = []
    for _, row in ds[ds["DSDECOD"].str.contains("DEAD", na=False)].iterrows():
        setcd = dm.loc[dm["USUBJID"] == row["USUBJID"], "SETCD"].iloc[0]
        group = tx.loc[tx["SETCD"] == setcd, "SET"].iloc[0]
        deaths.append(
            {
                "usubjid": str(row["USUBJID"]),
                "day": _number(row["DSSTDY"]),
                "disposition": str(row["DSDECOD"]),
                "setcd": str(setcd),
                "group": str(group),
            }
        )
    return deaths


def _integrity(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    dm, tx = frames["DM"], frames["TX"]
    subjects = set(dm["USUBJID"])
    orphans = {
        domain: int((~frames[domain]["USUBJID"].isin(subjects)).sum())
        for domain in ("DS", "MI", "BW", "PP", "PC")
    }
    planned = tx[tx["TXPARMCD"].isin(["PLANMSUB", "PLANFSUB"])]
    populations = {
        str(setcd): int((dm["SETCD"] == setcd).sum()) for setcd in sorted(tx["SETCD"].unique())
    }
    return {
        "duplicate_usubjid": int(dm["USUBJID"].duplicated().sum()),
        "dm_setcd_missing_in_tx": int((~dm["SETCD"].isin(tx["SETCD"])).sum()),
        "orphan_usubjid": orphans,
        "animals_by_set": populations,
        "planned_sets": int(planned["SETCD"].nunique()),
    }


def _auc_counts(pp: pd.DataFrame) -> dict[str, dict[str, int]]:
    auc = pp[pp["PPTESTCD"].str.startswith("AUC") & pp["PPSTRESN"].notna()]
    return {
        str(test): {"negative": int((group["PPSTRESN"] < 0).sum()), "quantified": len(group)}
        for test, group in auc.groupby("PPTESTCD")
    }


def validate_study(frames: dict[str, pd.DataFrame], zeros: dict[str, int]) -> Validation:
    """Run every rule on the frames; return clean tables, quarantine and the report."""
    pp, pc = frames["PP"], frames["PC"]
    auc_mask = pp["PPTESTCD"].str.startswith("AUC") & (pp["PPSTRESN"] < 0)
    conc_mask = pc["PCSTRESN"] <= 0
    rows = _flag(pp, "PP", auc_mask, RULE_AUC, "PPTESTCD", "PPSTRESN", "PPSTRESU")
    rows += _flag(pc, "PC", conc_mask, RULE_CONC, "PCTESTCD", "PCSTRESN", "PCSTRESU")
    quarantine = pd.DataFrame(rows, columns=QUARANTINE_COLUMNS)
    clean = {**frames, "PP": pp[~auc_mask].copy(), "PC": pc[~conc_mask].copy()}
    quantified = pc["PCSTRESN"].notna()
    version = _ts_value(frames["TS"], "SNDCTVER")
    report: dict[str, Any] = {
        "rows": {domain: len(frame) for domain, frame in frames.items()},
        "xpt_zeros_normalised": dict(sorted(zeros.items())),
        "structure_failures": _structure(frames),
        "auc": _auc_counts(pp),
        "concentrations": {
            "quantified": int(quantified.sum()),
            "negative": int((pc["PCSTRESN"] < 0).sum()),
        },
        "age": _age_check(frames["DM"], frames["TS"]),
        "terminology": {
            "value": version,
            "well_formed": bool(version and TERMINOLOGY_PATTERN.match(version)),
        },
        "deaths": _deaths(frames),
        "integrity": _integrity(frames),
        "quarantine": {
            "total": len(quarantine),
            "by_rule": {str(k): int(v) for k, v in quarantine["rule"].value_counts().items()},
        },
    }
    return Validation(clean=clean, quarantine=quarantine, report=report)


def mean_auctau(
    frames: dict[str, pd.DataFrame], sex: str, dose: float, day: float
) -> dict[str, Any]:
    """Naive mean AUCtau of a sex, dose group and study day, with the animals that count."""
    dm, tx, pp = frames["DM"], frames["TX"], frames["PP"]
    wide = tx.pivot(index="SETCD", columns="TXPARMCD", values="TXVAL")
    sets = wide[(wide["SEXPOP"] == sex) & (wide["TRTDOS"].astype(float) == dose)].index
    animals = dm.loc[dm["SETCD"].isin(sets), "USUBJID"]
    chosen = pp[
        (pp["PPTESTCD"] == "AUCTAU")
        & (pp["VISITDY"] == day)
        & pp["USUBJID"].isin(animals)
        & pp["PPSTRESN"].notna()
    ]
    return {
        "n": len(chosen),
        "mean": float(chosen["PPSTRESN"].mean()) if len(chosen) else None,
        "animals": sorted(str(a) for a in chosen["USUBJID"]),
    }
