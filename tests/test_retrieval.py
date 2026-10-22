"""Hybrid retrieval: BM25 and bge-small fused by RRF, deterministic, with sockets blocked."""

import json
import socket
from pathlib import Path
from typing import Any

import pytest

from cairn import retrieval

pytestmark = pytest.mark.usefixtures("block_sockets")


@pytest.fixture(scope="module")
def index() -> retrieval.Index:
    return retrieval.build_index()


def test_retrieval_sockets_blocked() -> None:
    with pytest.raises(RuntimeError, match="network blocked"):
        socket.create_connection(("example.com", 80))


def test_retrieval_rrf_formula_on_hand_example() -> None:
    fused = retrieval.rrf([["a", "b", "c"], ["b", "a", "d"]])
    scores = dict(fused)
    both = 1 / 61 + 1 / 62
    assert scores["a"] == pytest.approx(both, abs=1e-15)
    assert scores["b"] == pytest.approx(both, abs=1e-15)
    assert scores["c"] == pytest.approx(1 / 63, abs=1e-15)
    assert scores["d"] == pytest.approx(1 / 63, abs=1e-15)
    # a and b tie, as do c and d: the passage ID breaks each tie
    assert [passage_id for passage_id, _ in fused] == ["a", "b", "c", "d"]


def test_retrieval_rrf_tie_broken_by_passage_id() -> None:
    fused = retrieval.rrf([["z", "m"], ["m", "z"]])
    assert [passage_id for passage_id, _ in fused] == ["m", "z"]


def test_retrieval_rrf_uses_k_60() -> None:
    assert retrieval.RRF_K == 60
    assert retrieval.rrf([["only"]])[0][1] == pytest.approx(1 / 61, abs=1e-15)


def test_retrieval_hybrid_hits_carry_ranks(index: retrieval.Index) -> None:
    hits = index.search("NOAEL definition")
    assert len(hits) == retrieval.CANDIDATES
    assert [hit.fused_rank for hit in hits] == list(range(1, len(hits) + 1))
    for hit in hits:
        parts = [r for r in (hit.lexical_rank, hit.semantic_rank) if r is not None]
        assert parts, "a hit must come from at least one retriever"
        expected = sum(1 / (retrieval.RRF_K + rank) for rank in parts)
        assert hit.fused_score == pytest.approx(expected, abs=1e-12)
    assert [h.fused_score for h in hits] == sorted((h.fused_score for h in hits), reverse=True)


def test_retrieval_hybrid_finds_the_noael_definition(index: retrieval.Index) -> None:
    ids = [hit.passage_id for hit in index.search("NOAEL definition")[:3]]
    assert "FDA-IV-01" in ids


def test_retrieval_same_query_same_ranks_and_scores(index: retrieval.Index) -> None:
    fresh = retrieval.build_index()
    query = "maximum recommended starting dose in humans"
    first = index.search(query)
    second = fresh.search(query)
    assert [h.passage_id for h in first] == [h.passage_id for h in second]
    tolerance = retrieval.SCORE_TOLERANCE
    for one, other in zip(first, second, strict=True):
        assert (one.lexical_rank, one.semantic_rank) == (other.lexical_rank, other.semantic_rank)
        assert one.fused_score == pytest.approx(other.fused_score, abs=tolerance)
        assert one.lexical_score == pytest.approx(other.lexical_score, abs=tolerance)
        assert one.semantic_score == pytest.approx(other.semantic_score, abs=tolerance)


# --- Increment 6: reranker, threshold and abstention -----------------------------------------


@pytest.fixture(scope="module")
def calibration() -> dict[str, Any]:
    return retrieval.load_calibration()


@pytest.fixture(scope="module")
def reranked(
    index: retrieval.Index, calibration: dict[str, Any]
) -> dict[str, list[retrieval.RankedHit]]:
    """The reranked top 5 of every calibration question, computed once for the module."""
    questions = [e["question"] for key in retrieval.CALIBRATION_SETS for e in calibration[key]]
    return {q: index.rerank(q) for q in questions}


def test_rerank_returns_top_5_with_scores_in_order(index: retrieval.Index) -> None:
    hits = index.rerank("What is the definition of the no observed adverse effect level")
    assert len(hits) == retrieval.TOP == 5
    assert [h.rerank_rank for h in hits] == [1, 2, 3, 4, 5]
    assert [h.rerank_score for h in hits] == sorted((h.rerank_score for h in hits), reverse=True)
    assert hits[0].passage_id.startswith("FDA-")  # IV-01 or the glossary entry
    for hit in hits:
        assert hit.fused_rank >= 1 and hit.fused_score > 0


def test_rerank_candidates_are_the_rrf_top_20(index: retrieval.Index) -> None:
    query = "maximum recommended starting dose in humans"
    candidates = {h.passage_id: h for h in index.search(query)}
    assert len(candidates) == retrieval.CANDIDATES == 20
    for hit in index.rerank(query):
        assert hit.passage_id in candidates
        # the lexical, semantic and fused ranks of the RRF stage travel with the reranked hit
        assert hit.fused_rank == candidates[hit.passage_id].fused_rank
        assert hit.lexical_rank == candidates[hit.passage_id].lexical_rank
        assert hit.semantic_rank == candidates[hit.passage_id].semantic_rank


