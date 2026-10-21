"""Read SEND XPT domains, normalise XPT zeros and check the columns Cairn reads."""

from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa

from cairn.fetch import DOMAINS

ZERO_THRESHOLD = 1e-70


def _text(domain: str, column: str) -> pa.Column:
    return pa.Column(str, nullable=False, required=True, title=f"{domain}.{column}")


def _number(domain: str, column: str, nullable: bool = True) -> pa.Column:
    return pa.Column(float, nullable=nullable, required=True, title=f"{domain}.{column}")


def _schema(domain: str, text: list[str], numbers: list[str]) -> pa.DataFrameSchema:
    columns: dict[str, pa.Column] = {
        "STUDYID": pa.Column(str, pa.Check.str_length(min_value=1)),
        "DOMAIN": pa.Column(str, pa.Check.eq(domain)),
    }
    columns.update({name: _text(domain, name) for name in text})
    columns.update({name: _number(domain, name) for name in numbers})
    return pa.DataFrameSchema(columns, strict=False, name=domain)


SUBJECT = ["USUBJID"]
SCHEMAS: dict[str, pa.DataFrameSchema] = {
    "DM": _schema("DM", ["USUBJID", "SEX", "SETCD", "ARMCD", "AGEU"], ["AGE"]),
    "TX": _schema("TX", ["SETCD", "TXPARMCD", "TXVAL"], ["TXSEQ"]),
    "TS": _schema("TS", ["TSPARMCD", "TSVAL"], ["TSSEQ"]),
    "DS": _schema("DS", [*SUBJECT, "DSDECOD"], ["DSSEQ", "DSSTDY"]),
    "MI": _schema("MI", [*SUBJECT, "MITESTCD", "MISPEC"], ["MISEQ"]),
    "BW": _schema("BW", [*SUBJECT, "BWTESTCD", "BWSTRESU"], ["BWSEQ", "BWSTRESN", "BWDY"]),
    "PP": _schema("PP", [*SUBJECT, "PPTESTCD", "PPSTRESU"], ["PPSEQ", "PPSTRESN", "VISITDY"]),
    "PC": _schema("PC", [*SUBJECT, "PCTESTCD", "PCSTRESU"], ["PCSEQ", "PCSTRESN", "VISITDY"]),
}


def normalise_zeros(frame: pd.DataFrame) -> dict[str, int]:
    """Set numeric values with absolute value below 1e-70 to 0 in place; return counts."""
    counts: dict[str, int] = {}
    for column in frame.select_dtypes(include="number").columns:
        values = frame[column].to_numpy(dtype=float)
        tiny = (np.abs(values) < ZERO_THRESHOLD) & (values != 0)
        if tiny.any():
            values = np.where(tiny, 0.0, values)
            frame[column] = values
            counts[str(column)] = int(tiny.sum())
    return counts


def read_xpt(path: Path) -> pd.DataFrame:
    frame = pd.read_sas(path, format="xport", encoding="utf-8")
    assert isinstance(frame, pd.DataFrame)
    return frame


def read_domain(directory: Path, domain: str) -> tuple[pd.DataFrame, dict[str, int]]:
    """Read one domain with zero normalisation; return the frame and the normalised counts."""
    frame = read_xpt(directory / f"{domain.lower()}.xpt")
    return frame, normalise_zeros(frame)


def read_study(directory: Path) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    frames: dict[str, pd.DataFrame] = {}
    zeros: dict[str, int] = {}
    for domain in DOMAINS:
        frames[domain], counts = read_domain(directory, domain)
        zeros.update({f"{domain}.{column}": count for column, count in counts.items()})
    return frames, zeros
