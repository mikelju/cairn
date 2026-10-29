"""Workflow YAML loading: the shipped files load, and a bad file is rejected with a clear error."""

from pathlib import Path

import pytest

from cairn.workflow import NONCLINICAL_SUMMARY, WorkflowError, draft_schema_hash, load_workflow

GOOD = (Path(__file__).parents[1] / "workflows" / "nonclinical-summary.yaml").read_text("utf-8")


def test_workflow_config_nonclinical_summary_loads_as_before() -> None:
    assert NONCLINICAL_SUMMARY.pauses == ["await_decisions", "await_approval"]
    assert NONCLINICAL_SUMMARY.steps[0] == "gather" and NONCLINICAL_SUMMARY.steps[-1] == "approve"
    assert draft_schema_hash().startswith("fb4485")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (GOOD.replace("[gather, draft", "[gather, ponder, draft", 1), "unknown step ponder"),
        (GOOD.replace("tool: incidence", "tool: guess"), "unknown tool guess"),
        (GOOD.replace("name: nonclinical-summary\n", ""), "name"),
        (GOOD.replace("pauses: [await_decisions", "pauses: [nowhere, await_decisions"), "nowhere"),
        ("name: [unclosed", "nonclinical-summary.yaml"),
    ],
)
def test_workflow_config_rejects_a_bad_file(tmp_path: Path, text: str, message: str) -> None:
    (tmp_path / "nonclinical-summary.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(WorkflowError, match=message):
        load_workflow("nonclinical-summary", tmp_path)