def test_rerank_same_query_same_scores(index: retrieval.Index) -> None:
    query = "no observed adverse effect level definition"
    first, second = index.rerank(query), index.rerank(query)
    assert [h.passage_id for h in first] == [h.passage_id for h in second]
    for one, other in zip(first, second, strict=True):
        assert one.rerank_score == pytest.approx(other.rerank_score, abs=retrieval.RERANK_TOLERANCE)


def test_threshold_is_the_midpoint_of_the_two_ranges() -> None:
    assert retrieval.compute_threshold([3.0, 5.0, 4.0], [-2.0, 0.0, -1.0]) == 1.5


def test_threshold_overlapping_ranges_are_reported_not_fudged() -> None:
    with pytest.raises(ValueError, match="overlap"):
        retrieval.compute_threshold([1.0, 5.0], [0.5, 2.0])


def test_threshold_calibration_set_shape(calibration: dict[str, Any]) -> None:
    assert 8 <= len(calibration["in_library"]) <= 12
    assert 8 <= len(calibration["out_of_library"]) <= 12
    questions = [e["question"] for key in retrieval.CALIBRATION_SETS for e in calibration[key]]
    assert len(set(questions)) == len(questions)
    assert calibration["model"] == "BAAI/bge-reranker-v2-m3-int8"


def test_threshold_calibration_disjoint_from_e4(
    calibration: dict[str, Any],
) -> None:
    own = {e["question"].casefold() for key in retrieval.CALIBRATION_SETS for e in calibration[key]}
    e4_path = Path(__file__).parent / "evals" / "e4_questions.json"
    if e4_path.exists():  # written at increment 12, which must keep this disjoint
        e4 = json.loads(e4_path.read_text(encoding="utf-8"))
        e4_questions = {q["question"].casefold() for q in e4["in_library"] + e4["out_of_library"]}
        assert not own & e4_questions


def test_threshold_recomputed_equals_stored(
    calibration: dict[str, Any], reranked: dict[str, list[retrieval.RankedHit]]
) -> None:
    best = {q: hits[0].rerank_score for q, hits in reranked.items()}
    lowest_in = min(best[e["question"]] for e in calibration["in_library"])
    highest_out = max(best[e["question"]] for e in calibration["out_of_library"])
    assert lowest_in > highest_out, "in-library and out-of-library best scores overlap"
    recomputed = retrieval.compute_threshold(
        [best[e["question"]] for e in calibration["in_library"]],
        [best[e["question"]] for e in calibration["out_of_library"]],
    )
    assert recomputed == pytest.approx(calibration["threshold"], abs=retrieval.RERANK_TOLERANCE)
    assert retrieval.load_threshold() == calibration["threshold"]
    for key in retrieval.CALIBRATION_SETS:
        for entry in calibration[key]:
            assert best[entry["question"]] == pytest.approx(
                entry["best_score"], abs=retrieval.RERANK_TOLERANCE
            )


def test_search_guidance_abstains_on_every_out_of_library_question(
    calibration: dict[str, Any], reranked: dict[str, list[retrieval.RankedHit]]
) -> None:
    for entry in calibration["out_of_library"]:
        result = retrieval.decide(entry["question"], reranked[entry["question"]])
        assert result.abstained, entry["question"]
        assert result.hits == []
        assert result.message == "no supporting passage in the library"
        assert result.best_score < result.threshold


def test_search_guidance_abstains_end_to_end(index: retrieval.Index) -> None:
    result = retrieval.search_guidance(index, "What is the capital of Australia?")
    assert result.abstained
    assert result.hits == []
    assert result.message == retrieval.ABSTENTION


def test_search_guidance_answers_every_in_library_question(
    calibration: dict[str, Any], reranked: dict[str, list[retrieval.RankedHit]]
) -> None:
    for entry in calibration["in_library"]:
        result = retrieval.decide(entry["question"], reranked[entry["question"]])
        assert not result.abstained, entry["question"]
        assert result.message is None
        assert len(result.hits) == retrieval.TOP
        assert result.hits[0].rerank_score >= result.threshold


def test_search_guidance_abstains_on_reranker_score_never_on_rrf(
    index: retrieval.Index,
) -> None:
    query = "What is the definition of the no observed adverse effect level"
    top = index.search(query)[0]
    hits = index.rerank(query)
    # RRF scores live near 0.03; a threshold on that scale must not decide anything:
    assert top.fused_score < 0.05
    assert not retrieval.decide(query, hits, threshold=top.fused_score + 0.01).abstained
    # while a threshold above the best reranker score abstains whatever the RRF score is
    result = retrieval.decide(query, hits, threshold=hits[0].rerank_score + 0.01)
    assert result.abstained and result.hits == []
