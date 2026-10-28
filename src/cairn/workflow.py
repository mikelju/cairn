"""The nonclinical summary workflow: gather -> draft -> await_decisions -> verify_final ->
await_approval -> approve, on a LangGraph graph with a SQLite checkpointer and two pauses.

The model drafts once; code places every number, every quotation and every decision. People
resume the graph at the two pauses: with decisions (and the sexes whose NOAEL they confirm), then
with an approval. `verify_final` is pure so the API can recompute without a model call.
"""

import json
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field, TypeAdapter

from cairn.body_weight import body_weight_change
from cairn.content import DecisionRef, ObservationLedger, QuoteRef, Sentence, Text, ValueRef
from cairn.decisions import Decision, apply_decisions, noael_sentence
from cairn.gateway import LLMGateway
from cairn.incidence import incidence
from cairn.loop import _has_digit, _shown, strictify
from cairn.observation import Observation, check_build
from cairn.recording import RecordingKey, tool_schema_hash
from cairn.tk_summary import tk_summary
from cairn.tools import call_tool, study_design
from cairn.verify import Verdict, data_quality_note, verify

DRAFT_ID = "DRAFT"
DRAFT_TOOL = "write_draft"
DRAFT_PROMPT = (Path(__file__).parent / "prompts" / "draft.md").read_text(encoding="utf-8")
DRAFT_PROMPT_VERSION = "draft-1"
SECTIONS = ("design", "findings", "tk", "noael")
TK_OBS = "O5"
GUIDANCE_QUERIES = ("NS1", "NS2")
QUERIES_PATH = Path(__file__).parents[2] / "data" / "guidance" / "fixed_queries.json"


class Workflow(BaseModel):
    """The shape of a workflow: the steps in order and the steps that wait for a person."""

    name: str
    steps: list[str]
    pauses: list[str]


NONCLINICAL_SUMMARY = Workflow(
    name="nonclinical-summary",
    steps=["gather", "draft", "await_decisions", "verify_final", "await_approval", "approve"],
    pauses=["await_decisions", "await_approval"],
)


# The draft schema: like the question loop's, but a part may also point to a decision slot.
DraftPart = Annotated[Text | ValueRef | QuoteRef | DecisionRef, Field(discriminator="type")]


class DraftSentence(Sentence):
    parts: list[DraftPart]


class DraftOutput(BaseModel):
    design: list[DraftSentence]
    findings: list[DraftSentence]
    tk: list[DraftSentence]


def draft_tool() -> dict[str, Any]:
    return {
        "name": DRAFT_TOOL,
        "description": "Write the design, findings and toxicokinetics sections of the draft.",
        "strict": True,
        "input_schema": strictify(DraftOutput.model_json_schema()),
    }


def draft_schema_hash() -> str:
    return tool_schema_hash([draft_tool()])


def draft_key(model: str) -> RecordingKey:
    return RecordingKey(DRAFT_ID, DRAFT_PROMPT_VERSION, draft_schema_hash(), model)


class State(TypedDict, total=False):
    author: str
    observations: list[dict[str, Any]]  # Observation dumps, in ledger order O1..O5
    guidance: list[dict[str, Any]]  # search_guidance results for NS1 and NS2
    sections: dict[str, list[dict[str, Any]]]  # section name to Sentence dumps
    decisions: list[dict[str, Any]]
    confirmed: list[str]  # sexes whose NOAEL a person confirmed
    final: dict[str, Any]  # verdict of verify_final: ok, text, failures
    approved_by: str


def build_ledger(state: State) -> ObservationLedger:
    ledger = ObservationLedger()
    for dump in state.get("observations", []):
        ledger.add(Observation.model_validate(dump))
    for result in state.get("guidance", []):
        ledger.add_guidance(result)
    return ledger


def sections_of(state: State) -> list[Sentence]:
    adapter = TypeAdapter(list[Sentence])
    sections = state.get("sections", {})
    return [s for name in SECTIONS for s in adapter.validate_python(sections.get(name, []))]


def verify_final(state: State) -> Verdict:
    """Pure: the verdict on the draft once the decisions and confirmations are applied."""
    ledger = build_ledger(state)
    decisions = [Decision.model_validate(d) for d in state.get("decisions", [])]
    apply_decisions(ledger, decisions, frozenset(state.get("confirmed", [])))
    return verify(sections_of(state), ledger)


