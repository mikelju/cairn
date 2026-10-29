"""Laptop-only commands that can reach Bedrock: ask, record and smoke.

Only the gated live Explore route (`web/explore_live.py`) imports this module (D8, phase 06).
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from cairn.gateway import (
    DEFAULT_MODEL,
    MAX_TOKENS,
    MODEL_PROFILES,
    REGION,
    LLMGateway,
    Mode,
    Status,
    build_client,
)
from cairn.judge import (
    EXAMPLE_OBS,
    EXAMPLE_SENTENCE,
    JUDGE_MAX_TOKENS,
    JUDGE_MODEL,
    JUDGE_PROMPT_VERSION,
    JUDGE_TOOL,
    KAPPA_PATH,
    NOT_JUDGED,
    RECORDING_PATTERN,
    judge_key,
    judge_sentence,
    kappa,
)
from cairn.judge_cases import load_cases
from cairn.loop import MAX_CALLS, PROMPT, PROMPT_VERSION, LoopResult, LoopStatus, ask, schema_hash
from cairn.loop import tool_definitions as loop_tools
from cairn.pricing import call_cost
from cairn.questions import QUESTIONS
from cairn.recording import (
    RecordingClient,
    RecordingKey,
    ReplayClient,
    recorded_model,
    total_cost,
)
from cairn.workflow import (
    draft_key,
    draft_sections,
    final_sentences,
    gather_state,
    shown_facts,
    verify_final,
)

BUDGET_USD = 10.0  # smoke
RECORD_BUDGET_USD = 5.0  # phase ceiling (O5, D107): counts what is already recorded
# Ceiling for one model call: a generous prompt size and the largest reply the gateway allows.
CEILING_INPUT_TOKENS = 20_000
CEILING_OUTPUT_TOKENS = MAX_TOKENS
SMOKE_CALLS_PER_PROFILE = 3
SMOKE_MAX_TOKENS = 512
SMOKE_PATH = Path("docs/adr/evidence/bedrock-smoke.json")


def make_client(mode: Mode) -> Any:
    """Build the real Bedrock client; tests replace this with a fake."""
    return build_client(mode)


def call_ceiling(model: str) -> float:
    return call_cost(model, CEILING_INPUT_TOKENS, CEILING_OUTPUT_TOKENS)


def record_ceiling(model: str, count: int) -> float:
    return count * MAX_CALLS * call_ceiling(model)


def recorded_spend(directory: Path, pattern: str = "*.json") -> float:
    """Spend already kept in the recordings of a folder (fixtures carry no cost and count zero)."""
    total = 0.0
    for path in sorted(directory.glob(pattern)) if directory.is_dir() else []:
        try:
            total += total_cost(json.loads(path.read_text(encoding="utf-8"))) or 0.0
        except (ValueError, KeyError, TypeError):  # not a recording: it carries no spend
            continue
    return total


def smoke_ceiling() -> float:
    return sum(call_ceiling(model) for model in MODEL_PROFILES) * SMOKE_CALLS_PER_PROFILE


def question_text(question: str) -> tuple[str, str]:
    """Return (question id, text); a known ID maps to its predefined text."""
    if question.upper() in QUESTIONS:
        return question.upper(), QUESTIONS[question.upper()]
    return "", question


def ask_replay(question_id: str, directory: Path, model: str) -> LoopResult:
    key = RecordingKey(question_id, PROMPT_VERSION, schema_hash(), model)
    client = ReplayClient.load(directory, key)
    return ask(QUESTIONS[question_id], LLMGateway(Mode.REPLAY, client=client), model)


def ask_live(text: str, model: str) -> LoopResult:
    return ask(text, LLMGateway(Mode.LIVE, client=make_client(Mode.LIVE)), model)


# Outcomes worth keeping as a recording; a truncated, capped or failed run is not saved.
SAVED_STATUSES = (LoopStatus.ANSWERED, LoopStatus.DECLINED, LoopStatus.REJECTED)


@dataclass
class RecordReport:
    saved: list[Path] = field(default_factory=list)
    spent: float = 0.0
    stopped: str = ""
    outcomes: dict[str, str] = field(default_factory=dict)

    @property
    def unsaved(self) -> list[str]:
        saved = {path.stem.upper() for path in self.saved}
        return [question for question in self.outcomes if question not in saved]


def record_questions(
    ids: list[str],
    directory: Path,
    model: str,
    budget: float = RECORD_BUDGET_USD,
    spent: float = 0.0,
) -> RecordReport:
    """Record each question; stop before the next could pass the budget, `spent` included."""
    report = RecordReport(spent=spent)
    ids = list(dict.fromkeys(ids))
    step = MAX_CALLS * call_ceiling(model)
    for question_id in ids:
        if report.spent + step > budget:
            report.stopped = f"stopped before {question_id}: ceiling would pass {budget:.2f} USD"
            break
        key = RecordingKey(question_id, PROMPT_VERSION, schema_hash(), model)
        recorder: RecordingClient | None = None
        try:
            recorder = RecordingClient(make_client(Mode.RECORD), key, REGION)
            result = ask(QUESTIONS[question_id], LLMGateway(Mode.RECORD, client=recorder), model)
        except Exception as error:  # keep what is saved, report the spending and stop
            if recorder is not None:
                report.spent += total_cost({"calls": recorder.calls}) or 0.0
            report.outcomes[question_id] = f"{type(error).__name__}: {error}"
            report.stopped = f"error: {question_id}: {report.outcomes[question_id]}"
            break
        report.spent += total_cost({"calls": recorder.calls}) or 0.0
        report.outcomes[question_id] = result.status.value
        if result.status in SAVED_STATUSES:
            report.saved.append(recorder.save(directory))
    return report


DRAFT_BUDGET_USD = 2.0  # decision O1 of phase 04


def record_draft(directory: Path, model: str) -> Path:
    """Record the one draft call; save only if the example decisions, confirmed, verify green."""
    from cairn.decisions import enumerate_slots, example_decisions
    from cairn.workflow import build_ledger

    state = gather_state()
    recorder = RecordingClient(make_client(Mode.RECORD), draft_key(model), REGION)
    state["sections"] = draft_sections(state, LLMGateway(Mode.RECORD, client=recorder), model)
    slots = enumerate_slots(build_ledger(state))
    state["decisions"] = [
        d.model_dump() for d in example_decisions(slots, "Recorder", date.today().isoformat())
    ]
    state["confirmed"] = ["F", "M"]
    verdict = verify_final(state)
    if not verdict.ok:
        raise ValueError("the draft fails the rules: " + "; ".join(map(str, verdict.failures)))
    return recorder.save(directory)


JUDGE_BUDGET_USD = 2.0  # decision O1 of phase 05, for all the judge recordings kept
JUDGE_CEILING_INPUT_TOKENS = 4_000  # the longest cited Observation plus the prompt, with room
KAPPA_THRESHOLD = 0.70  # decision O2


def judge_step(model: str) -> float:
    """Ceiling for one judge call: a generous prompt and the reply cap."""
    return call_cost(model, JUDGE_CEILING_INPUT_TOKENS, JUDGE_MAX_TOKENS)


@dataclass
class JudgeInputs:
    """What the judge is recorded on: (sentence, facts) pairs, and the E5 cases among them."""

    items: list[tuple[str, str]]
    cases: list[dict[str, Any]]


def judge_inputs(cases_path: Path, draft_dir: Path) -> JudgeInputs:
    """The E5 cases, the draft sentences under the example decisions and the EXAMPLE sentence."""
    from cairn.decisions import enumerate_slots, example_decisions
    from cairn.workflow import build_ledger

    state = gather_state()
    ledger = build_ledger(state)
    cases = load_cases(cases_path)
    items = [(c["sentence"], shown_facts(ledger, c["obs"])) for c in cases]
    model = recorded_model(draft_dir, "DRAFT", DEFAULT_MODEL)
    client = ReplayClient.load(draft_dir, draft_key(model))
    state["sections"] = draft_sections(state, LLMGateway(Mode.REPLAY, client=client), model)
    slots = enumerate_slots(ledger)
    decisions = example_decisions(slots, "Recorder", date.today().isoformat())
    state["decisions"] = [d.model_dump() for d in decisions]
    state["confirmed"] = ["F", "M"]
    items += final_sentences(state)
    items.append((EXAMPLE_SENTENCE, shown_facts(ledger, EXAMPLE_OBS)))
    return JudgeInputs(list(dict.fromkeys(items)), cases)


@dataclass
class JudgeReport:
    saved: int = 0
    spent: float = 0.0
    stopped: str = ""
    kappa: float | None = None
    verdicts: dict[str, str] = field(default_factory=dict)  # sentence to verdict


def record_judge(
    inputs: JudgeInputs,
    directory: Path,
    model: str = JUDGE_MODEL,
    result_path: Path = KAPPA_PATH,
    budget: float = JUDGE_BUDGET_USD,
) -> JudgeReport:
    """Record one judge call per sentence; stop before a call could pass the budget.

    The budget counts the judge recordings already kept. When every E5 case got a verdict the
    kappa against the labels is written to `result_path`.
    """
    report = JudgeReport(spent=recorded_spend(directory, RECORDING_PATTERN))
    started = report.spent
    for sentence, facts in inputs.items:
        if report.spent + judge_step(model) > budget:
            report.stopped = f"stopped: ceiling would pass {budget:.2f} USD"
            break
        recorder = RecordingClient(
            make_client(Mode.RECORD), judge_key(sentence, facts, model), REGION
        )
        try:
            result = judge_sentence(
                LLMGateway(Mode.RECORD, client=recorder), sentence, facts, model
            )
        except Exception as error:  # keep what is saved, report the spending and stop
            report.spent += total_cost({"calls": recorder.calls}) or 0.0
            report.stopped = f"error: {type(error).__name__}: {error}"
            break
        report.spent += total_cost({"calls": recorder.calls}) or 0.0
        report.verdicts[sentence] = result["verdict"]
        if report.spent + started > budget:  # the real cost passed the ceiling: keep nothing more
            report.stopped = f"stopped: spend passed {budget:.2f} USD, this call is not saved"
            break
        if result["verdict"] != NOT_JUDGED:
            recorder.save(directory)
            report.saved += 1
    report.spent -= started  # this run only
    cases = inputs.cases
    predicted = [report.verdicts.get(c["sentence"], NOT_JUDGED) for c in cases]
    if NOT_JUDGED not in predicted:
        report.kappa = kappa([_label(c["label"]) for c in cases], predicted)
        write_kappa(result_path, model, len(cases), report.kappa)
    return report


def _label(label: str) -> str:
    return "supported" if label == "faithful" else "overstated"


def write_kappa(path: Path, model: str, n: int, value: float) -> None:
    """The result the judge panel reads: judge, prompt version, n, kappa and the label source."""
    data = {
        "judge": model,
        "prompt_version": JUDGE_PROMPT_VERSION,
        "n": n,
        "kappa": round(value, 4),
        "threshold": KAPPA_THRESHOLD,
        "labels": "built by code from the study findings, not by independent experts",
        "date": date.today().isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mask_account_ids(node: Any) -> Any:
    """Replace any run of 12 digits, the length of an AWS account ID, in every string."""
    if isinstance(node, str):
        return re.sub(r"\d{12}", "[masked]", node)
    if isinstance(node, list):
        return [mask_account_ids(item) for item in node]
    if isinstance(node, dict):
        return {key: mask_account_ids(value) for key, value in node.items()}
    return node


def _smoke_call(
    gateway: LLMGateway, model: str, name: str, messages: list[dict[str, Any]], **kwargs: Any
) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name, "error": None, "quota_error": False}
    try:
        reply = gateway.create(model, messages, max_tokens=SMOKE_MAX_TOKENS, **kwargs)
    except Exception as error:  # the smoke test records every failure and goes on
        status = getattr(error, "status_code", None)
        entry["error"] = type(error).__name__  # the message can carry an account ID or a role ARN
        entry["status_code"] = status
        entry["quota_error"] = status == 429 or "Throttl" in type(error).__name__
        return entry
    uses = [b for b in reply.content if b.get("type") == "tool_use"]
    entry.update(
        stop_reason=reply.stop_reason,
        status=reply.status.value,
        refusal=reply.status is Status.DECLINED,
        tool_calls=[b.get("name") for b in uses],
        latency_s=round(reply.latency_s, 3),
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        cost_usd=call_cost(model, reply.input_tokens, reply.output_tokens),
    )
    return entry


def smoke(path: Path = SMOKE_PATH, budget: float = BUDGET_USD) -> dict[str, Any]:
    """Send question, draft and judge prompts to each profile and write the evidence file."""
    gateway = LLMGateway(Mode.LIVE, client=make_client(Mode.LIVE))
    evidence: dict[str, Any] = {"date": date.today().isoformat(), "region": REGION, "profiles": []}
    spent = 0.0
    for model, profile in MODEL_PROFILES.items():
        record: dict[str, Any] = {"model": model, "profile": profile, "calls": []}
        evidence["profiles"].append(record)
        if spent + call_ceiling(model) * SMOKE_CALLS_PER_PROFILE > budget:
            record["skipped"] = "ceiling would pass the budget"
            continue
        question = [{"role": "user", "content": QUESTIONS["Q2"]}]
        draft = [{"role": "user", "content": "Write two plain sentences on rat liver findings."}]
        judge = [
            {
                "role": "user",
                "content": "Evidence: 3 of 10 animals had a finding. Draft: 'Some animals had "
                "a finding.' Call judge_verdict.",
            }
        ]
        calls = [
            _smoke_call(gateway, model, "question", question, system=PROMPT, tools=loop_tools()),
            _smoke_call(gateway, model, "draft", draft),
            _smoke_call(gateway, model, "judge", judge, tools=[JUDGE_TOOL]),
        ]
        record["calls"] = calls
        spent += sum(c.get("cost_usd", 0.0) for c in calls)
    evidence["total_cost_usd"] = spent
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(mask_account_ids(evidence), indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return evidence
