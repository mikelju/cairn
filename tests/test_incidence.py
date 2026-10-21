"""The incidence tool and its screen (C3, C4, C2). Expected values are the frozen literals."""

from typing import Any

import pytest

from cairn.incidence import MIN_EXAMINED, MIN_EXCESS, SCREEN_RULE, _passes
from cairn.observation import Observation, query
from cairn.tools import call_tool

NE = None  # not examined

# (sex, tissue, finding): (affected, examined) at 0, 20, 200 and 400 mg/kg/day
SCREEN: dict[tuple[str, str, str], list[tuple[int | None, int | None]]] = {
    ("F", "GLAND, ADRENAL", "Vacuolization"): [(0, 10), (2, 10), (7, 10), (10, 10)],
    ("M", "GLAND, ADRENAL", "Vacuolization"): [(1, 10), (1, 10), (1, 10), (9, 10)],
    ("F", "GLAND, MAMMARY", "Atrophy fat"): [(0, 10), (0, 10), (5, 10), (5, 10)],
    ("M", "KIDNEY", "Necrosis"): [(0, 10), (NE, NE), (0, 1), (3, 10)],
    ("F", "LIVER", "Vacuolization"): [(0, 10), (0, 10), (0, 10), (3, 10)],
    ("M", "LIVER", "Vacuolization"): [(0, 10), (0, 10), (0, 10), (3, 10)],
    ("F", "LIVER", "Hypertrophy hepatocellular"): [(0, 10), (0, 10), (0, 10), (3, 10)],
    ("M", "PANCREAS", "Inflammation"): [(0, 10), (NE, NE), (NE, NE), (3, 10)],
    ("F", "SPLEEN", "Congestion"): [(5, 10), (NE, NE), (NE, NE), (8, 10)],
}
DOSES = [0.0, 20.0, 200.0, 400.0]


