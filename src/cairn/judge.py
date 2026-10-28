"""The judge: a Sonnet reading of one sentence against the data it cites. It warns, never blocks.

One call per sentence through the gateway, forced to the strict tool `judge_verdict`. In the app
the judge only replays: a sentence with no recording, or a refused or truncated reply, is "not
judged" and never gets an invented verdict. The reason is kept only if it holds no digit.
"""

from pathlib import Path
from typing import Any

from cairn.canonical import canonical_sha256
from cairn.fetch import REPO_ROOT
from cairn.gateway import GatewayError, LLMGateway, Mode, Status
from cairn.recording import RecordingKey, ReplayClient, StaleRecording, tool_schema_hash

JUDGE_MODEL = "sonnet-4-6"  # the drafter is Opus 4.6
JUDGE_PROMPT = (Path(__file__).parent / "prompts" / "judge.md").read_text(encoding="utf-8")
JUDGE_PROMPT_VERSION = "judge-1"
JUDGE_MAX_TOKENS = 400
CATEGORIES = ("none", "causal", "certainty", "safety", "magnitude")
NOT_JUDGED = "not judged"
ITEM_PREFIX = "J-"
RECORDING_PATTERN = ITEM_PREFIX.lower() + "*.json"  # recording files are named by lowercased ID
KAPPA_PATH = (
    REPO_ROOT / "data" / "judge" / "e5_result.json"
)  # written by record-judge, read by step 5
JUDGE_TOOL = {
    "name": "judge_verdict",
    "description": "Judge whether the wording of a draft sentence is supported by the data given.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["supported", "overstated"]},
            "category": {"type": "string", "enum": list(CATEGORIES)},
            "reason": {"type": "string"},
        },
        "required": ["verdict", "category", "reason"],
        "additionalProperties": False,
    },
}
# The one overstated sentence shown as an EXAMPLE in step 5, judged from the study's incidence.
EXAMPLE_SENTENCE = "The test article caused adrenal vacuolization in females at 400 mg/kg/day."
EXAMPLE_OBS = ("O2",)


def item_id(sentence: str, facts: str) -> str:
    """The recording ID of a sentence with its data: the same inputs always map to one file."""
    return ITEM_PREFIX + canonical_sha256({"sentence": sentence, "facts": facts})[:16]


def judge_key(sentence: str, facts: str, model: str = JUDGE_MODEL) -> RecordingKey:
    return RecordingKey(
        item_id(sentence, facts), JUDGE_PROMPT_VERSION, tool_schema_hash([JUDGE_TOOL]), model
    )


def not_judged(sentence: str, facts: str) -> dict[str, str]:
    return {
        "id": item_id(sentence, facts),
        "sentence": sentence,
        "verdict": NOT_JUDGED,
        "category": "",
        "reason": "",
    }


def judge_sentence(
    gateway: LLMGateway, sentence: str, facts: str, model: str = JUDGE_MODEL
) -> dict[str, str]:
    """One verdict; a refusal, a truncation or a malformed reply gives "not judged"."""
    message = f"Data:\n{facts or '(none cited)'}\n\nSentence: {sentence}"
    reply = gateway.create(
        model,
        [{"role": "user", "content": message}],
        system=JUDGE_PROMPT,
        tools=[JUDGE_TOOL],
        tool_choice={"type": "tool", "name": JUDGE_TOOL["name"]},
        max_tokens=JUDGE_MAX_TOKENS,
    )
    result = not_judged(sentence, facts)
    uses = [
        b for b in reply.content if b.get("type") == "tool_use" and b["name"] == "judge_verdict"
    ]
    if reply.status is not Status.OK or not uses:
        return result
    verdict = uses[0]["input"]
    if verdict.get("verdict") not in ("supported", "overstated") or (
        verdict.get("category") not in CATEGORIES
    ):
        return result
    reason = str(verdict.get("reason", ""))
    result.update(
        verdict=verdict["verdict"],
        category=verdict["category"],
        reason="" if any(char.isdigit() for char in reason) else reason,
    )
    return result


def replay_judge(directory: Path, sentence: str, facts: str) -> dict[str, str]:
    """The recorded verdict of a sentence, or "not judged" when there is no current recording."""
    try:
        client = ReplayClient.load(directory, judge_key(sentence, facts))
        return judge_sentence(LLMGateway(Mode.REPLAY, client=client), sentence, facts)
    except (StaleRecording, GatewayError):
        return not_judged(sentence, facts)


def kappa(labels: list[str], predictions: list[str]) -> float:
    """Cohen's kappa of two raters over the same cases: agreement beyond chance."""
    n = len(labels)
    observed = sum(a == b for a, b in zip(labels, predictions, strict=True)) / n
    chance = sum(
        (labels.count(c) / n) * (predictions.count(c) / n) for c in {*labels, *predictions}
    )
    return 1.0 if chance == 1 else (observed - chance) / (1 - chance)


def summary(results: list[dict[str, Any]]) -> dict[str, int]:
    """Counts for the audit entry: sentences, judged, and warnings."""
    judged = [r for r in results if r["verdict"] != NOT_JUDGED]
    return {
        "sentences": len(results),
        "judged": len(judged),
        "warnings": sum(r["verdict"] == "overstated" for r in judged),
    }
