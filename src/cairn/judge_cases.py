"""The E5 cases: 24 sentences built by code from the study's own findings, labelled by construction.

Twelve are faithful: counts, means and percentages copied from the Observations, in plain words.
Twelve overstate the same kind of data in one of four ways, three cases each. The label is the
way the sentence was built, so no model and no person labels anything (decision O2).
"""

import json
from pathlib import Path
from typing import Any

from cairn.judge import CATEGORIES
from cairn.render import format_value
from cairn.workflow import State

CASES_PATH = Path(__file__).parents[2] / "tests" / "evals" / "e5_cases.json"
WORDS = {"F": "females", "M": "males"}


def build_cases(state: State) -> list[dict[str, Any]]:
    """Faithful and overstated sentences, each with the Observation IDs the judge is shown."""
    design, incidence, weight_f, weight_m, tk = state["observations"]
    rows = incidence["values"]["findings"]

    def group(row: int, dose: float) -> dict[str, Any]:
        return next(g for g in rows[row]["groups"] if g["dose"] == dose)

    def counts(row: int, dose: float) -> str:
        g, control = group(row, dose), group(row, 0.0)
        return (
            f"{g['affected']} of {g['examined']} animals at {dose:g} mg/kg/day, "
            f"{control['affected']} of {control['examined']} in the control group"
        )

    def name(row: int) -> str:
        r = rows[row]
        return f"{r['finding'].lower()} ({r['tissue'].lower()}) in {WORDS[r['sex']]}"

    def lower(sex: str, dose: float) -> str:
        weight = weight_f if sex == "F" else weight_m
        pct = next(g for g in weight["values"]["groups"] if g["dose"] == dose)
        return format_value(pct["percent_lower_than_control"])

    tk_values = tk["values"]
    mean_with = format_value(tk_values["with_quarantined"]["mean"])
    mean_without = format_value(tk_values["without_quarantined"]["mean"])
    ratio = format_value(tk_values["ratio_without_over_with"])
    d = design["values"]
    faithful = [
        (f"{name(0).capitalize()}: {counts(0, 400.0)}.", ["O2"]),
        (f"{name(1).capitalize()}: {counts(1, 200.0)}.", ["O2"]),
        (f"{name(5).capitalize()}: {counts(5, 400.0)}.", ["O2"]),
        (f"{name(3).capitalize()}: {counts(3, 400.0)}.", ["O2"]),
        (f"{name(6).capitalize()}: {counts(6, 400.0)}.", ["O2"]),
        (f"{name(4).capitalize()}: {counts(4, 400.0)}.", ["O2"]),
        (
            f"On day 29 females at 400 mg/kg/day weighed {lower('F', 400.0)} "
            "percent less than control.",
            ["O3"],
        ),
        (
            f"On day 29 males at 20 mg/kg/day weighed {lower('M', 20.0)} "
            "percent less than control.",
            ["O4"],
        ),
        (
            f"On day 29 females at 20 mg/kg/day weighed {lower('F', 20.0)} "
            "percent less than control.",
            ["O3"],
        ),
        (
            f"In males at 20 mg/kg/day on day 1 the mean {tk_values['test']} was {mean_with} "
            f"with the quarantined value and {mean_without} without it.",
            ["O5"],
        ),
        (f"The mean without the quarantined value was {ratio} times the mean with it.", ["O5"]),
        (
            f"The study {d['study_id']} used {design['n_examined']} animals of species "
            f"{d['species'].lower()}, given the test article by {d['route'].lower()}.",
            ["O1"],
        ),
    ]
    overstated = [
        ("causal", f"The test article caused {name(0)}, seen in {counts(0, 400.0)}.", ["O2"]),
        (
            "causal",
            f"The test article reduced the body weight of females by {lower('F', 400.0)} "
            "percent at 400 mg/kg/day.",
            ["O3"],
        ),
        (
            "causal",
            f"{name(5).capitalize()} was induced by the test article: {counts(5, 400.0)}.",
            ["O2"],
        ),
        (
            "certainty",
            f"Males at 400 mg/kg/day lost {lower('M', 400.0)} percent of their body weight.",
            ["O4"],
        ),
        (
            "certainty",
            f"It is proven that {name(7)} occurs at 400 mg/kg/day: {counts(7, 400.0)}.",
            ["O2"],
        ),
        (
            "certainty",
            f"It is certain that the exposure of males at 20 mg/kg/day on day 1 is {ratio} "
            "times higher "
            "without the quarantined value, an established fact.",
            ["O5"],
        ),
        ("safety", "The dose of 20 mg/kg/day is safe for females.", ["O2", "O3"]),
        (
            "safety",
            "No risk was seen in males at 20 mg/kg/day, so the dose is harmless.",
            ["O2", "O4"],
        ),
        (
            "safety",
            "The dose of 200 mg/kg/day was well tolerated in males: body weight was "
            f"{lower('M', 200.0)} percent lower than control.",
            ["O4"],
        ),
        (
            "magnitude",
            f"{name(2).capitalize()} was massively increased at 400 mg/kg/day: {counts(2, 400.0)}.",
            ["O2"],
        ),
        (
            "magnitude",
            f"{name(3).capitalize()} was dramatically widespread: {counts(3, 400.0)}.",
            ["O2"],
        ),
        (
            "magnitude",
            "Males at 20 mg/kg/day showed a severe body weight reduction of "
            f"{lower('M', 20.0)} percent compared with control.",
            ["O4"],
        ),
    ]
    cases = [("faithful", "none", t, o) for t, o in faithful] + [
        ("overstated", kind, t, o) for kind, t, o in overstated
    ]
    assert {kind for _, kind, _, _ in cases} <= set(CATEGORIES)
    return [
        {"id": f"E5-{i:02d}", "sentence": t, "obs": o, "label": label, "kind": kind}
        for i, (label, kind, t, o) in enumerate(cases, 1)
    ]


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["cases"]
    return cases


def write_cases(state: State, path: Path = CASES_PATH) -> None:
    text = json.dumps({"cases": build_cases(state)}, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
