"""The tool registry: one list of typed functions served over MCP, REST and the CLI."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError, validate_call

from cairn.body_weight import body_weight_change
from cairn.canonical import canonical_sha256
from cairn.incidence import incidence
from cairn.jobs import execute, inputs_hash
from cairn.observation import Observation, build_observation, query
from cairn.tk_summary import tk_summary


def run_job(kind: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a job to completion and return its kind, inputs hash and outputs."""
    arguments = params or {}
    return {
        "kind": kind,
        "inputs_sha256": inputs_hash(kind, arguments),
        "status": "done",
        "outputs": execute(kind, arguments),
    }


STUDY_DESIGN_SQL = """SELECT tx.SETCD AS setcd, any_value(tx."SET") AS label,
  max(CASE WHEN TXPARMCD = 'SEXPOP' THEN TXVAL END) AS sex,
  CAST(max(CASE WHEN TXPARMCD = 'TRTDOS' THEN TXVAL END) AS DOUBLE) AS dose,
  max(CASE WHEN TXPARMCD = 'TRTDOSU' THEN TXVAL END) AS dose_unit,
  max(CASE WHEN TXPARMCD = 'TKDESC' THEN TXVAL END) = 'TK' AS toxicokinetic,
  (SELECT count(*) FROM dm WHERE dm.SETCD = tx.SETCD) AS animals
FROM tx GROUP BY tx.SETCD ORDER BY tx.SETCD"""
STUDY_TERMS_SQL = """SELECT TSPARMCD AS code, TSVAL AS value FROM ts
WHERE TSPARMCD IN ('SPREFID', 'SPECIES', 'STRAIN', 'ROUTE') ORDER BY TSPARMCD"""


def study_design() -> Observation:
    """Return the design of the study: species, route and one entry per treatment set."""
    groups = query(STUDY_DESIGN_SQL)
    terms = {row["code"]: row["value"] for row in query(STUDY_TERMS_SQL)}
    return build_observation(
        tool="study_design",
        kind="study_design",
        population="all animals",
        n_examined=sum(int(group["animals"]) for group in groups),
        values={
            "study_id": terms["SPREFID"],
            "species": terms["SPECIES"],
            "strain": terms["STRAIN"],
            "route": terms["ROUTE"],
            "groups": groups,
        },
        sql=STUDY_DESIGN_SQL + "\n;\n" + STUDY_TERMS_SQL,
        source_rows=[{"domain": "TX", "setcd": group["setcd"]} for group in groups],
    )


REGISTRY: dict[str, Callable[..., Any]] = {
    "run_job": run_job,
    "study_design": study_design,
    "incidence": incidence,
    "body_weight_change": body_weight_change,
    "tk_summary": tk_summary,
}


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a registered tool and return a plain JSON-ready dict.

    Arguments are validated against the tool's own type annotations, the same schema MCP
    publishes, so REST and the CLI reject what MCP rejects (pydantic ValidationError).
    """
    result = validate_call(REGISTRY[name])(**arguments)
    return result.model_dump(mode="json") if isinstance(result, BaseModel) else dict(result)


def result_sha256(result: dict[str, Any]) -> str:
    return canonical_sha256(result)


def argument_problems(error: ValidationError) -> str:
    """Plain-language list of what is wrong with the arguments of a tool call."""
    return "; ".join(
        f"{'.'.join(str(step) for step in problem['loc']) or 'arguments'}: {problem['msg']}"
        for problem in error.errors(include_url=False, include_context=False, include_input=False)
    )