def gather_state() -> State:
    """Run the study tools in a fixed order (ledger IDs O1..O5) and the two guidance searches."""
    check_build()
    observations = [
        study_design(),
        incidence(),
        body_weight_change(sex="F"),
        body_weight_change(sex="M"),
        tk_summary(sex="M", dose=20.0, day=1.0),
    ]
    queries = {q["id"]: q["query"] for q in json.loads(QUERIES_PATH.read_text("utf-8"))["queries"]}
    return {
        "observations": [o.model_dump(mode="json") for o in observations],
        "guidance": [call_tool("search_guidance", {"query": queries[q]}) for q in GUIDANCE_QUERIES],
    }


def slot_ids(state: State) -> list[str]:
    ledger = build_ledger(state)
    apply_decisions(ledger, [])
    return [slot for slot in ledger.slots if slot.startswith("D")]


def draft_sections(
    state: State, gateway: LLMGateway, model: str
) -> dict[str, list[dict[str, Any]]]:
    """One model call forced to write_draft; code adds the NOAEL section and the quality note."""
    ledger = build_ledger(state)
    shown = "\n".join(_shown(obs_id, ledger.get(obs_id)) for obs_id in ledger.ids)
    message = f"Tool results:\n{shown}\n\nDecision slots, in order: {', '.join(slot_ids(state))}"
    reply = gateway.create(
        model,
        [{"role": "user", "content": message}],
        system=DRAFT_PROMPT,
        tools=[draft_tool()],
        tool_choice={"type": "tool", "name": DRAFT_TOOL},
    )
    uses = [b for b in reply.content if b.get("type") == "tool_use" and b["name"] == DRAFT_TOOL]
    if not uses:
        raise ValueError(f"the model did not write a draft: {reply.message or reply.stop_reason}")
    out = DraftOutput.model_validate(uses[0]["input"])
    if _has_digit([*out.design, *out.findings, *out.tk]):
        raise ValueError("the model wrote a digit; rejected before rendering")
    sections: dict[str, list[Sentence]] = {
        "design": [*out.design],
        "findings": [*out.findings],
        "tk": [*out.tk, data_quality_note(TK_OBS)],
        "noael": [noael_sentence("F"), noael_sentence("M")],
    }
    return {name: [s.model_dump(mode="json") for s in items] for name, items in sections.items()}


def build_graph(
    gateway: LLMGateway,
    model: str,
    checkpointer: BaseCheckpointSaver[Any],
    workflow: Workflow = NONCLINICAL_SUMMARY,
) -> Any:
    """Compile the workflow; the pauses are `interrupt` calls resumed with `Command(resume=...)`."""

    async def gather(state: State) -> State:
        return gather_state()

    async def draft(state: State) -> State:
        return {"sections": draft_sections(state, gateway, model)}

    async def await_decisions(state: State) -> State:
        answer = interrupt({"waiting": "decisions", "slots": slot_ids(state)})
        return {"decisions": answer["decisions"], "confirmed": answer.get("confirmed", [])}

    async def verify_node(state: State) -> State:
        verdict = verify_final(state)
        failures = [str(f) for f in verdict.failures]
        return {"final": {"ok": verdict.ok, "text": verdict.text, "failures": failures}}

    async def await_approval(state: State) -> State:
        answer = interrupt({"waiting": "approval", "final": state["final"]})
        return {"approved_by": answer["approved_by"]}

    async def approve(state: State) -> State:
        return {}

    nodes = {
        "gather": gather,
        "draft": draft,
        "await_decisions": await_decisions,
        "verify_final": verify_node,
        "await_approval": await_approval,
        "approve": approve,
    }
    graph = StateGraph(State)
    for step in workflow.steps:
        graph.add_node(step, nodes[step])
    graph.add_edge(START, workflow.steps[0])
    for before, after in zip(workflow.steps, workflow.steps[1:], strict=False):
        graph.add_edge(before, after)
    graph.add_edge(workflow.steps[-1], END)
    return graph.compile(checkpointer=checkpointer)
