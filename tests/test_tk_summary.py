"""The tk_summary tool (C6). Expected values are the frozen literals."""

from cairn.observation import Observation
from cairn.tools import call_tool
from cairn.validate import mean_auctau


def test_tk_summary_naive_means_and_ratio() -> None:
    result = call_tool("tk_summary", {})
    values = result["values"]
    assert values["with_quarantined"]["n"] == 3
    assert round(values["with_quarantined"]["mean"]) == 2821
    assert values["without_quarantined"]["n"] == 2
    assert round(values["without_quarantined"]["mean"]) == 15956
    assert values["ratio_without_over_with"] == 5.7
    assert result["n_examined"] == 3
    assert "TK satellite" in result["population"]


def test_tk_summary_flags_the_quarantined_row() -> None:
    values = call_tool("tk_summary", {})["values"]
    assert values["contains_quarantined"] is True
    assert [(row["usubjid"], row["value"]) for row in values["quarantined_rows"]] == [
        ("PDS2014-0032", -23450.0)
    ]


def test_tk_summary_matches_phase_01_mean_auctau() -> None:
    from cairn.ingest import load_study
    from cairn.validate import validate_study

    frames, zeros, _ = load_study()
    with_q = mean_auctau(frames, "M", 20.0, 1.0)
    without_q = mean_auctau(validate_study(frames, zeros).clean, "M", 20.0, 1.0)
    values = call_tool("tk_summary", {})["values"]
    assert values["with_quarantined"]["n"] == with_q["n"]
    assert abs(values["with_quarantined"]["mean"] - with_q["mean"]) < 0.01
    assert values["without_quarantined"]["n"] == without_q["n"]
    assert abs(values["without_quarantined"]["mean"] - without_q["mean"]) < 0.01


def test_tk_summary_without_data_has_no_ratio() -> None:
    values = call_tool("tk_summary", {"sex": "F", "dose": 20.0, "day": 99.0})["values"]
    assert values["with_quarantined"] == {"n": 0, "mean": None}
    assert values["ratio_without_over_with"] is None
    assert values["contains_quarantined"] is False


def test_observation_tk_summary_valid_and_stable() -> None:
    first, second = call_tool("tk_summary", {}), call_tool("tk_summary", {})
    observation = Observation.model_validate(first)
    assert observation.tool.name == "tk_summary"
    assert len(observation.source_rows) == 3
    assert first["content_sha256"] == second["content_sha256"]
