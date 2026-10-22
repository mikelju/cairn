"""Hybrid retrieval: BM25 and bge-small fused by RRF, deterministic, with sockets blocked."""

import socket

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
