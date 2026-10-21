"""The verifier: rules 1-7 applied in order to a drafted answer before anyone reads it.

Rule 8 (quote provenance) belongs to a later phase. The expression lists live here, in code,
not in configuration. A draft passes only when no rule reports a failure.
"""

import itertools
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from cairn.content import ObservationLedger, Sentence, Text, UnresolvedRef, ValueRef
from cairn.render import render, render_parts, render_sentence

RULE_REASONS = {
    1: "every sentence needs at least one reference to a tool result",
    2: "every reference must point to an existing observation and field that can be formatted",
    3: "model-written text must not contain digits; numbers are placed by code",
    4: "an incidence statement must say how many animals were examined",
    5: "data with quarantined rows needs the fixed data-quality note",
    6: "no safety claim and no NOAEL that a person has not recorded",
    7: "no study term written by hand and no expression from the wording list",
}

# Matching is whole-word and case-insensitive on normalized text (NFKC, no invisible characters
# or combining marks,
# any Unicode space is a space, any dash is a hyphen). Inside an expression a space or hyphen
# matches any run of spaces and hyphens, or nothing, and the last word accepts a plural.
# Rule 6: safety claims and NOAEL statements.
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
    "NOAEL",
    "no observed adverse effect level",
)
# Rule 7: study terms that must go in as references, and wording that is never used.
# Every text value of an Observation in the ledger is also a study term (see _ledger_terms).
STUDY_TERMS = (
    "PDS2014",
    "rat",
    "Sprague-Dawley",
    "oral gavage",
    "gavage",
)
WORDING_LIST = (
    "lost",
    "lose",
    "losing",
    "weight loss",
    "loss of weight",
    "loss of body weight",
)
# Text values the code itself places on purpose as fixed vocabulary, so the model may write them.
VOCABULARY_KEYS = frozenset({"status", "wording", "screen_rule"})
# Ledger values shorter than this many letters (sex codes, group numbers) are not study terms:
# one or two letters would block ordinary words; three keeps tissues such as EYE.
MIN_TERM_LETTERS = 3
# Stands for a placed value in the text the model wrote (no digit, letter or space).
REF_MARK = "\ue000"
# Rule 3 on text placed by a reference: these fields hold identifiers and group labels whose
# legitimate content carries digits (study id "PDS2014", animal id, set code, "400 mg/kg" in a
# group label). Any other text value cited by a reference with a number is blocked by rule 3.
# In a label the only number accepted is a dose with its unit ("400 mg/kg").
STRUCTURAL_FIELDS = frozenset({"study_id", "usubjid", "setcd", "label"})
DOSE_UNITS = r"(?:[muµ]?g|mL)/kg(?:/(?:day|d))?"
DOSE_WITH_UNIT = re.compile(rf"(?<![\w.])\d[\d.,]*\s*{DOSE_UNITS}(?![\w/])", re.IGNORECASE)
# Abbreviations whose full stop does not end a sentence (rule 1).
ABBREVIATIONS = re.compile(r"(?<!\w)(?:e\.g\.|i\.e\.|vs\.|approx\.|etc\.|cf\.)", re.IGNORECASE)
# A sentence end (after NFKC, so full-width and ellipsis marks are already ASCII): a run of
# ! ? or an ellipsis, then anything; or a full stop, then a space and anything, or no space and a
# capital (or a placed value), with closing quotes or brackets allowed in between.
SENTENCE_END = re.compile(
    r"""(?:(?:[!?]+|\.{2,})["')\]]*(?:\s+\S|[^\s"')\]])"""
    r"""|\.["')\]]*(?:\s+\S|[A-Z\ue000]))"""
)
# Characters with no visible form that are not format characters (Cf) and survive NFKC
# (the Hangul fillers and the blank braille cell); combining marks (Mn, Me) are dropped too.
INVISIBLE = frozenset("\u115f\u1160\u3164\uffa0\u2800")
# A value that is a unit (mg/kg), not a study term.
UNIT = re.compile(r"[A-Za-z]+(?:/[A-Za-z]+)+")
MAX_PERMUTED_WORDS = 4

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


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    kept = (
        ch
        for ch in text
        if unicodedata.category(ch) not in ("Cf", "Mn", "Me") and ch not in INVISIBLE
    )
    return "".join(
        " " if ch.isspace() else "-" if unicodedata.category(ch) == "Pd" or ch == "\u2212" else ch
        for ch in kept
    )


def _expression(expression: str) -> str:
    words = [word for word in re.split(r"[\s-]+", expression) if word]
    return r"[\s-]*".join(re.escape(word) for word in words) + "(?:e?s)?"


def _pattern(expressions: Iterator[str] | tuple[str, ...]) -> re.Pattern[str]:
    ordered = sorted(set(expressions), key=len, reverse=True)
    alternatives = "|".join(_expression(e) for e in ordered)
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


SAFETY_PATTERN = _pattern(SAFETY_EXPRESSIONS)
WORDING_PATTERN = _pattern(WORDING_LIST)


