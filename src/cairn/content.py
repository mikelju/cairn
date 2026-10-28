"""Typed content: model text, references to Observation fields and sentences made of both."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from cairn.observation import Observation

OBSERVATION_FIELDS = ("n_examined", "population", "kind")


class Text(BaseModel):
    """Words written by the model; the renderer passes them through as written."""

    type: Literal["text"] = "text"
    text: str


class ValueRef(BaseModel):
    """A pointer to one field of one Observation; the code places the value it points to."""

    type: Literal["ref"] = "ref"
    obs_id: str
    field: str


class QuoteRef(BaseModel):
    """A pointer to stored sentences of one guideline passage; the code copies their text."""

    type: Literal["quote"] = "quote"
    passage_id: str
    sentence_ids: list[str]


class DecisionRef(BaseModel):
    """A slot a person fills (D1.., NOAEL-F, NOAEL-M); the code places its text.

    Hidden from the JSON schema so the question loop's tool definitions, and the recordings keyed
    to them, do not change; the draft schema of phase 04 adds it back.
    """

    type: Literal["decision"] = "decision"
    slot: str


Part = Annotated[
    Text | ValueRef | QuoteRef | SkipJsonSchema[DecisionRef], Field(discriminator="type")
]


class Sentence(BaseModel):
    parts: list[Part]


class UnresolvedRef(ValueError):
    """A reference whose Observation or field does not exist, or whose value has no format."""


class ObservationLedger:
    """Holds the Observations of one run and gives them IDs O1, O2... by call order."""

    def __init__(self) -> None:
        self._observations: dict[str, Observation] = {}
        self._retrieved: dict[str, dict[str, str]] = {}
        self.slots: dict[str, str | None] = {}  # slot ID to decision text; None while empty

    def add_guidance(self, result: dict[str, Any]) -> None:
        """Record the passages a `search_guidance` result returned at or above its threshold.

        Rule 8 accepts a quotation only for a passage recorded here, with the sentence texts the
        tool returned. An abstention records nothing.
        """
        if result.get("abstained"):
            return
        for hit in result.get("hits", []):
            if hit["rerank_score"] >= result["threshold"]:
                self._retrieved[hit["passage_id"]] = {
                    s["sentence_id"]: s["text"] for s in hit["sentences"]
                }

    def place_slot(self, ref: DecisionRef, strict: bool = False) -> str:
        """The text of a filled slot, or a visible empty slot; strict raises for an empty one."""
        if ref.slot not in self.slots:
            raise UnresolvedRef(f"unknown slot {ref.slot}")
        text = self.slots[ref.slot]
        if text:
            return text
        if strict:
            raise UnresolvedRef(f"slot {ref.slot} has no decision")
        return f"[{ref.slot}: no decision yet]"

    @property
    def retrieved(self) -> dict[str, dict[str, str]]:
        """Passage ID to {sentence ID: text} for every passage retrieved in this run."""
        return {pid: dict(sentences) for pid, sentences in self._retrieved.items()}

    def add(self, observation: Observation) -> str:
        obs_id = f"O{len(self._observations) + 1}"
        self._observations[obs_id] = observation
        return obs_id

    def get(self, obs_id: str) -> Observation:
        try:
            return self._observations[obs_id]
        except KeyError:
            raise UnresolvedRef(f"unknown observation {obs_id}") from None

    @property
    def observations(self) -> list[Observation]:
        return list(self._observations.values())

    @property
    def ids(self) -> list[str]:
        return list(self._observations)

    def resolve(self, ref: ValueRef) -> Any:
        """Walk the dotted field path: dict keys and list positions, from the Observation values."""
        observation = self.get(ref.obs_id)
        field = ref.field.removeprefix("values.")  # the model sees the values under "values"
        head, *rest = field.split(".")
        if head in OBSERVATION_FIELDS:
            current: Any = getattr(observation, head)
        else:
            current = observation.values
            rest = [head, *rest]
        for step in rest:
            try:
                current = current[int(step)] if isinstance(current, list) else current[step]
            except (KeyError, IndexError, ValueError, TypeError):
                raise UnresolvedRef(f"{ref.obs_id} has no field {ref.field}") from None
        return current
