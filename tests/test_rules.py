"""Verifier rules 1-7: each has a passing and a failing fixture (C9)."""

from cairn.content import Sentence, Text, ValueRef
from cairn.verify import RULE_REASONS, Verdict, data_quality_note, verify
from conftest import World


def text(value: str) -> Text:
    return Text(text=value)


def passing(world: World) -> list[Sentence]:
    """A clean draft: references everywhere, no digits, denominators, the note after the TK mean."""
    weight = world.ref(world.weight, "groups.3.percent_lower_than_control")
    tk = world.ref(world.tk, "with_quarantined.mean")
    return [
        Sentence(
            parts=[
                text("Females at the top dose were "),
                weight,
                text(" percent lower than control."),
            ]
        ),
        Sentence(parts=[text("The naive mean was "), tk, text(".")]),
        data_quality_note(world.tk),
    ]


def only(verdict: Verdict, rule: int) -> None:
    assert not verdict.ok
    assert verdict.rules == [rule]
    failure = verdict.failures[0]
    assert failure.rule == rule
    assert RULE_REASONS[rule] in failure.reason
    assert str(failure).startswith(f"Rule {rule}")


def test_rule_0_clean_draft_passes_and_renders(world: World) -> None:
    verdict = verify(passing(world), world.ledger)
    assert verdict.ok
    assert verdict.text is not None
    assert "20.7 percent lower than control" in verdict.text
    assert "The naive mean was 2,821." in verdict.text
    assert "PDS2014-0032" in verdict.text


def test_rule_1_sentence_with_a_reference_passes(world: World) -> None:
    sentence = Sentence(parts=[text("Examined: "), world.ref(world.design, "n_examined")])
    assert verify([sentence], world.ledger).ok


def test_rule_1_sentence_without_a_reference_fails(world: World) -> None:
    verdict = verify([Sentence(parts=[text("Body weight was lower.")])], world.ledger)
    only(verdict, 1)


def test_rule_2_resolving_reference_passes(world: World) -> None:
    sentence = Sentence(parts=[world.ref(world.design, "species")])
    assert verify([sentence], world.ledger).ok


def test_rule_2_unresolved_references_fail(world: World) -> None:
    for ref in (
        ValueRef(obs_id="O99", field="n_examined"),
        world.ref(world.design, "no_such_field"),
        world.ref(world.design, "groups"),
    ):
        only(verify([Sentence(parts=[text("Value "), ref])], world.ledger), 2)


def test_rule_3_text_without_digits_passes(world: World) -> None:
    sentence = Sentence(parts=[text("Weight was "), world.ref(world.weight, "groups.1.n")])
    assert verify([sentence], world.ledger).ok


def test_rule_3_digit_in_model_text_fails(world: World) -> None:
    for written in ("About 21 percent lower than control", "Group 2", "1,000", "20%"):
        sentence = Sentence(parts=[text(written + " in "), world.ref(world.weight, "sex")])
        only(verify([sentence], world.ledger), 3)


def test_rule_4_incidence_with_denominator_passes(world: World) -> None:
    group = "findings.0.groups.3"
    sentence = Sentence(
        parts=[
            world.ref(world.incidence, f"{group}.affected"),
            text(" of "),
            world.ref(world.incidence, f"{group}.examined"),
            text(" animals were affected."),
        ]
    )
    assert verify([sentence], world.ledger).ok


def test_rule_4_incidence_without_denominator_fails(world: World) -> None:
    sentence = Sentence(
        parts=[world.ref(world.incidence, "findings.0.groups.3.affected"), text(" were affected.")]
    )
    only(verify([sentence], world.ledger), 4)
    other_group = Sentence(
        parts=[
            world.ref(world.incidence, "findings.0.groups.3.affected"),
            text(" of "),
            world.ref(world.incidence, "findings.0.groups.2.examined"),
        ]
    )
    only(verify([other_group], world.ledger), 4)


def test_rule_5_quarantined_data_with_the_note_passes(world: World) -> None:
    assert verify(passing(world), world.ledger).ok
    note_first = [passing(world)[1], data_quality_note(world.tk)]
    assert verify(note_first, world.ledger).ok


def test_rule_5_quarantined_data_without_the_note_fails(world: World) -> None:
    mean = Sentence(
        parts=[text("The naive mean was "), world.ref(world.tk, "with_quarantined.mean")]
    )
    only(verify([mean], world.ledger), 5)
    altered = Sentence(
        parts=[
            text("The value of animal "),
            world.ref(world.tk, "quarantined_rows.0.usubjid"),
            text(" is fine."),
        ]
    )
    only(verify([mean, altered], world.ledger), 5)
    far_away = [mean, passing(world)[0], data_quality_note(world.tk)]
    only(verify(far_away, world.ledger), 5)


def test_rule_6_neutral_wording_passes(world: World) -> None:
    sentence = Sentence(parts=[text("The screen listed "), world.ref(world.incidence, "screen")])
    assert verify([sentence], world.ledger).ok


def test_rule_6_safety_claims_and_noael_fail(world: World) -> None:
    for written in ("The dose is safe in ", "There is no risk in ", "The NOAEL is set in "):
        sentence = Sentence(parts=[text(written), world.ref(world.design, "species")])
        only(verify([sentence], world.ledger), 6)


def test_rule_7_study_terms_as_references_pass(world: World) -> None:
    sentence = Sentence(
        parts=[
            world.ref(world.design, "study_id"),
            text(" used "),
            world.ref(world.design, "species"),
            text(" by "),
            world.ref(world.design, "route"),
            text(", a rate of "),
            world.ref(world.weight, "groups.1.n"),
        ]
    )
    assert verify([sentence], world.ledger).ok


def test_rule_7_hand_written_terms_and_wording_fail(world: World) -> None:
    for written in ("The rats in ", "Sprague-Dawley animals in ", "Females lost weight in "):
        sentence = Sentence(parts=[text(written), world.ref(world.design, "species")])
        only(verify([sentence], world.ledger), 7)


def test_rules_apply_in_order_and_report_every_failure(world: World) -> None:
    sentence = Sentence(parts=[text("21 rats lost weight, a safe dose")])
    verdict = verify([sentence, passing(world)[0]], world.ledger)
    assert verdict.rules == [1, 3, 6, 7]
    assert [f.rule for f in verdict.failures] == sorted(f.rule for f in verdict.failures)
