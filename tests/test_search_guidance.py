"""search_guidance in the registry: cached results in replay, abstention below the threshold."""

import subprocess
import sys

import pytest
from typer.testing import CliRunner

from cairn import retrieval
from cairn.cli import app as cli_app
from cairn.tools import REGISTRY, call_tool

G2 = "How does the FDA 2005 guidance define the no observed adverse effect level (NOAEL)?"


def test_search_guidance_returns_top_five_with_ranks_and_text() -> None:
    result = call_tool("search_guidance", {"query": G2})
    assert result["abstained"] is False
    assert result["message"] is None
    assert len(result["hits"]) == 5
    first = result["hits"][0]
    for key in (
        "passage_id",
        "rerank_rank",
        "rerank_score",
        "lexical_rank",
        "semantic_rank",
        "fused_rank",
        "doc",
        "section",
        "page_start",
        "text",
        "sentences",
    ):
        assert key in first
    scores = [hit["rerank_score"] for hit in result["hits"]]
    assert scores == sorted(scores, reverse=True)
    assert first["sentences"][0]["sentence_id"].startswith(first["passage_id"])


def test_search_guidance_abstains_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """A best score under the stored threshold gives no passage and the explicit message."""
    monkeypatch.setattr(retrieval, "load_threshold", lambda *a, **k: 100.0)
    result = call_tool("search_guidance", {"query": G2})
    assert result["abstained"] is True
    assert result["hits"] == []
    assert result["message"] == "no supporting passage in the library"
    assert result["threshold"] == 100.0
    assert result["best_score"] < 100.0


def test_search_guidance_replay_never_loads_the_models() -> None:
    """Run in a fresh interpreter: other tests in the session may have loaded the models."""
    code = "\n".join(
        [
            "import sys",
            "from cairn.tools import call_tool",
            f"call_tool('search_guidance', {{'query': {G2!r}}})",
            "assert 'fastembed' not in sys.modules and 'onnxruntime' not in sys.modules",
        ]
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_search_guidance_unknown_query_is_stale_in_replay() -> None:
    with pytest.raises(retrieval.StaleRetrievalCache, match="stale retrieval cache: rebuild"):
        call_tool("search_guidance", {"query": "a question nobody cached"})
    result = CliRunner().invoke(cli_app, ["search-guidance", "a question nobody cached"])
    assert result.exit_code == 1


def test_search_guidance_is_in_the_registry_and_rejects_bad_arguments() -> None:
    assert "search_guidance" in REGISTRY
    result = CliRunner().invoke(cli_app, ["search-guidance"])
    assert result.exit_code != 0
