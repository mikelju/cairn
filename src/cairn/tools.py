"""The tool registry: one list of typed functions served over MCP, REST and the CLI."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from cairn.canonical import canonical_sha256
from cairn.ingest import load_study
from cairn.jobs import execute, inputs_hash


class Group(BaseModel):
    setcd: str
    label: str
    sex: str
    dose: float
    dose_unit: str
    toxicokinetic: bool
    animals: int


class StudyDesign(BaseModel):
    study_id: str
    species: str
    strain: str
    route: str
    groups: list[Group]


def run_job(kind: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a job to completion and return its kind, inputs hash and outputs."""
    arguments = params or {}
    return {
        "kind": kind,
        "inputs_sha256": inputs_hash(kind, arguments),
        "status": "done",
        "outputs": execute(kind, arguments),
    }


def study_design() -> StudyDesign:
    """Return the design of the study: species, route and one entry per treatment set."""
    frames, _, _ = load_study()
    tx, dm, ts = frames["TX"], frames["DM"], frames["TS"]
    wide = tx.pivot(index="SETCD", columns="TXPARMCD", values="TXVAL")
    labels: dict[str, str] = dict(zip(tx["SETCD"].astype(str), tx["SET"].astype(str), strict=False))

    def value(code: str) -> str:
        return str(ts.loc[ts["TSPARMCD"] == code, "TSVAL"].iloc[0])

    groups = [
        Group(
            setcd=str(setcd),
            label=labels[str(setcd)],
            sex=str(row["SEXPOP"]),
            dose=float(row["TRTDOS"]),
            dose_unit=str(row["TRTDOSU"]),
            toxicokinetic=str(row["TKDESC"]) == "TK",
            animals=int((dm["SETCD"] == setcd).sum()),
        )
        for setcd, row in wide.iterrows()
    ]
    return StudyDesign(
        study_id=value("SPREFID"),
        species=value("SPECIES"),
        strain=value("STRAIN"),
        route=value("ROUTE"),
        groups=groups,
    )


REGISTRY: dict[str, Callable[..., Any]] = {"run_job": run_job, "study_design": study_design}


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a registered tool and return a plain JSON-ready dict."""
    result = REGISTRY[name](**arguments)
    return result.model_dump(mode="json") if isinstance(result, BaseModel) else dict(result)


def result_sha256(result: dict[str, Any]) -> str:
    return canonical_sha256(result)
