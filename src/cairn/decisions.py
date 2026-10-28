"""Decision slots and the NOAEL rule: people decide adversity, code places and computes the rest.

Slots are enumerated by code from the incidence and body weight Observations of a run, before any
drafting: D1..Dn per finding and sex in ledger order, then NOAEL-F and NOAEL-M. A person fills a D
slot with a Decision; the NOAEL of a sex is a pure function of those decisions and fills its slot
only once a person confirms it.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel

from cairn.content import DecisionRef, ObservationLedger, QuoteRef, Sentence, Text

SEX_WORDS = {"F": "females", "M": "males"}
# The step 3 definition of the NOAEL (FDA 2005, section IV), returned by fixed query NS1.
NOAEL_DEFINITION = QuoteRef(passage_id="FDA-IV-01", sentence_ids=["FDA-IV-01.s2"])


class Decision(BaseModel):
    dec_id: str  # the slot it fills
    finding: str
    sex: str
    treatment_related_from: float | None  # lowest dose judged treatment-related; None if none
    adverse_from: float | None  # lowest dose judged adverse; None if none
    actor: str
    ts: str


@dataclass(frozen=True)
class Slot:
    slot: str
    finding: str
    sex: str
    doses: tuple[float, ...]
    examined: dict[float, int | None] | None  # animals examined per dose; None if all were


@dataclass(frozen=True)
class Noael:
    sex: str
    dose: float | None  # None: not established
    flags: list[str] = field(default_factory=list)  # adverse findings not fully examined at dose


def enumerate_slots(ledger: ObservationLedger) -> list[Slot]:
    """One slot per finding and sex of the incidence and body weight Observations, in order."""
    found: list[tuple[str, str, tuple[float, ...], dict[float, int | None] | None]] = []
    for observation in ledger.observations:
        values = observation.values
        if observation.kind.startswith("incidence"):
            for row in values["findings"]:
                examined = {g["dose"]: g["examined"] for g in row["groups"]}
                found.append(
                    (f"{row['tissue']} {row['finding']}", row["sex"], tuple(examined), examined)
                )
        elif observation.kind == "body_weight_change":
            doses = tuple(g["dose"] for g in values["groups"])
            found.append(("body weight", values["sex"], doses, None))
    return [Slot(f"D{i}", *item) for i, item in enumerate(found, 1)]


def noael_rule(sex: str, slots: list[Slot], decisions: list[Decision]) -> Noael:
    """The highest dose below the lowest adverse dose; the highest tested if nothing is adverse;
    not established if the lowest adverse dose is the lowest treated dose.

    Flags every adverse finding whose tissue was not examined in every animal at that dose.
    """
    mine = [s for s in slots if s.sex == sex]
    treated = sorted({d for s in mine for d in s.doses if d > 0})
    by_slot = {d.dec_id: d for d in decisions}
    onset: dict[str, float] = {}
    for s in mine:
        decision = by_slot.get(s.slot)
        if decision and decision.adverse_from is not None:
            onset[s.slot] = decision.adverse_from
    adverse = [s for s in mine if s.slot in onset]
    if not adverse:
        return Noael(sex, max(treated))
    below = [d for d in treated if d < min(onset.values())]
    if not below:
        return Noael(sex, None)
    dose = max(below)
    flags: list[str] = []
    for s in adverse:
        if s.examined is None:
            continue
        seen, full = s.examined.get(dose), max(n or 0 for n in s.examined.values())
        if seen is None:
            flags.append(f"{s.finding} was not examined at this dose")
        elif seen < full:
            flags.append(f"{s.finding} was examined in {seen} of {full} animals at this dose")
    return Noael(sex, dose, flags)


def _dose(dose: float | None, none: str) -> str:
    return none if dose is None else f"{dose:g} mg/kg/day"


def decision_text(slot: Slot, decision: Decision) -> str:
    return (
        f"{slot.finding}, {SEX_WORDS[slot.sex]}: treatment-related from "
        f"{_dose(decision.treatment_related_from, 'no dose')}, adverse from "
        f"{_dose(decision.adverse_from, 'no dose')}"
    )


def noael_text(result: Noael) -> str:
    text = f"NOAEL, {SEX_WORDS[result.sex]}: {_dose(result.dose, 'not established')}"
    if result.flags:
        text += "; confirmed by a person despite incomplete examination: " + "; ".join(result.flags)
    return text


def noael_sentence(sex: str) -> Sentence:
    """The sentence that places a NOAEL slot and quotes the definition it applies."""
    return Sentence(
        parts=[
            DecisionRef(slot=f"NOAEL-{sex}"),
            Text(text=" under the definition of the guidance: "),
            NOAEL_DEFINITION,
        ]
    )


def apply_decisions(
    ledger: ObservationLedger, decisions: list[Decision], confirmed: frozenset[str] = frozenset()
) -> dict[str, Noael]:
    """Fill the ledger's slots from the decisions; a NOAEL slot fills only for a confirmed sex.

    Returns the NOAEL of each sex, so the caller can show it before anyone confirms it.
    """
    slots = enumerate_slots(ledger)
    by_slot = {d.dec_id: d for d in decisions}
    ledger.slots = {
        s.slot: decision_text(s, by_slot[s.slot]) if s.slot in by_slot else None for s in slots
    }
    noaels = {sex: noael_rule(sex, slots, decisions) for sex in sorted({s.sex for s in slots})}
    for sex, result in noaels.items():
        ledger.slots[f"NOAEL-{sex}"] = noael_text(result) if sex in confirmed else None
    return noaels


# The example decision set: (sex, finding) -> (treatment-related from, adverse from), mg/kg/day.
EXAMPLE = {
    ("F", "GLAND, ADRENAL Vacuolization"): (20.0, 200.0),
    ("M", "GLAND, ADRENAL Vacuolization"): (400.0, 400.0),
    ("F", "GLAND, MAMMARY Atrophy fat"): (200.0, None),
    ("M", "KIDNEY Necrosis"): (400.0, 400.0),
    ("F", "LIVER Vacuolization"): (400.0, None),
    ("M", "LIVER Vacuolization"): (400.0, None),
    ("F", "LIVER Hypertrophy hepatocellular"): (400.0, None),
    ("M", "PANCREAS Inflammation"): (400.0, 400.0),
    ("F", "SPLEEN Congestion"): (None, None),
    ("F", "body weight"): (20.0, 200.0),
    ("M", "body weight"): (400.0, None),
}


def example_decisions(slots: list[Slot], actor: str, ts: str) -> list[Decision]:
    """The example decisions for the slots of the study, as one person would record them."""
    return [
        Decision(
            dec_id=s.slot,
            finding=s.finding,
            sex=s.sex,
            treatment_related_from=EXAMPLE[s.sex, s.finding][0],
            adverse_from=EXAMPLE[s.sex, s.finding][1],
            actor=actor,
            ts=ts,
        )
        for s in slots
    ]
