"""The body_weight_change tool (C5, C6). Expected values are the frozen literals."""

import json
from typing import Any, cast

import pytest
from pydantic import ValidationError

from cairn.body_weight import body_weight_change
from cairn.observation import Observation
from cairn.tools import call_tool


def groups_of(result: dict[str, object]) -> list[dict[str, object]]:
    values = result["values"]
    assert isinstance(values, dict)
    groups: list[dict[str, object]] = values["groups"]
    return groups


def test_body_weight_change_percent_lower_than_control_and_n() -> None:
    result = call_tool("body_weight_change", {"sex": "F"})
    groups = groups_of(result)
    assert [g["dose"] for g in groups] == [0.0, 20.0, 200.0, 400.0]
    assert [g["n"] for g in groups] == [15, 10, 10, 15]
    percent = [g["percent_lower_than_control"] for g in groups]
    assert percent[0] is None
    assert [round(float(p), 1) for p in percent[1:]] == [9.3, 17.6, 20.7]  # type: ignore[arg-type]
    assert result["n_examined"] == 50
    assert result["values"]["wording"] == "lower than control"


def test_body_weight_change_positive_mean_change_in_every_group() -> None:
    groups = groups_of(call_tool("body_weight_change", {"sex": "F"}))
    assert all(float(g["mean_change_from_baseline_g"]) > 0 for g in groups)  # type: ignore[arg-type]


def test_body_weight_change_only_one_animal_negative() -> None:
    result = call_tool("body_weight_change", {"sex": "F"})
    assert result["values"]["animals_with_negative_change"] == [
        {"usubjid": "PDS2014-0165", "dose": 400.0, "change_g": -5.3}
    ]


def test_body_weight_change_never_says_lost() -> None:
    text = json.dumps(call_tool("body_weight_change", {"sex": "F"})).lower()
    assert "lost" not in text
    assert "loss" not in text


def test_body_weight_change_main_population_leaves_out_recovery() -> None:
    result = call_tool("body_weight_change", {"sex": "F", "population": "main"})
    assert [g["n"] for g in groups_of(result)] == [10, 10, 10, 10]
    assert "recovery animals excluded" in result["population"]


def test_observation_body_weight_valid_and_stable() -> None:
    first, second = call_tool("body_weight_change", {}), call_tool("body_weight_change", {})
    observation = Observation.model_validate(first)
    assert observation.tool.name == "body_weight_change"
    assert observation.values["sex"] == "F"
    assert len(observation.source_rows) == 50
    assert first["content_sha256"] == second["content_sha256"]


@pytest.mark.parametrize("population", ["tk", "all", "tk_satellites", "main_and_tk"])
def test_tool_rejects_tk_in_body_weight(population: str) -> None:
    with pytest.raises(ValidationError):
        call_tool("body_weight_change", {"sex": "F", "population": population})


def test_tool_rejects_tk_in_body_weight_schema() -> None:
    from pydantic import TypeAdapter

    schema = TypeAdapter(cast(Any, body_weight_change)).json_schema()
    options = schema["properties"]["population"]["enum"]
    assert options == ["main_and_recovery", "main"]
    assert not any("tk" in option for option in options)
