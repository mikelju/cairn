"""E1: exact figures with no model. Every expected value below is a frozen literal."""

from functools import cache
from typing import Any

import pytest

from cairn.body_weight import body_weight_change
from cairn.content import ObservationLedger
from cairn.decisions import apply_decisions, enumerate_slots, example_decisions
from cairn.incidence import incidence
from cairn.tools import call_tool


@cache
def validation_report() -> dict[str, Any]:
    report: dict[str, Any] = call_tool("run_job", {"kind": "validate_study"})["outputs"]["report"]
    return report


@cache
def tool(name: str, **arguments: Any) -> dict[str, Any]:
    return call_tool(name, arguments)


def report_value(path: str) -> Any:
    current: Any = validation_report()
    for step in path.split("."):
        current = current[step]
    return current


# Phase 01 validation facts.
VALIDATION_FACTS = [
    ("auc.AUCIFO.negative", 10),
    ("auc.AUCIFO.quantified", 16),
    ("auc.AUCTAU.negative", 2),
    ("auc.AUCTAU.quantified", 36),
    ("quarantine.total", 12),
    ("quarantine.by_rule", {"pp_auc_positive": 12}),
    ("concentrations.quantified", 226),
    ("concentrations.negative", 0),
    ("age.animals_checked", 124),
    ("age.animals_mismatching", 124),
    ("age.dm_age_values", [0.0]),
    ("terminology.value", "SEND Terminology 2013-012-20"),
    ("terminology.well_formed", False),
    ("xpt_zeros_normalised", {"DM.AGE": 124, "PC.PCTPTNUM": 18}),
]


@pytest.mark.parametrize(("path", "expected"), VALIDATION_FACTS)
def test_e1_validation_fact(path: str, expected: Any) -> None:
    assert report_value(path) == expected


def test_e1_one_death_in_a_control_tk_satellite() -> None:
    deaths = report_value("deaths")
    assert [(d["usubjid"], d["day"], d["group"]) for d in deaths] == [
        ("PDS2014-0119", 3.0, "Female, Vehicle, 0 mg/kg , TK")
    ]


# The 9 rows of the screen: (affected, examined) at 0, 20, 200 and 400 mg/kg/day.
# None affected means not examined.
SCREEN_ROWS = [
    ("F", "GLAND, ADRENAL", "Vacuolization", [(0, 10), (2, 10), (7, 10), (10, 10)]),
    ("M", "GLAND, ADRENAL", "Vacuolization", [(1, 10), (1, 10), (1, 10), (9, 10)]),
    ("F", "GLAND, MAMMARY", "Atrophy fat", [(0, 10), (0, 10), (5, 10), (5, 10)]),
    ("M", "KIDNEY", "Necrosis", [(0, 10), (None, None), (0, 1), (3, 10)]),
    ("F", "LIVER", "Vacuolization", [(0, 10), (0, 10), (0, 10), (3, 10)]),
    ("M", "LIVER", "Vacuolization", [(0, 10), (0, 10), (0, 10), (3, 10)]),
    ("F", "LIVER", "Hypertrophy hepatocellular", [(0, 10), (0, 10), (0, 10), (3, 10)]),
    ("M", "PANCREAS", "Inflammation", [(0, 10), (None, None), (None, None), (3, 10)]),
    ("F", "SPLEEN", "Congestion", [(5, 10), (None, None), (None, None), (8, 10)]),
]


def test_e1_screen_has_exactly_nine_rows() -> None:
    assert len(tool("incidence", screen=True)["values"]["findings"]) == 9


@pytest.mark.parametrize(("sex", "tissue", "finding", "counts"), SCREEN_ROWS)
def test_e1_screen_row_counts(
    sex: str, tissue: str, finding: str, counts: list[tuple[int | None, int | None]]
) -> None:
    rows = [
        row
        for row in tool("incidence", screen=True)["values"]["findings"]
        if (row["sex"], row["tissue"], row["finding"]) == (sex, tissue, finding)
    ]
    assert len(rows) == 1
    assert [(g["affected"], g["examined"]) for g in rows[0]["groups"]] == counts


# Female body weight on day 29.
def groups() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = tool("body_weight_change", sex="F")["values"]["groups"]
    return result


@pytest.mark.parametrize(("index", "expected"), [(1, 9.3), (2, 17.6), (3, 20.7)])
def test_e1_female_percent_lower_than_control(index: int, expected: float) -> None:
    assert round(groups()[index]["percent_lower_than_control"], 1) == expected


def test_e1_female_n_per_group() -> None:
    assert [g["n"] for g in groups()] == [15, 10, 10, 15]


def test_e1_female_every_group_gained_weight() -> None:
    assert all(g["mean_change_from_baseline_g"] > 0 for g in groups())


def test_e1_female_one_animal_lost_nothing_but_has_a_negative_change() -> None:
    negative = tool("body_weight_change", sex="F")["values"]["animals_with_negative_change"]
    assert negative == [{"usubjid": "PDS2014-0165", "dose": 400.0, "change_g": -5.3}]
    assert tool("body_weight_change", sex="F")["values"]["wording"] == "lower than control"


# Naive TK mean, males at 20 mg/kg/day on day 1.
def tk() -> dict[str, Any]:
    values: dict[str, Any] = tool("tk_summary", sex="M", dose=20.0, day=1.0)["values"]
    return values


def test_e1_tk_mean_with_quarantined_value() -> None:
    assert (tk()["with_quarantined"]["n"], round(tk()["with_quarantined"]["mean"])) == (3, 2821)


def test_e1_tk_mean_without_quarantined_value() -> None:
    assert (tk()["without_quarantined"]["n"], round(tk()["without_quarantined"]["mean"])) == (
        2,
        15956,
    )


def test_e1_tk_ratio_and_quarantined_animal() -> None:
    assert tk()["ratio_without_over_with"] == 5.7
    assert [(r["usubjid"], r["value"]) for r in tk()["quarantined_rows"]] == [
        ("PDS2014-0032", -23450.0)
    ]


# The example decision set: females 20 and males 200 mg/kg/day, the male flags need confirmation.
def test_e1_example_decisions_give_the_noael_per_sex() -> None:
    ledger = ObservationLedger()
    ledger.add(incidence())
    ledger.add(body_weight_change(sex="F"))
    ledger.add(body_weight_change(sex="M"))
    decisions = example_decisions(enumerate_slots(ledger), "R. Reviewer", "2026-10-27T10:00:00Z")
    noaels = apply_decisions(ledger, decisions)
    assert (noaels["F"].dose, noaels["M"].dose) == (20.0, 200.0)
    assert noaels["F"].flags == []
    assert [flag.split(" was ")[0] for flag in noaels["M"].flags] == [
        "KIDNEY Necrosis",
        "PANCREAS Inflammation",
    ]
    assert ledger.slots["NOAEL-M"] is None  # nothing is placed until a person confirms
