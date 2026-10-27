"""Decision slots, DecisionRef in the renderer and verifier, and the NOAEL rule (phase 04)."""

import pytest

from cairn.body_weight import body_weight_change
from cairn.content import DecisionRef, ObservationLedger, Sentence, Text, UnresolvedRef
from cairn.decisions import (
    Decision,
    Slot,
    apply_decisions,
    enumerate_slots,
    example_decisions,
    noael_rule,
    noael_sentence,
)
from cairn.incidence import incidence
from cairn.render import render
from cairn.tools import call_tool
from cairn.verify import verify

NS1 = (
    "How should the no observed adverse effect level be determined and reported "
    "from a repeat-dose toxicity study?"
)


def study_ledger() -> ObservationLedger:
    """Incidence screen and body weight of both sexes, with the step 3 passages retrieved."""
    ledger = ObservationLedger()
    ledger.add(incidence())
    ledger.add(body_weight_change(sex="F"))
    ledger.add(body_weight_change(sex="M"))
    ledger.add_guidance(call_tool("search_guidance", {"query": NS1}))
    return ledger


def say(*parts: str | DecisionRef) -> Sentence:
    return Sentence(parts=[Text(text=p) if isinstance(p, str) else p for p in parts])


def test_decisionref_slots_are_enumerated_by_code_and_stable() -> None:
    first, second = enumerate_slots(study_ledger()), enumerate_slots(study_ledger())
    assert first == second
    assert [s.slot for s in first] == [f"D{i}" for i in range(1, 12)]
    assert [(s.sex, s.finding) for s in first][:2] == [
        ("F", "GLAND, ADRENAL Vacuolization"),
        ("F", "GLAND, MAMMARY Atrophy fat"),
    ]
    assert [(s.sex, s.finding) for s in first][-2:] == [("F", "body weight"), ("M", "body weight")]


def test_decisionref_renders_the_decision_or_a_visible_empty_slot() -> None:
    ledger = study_ledger()
    sentence = say("Adrenal: ", DecisionRef(slot="D1"))
    apply_decisions(ledger, [])
    assert render([sentence], ledger) == "Adrenal: [D1: no decision yet]"
    slots = enumerate_slots(ledger)
    apply_decisions(ledger, example_decisions(slots, "R. Reviewer", "2026-10-27T10:00:00Z"))
    assert render([sentence], ledger) == (
        "Adrenal: GLAND, ADRENAL Vacuolization, females: treatment-related from 20 mg/kg/day, "
        "adverse from 200 mg/kg/day"
    )


def test_decisionref_unknown_slot_does_not_resolve() -> None:
    with pytest.raises(UnresolvedRef):
        render([say("x ", DecisionRef(slot="D99"))], study_ledger())


def test_rule_1_decisionref_counts_as_a_reference() -> None:
    ledger = study_ledger()
    apply_decisions(ledger, example_decisions(enumerate_slots(ledger), "R", "t"))
    assert verify([say("Finding: ", DecisionRef(slot="D1"))], ledger).ok


def test_rule_1_decisionref_sentence_must_still_be_one_sentence() -> None:
    ledger = study_ledger()
    apply_decisions(ledger, example_decisions(enumerate_slots(ledger), "R", "t"))
    verdict = verify([say("Finding. Another: ", DecisionRef(slot="D1"))], ledger)
    assert verdict.rules == [1]


def test_rule_2_decisionref_resolving_slot_passes_and_unfilled_or_unknown_fails() -> None:
    ledger = study_ledger()
    apply_decisions(ledger, [])
    assert verify([say("Finding: ", DecisionRef(slot="D1"))], ledger).rules == [2]
    apply_decisions(ledger, example_decisions(enumerate_slots(ledger), "R", "t"))
    assert verify([say("Finding: ", DecisionRef(slot="D1"))], ledger).ok
    assert verify([say("Finding: ", DecisionRef(slot="D99"))], ledger).rules == [2]


def test_rule_6_noael_in_model_text_fails_and_confirmed_noael_decisionref_passes() -> None:
    ledger = study_ledger()
    decisions = example_decisions(enumerate_slots(ledger), "R", "t")
    apply_decisions(ledger, decisions, frozenset("FM"))
    assert verify([say("The NOAEL is high: ", DecisionRef(slot="D1"))], ledger).rules == [6]
    verdict = verify([noael_sentence("F"), noael_sentence("M")], ledger)
    assert verdict.ok
    assert verdict.text is not None
    assert "NOAEL, females: 20 mg/kg/day" in verdict.text
    assert "Several definitions of NOAEL exist" in verdict.text
    assert "(FDA 2005" in verdict.text


def test_rule_6_unconfirmed_noael_slot_fails_rule_2() -> None:
    ledger = study_ledger()
    apply_decisions(ledger, example_decisions(enumerate_slots(ledger), "R", "t"))
    assert verify([noael_sentence("F")], ledger).rules == [2]


def _slot(name: str, doses: tuple[float, ...], examined: dict[float, int | None] | None) -> Slot:
    return Slot(name, name, "F", doses, examined)


def _decide(slot: str, adverse_from: float | None) -> Decision:
    return Decision(
        dec_id=slot, finding=slot, sex="F", treatment_related_from=None,
        adverse_from=adverse_from, actor="R", ts="t",
    )  # fmt: skip


DOSES = (0.0, 20.0, 200.0, 400.0)


@pytest.mark.parametrize(
    ("adverse", "expected"),
    [
        ([None], 400.0),  # nothing adverse: the highest dose tested
        ([200.0, 400.0], 20.0),  # the highest dose below the lowest adverse dose
        ([20.0], None),  # the lowest adverse dose is the lowest treated dose: not established
    ],
)
def test_noael_rule_three_branches(adverse: list[float | None], expected: float | None) -> None:
    slots = [_slot(f"D{i}", DOSES, None) for i, _ in enumerate(adverse, 1)]
    decisions = [_decide(s.slot, a) for s, a in zip(slots, adverse, strict=True)]
    assert noael_rule("F", slots, decisions).dose == expected


def test_noael_rule_flags_an_adverse_finding_not_examined_in_every_animal() -> None:
    slots = [
        _slot("D1", DOSES, {0.0: 10, 20.0: 10, 200.0: 10, 400.0: 10}),
        _slot("D2", DOSES, {0.0: 10, 20.0: 1, 200.0: 10, 400.0: 10}),
        _slot("D3", DOSES, {0.0: 10, 20.0: None, 200.0: 10, 400.0: 10}),
    ]
    decisions = [_decide("D1", 200.0), _decide("D2", 400.0), _decide("D3", 400.0)]
    result = noael_rule("F", slots, decisions)
    assert result.dose == 20.0
    assert result.flags == [
        "D2 was examined in 1 of 10 animals at this dose",
        "D3 was not examined at this dose",
    ]


def test_noael_rule_example_set_gives_females_20_and_males_200_with_the_male_flags() -> None:
    ledger = study_ledger()
    slots = enumerate_slots(ledger)
    noaels = apply_decisions(ledger, example_decisions(slots, "R", "t"), frozenset("FM"))
    assert (noaels["F"].dose, noaels["M"].dose) == (20.0, 200.0)
    assert noaels["F"].flags == []
    assert noaels["M"].flags == [
        "KIDNEY Necrosis was examined in 1 of 10 animals at this dose",
        "PANCREAS Inflammation was not examined at this dose",
    ]
