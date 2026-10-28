"""E5: the judge against 24 cases labelled by construction, offline: kappa of the recorded verdicts.

The cases are built by code from the study's findings (decision O2). Every case must have a
current recording: a changed sentence, prompt or schema leaves it without one and fails here.
The fixture recordings are hand-written; the recordings in `recordings/` count once they exist.
"""

import json
from pathlib import Path

import pytest

from cairn import judge
from cairn.judge import KAPPA_PATH
from cairn.judge_cases import CASES_PATH, build_cases, load_cases
from cairn.live import KAPPA_THRESHOLD
from cairn.workflow import build_ledger, gather_state, shown_facts

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "recordings"
REAL = ROOT / "recordings"
REAL_RECORDED = any(REAL.glob(judge.RECORDING_PATTERN))
FOLDERS = [FIXTURES, *([REAL] if REAL_RECORDED else [])]


def verdicts(directory: Path) -> tuple[list[str], list[str]]:
    """(labels, recorded verdicts) of the cases, in order."""
    ledger = build_ledger(gather_state())
    cases = load_cases()
    found = [
        judge.replay_judge(directory, c["sentence"], shown_facts(ledger, c["obs"]))["verdict"]
        for c in cases
    ]
    return ["supported" if c["label"] == "faithful" else "overstated" for c in cases], found


def test_e5_case_file_is_what_the_study_builds() -> None:
    assert load_cases() == build_cases(gather_state()), (
        "cases changed: regenerate with write_cases(gather_state()) and re-record the judge"
    )


def test_e5_has_both_labels_and_four_kinds_of_overstatement() -> None:
    cases = load_cases(CASES_PATH)
    assert len(cases) == 24
    assert {c["label"] for c in cases} == {"faithful", "overstated"}
    assert sum(c["label"] == "faithful" for c in cases) == 12
    kinds = {c["kind"] for c in cases if c["label"] == "overstated"}
    assert kinds == {"causal", "certainty", "safety", "magnitude"}
    assert all(c["kind"] == "none" for c in cases if c["label"] == "faithful")
    assert len({c["sentence"] for c in cases}) == 24


def test_e5_real_recordings_and_result_file_go_together() -> None:
    assert KAPPA_PATH.is_file() == REAL_RECORDED, (
        "data/judge/e5_result.json and the judge recordings come from one make record-judge"
    )


@pytest.mark.parametrize("directory", FOLDERS, ids=lambda d: d.parent.name + "/" + d.name)
def test_e5_kappa_of_the_recorded_judge_reaches_the_threshold(directory: Path) -> None:
    labels, found = verdicts(directory)
    assert judge.NOT_JUDGED not in found, "a case has no current recording: run make record-judge"
    value = judge.kappa(labels, found)
    assert value >= KAPPA_THRESHOLD, f"kappa {value:.3f} is under {KAPPA_THRESHOLD}"
    if directory == REAL:  # the file the panel reads says what the recordings give
        result = json.loads(KAPPA_PATH.read_text(encoding="utf-8"))
        assert (result["n"], result["kappa"]) == (len(labels), round(value, 4))
        assert result["threshold"] == KAPPA_THRESHOLD
