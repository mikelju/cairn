"""The incidence tool: histopathology counts by tissue and finding, with the screen."""

from typing import Any

from cairn.observation import ANIMALS_SQL, NOT_EXAMINED, Observation, build_observation, query

MIN_EXAMINED = 5
MIN_EXCESS = 3
SCREEN_RULE = (
    "Screen: a finding enters, by sex, if in any dose group above zero with "
    f"{MIN_EXAMINED} or more examined animals at least {MIN_EXCESS} more are affected than in "
    "control; it never enters when control has no examined animal. "
    "It is a screen, not a statistical test nor a treatment-relatedness decision."
)

INCIDENCE_SQL = f"""WITH {ANIMALS_SQL},
main_animal AS (SELECT * FROM animal WHERE NOT is_tk AND NOT is_recovery),
examined AS (
  SELECT DISTINCT a.usubjid, a.sex, a.dose, mi.MISPEC AS tissue
  FROM main_animal a JOIN mi ON mi.USUBJID = a.usubjid
  WHERE COALESCE(mi.MISTAT, '') <> 'NOT DONE'
),
affected AS (
  SELECT DISTINCT a.usubjid, a.sex, a.dose, mi.MISPEC AS tissue, mi.MISTRESC AS finding
  FROM main_animal a JOIN mi ON mi.USUBJID = a.usubjid
  WHERE COALESCE(mi.MISTAT, '') <> 'NOT DONE' AND mi.MISTRESC <> 'NORMAL'
),
findings AS (SELECT DISTINCT sex, tissue, finding FROM affected),
doses AS (SELECT DISTINCT sex, dose FROM main_animal)
SELECT f.sex, f.tissue, f.finding, d.dose,
  (SELECT count(*) FROM examined e
    WHERE e.sex = f.sex AND e.tissue = f.tissue AND e.dose = d.dose) AS examined,
  (SELECT count(*) FROM affected x
    WHERE x.sex = f.sex AND x.tissue = f.tissue AND x.finding = f.finding
      AND x.dose = d.dose) AS affected
FROM findings f JOIN doses d ON d.sex = f.sex
ORDER BY f.sex, f.tissue, f.finding, d.dose"""

AFFECTED_ANIMALS_SQL = f"""WITH {ANIMALS_SQL}
SELECT DISTINCT a.usubjid, a.sex, a.dose, mi.MISPEC AS tissue, mi.MISTRESC AS finding
FROM animal a JOIN mi ON mi.USUBJID = a.usubjid
WHERE NOT a.is_tk AND NOT a.is_recovery
  AND COALESCE(mi.MISTAT, '') <> 'NOT DONE' AND mi.MISTRESC <> 'NORMAL'
ORDER BY a.sex, mi.MISPEC, mi.MISTRESC, a.dose, a.usubjid"""


EXAMINED_ANIMALS_SQL = f"""WITH {ANIMALS_SQL}
SELECT count(DISTINCT a.usubjid) AS n
FROM animal a JOIN mi ON mi.USUBJID = a.usubjid
WHERE NOT a.is_tk AND NOT a.is_recovery AND COALESCE(mi.MISTAT, '') <> 'NOT DONE'"""


def _passes(groups: list[dict[str, Any]]) -> bool:
    control = next(group for group in groups if group["dose"] == 0)
    if not control["examined"]:
        return False
    return any(
        group["dose"] > 0
        and (group["examined"] or 0) >= MIN_EXAMINED
        and group["affected"] - control["affected"] >= MIN_EXCESS
        for group in groups
    )


def incidence(screen: bool = True) -> Observation:
    """Incidence of microscopic findings in the main study; with screen=True only the screen."""
    rows = query(INCIDENCE_SQL)
    table: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        examined = int(row["examined"])
        group = {
            "dose": float(row["dose"]),
            "examined": examined if examined else None,
            "affected": int(row["affected"]) if examined else None,
            "status": "examined" if examined else NOT_EXAMINED,
        }
        table.setdefault((row["sex"], row["tissue"], row["finding"]), []).append(group)
    findings = [
        {"sex": sex, "tissue": tissue, "finding": finding, "groups": groups}
        for (sex, tissue, finding), groups in table.items()
        if not screen or _passes(groups)
    ]
    affected_animals = query(AFFECTED_ANIMALS_SQL)
    kept = {(f["sex"], f["tissue"], f["finding"]) for f in findings}
    source_rows = [
        {"domain": "MI", **animal}
        for animal in affected_animals
        if (animal["sex"], animal["tissue"], animal["finding"]) in kept
    ]
    values: dict[str, Any] = {
        "screen": screen,
        "screen_rule": SCREEN_RULE if screen else None,
        "findings": findings,
    }
    return build_observation(
        tool="incidence",
        kind="incidence_screen" if screen else "incidence_full",
        population="main study (TK satellites and recovery animals excluded)",
        n_examined=int(query(EXAMINED_ANIMALS_SQL)[0]["n"]),
        values=values,
        sql="\n;\n".join([INCIDENCE_SQL, AFFECTED_ANIMALS_SQL, EXAMINED_ANIMALS_SQL]),
        source_rows=source_rows,
    )
