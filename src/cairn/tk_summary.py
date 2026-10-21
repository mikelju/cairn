"""The tk_summary tool: naive AUCtau mean in the TK satellite set, with and without quarantine."""

from typing import Annotated, Any, Literal

from pydantic import Field, validate_call

from cairn.observation import ANIMALS_SQL, Observation, build_observation, query

TK_SUMMARY_SQL = f"""WITH {ANIMALS_SQL},
tk_animal AS (SELECT * FROM animal WHERE is_tk AND sex = ? AND dose = ?),
values_in_set AS (
  SELECT pp.USUBJID AS usubjid, pp.PPSTRESN AS value, false AS quarantined, NULL AS source_row
  FROM pp JOIN tk_animal t ON t.usubjid = pp.USUBJID
  WHERE pp.PPTESTCD = 'AUCTAU' AND pp.VISITDY = ? AND pp.PPSTRESN IS NOT NULL
  UNION ALL
  SELECT q.usubjid, q.value, true AS quarantined, q.source_row
  FROM quarantine q JOIN tk_animal t ON t.usubjid = q.usubjid
  WHERE q.domain = 'PP' AND q.test = 'AUCTAU' AND q.visit_day = ?
)
SELECT usubjid, value, quarantined, source_row FROM values_in_set ORDER BY usubjid"""


def _summary(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "mean": round(sum(values) / len(values), 2) if values else None,
    }


@validate_call
def tk_summary(
    sex: Literal["F", "M"] = "M",
    dose: Annotated[float, Field(allow_inf_nan=False)] = 20.0,
    day: Annotated[float, Field(allow_inf_nan=False)] = 1.0,
) -> Observation:
    """Naive AUCtau mean in the TK satellite set, with and without the quarantined value."""
    rows = query(TK_SUMMARY_SQL, [sex, dose, day, day])
    kept = [float(row["value"]) for row in rows if not row["quarantined"]]
    every = [float(row["value"]) for row in rows]
    quarantined = [
        {"usubjid": row["usubjid"], "value": float(row["value"]), "source_row": row["source_row"]}
        for row in rows
        if row["quarantined"]
    ]
    with_quarantined, without_quarantined = _summary(every), _summary(kept)
    ratio = None
    if without_quarantined["mean"] is not None and with_quarantined["mean"]:
        ratio = round(without_quarantined["mean"] / with_quarantined["mean"], 1)
    return build_observation(
        tool="tk_summary",
        kind="tk_auctau_naive_mean",
        population="TK satellite animals",
        n_examined=len(every),
        values={
            "sex": sex,
            "dose": dose,
            "day": day,
            "test": "AUCTAU",
            "with_quarantined": with_quarantined,
            "without_quarantined": without_quarantined,
            "ratio_without_over_with": ratio,
            "contains_quarantined": bool(quarantined),
            "quarantined_rows": quarantined,
        },
        sql=TK_SUMMARY_SQL,
        source_rows=[
            {"domain": "PP", "usubjid": row["usubjid"], "quarantined": bool(row["quarantined"])}
            for row in rows
        ],
    )
