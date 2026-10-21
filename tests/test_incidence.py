"""The incidence tool and its screen (C3, C4, C2). Expected values are the frozen literals."""

from typing import Any

import pytest

from cairn.incidence import MIN_EXAMINED, MIN_EXCESS, SCREEN_RULE
from cairn.observation import Observation, query
from cairn.tools import call_tool

NE = None  # not examined

# (sex, tissue, finding): (affected, examined) at 0, 20, 200 and 400 mg/kg/day
SCREEN: dict[tuple[str, str, str], list[tuple[int | None, int]]] = {
    ("F", "GLAND, ADRENAL", "Vacuolization"): [(0, 10), (2, 10), (7, 10), (10, 10)],
    ("M", "GLAND, ADRENAL", "Vacuolization"): [(1, 10), (1, 10), (1, 10), (9, 10)],
    ("F", "GLAND, MAMMARY", "Atrophy fat"): [(0, 10), (0, 10), (5, 10), (5, 10)],
    ("M", "KIDNEY", "Necrosis"): [(0, 10), (NE, 0), (0, 1), (3, 10)],
    ("F", "LIVER", "Vacuolization"): [(0, 10), (0, 10), (0, 10), (3, 10)],
    ("M", "LIVER", "Vacuolization"): [(0, 10), (0, 10), (0, 10), (3, 10)],
    ("F", "LIVER", "Hypertrophy hepatocellular"): [(0, 10), (0, 10), (0, 10), (3, 10)],
    ("M", "PANCREAS", "Inflammation"): [(0, 10), (NE, 0), (NE, 0), (3, 10)],
    ("F", "SPLEEN", "Congestion"): [(5, 10), (NE, 0), (NE, 0), (8, 10)],
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
    assert str(MIN_EXAMINED) in SCREEN_RULE
    assert str(MIN_EXCESS) in SCREEN_RULE
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
