"""The nonclinical summary workflow: gather -> draft -> await_decisions -> verify_final ->
judge -> await_approval -> approve, on a LangGraph graph with a SQLite checkpointer and two pauses.

The model drafts once; code places every number, every quotation and every decision. People
resume the graph at the two pauses: with decisions (and the sexes whose NOAEL they confirm), then
with an approval. `verify_final` is pure so the API can recompute without a model call.
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any, TypedDict

import yaml
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, create_model

from cairn.content import DecisionRef, ObservationLedger, QuoteRef, Sentence, Text, ValueRef
from cairn.decisions import Decision, apply_decisions, noael_sentence
from cairn.gateway import LLMGateway
from cairn.judge import not_judged, replay_judge
from cairn.loop import _has_digit, _shown, strictify
from cairn.observation import Observation, check_build
from cairn.recording import RecordingKey, tool_schema_hash
from cairn.render import render_sentence
from cairn.tools import REGISTRY, call_tool
from cairn.verify import Verdict, data_quality_note, verify

DRAFT_TOOL = "write_draft"
STEPS = ("gather", "draft", "await_decisions", "verify_final", "judge", "await_approval", "approve")
QUERIES_PATH = Path(__file__).parents[2] / "data" / "guidance" / "fixed_queries.json"
WORKFLOWS_DIR = Path(__file__).parents[2] / "workflows"


class WorkflowError(ValueError):
    """A workflow file that cannot be loaded; the message names the file and the problem."""


class GatherCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    arguments: dict[str, Any] = {}


class QualityNote(BaseModel):
    """The fixed data-quality sentence that code appends to a section."""

    model_config = ConfigDict(extra="forbid")

    section: str
    obs: str


class Workflow(BaseModel):
    """A workflow as its YAML file says it: the steps, the pauses, what to gather and draft."""

    model_config = ConfigDict(extra="forbid")

    name: str
    steps: list[str]
    pauses: list[str]
    gather: list[GatherCall]  # study tools, in order: ledger IDs O1..On
    guidance: list[str] = []  # fixed queries searched after the tools (ledger IDs go on)
    prompt: str  # path of the drafting prompt, relative to the workflows folder
    prompt_version: str
    recording: str  # the question ID of the draft recording
    sections: list[str]  # in order; the model drafts all of them but "noael", which code writes
    quality_note: QualityNote | None = None

    def validate_content(self) -> None:
        if unknown := [step for step in self.steps if step not in STEPS]:
            raise ValueError(f"unknown step {unknown[0]}; known steps: {', '.join(STEPS)}")
        if unknown := [step for step in self.pauses if step not in self.steps]:
            raise ValueError(f"pause {unknown[0]} is not one of the steps")
        if unknown := [c.tool for c in self.gather if c.tool not in REGISTRY]:
            raise ValueError(f"unknown tool {unknown[0]}; known tools: {', '.join(REGISTRY)}")
        if self.quality_note and self.quality_note.section not in self.sections:
            raise ValueError(f"quality note section {self.quality_note.section} is not a section")

    @property
    def drafted(self) -> list[str]:
        return [name for name in self.sections if name != "noael"]

    @property
    def prompt_text(self) -> str:
        return (WORKFLOWS_DIR / self.prompt).read_text(encoding="utf-8")


def load_workflow(name: str, directory: Path = WORKFLOWS_DIR) -> Workflow:
    """Read `<name>.yaml` into a Workflow, or raise WorkflowError saying what is wrong."""
    path = directory / f"{name}.yaml"
    try:
        workflow = Workflow.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        workflow.validate_content()
    except (OSError, yaml.YAMLError, ValidationError, ValueError) as error:
        raise WorkflowError(f"{path.name}: {error}") from error
    return workflow


NONCLINICAL_SUMMARY = load_workflow("nonclinical-summary")
DRAFT_ID = NONCLINICAL_SUMMARY.recording
DRAFT_PROMPT_VERSION = NONCLINICAL_SUMMARY.prompt_version
SECTIONS = tuple(NONCLINICAL_SUMMARY.sections)
TK_OBS = "O5"


# The draft schema: like the question loop's, but a part may also point to a decision slot.
DraftPart = Annotated[Text | ValueRef | QuoteRef | DecisionRef, Field(discriminator="type")]


class DraftSentence(Sentence):
    parts: list[DraftPart]


def draft_output(workflow: Workflow) -> type[BaseModel]:
    """The draft schema: one list of sentences per section the model writes."""
    fields: Any = {name: (list[DraftSentence], ...) for name in workflow.drafted}
    return create_model("DraftOutput", **fields)


def draft_tool(workflow: Workflow = NONCLINICAL_SUMMARY) -> dict[str, Any]:
    return {
        "name": DRAFT_TOOL,
        "description": "Write the design, findings and toxicokinetics sections of the draft.",
        "strict": True,
        "input_schema": strictify(draft_output(workflow).model_json_schema()),
    }


def draft_schema_hash(workflow: Workflow = NONCLINICAL_SUMMARY) -> str:
    return tool_schema_hash([draft_tool(workflow)])


def draft_key(model: str, workflow: Workflow = NONCLINICAL_SUMMARY) -> RecordingKey:
    return RecordingKey(
        workflow.recording, workflow.prompt_version, draft_schema_hash(workflow), model
    )


class State(TypedDict, total=False):
    author: str
    observations: list[dict[str, Any]]  # Observation dumps, in ledger order O1..O5
    guidance: list[dict[str, Any]]  # search_guidance results for NS1 and NS2
    sections: dict[str, list[dict[str, Any]]]  # section name to Sentence dumps
    decisions: list[dict[str, Any]]
    confirmed: list[str]  # sexes whose NOAEL a person confirmed
    final: dict[str, Any]  # verdict of verify_final: ok, text, failures
    judge: list[dict[str, str]]  # one warning-only verdict per sentence of the final text
    approved_by: str


def build_ledger(state: State) -> ObservationLedger:
    ledger = ObservationLedger()
    for dump in state.get("observations", []):
        ledger.add(Observation.model_validate(dump))
    for result in state.get("guidance", []):
        ledger.add_guidance(result)
    return ledger


def sections_of(state: State, workflow: Workflow = NONCLINICAL_SUMMARY) -> list[Sentence]:
    adapter = TypeAdapter(list[Sentence])
    sections = state.get("sections", {})
    return [
        s for name in workflow.sections for s in adapter.validate_python(sections.get(name, []))
    ]


def final_ledger(state: State) -> ObservationLedger:
    """The ledger with the decisions and confirmations applied, as the final text is checked."""
    ledger = build_ledger(state)
    decisions = [Decision.model_validate(d) for d in state.get("decisions", [])]
    apply_decisions(ledger, decisions, frozenset(state.get("confirmed", [])))
    return ledger


def verify_final(state: State, workflow: Workflow = NONCLINICAL_SUMMARY) -> Verdict:
    """Pure: the verdict on the draft once the decisions and confirmations are applied."""
    return verify(sections_of(state, workflow), final_ledger(state))


def shown_facts(ledger: ObservationLedger, obs_ids: Iterable[str]) -> str:
    """The Observations as the judge sees them, one line each."""
    return "\n".join(_shown(obs_id, ledger.get(obs_id)) for obs_id in dict.fromkeys(obs_ids))


def final_sentences(state: State) -> list[tuple[str, str]]:
    """Each sentence of the final text with the facts of the Observations it cites."""
    ledger = final_ledger(state)
    return [
        (
            render_sentence(sentence, ledger),
            shown_facts(ledger, (p.obs_id for p in sentence.parts if isinstance(p, ValueRef))),
        )
        for sentence in sections_of(state)
    ]


def gather_state(workflow: Workflow = NONCLINICAL_SUMMARY) -> State:
    """Run the workflow's study tools in order (ledger IDs O1..) and its guidance searches."""
    check_build()
    queries = {q["id"]: q["query"] for q in json.loads(QUERIES_PATH.read_text("utf-8"))["queries"]}
    return {
        "observations": [call_tool(c.tool, c.arguments) for c in workflow.gather],
        "guidance": [
            call_tool("search_guidance", {"query": queries[q]}) for q in workflow.guidance
        ],
    }


