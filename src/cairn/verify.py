"""The verifier: rules 1-7 applied in order to a drafted answer before anyone reads it.

Rule 8 (quote provenance) belongs to a later phase. The expression lists live here, in code,
not in configuration. A draft passes only when no rule reports a failure.
"""

import re
from dataclasses import dataclass, field

from cairn.content import ObservationLedger, Sentence, Text, UnresolvedRef, ValueRef
from cairn.render import render_sentence

RULE_REASONS = {
    1: "every sentence needs at least one reference to a tool result",
    2: "every reference must point to an existing observation and field that can be formatted",
    3: "model-written text must not contain digits; numbers are placed by code",
    4: "an incidence statement must say how many animals were examined",
    5: "data with quarantined rows needs the fixed data-quality note",
    6: "no safety claim and no NOAEL that a person has not recorded",
    7: "no study term written by hand and no expression from the wording list",
}

# Rule 6: safety claims and NOAEL statements (case-insensitive, whole words).
SAFETY_EXPRESSIONS = (
    "safe",
    "safely",
    "no risk",
    "risk-free",
    "harmless",
    "non-toxic",
    "well tolerated",
    "no concern",
    "no adverse effect",
    "no adverse effects",
    "NOAEL",
    "no observed adverse effect level",
)
# Rule 7: study terms that must go in as references, and wording that is never used.
STUDY_TERMS = (
    "PDS2014",
    "rat",
    "rats",
    "Sprague-Dawley",
    "Sprague Dawley",
    "oral gavage",
    "gavage",
)
WORDING_LIST = (
    "lost",
    "lose",
    "loses",
    "losing",
    "weight loss",
    "loss of weight",
    "loss of body weight",
)

DATA_QUALITY_LEAD = "Data quality note: the value of animal "
DATA_QUALITY_TAIL = (
    " was quarantined by validation as not physically possible; "
    "the mean is shown with and without it."
)
# Any field of an Observation holding rows that validation quarantined.
QUARANTINE_FLAG = "contains_quarantined"
QUARANTINE_ANIMAL_FIELD = "quarantined_rows.0.usubjid"


def data_quality_note(obs_id: str) -> Sentence:
    """The one fixed data-quality sentence for an Observation with quarantined rows."""
    return Sentence(
        parts=[
            Text(text=DATA_QUALITY_LEAD),
            ValueRef(obs_id=obs_id, field=QUARANTINE_ANIMAL_FIELD),
            Text(text=DATA_QUALITY_TAIL),
        ]
    )


@dataclass(frozen=True)
class Failure:
    rule: int
    reason: str
    sentence: int | None = None

    def __str__(self) -> str:
        where = "" if self.sentence is None else f" (sentence {self.sentence + 1})"
        return f"Rule {self.rule}{where}: {self.reason}"


@dataclass
class Verdict:
    failures: list[Failure] = field(default_factory=list)
    text: str | None = None

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def rules(self) -> list[int]:
        return sorted({failure.rule for failure in self.failures})


def _pattern(expressions: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(e) for e in sorted(expressions, key=len, reverse=True))
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.IGNORECASE)


SAFETY_PATTERN = _pattern(SAFETY_EXPRESSIONS)
STUDY_TERM_PATTERN = _pattern(STUDY_TERMS)
WORDING_PATTERN = _pattern(WORDING_LIST)


def _refs(sentence: Sentence) -> list[ValueRef]:
    return [part for part in sentence.parts if isinstance(part, ValueRef)]


def _model_text(sentence: Sentence) -> str:
    return " ".join(part.text for part in sentence.parts if isinstance(part, Text))


def _is_incidence_count(ref: ValueRef) -> bool:
    return ref.field.rsplit(".", 1)[-1] == "affected"


def _has_denominator(ref: ValueRef, refs: list[ValueRef]) -> bool:
    prefix = ref.field[: -len("affected")]
    wanted = {f"{prefix}examined", "n_examined"}
    return any(other.obs_id == ref.obs_id and other.field in wanted for other in refs)


def _cites_quarantine(ref: ValueRef, ledger: ObservationLedger) -> bool:
    try:
        return bool(ledger.get(ref.obs_id).values.get(QUARANTINE_FLAG))
    except UnresolvedRef:
        return False


def verify(sentences: list[Sentence], ledger: ObservationLedger) -> Verdict:
    """Apply rules 1-7 in order; the verdict carries every failure and, if none, the text."""
    failures: list[Failure] = []

    def fail(rule: int, index: int | None, detail: str = "") -> None:
        reason = RULE_REASONS[rule] + (f": {detail}" if detail else "")
        failures.append(Failure(rule, reason, index))

    for index, sentence in enumerate(sentences):  # rule 1
        if not _refs(sentence):
            fail(1, index)
    for index, sentence in enumerate(sentences):  # rule 2
        try:
            render_sentence(sentence, ledger)
        except UnresolvedRef as error:
            fail(2, index, str(error))
    for index, sentence in enumerate(sentences):  # rule 3
        if re.search(r"\d", _model_text(sentence)):
            fail(3, index)
    for index, sentence in enumerate(sentences):  # rule 4
        refs = _refs(sentence)
        if any(_is_incidence_count(ref) and not _has_denominator(ref, refs) for ref in refs):
            fail(4, index)
    for index, sentence in enumerate(sentences):  # rule 5
        if sentence in (data_quality_note(ref.obs_id) for ref in _refs(sentence)):
            continue
        quarantined = [ref for ref in _refs(sentence) if _cites_quarantine(ref, ledger)]
        for obs_id in dict.fromkeys(ref.obs_id for ref in quarantined):
            note = data_quality_note(obs_id)
            if note not in sentences[index : index + 2]:
                fail(5, index)
    for index, sentence in enumerate(sentences):  # rule 6
        match = SAFETY_PATTERN.search(_model_text(sentence))
        if match:
            fail(6, index, f'"{match.group(0)}"')
    for index, sentence in enumerate(sentences):  # rule 7
        match = STUDY_TERM_PATTERN.search(_model_text(sentence)) or WORDING_PATTERN.search(
            _model_text(sentence)
        )
        if match:
            fail(7, index, f'"{match.group(0)}"')
    if failures:
        return Verdict(failures=failures)
    return Verdict(text=" ".join(render_sentence(s, ledger) for s in sentences))
