"""The renderer places every number from an Observation field; model text has no digits."""

import re

import pytest

from cairn.body_weight import body_weight_change
from cairn.content import ObservationLedger, Sentence, Text, UnresolvedRef, ValueRef
from cairn.incidence import incidence
from cairn.render import format_value, render
from cairn.tk_summary import tk_summary
from cairn.tools import study_design


def run_once() -> tuple[str, ObservationLedger, list[Sentence]]:
    ledger = ObservationLedger()
    design_id = ledger.add(study_design())
    weight_id = ledger.add(body_weight_change())
    tk_id = ledger.add(tk_summary())
    sentences = [
        Sentence(
            parts=[
                Text(text="Study "),
                ValueRef(obs_id=design_id, field="study_id"),
                Text(text=" used "),
                ValueRef(obs_id=design_id, field="species"),
                Text(text=" and the high dose group had "),
                ValueRef(obs_id=weight_id, field="groups.3.percent_lower_than_control"),
                Text(text=" percent lower than control, n = "),
                ValueRef(obs_id=weight_id, field="groups.3.n"),
                Text(text="."),
            ]
        ),
        Sentence(
            parts=[
                Text(text="AUCtau was "),
                ValueRef(obs_id=tk_id, field="with_quarantined.mean"),
                Text(text=" versus "),
                ValueRef(obs_id=tk_id, field="without_quarantined.mean"),
                Text(text=", a ratio of "),
                ValueRef(obs_id=tk_id, field="ratio_without_over_with"),
                Text(text="; examined "),
                ValueRef(obs_id=tk_id, field="n_examined"),
                Text(text=" animals."),
            ]
        ),
    ]
    return render(sentences, ledger), ledger, sentences


def test_renderer_places_numbers_from_observations() -> None:
    text, ledger, _ = run_once()
    assert "PDS2014" in text
    assert "20.7 percent lower than control, n = 15" in text
    assert "AUCtau was 2,821 versus 15,956, a ratio of 5.7; examined 3 animals." in text
    weight = ledger.get("O2").values["groups"][3]
    assert str(weight["n"]) in text
    assert f"{weight['percent_lower_than_control']:.1f}" in text


def test_renderer_model_text_has_no_digits() -> None:
    _, _, sentences = run_once()
    chunks = [part.text for s in sentences for part in s.parts if isinstance(part, Text)]
    assert not any(re.search(r"\d", chunk) for chunk in chunks)


def test_renderer_ids_repeat_across_runs() -> None:
    first_text, first_ledger, _ = run_once()
    second_text, second_ledger, _ = run_once()
    assert first_ledger.ids == second_ledger.ids == ["O1", "O2", "O3"]
    assert first_text == second_text


def test_renderer_unresolved_references_raise() -> None:
    ledger = ObservationLedger()
    obs_id = ledger.add(tk_summary())
    for ref in (
        ValueRef(obs_id="O9", field="n_examined"),
        ValueRef(obs_id=obs_id, field="no_such_field"),
        ValueRef(obs_id=obs_id, field="quarantined_rows.7.value"),
        ValueRef(obs_id=obs_id, field="with_quarantined"),
    ):
        with pytest.raises(UnresolvedRef):
            render([Sentence(parts=[ref])], ledger)


def test_renderer_formats_by_type() -> None:
    assert format_value(True) == "yes"
    assert format_value(15) == "15"
    assert format_value(12345) == "12,345"
    assert format_value(20.0) == "20"
    assert format_value(9.3) == "9.3"
    assert format_value(17.58) == "17.6"
    assert format_value(15956.4) == "15,956"
    assert format_value("Vacuolization") == "Vacuolization"
    with pytest.raises(UnresolvedRef):
        format_value(None)


def test_renderer_reads_nested_incidence_fields() -> None:
    ledger = ObservationLedger()
    obs_id = ledger.add(incidence())
    sentence = Sentence(
        parts=[
            ValueRef(obs_id=obs_id, field="findings.0.finding"),
            Text(text=" affected "),
            ValueRef(obs_id=obs_id, field="findings.0.groups.3.affected"),
            Text(text=" of "),
            ValueRef(obs_id=obs_id, field="findings.0.groups.3.examined"),
        ]
    )
    assert render([sentence], ledger) == "Vacuolization affected 10 of 10"


def test_renderer_accepts_values_prefix_in_field_paths() -> None:
    ledger = ObservationLedger()
    obs_id = ledger.add(incidence())
    plain = ValueRef(obs_id=obs_id, field="findings.0.finding")
    shown = ValueRef(obs_id=obs_id, field="values.findings.0.finding")
    assert ledger.resolve(plain) == ledger.resolve(shown) == "Vacuolization"


def test_renderer_separates_fused_text_and_value() -> None:
    ledger = ObservationLedger()
    obs_id = ledger.add(incidence())
    finding = ValueRef(obs_id=obs_id, field="findings.0.finding")
    parts: list[Text | ValueRef] = [
        Text(text="containing"),
        finding,
        Text(text="animals"),
        finding,
        Text(text="."),
    ]
    fused = Sentence(parts=parts)
    assert render([fused], ledger) == "containing Vacuolization animals Vacuolization."
    spaced = Sentence(parts=[Text(text="of "), finding, Text(text=" ("), finding, Text(text=")")])
    assert render([spaced], ledger) == "of Vacuolization (Vacuolization)"
