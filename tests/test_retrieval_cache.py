"""The precomputed retrieval cache: fixed queries, recorded queries, replay without the models."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from cairn import retrieval

pytestmark = pytest.mark.usefixtures("block_sockets")


@pytest.fixture(scope="module")
def index() -> retrieval.Index:
    return retrieval.build_index()


@pytest.fixture(scope="module")
def cache() -> dict[str, list[dict[str, object]]]:
    data = json.loads(retrieval.CACHE_PATH.read_text(encoding="utf-8"))
    queries: dict[str, list[dict[str, object]]] = data["queries"]
    return queries


def test_retrieval_cache_fixed_queries_file() -> None:
    fixed = retrieval.load_fixed_queries()
    assert [q["id"] for q in fixed] == ["NS1", "NS2", "G1", "G2", "G3"]
    assert [q["used_by"] for q in fixed][:2] == ["nonclinical-summary"] * 2
    queries = [q["query"] for q in fixed]
    assert len(set(queries)) == 5
    own = {
        e["question"].casefold()
        for k in retrieval.CALIBRATION_SETS
        for e in retrieval.load_calibration()[k]
    }
    assert not own & {q.casefold() for q in queries}
    assert not re.search(r"\d{12}", json.dumps(fixed))


def test_retrieval_cache_covers_fixed_and_recorded_queries(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    wanted = {q["query"] for q in retrieval.load_fixed_queries()}
    wanted |= set(retrieval.recorded_queries(Path("recordings")))
    assert wanted <= set(cache)
    assert set(cache) == wanted, "the cache holds only the fixed and the recorded queries"


def test_retrieval_cache_recorded_queries_are_read_from_recordings(tmp_path: Path) -> None:
    call = {
        "response": {
            "content": [
                {"type": "text", "text": "thinking"},
                {"type": "tool_use", "name": "search_guidance", "input": {"query": "alpha beta"}},
                {"type": "tool_use", "name": "run_job", "input": {"kind": "validate_study"}},
            ]
        }
    }
    other = {
        "response": {
            "content": [
                {"type": "tool_use", "name": "search_guidance", "input": {"query": "alpha beta"}}
            ]
        }
    }
    (tmp_path / "g1.json").write_text(json.dumps({"calls": [call, other]}), encoding="utf-8")
    (tmp_path / "q9.json").write_text(json.dumps({"calls": []}), encoding="utf-8")
    assert retrieval.recorded_queries(tmp_path) == ["alpha beta"]


def test_retrieval_cache_equals_fresh_retrieval(
    index: retrieval.Index, cache: dict[str, list[dict[str, object]]]
) -> None:
    for query, stored in cache.items():
        fresh = index.rerank(query)
        assert [h["passage_id"] for h in stored] == [h.passage_id for h in fresh], query
        for old, new in zip(stored, fresh, strict=True):
            assert old["rerank_rank"] == new.rerank_rank
            assert (old["lexical_rank"], old["semantic_rank"], old["fused_rank"]) == (
                new.lexical_rank,
                new.semantic_rank,
                new.fused_rank,
            )
            assert old["rerank_score"] == pytest.approx(
                new.rerank_score, abs=retrieval.RERANK_TOLERANCE
            )
            assert old["fused_score"] == pytest.approx(
                new.fused_score, abs=retrieval.SCORE_TOLERANCE
            )
            assert old["lexical_score"] == pytest.approx(
                new.lexical_score, abs=retrieval.SCORE_TOLERANCE
            )
            assert old["semantic_score"] == pytest.approx(
                new.semantic_score, abs=retrieval.SCORE_TOLERANCE
            )


def test_retrieval_cache_lookup_returns_guidance_without_the_models() -> None:
    query = retrieval.load_fixed_queries()[3]["query"]
    result = retrieval.cached_guidance(query)
    assert not result.abstained
    assert len(result.hits) == retrieval.TOP
    assert result.hits[0].passage_id.startswith("FDA-")


def test_retrieval_cache_unknown_query_is_stale() -> None:
    with pytest.raises(retrieval.StaleRetrievalCache, match="stale retrieval cache: rebuild"):
        retrieval.cached_guidance("a query nobody recorded")


def test_retrieval_cache_replay_never_imports_the_models() -> None:
    code = (
        "import sys\n"
        "from cairn import retrieval\n"
        "q = retrieval.load_fixed_queries()[2]['query']\n"
        "r = retrieval.cached_guidance(q)\n"
        "assert r.hits\n"
        "bad = [m for m in ('fastembed', 'onnxruntime') if m in sys.modules]\n"
        "print('IMPORTED' if bad else 'CLEAN', bad)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "CLEAN []", out.stdout + out.stderr


class _StubIndex:
    """Serves the cached hits back, optionally changed, so the check needs no model."""

    def __init__(self, cache: dict[str, list[dict[str, object]]], drift: float = 0.0) -> None:
        self.cache = cache
        self.drift = drift

    def hits(self, query: str) -> list[dict[str, object]]:
        hits = [dict(h) for h in self.cache[query]]
        hits[0]["rerank_score"] = float(str(hits[0]["rerank_score"])) + self.drift
        return hits

    def rerank(self, query: str) -> list[retrieval.RankedHit]:
        return [retrieval.RankedHit(**h) for h in self.hits(query)]  # type: ignore[arg-type]


def test_retrieval_cache_check_accepts_platform_drift(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    stub = _StubIndex(cache, drift=retrieval.PLATFORM_RERANK_TOLERANCE / 2)
    assert retrieval.check_cache(stub, retrieval.CACHE_PATH) == []  # type: ignore[arg-type]


def test_retrieval_cache_check_accepts_a_swap_and_a_changed_last_passage(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    class Moved(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            scores = (hits[2]["rerank_score"], hits[3]["rerank_score"])
            hits[2], hits[3] = hits[3], hits[2]
            hits[2]["rerank_score"], hits[3]["rerank_score"] = scores
            hits[4]["passage_id"] = "OTHER-01"
            return hits

    assert retrieval.check_cache(Moved(cache), retrieval.CACHE_PATH) == []  # type: ignore[arg-type]


def test_retrieval_cache_check_reports_a_stale_cache(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    drifted = retrieval.check_cache(_StubIndex(cache, drift=1.0), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert drifted and all("rerank_score differs by 1.0000" in p for p in drifted)

    class NewBest(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            hits[0]["passage_id"] = "OTHER-01"
            return hits

    best = retrieval.check_cache(NewBest(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert best and all("ranked passages differ" in p for p in best)

    class Reordered(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            hits[1]["semantic_rank"] = 99
            return hits

    ranks = retrieval.check_cache(Reordered(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert ranks and all("semantic_rank" in p for p in ranks)
