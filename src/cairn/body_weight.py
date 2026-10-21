"""The body_weight_change tool: day-29 weight against control and change from baseline."""

from typing import Any, Literal

from pydantic import validate_call

from cairn.observation import ANIMALS_SQL, Observation, build_observation, query

WORDING = "lower than control"
Population = Literal["main_and_recovery", "main"]
POPULATION_LABELS: dict[str, str] = {
    "main_and_recovery": "main study and recovery animals (TK satellites excluded)",
    "main": "main study (TK satellites and recovery animals excluded)",
}

BODY_WEIGHT_SQL = f"""WITH {ANIMALS_SQL}
SELECT a.usubjid, a.dose, baseline.BWSTRESN AS baseline_g, day29.BWSTRESN AS day29_g,
       day29.BWSTRESN - baseline.BWSTRESN AS change_g
FROM animal a
JOIN bw day29 ON day29.USUBJID = a.usubjid AND day29.BWTESTCD = 'BW' AND day29.BWDY = 29
JOIN bw baseline ON baseline.USUBJID = a.usubjid AND baseline.BWTESTCD = 'BW'
  AND baseline.BWBLFL = 'Y'
WHERE a.sex = ? AND NOT a.is_tk AND (NOT a.is_recovery OR ?)
ORDER BY a.dose, a.usubjid"""


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


@validate_call
def body_weight_change(
    sex: Literal["F", "M"] = "F", population: Population = "main_and_recovery"
) -> Observation:
    """Body weight on day 29 as percent lower than control, and change from baseline."""
    rows = query(BODY_WEIGHT_SQL, [sex, population == "main_and_recovery"])
    doses = sorted({float(row["dose"]) for row in rows})
    means = {dose: _mean([row["day29_g"] for row in rows if row["dose"] == dose]) for dose in doses}
    control = means[0.0]
    groups: list[dict[str, Any]] = []
    for dose in doses:
        members = [row for row in rows if row["dose"] == dose]
        groups.append(
            {
                "dose": dose,
                "n": len(members),
                "mean_day29_g": round(means[dose], 2),
                "percent_lower_than_control": (
                    None if dose == 0 else round(100 * (control - means[dose]) / control, 2)
                ),
                "mean_change_from_baseline_g": round(
                    _mean([row["change_g"] for row in members]), 2
                ),
            }
        )
    negative = [
        {
            "usubjid": row["usubjid"],
            "dose": float(row["dose"]),
            "change_g": round(row["change_g"], 1),
        }
        for row in rows
        if row["change_g"] < 0
    ]
    return build_observation(
        tool="body_weight_change",
        kind="body_weight_change",
        population=POPULATION_LABELS[population],
        n_examined=len(rows),
        values={
            "sex": sex,
            "day": 29,
            "wording": WORDING,
            "groups": groups,
            "animals_with_negative_change": negative,
        },
        sql=BODY_WEIGHT_SQL,
        source_rows=[
            {"domain": "BW", "usubjid": row["usubjid"], "dose": float(row["dose"])} for row in rows
        ],
    )