def slot_ids(state: State) -> list[str]:
    ledger = build_ledger(state)
    apply_decisions(ledger, [])
    return [slot for slot in ledger.slots if slot.startswith("D")]


def draft_sections(
    state: State, gateway: LLMGateway, model: str, workflow: Workflow = NONCLINICAL_SUMMARY
) -> dict[str, list[dict[str, Any]]]:
    """One model call forced to write_draft; code adds the NOAEL section and the quality note."""
    ledger = build_ledger(state)
    shown = "\n".join(_shown(obs_id, ledger.get(obs_id)) for obs_id in ledger.ids)
    message = f"Tool results:\n{shown}"
    if "await_decisions" in workflow.steps:
        message += f"\n\nDecision slots, in order: {', '.join(slot_ids(state))}"
    reply = gateway.create(
        model,
        [{"role": "user", "content": message}],
        system=workflow.prompt_text,
        tools=[draft_tool(workflow)],
        tool_choice={"type": "tool", "name": DRAFT_TOOL},
    )
    uses = [b for b in reply.content if b.get("type") == "tool_use" and b["name"] == DRAFT_TOOL]
    if not uses:
        raise ValueError(f"the model did not write a draft: {reply.message or reply.stop_reason}")
    out = draft_output(workflow).model_validate(uses[0]["input"])
    written: dict[str, list[Sentence]] = {name: [*getattr(out, name)] for name in workflow.drafted}
    if _has_digit([s for items in written.values() for s in items]):
        raise ValueError("the model wrote a digit; rejected before rendering")
    if note := workflow.quality_note:
        written[note.section].append(data_quality_note(note.obs))
    if "noael" in workflow.sections:
        written["noael"] = [noael_sentence("F"), noael_sentence("M")]
    return {name: [s.model_dump(mode="json") for s in written[name]] for name in workflow.sections}


def build_graph(
    gateway: LLMGateway,
    model: str,
    checkpointer: BaseCheckpointSaver[Any],
    workflow: Workflow = NONCLINICAL_SUMMARY,
    judge_dir: Path | None = None,
) -> Any:
    """Compile the workflow; the pauses are `interrupt` calls resumed with `Command(resume=...)`.

    The judge node replays the recordings in `judge_dir` and never changes `final`.
    """

    async def gather(state: State) -> State:
        return gather_state(workflow)

    async def draft(state: State) -> State:
        return {"sections": draft_sections(state, gateway, model, workflow)}

    async def await_decisions(state: State) -> State:
        answer = interrupt({"waiting": "decisions", "slots": slot_ids(state)})
        return {"decisions": answer["decisions"], "confirmed": answer.get("confirmed", [])}

    async def verify_node(state: State) -> State:
        verdict = verify_final(state, workflow)
        failures = [str(f) for f in verdict.failures]
        return {"final": {"ok": verdict.ok, "text": verdict.text, "failures": failures}}

    async def judge_node(state: State) -> State:
        if not state["final"]["ok"]:
            return {"judge": []}
        return {
            "judge": [
                replay_judge(judge_dir, text, facts) if judge_dir else not_judged(text, facts)
                for text, facts in final_sentences(state)
            ]
        }

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
        "judge": judge_node,
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
