"""The question loop: the model picks tools and drafts, the code places every number.

At most MAX_CALLS model calls per question. The model sees tool results by ID (O1, O2...)
and ends by calling write_answer with a list of Sentence made of Text and ValueRef parts.
Text with a digit is rejected before rendering; the rest is rendered and verified.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError, validate_call

from cairn.content import ObservationLedger, Sentence, Text
from cairn.gateway import DEFAULT_MODEL, GatewayResult, LLMGateway, Status
from cairn.observation import Observation
from cairn.recording import tool_schema_hash
from cairn.tools import REGISTRY, argument_problems
from cairn.verify import Verdict, verify

MAX_CALLS = 6
FIRST_TOOL = "run_job"
ANSWER_TOOL = "write_answer"
STUDY_TOOLS = ("run_job", "study_design", "incidence", "body_weight_change", "tk_summary")
PROMPT = (Path(__file__).parent / "prompts" / "question.md").read_text(encoding="utf-8")
PROMPT_VERSION = "question-5"
SENTENCES = TypeAdapter(list[Sentence])


class LoopStatus(StrEnum):
    ANSWERED = "answered"
    DECLINED = "declined"
    TRUNCATED = "truncated"
    CAPPED = "capped"
    REJECTED = "rejected"


@dataclass
class Step:
    """One tool call of the model, for the trace."""

    tool: str
    arguments: dict[str, Any]
    obs_id: str | None = None
    error: str | None = None


@dataclass
class LoopResult:
    status: LoopStatus
    question: str
    calls: int = 0
    steps: list[Step] = field(default_factory=list)
    ledger: ObservationLedger = field(default_factory=ObservationLedger)
    sentences: list[Sentence] = field(default_factory=list)
    verdict: Verdict | None = None
    rendered: str | None = None
    message: str = ""
    model: str = ""
    prompt_version: str = PROMPT_VERSION
    tool_schema_sha256: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0


# Open-ended parameters the model never needs to set; strict schemas cannot express them.
HIDDEN_PARAMETERS = {"run_job": ("params",), "incidence": ("screen",)}


def strictify(node: Any) -> Any:
    """Make a JSON schema acceptable to strict tool use.

    Every object closes with additionalProperties false and lists all its properties as
    required; titles, defaults and the discriminator are dropped and oneOf becomes anyOf.
    """
    if isinstance(node, list):
        return [strictify(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {
        key: strictify(value)
        for key, value in node.items()
        if key not in ("title", "default", "discriminator")
    }
    if "oneOf" in out:
        out["anyOf"] = out.pop("oneOf")
    if out.get("type") == "object":
        out["additionalProperties"] = False
        out["required"] = list(out.get("properties", {}))
    return out


def _definition(name: str) -> dict[str, Any]:
    function = REGISTRY[name]
    schema = TypeAdapter(function).json_schema()  # type: ignore[arg-type]
    for hidden in HIDDEN_PARAMETERS.get(name, ()):
        schema["properties"].pop(hidden, None)
    schema = strictify(schema)
    description = (function.__doc__ or name).strip().splitlines()[0]
    return {"name": name, "description": description, "strict": True, "input_schema": schema}


def tool_definitions() -> list[dict[str, Any]]:
    """Strict definitions of the study tools plus write_answer, generated from the types."""
    sentences = SENTENCES.json_schema()
    definitions = sentences.pop("$defs", {})  # references resolve from the schema root
    answer = {
        "name": ANSWER_TOOL,
        "description": "Give the final answer as a list of sentences made of text and ref parts.",
        "strict": True,
        "input_schema": strictify(
            {"type": "object", "properties": {"sentences": sentences}, "$defs": definitions}
        ),
    }
    return [*(_definition(name) for name in STUDY_TOOLS), answer]


def schema_hash() -> str:
    """The hash that keys a recording to the tool definitions sent to the model."""
    return tool_schema_hash(tool_definitions())


def _shown(obs_id: str, observation: Observation) -> str:
    """What the model sees of an Observation: its ID and values, never the internal hash ID."""
    return json.dumps(
        {
            "id": obs_id,
            "kind": observation.kind,
            "population": observation.population,
            "n_examined": observation.n_examined,
            "values": observation.values,
        },
        default=str,
    )


def _has_digit(sentences: list[Sentence]) -> bool:
    return any(
        char.isdigit()
        for sentence in sentences
        for part in sentence.parts
        if isinstance(part, Text)
        for char in part.text
    )


def _run_tool(name: str, arguments: dict[str, Any], result: LoopResult) -> tuple[str, Step, bool]:
    """Run one study tool; return the text for the model, the step and whether it failed."""
    step = Step(tool=name, arguments=arguments)
    try:
        output = validate_call(REGISTRY[name])(**arguments)
    except (ValidationError, TypeError) as error:
        step.error = argument_problems(error) if isinstance(error, ValidationError) else str(error)
        return f"invalid arguments: {step.error}", step, True
    except Exception as error:  # a failing tool goes back to the model; it counts toward the cap
        step.error = f"{type(error).__name__}: {error}"
        return f"tool error: {step.error}", step, True
    if isinstance(output, Observation):
        step.obs_id = result.ledger.add(output)
        return _shown(step.obs_id, output), step, False
    return json.dumps({"kind": output["kind"], "status": output["status"]}), step, False


def _finish_answer(arguments: dict[str, Any], result: LoopResult) -> str | None:
    """Check, render and verify the answer; return an error for the model, or None when done."""
    try:
        sentences = SENTENCES.validate_python(arguments.get("sentences"))
    except ValidationError as error:
        return f"invalid answer: {argument_problems(error)}"
    result.sentences = sentences
    if _has_digit(sentences):
        result.status = LoopStatus.REJECTED
        result.message = "the model wrote a digit; rejected before rendering"
        return None
    result.verdict = verify(sentences, result.ledger)
    result.rendered = result.verdict.text
    result.status = LoopStatus.ANSWERED
    return None


def _account(result: LoopResult, reply: GatewayResult) -> None:
    result.calls += 1
    result.input_tokens += reply.input_tokens
    result.output_tokens += reply.output_tokens
    result.latency_s += reply.latency_s


def _handle(
    use: dict[str, Any], result: LoopResult, first_done: bool
) -> tuple[str | None, str, bool]:
    """Handle one tool_use block; return (error, text for the model, answer finished)."""
    name, arguments = str(use.get("name")), dict(use.get("input") or {})
    if not first_done and name != FIRST_TOOL:
        error = f"the first tool call must be {FIRST_TOOL}"
        result.steps.append(Step(tool=name, arguments=arguments, error=error))
        return error, error, False
    if name == ANSWER_TOOL:
        problem = _finish_answer(arguments, result)
        result.steps.append(Step(tool=name, arguments=arguments, error=problem))
        return problem, problem or "", problem is None
    if name in STUDY_TOOLS:
        text, step, failed = _run_tool(name, arguments, result)
        result.steps.append(step)
        return (text if failed else None), text, False
    error = f"unknown tool {name}"
    result.steps.append(Step(tool=name, arguments=arguments, error=error))
    return error, error, False


def ask(question: str, gateway: LLMGateway, model: str = DEFAULT_MODEL) -> LoopResult:
    """Run the loop for one question over a gateway and return everything that happened."""
    tools = tool_definitions()
    result = LoopResult(
        status=LoopStatus.CAPPED,
        question=question,
        model=model,
        tool_schema_sha256=tool_schema_hash(tools),
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    first_done = False
    while result.calls < MAX_CALLS:
        reply = gateway.create(
            model, messages, system=PROMPT, tools=tools, tool_choice={"type": "auto"}
        )
        _account(result, reply)
        if reply.status is not Status.OK:
            result.status = (
                LoopStatus.DECLINED if reply.status is Status.DECLINED else LoopStatus.TRUNCATED
            )
            result.message = reply.message
            return result
        messages.append({"role": "assistant", "content": reply.content})
        uses = [block for block in reply.content if block.get("type") == "tool_use"]
        if not uses:
            result.status = LoopStatus.DECLINED
            result.message = "the model declined"
            return result
        feedback: list[dict[str, Any]] = []
        for use in uses:
            error, text, finished = _handle(use, result, first_done)
            if finished:
                return result
            first_done = first_done or (str(use.get("name")) == FIRST_TOOL and error is None)
            block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": use["id"],
                "content": text,
            }
            if error:
                block["is_error"] = True
            feedback.append(block)
        messages.append({"role": "user", "content": feedback})
    result.message = f"stopped at the cap of {MAX_CALLS} model calls"
    return result