def by_finding(result: dict[str, Any]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    return {
        (f["sex"], f["tissue"], f["finding"]): f["groups"] for f in result["values"]["findings"]
    }


def test_incidence_screen_returns_exactly_the_nine_rows_with_counts() -> None:
    table = by_finding(call_tool("incidence", {"screen": True}))
    assert set(table) == set(SCREEN)
    for key, expected in SCREEN.items():
        groups = table[key]
        assert [g["dose"] for g in groups] == DOSES
        assert [(g["affected"], g["examined"]) for g in groups] == expected


def test_incidence_screen_not_examined_cells_and_renal_necrosis_at_200() -> None:
    table = by_finding(call_tool("incidence", {"screen": True}))
    not_examined = sorted(
        (key, g["dose"])
        for key, groups in table.items()
        for g in groups
        if g["status"] == "not examined"
    )
    assert not_examined == [
        (("F", "SPLEEN", "Congestion"), 20.0),
        (("F", "SPLEEN", "Congestion"), 200.0),
        (("M", "KIDNEY", "Necrosis"), 20.0),
        (("M", "PANCREAS", "Inflammation"), 20.0),
        (("M", "PANCREAS", "Inflammation"), 200.0),
    ]
    kidney = table[("M", "KIDNEY", "Necrosis")][2]
    assert (kidney["dose"], kidney["affected"], kidney["examined"]) == (200.0, 0, 1)


def test_incidence_screen_excludes_tk_satellites_and_recovery_animals() -> None:
    result = call_tool("incidence", {"screen": True})
    assert result["n_examined"] == 80
    excluded = {
        row["usubjid"]
        for row in query(
            "SELECT dm.USUBJID AS usubjid FROM dm JOIN tx ON tx.SETCD = dm.SETCD "
            "WHERE (tx.TXPARMCD = 'TKDESC' AND tx.TXVAL = 'TK') OR dm.ARM ILIKE '%recovery%'"
        )
    }
    assert excluded
    used = {row["usubjid"] for row in result["source_rows"]}
    assert used
    assert used.isdisjoint(excluded)
    assert "TK satellites and recovery animals excluded" in result["population"]


def test_incidence_full_returns_every_finding_including_the_screen() -> None:
    full = call_tool("incidence", {"screen": False})
    table = by_finding(full)
    assert len(table) == 82
    assert set(SCREEN) <= set(table)
    for key, expected in SCREEN.items():
        assert [(g["affected"], g["examined"]) for g in table[key]] == expected
    assert full["values"]["screen"] is False
    assert full["values"]["screen_rule"] is None
    assert full["kind"] == "incidence_full"


def test_incidence_full_keeps_results_unmerged() -> None:
    table = by_finding(call_tool("incidence", {"screen": False}))
    pancreas = {f for (sex, tissue, f) in table if tissue == "PANCREAS"}
    assert {"Inflammation", "Inflammation chronic"} <= pancreas
    assert ("F", "PANCREAS", "Inflammation") not in SCREEN
    assert ("F", "PANCREAS", "Inflammation") not in by_finding(
        call_tool("incidence", {"screen": True})
    )


def test_screen_rule_text_matches() -> None:
    result = call_tool("incidence", {"screen": True})
    assert result["values"]["screen_rule"] == SCREEN_RULE
    assert "not a statistical test" in SCREEN_RULE


@pytest.mark.parametrize("screen", [True, False])
def test_observation_incidence_valid_and_stable(screen: bool) -> None:
    first, second = (
        call_tool("incidence", {"screen": screen}),
        call_tool("incidence", {"screen": screen}),
    )
    observation = Observation.model_validate(first)
    assert observation.tool.name == "incidence"
    assert observation.n_examined == 80
    assert "FROM mi" in observation.sql or "JOIN mi" in observation.sql
    assert observation.source_rows
    assert first["content_sha256"] == second["content_sha256"]


def group(dose: float, affected: int | None, examined: int | None) -> dict[str, Any]:
    return {"dose": dose, "affected": affected, "examined": examined}


# Each row changes one condition of SCREEN_RULE against the passing baseline (F9).
PASSES_TABLE = [
    ("baseline passes", [group(0, 0, 10), group(400, MIN_EXCESS, 10)], True),
    ("one animal short of the excess", [group(0, 0, 10), group(400, MIN_EXCESS - 1, 10)], False),
    ("excess is over control, not absolute", [group(0, 2, 10), group(400, MIN_EXCESS, 10)], False),
    ("one animal short of the examined minimum", [group(0, 0, 10), group(400, 5, 4)], False),
    ("the minimum examined count is enough", [group(0, 0, 10), group(400, 5, MIN_EXAMINED)], True),
    ("control with no examined animal", [group(0, None, None), group(400, 5, 10)], False),
    ("dose zero never counts as a dose group", [group(0, 0, 10), group(0, 6, 10)], False),
    ("a group not examined cannot pass", [group(0, 0, 10), group(400, None, None)], False),
    ("any group may pass", [group(0, 0, 10), group(20, 0, 10), group(200, 4, 10)], True),
]


@pytest.mark.parametrize(
    ("name", "groups", "expected"), PASSES_TABLE, ids=[row[0] for row in PASSES_TABLE]
)
def test_screen_conditions_each_change_the_result(
    name: str, groups: list[dict[str, Any]], expected: bool
) -> None:
    assert _passes(groups) is expected


def test_screen_rule_text_states_every_condition_applied() -> None:
    assert f"{MIN_EXAMINED} or more examined" in SCREEN_RULE
    assert f"at least {MIN_EXCESS} more" in SCREEN_RULE
    assert "above zero" in SCREEN_RULE
    assert "control has no examined animal" in SCREEN_RULE


def test_not_examined_group_has_no_zero_to_quote() -> None:
    table = by_finding(call_tool("incidence", {"screen": True}))
    spleen = [g for g in table[("F", "SPLEEN", "Congestion")] if g["status"] == "not examined"]
    assert spleen
    assert all(g["examined"] is None and g["affected"] is None for g in spleen)