def _text_values(value: Any, key: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for name, item in value.items():
            if name not in VOCABULARY_KEYS:
                yield from _text_values(item, str(name))
    elif isinstance(value, list):
        for item in value:
            yield from _text_values(item, key)
    elif isinstance(value, str):
        yield key, value


def _ledger_terms(ledger: ObservationLedger) -> set[str]:
    """Text values of the ledger's Observations (tissues, findings, labels...) as study terms."""
    terms: set[str] = set()
    for observation in ledger.observations:
        for key, text in _text_values(observation.values):
            if key.endswith("unit") or UNIT.fullmatch(text.strip()):
                continue  # units (mg/kg) are not study terms
            candidates = [text] if key == "label" else [text, *text.split(",")]
            terms.update(
                c.strip() for c in candidates if sum(ch.isalpha() for ch in c) >= MIN_TERM_LETTERS
            )
    for term in list(terms):  # the same words in any order ("Atrophy fat" and "fat atrophy")
        words = [w for w in re.split(r"[\s,;-]+", term) if w]
        if 2 <= len(words) <= MAX_PERMUTED_WORDS:
            terms.update(" ".join(order) for order in itertools.permutations(words))
    return terms


def _refs(sentence: Sentence) -> list[ValueRef]:
    return [part for part in sentence.parts if isinstance(part, ValueRef)]


def _model_text(sentence: Sentence) -> str:
    """What the model wrote, joined as the renderer joins it, with a mark where a value goes."""
    return render_parts(sentence, lambda ref: REF_MARK)


def _ends_a_sentence(written: str) -> bool:
    text = _normalize(written).replace("。", "!")  # ideographic full stop
    text = ABBREVIATIONS.sub(lambda m: m.group(0).replace(".", ""), text)
    return bool(SENTENCE_END.search(text))


def _placed_text_has_number(sentence: Sentence, ledger: ObservationLedger) -> bool:
    """A number inside text that a reference places (rule 3), except in structural fields."""
    for ref in _refs(sentence):
        try:
            value = ledger.resolve(ref)
        except UnresolvedRef:
            continue
        if not isinstance(value, str):
            continue
        name = next((s for s in reversed(ref.field.split(".")) if not s.isdigit()), "")
        if name in STRUCTURAL_FIELDS:
            value = DOSE_WITH_UNIT.sub("", value) if name == "label" else ""
        if _has_number(value):
            return True
    return False


def _joined(texts: list[str]) -> tuple[str, list[int]]:
    """Normalize each text and join them with a space, as the renderer does; return the start
    offset of each text in the joined string."""
    normalized = [_normalize(t) for t in texts]
    starts: list[int] = []
    position = 0
    for item in normalized:
        starts.append(position)
        position += len(item) + 1
    return " ".join(normalized), starts


def _search_final(
    pattern: re.Pattern[str], texts: list[str]
) -> Iterator[tuple[int, re.Match[str]]]:
    """Matches of the pattern in the final text; each yields the sentence where it starts."""
    joined, starts = _joined(texts)
    seen: set[int] = set()
    for match in pattern.finditer(joined):
        index = max(i for i, start in enumerate(starts) if start <= match.start())
        if index not in seen:
            seen.add(index)
            yield index, match


def _has_number(text: str) -> bool:
    return any(unicodedata.category(ch).startswith("N") for ch in text)


def _is_incidence_count(ref: ValueRef) -> bool:
    return ref.field.rsplit(".", 1)[-1] == "affected"


def _has_denominator(ref: ValueRef, refs: list[ValueRef]) -> bool:
    wanted = f"{ref.field[: -len('affected')]}examined"
    return any(other.obs_id == ref.obs_id and other.field == wanted for other in refs)


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

    written = [_model_text(sentence) for sentence in sentences]
    rendered: list[str] = []
    errors: dict[int, str] = {}
    for index, sentence in enumerate(sentences):
        try:
            rendered.append(render_sentence(sentence, ledger))
        except UnresolvedRef as error:
            rendered.append(written[index].replace(REF_MARK, ""))
            errors[index] = str(error)
    for index, sentence in enumerate(sentences):  # rule 1, on the model text and the final text
        if not _refs(sentence):
            fail(1, index)
        elif _ends_a_sentence(written[index]) or (
            index not in errors and _ends_a_sentence(rendered[index])
        ):
            fail(1, index, "one Sentence must be one sentence, each with its own reference")
    for index, detail in errors.items():  # rule 2
        fail(2, index, detail)
    for index in range(len(sentences)):  # rule 3
        if _has_number(written[index]) or _placed_text_has_number(sentences[index], ledger):
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
    for index, match in _search_final(SAFETY_PATTERN, rendered):  # rule 6, final rendered text
        fail(6, index, f'"{match.group(0)}"')
    study_pattern = _pattern((*STUDY_TERMS, *_ledger_terms(ledger)))
    by_hand = dict(_search_final(study_pattern, written))  # rule 7: study terms by hand
    wording = dict(_search_final(WORDING_PATTERN, rendered))  # and wording in the final text
    for index in sorted(by_hand.keys() | wording.keys()):
        match = by_hand.get(index) or wording[index]
        fail(7, index, f'"{match.group(0)}"')
    if failures:
        return Verdict(failures=failures)
    return Verdict(text=render(sentences, ledger))
