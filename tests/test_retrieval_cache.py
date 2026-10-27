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
    wanted = set(retrieval.required_queries(recordings=Path("recordings")))
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
    written_on = json.loads(retrieval.CACHE_PATH.read_text(encoding="utf-8")).get("platform")
    if written_on != retrieval.build_platform():
        # D113: the strict comparison holds only on the platform that built the cache
        problems = retrieval.check_cache(index)
        assert not problems, " | ".join(problems)
        return
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


@pytest.fixture
def other_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cache was written elsewhere: the tolerant cross-platform comparison applies."""
    monkeypatch.setattr(retrieval, "build_platform", lambda: "another-platform")


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


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_accepts_platform_drift(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    stub = _StubIndex(cache, drift=retrieval.PLATFORM_RERANK_TOLERANCE / 2)
    assert retrieval.check_cache(stub, retrieval.CACHE_PATH) == []  # type: ignore[arg-type]


def _score(hit: dict[str, object]) -> float:
    return float(str(hit["rerank_score"]))


def _swap_neighbours(hits: list[dict[str, object]], first: float, second: float) -> None:
    """Positions 3 and 4 trade places; the fresh list stays sorted by score, as the reranker's is.

    The passage that moves up scores `first` and the one that moves down `second`; each keeps its
    own other scores and takes the rank of its new position.
    """
    hits[2], hits[3] = hits[3], hits[2]
    hits[2]["rerank_score"], hits[3]["rerank_score"] = first, second
    hits[2]["rerank_rank"], hits[3]["rerank_rank"] = 3, 4


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_accepts_a_swap_and_a_changed_last_passage(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    class Moved(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            old3, old4 = _score(hits[2]), _score(hits[3])
            if old3 - old4 < retrieval.PLATFORM_RERANK_TOLERANCE:  # only a near-tie can swap
                middle = (old3 + old4) / 2  # each score drifts by half the gap, within tolerance
                _swap_neighbours(hits, middle + 1e-3, middle - 1e-3)
                swapped.append(query)
                drifts.extend([abs(old4 - middle), abs(old3 - middle)])
            hits[4]["passage_id"] = "OTHER-01"
            return hits

    swapped: list[str] = []
    drifts: list[float] = []
    assert retrieval.check_cache(Moved(cache), retrieval.CACHE_PATH) == []  # type: ignore[arg-type]
    assert swapped and max(drifts) > 0
    assert max(drifts) < retrieval.PLATFORM_RERANK_TOLERANCE


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_reports_one_passage_drifting_beyond_the_tolerance_in_a_swap(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    tolerance = retrieval.PLATFORM_RERANK_TOLERANCE

    class Drifted(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            old3, old4 = _score(hits[2]), _score(hits[3])
            gap = old3 - old4
            if 0.05 < gap < tolerance:  # the lower passage jumps above the higher one
                moved_up = old4 + tolerance + 0.05  # its own score moves by more than the tolerance
                _swap_neighbours(hits, moved_up, old3)
                # by position both scores still agree within the tolerance
                assert abs(moved_up - old3) <= tolerance and abs(old3 - old4) <= tolerance
                drifted.append(query)
            return hits

    drifted: list[str] = []
    problems = retrieval.check_cache(Drifted(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert drifted, "no cached query has a near-tie at positions 3 and 4 to model"
    assert not any("position" in p for p in problems)
    assert len(problems) == len(drifted)
    assert all("rerank_score differs by" in p for p in problems)


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_accepts_a_one_rank_shift_of_a_near_tie(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    class Shifted(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            hits[1]["semantic_rank"] = int(str(hits[1]["semantic_rank"])) + 1
            hits[1]["fused_rank"] = int(str(hits[1]["fused_rank"])) + 1
            hits[1]["fused_score"] = float(str(hits[1]["fused_score"])) - 2.5e-4
            return hits

    assert retrieval.check_cache(Shifted(cache), retrieval.CACHE_PATH) == []  # type: ignore[arg-type]


AMD64_QUERY = "nonclinical data to support first-in-human clinical trial anticancer drug"


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_accepts_two_near_ties_swapped_at_the_cut_on_amd64(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    """D116: observed on a GitHub amd64 runner, two passages lost and two gained at the cut."""
    stored = cache[AMD64_QUERY]
    assert [h["passage_id"] for h in stored] == [
        "S9-1.2-01", "S9-1.3-01", "S9-1.1-01", "S9-3.3-01", "S9-3.6-01",
    ]  # fmt: skip
    by_id = {str(h["passage_id"]): h for h in stored}
    observed = [
        ("S9-1.3-01", 3.378), ("S9-1.2-01", 3.295), ("S9-3.4-01", 2.325),
        ("M3-6-01", 2.305), ("S9-1.1-01", 2.237),
    ]  # fmt: skip

    class Amd64(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            if query != AMD64_QUERY:
                return hits
            fresh = []
            for rank, (pid, score) in enumerate(observed, start=1):
                hit = dict(by_id.get(pid, stored[-1]))  # a new passage borrows the foot's scores
                hit.update(passage_id=pid, rerank_score=score, rerank_rank=rank)
                fresh.append(hit)
            return fresh

    assert retrieval.check_cache(Amd64(cache), retrieval.CACHE_PATH) == []  # type: ignore[arg-type]


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_reports_a_stale_cache(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    drifted = retrieval.check_cache(_StubIndex(cache, drift=2.0), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert drifted and all("rerank_score differs by 2.0000" in p for p in drifted)

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


def _ranked(scores: dict[str, float]) -> list[retrieval.RankedHit]:
    return [
        retrieval.RankedHit(
            passage_id=pid, fused_rank=i, fused_score=0.01, lexical_rank=i, lexical_score=1.0,
            semantic_rank=i, semantic_score=0.5, rerank_rank=i, rerank_score=score,
        )
        for i, (pid, score) in enumerate(scores.items(), start=1)
    ]  # fmt: skip


def test_retrieval_cache_same_top_tolerates_near_ties_only() -> None:
    near = retrieval.PLATFORM_RERANK_TOLERANCE * 1.5
    far = retrieval.PLATFORM_RERANK_TOLERANCE * 3
    stored = [h.model_dump() for h in _ranked({"A": 3.0, "B": 3.0 - near, "C": 2.0, "D": 1.0})]
    swapped = _ranked({"B": 3.0, "A": 3.0 - near, "C": 2.0, "D": 1.0})
    assert retrieval._same_top(stored, swapped, {h.passage_id: h for h in swapped})
    entered = _ranked({"A": 3.0, "B": 2.9, "C": 2.0, "E": 1.0 + near / 3})
    assert retrieval._same_top(stored, entered, {h.passage_id: h for h in entered})
    clear = _ranked({"B": 3.0 + far, "A": 3.0, "C": 2.0, "D": 1.0})
    assert not retrieval._same_top(stored, clear, {h.passage_id: h for h in clear})
    clear_entry = _ranked({"A": 5.0, "B": 4.9, "E": 4.8, "C": 1.2})
    assert not retrieval._same_top(stored, clear_entry, {h.passage_id: h for h in clear_entry})


def test_retrieval_cache_same_top_reports_a_lost_passage_above_the_foot() -> None:
    # G2 case: the fresh list loses FDA-GLOSSARY-02 (rank 2, 2.67, foot 1.61) and gains a new foot
    stored = [
        h.model_dump()
        for h in _ranked(
            {"FDA-IV-02": 3.22, "FDA-GLOSSARY-02": 2.67, "FDA-IV-03": 2.46, "FDA-IV-01": 2.24,
             "M3-6-01": 1.61}
        )
    ]  # fmt: skip
    fresh = _ranked(
        {"FDA-IV-02": 3.22, "FDA-IV-03": 2.46, "FDA-IV-01": 2.24, "M3-6-01": 1.61, "NEW-01": 1.60}
    )
    assert not retrieval._same_top(stored, fresh, {h.passage_id: h for h in fresh})


def test_retrieval_cache_same_top_reports_renamed_passages_well_above_the_other_foot() -> None:
    stored = [h.model_dump() for h in _ranked({"A": 3.0, "B": 2.0, "C": 1.9, "D": 1.8, "E": 1.7})]
    renamed = _ranked({"A": 3.0, "X": 1.0, "Y": 0.9, "Z": 0.8, "W": 0.7})
    assert not retrieval._same_top(stored, renamed, {h.passage_id: h for h in renamed})
    two = _ranked({"A": 3.0, "B": 2.0, "C": 1.9, "X": 0.8, "Y": 0.7})
    assert not retrieval._same_top(stored, two, {h.passage_id: h for h in two})
    # two near-ties at the cut may change places: each is within the tolerance of the other foot
    tied = [h.model_dump() for h in _ranked({"A": 3.0, "B": 2.5, "C": 2.4, "D": 2.3, "E": 2.2})]
    cut = _ranked({"A": 3.0, "B": 2.5, "X": 2.35, "Y": 2.3, "C": 2.25})
    assert retrieval._same_top(tied, cut, {h.passage_id: h for h in cut})


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_reports_score_differences_of_common_passages(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    class Moved(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            hits[1]["fused_score"] = float(str(hits[1]["fused_score"])) + 1e-3
            hits[2]["lexical_score"] = float(str(hits[2]["lexical_score"])) + 1e-3
            hits[3]["semantic_score"] = float(str(hits[3]["semantic_score"])) + 1e-2
            return hits

    problems = retrieval.check_cache(Moved(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    for name in ("fused_score", "lexical_score", "semantic_score"):
        assert any(f"{name} differs by" in p for p in problems), name


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_compares_common_passages_by_id(
    cache: dict[str, list[dict[str, object]]],
) -> None:
    class Rotated(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            # the scores keep their positions but two passages swap: by position all agree
            scores = [h["rerank_score"] for h in hits]
            hits[3], hits[4] = hits[4], hits[3]
            hits[3]["rerank_score"], hits[4]["rerank_score"] = scores[3], scores[4]
            return hits

    # stored scores of positions 4 and 5 differ by more than the tolerance in some query
    gaps = [
        abs(float(str(h[3]["rerank_score"])) - float(str(h[4]["rerank_score"])))
        for h in cache.values()
    ]
    assert max(gaps) > retrieval.PLATFORM_RERANK_TOLERANCE
    problems = retrieval.check_cache(Rotated(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert any("rerank_score differs by" in p for p in problems)


def test_retrieval_cache_check_is_strict_on_the_platform_that_wrote_the_cache(
    cache: dict[str, list[dict[str, object]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    written_on = json.loads(retrieval.CACHE_PATH.read_text(encoding="utf-8"))["platform"]
    monkeypatch.setattr(retrieval, "build_platform", lambda: written_on)
    drift = retrieval.PLATFORM_RERANK_TOLERANCE / 2
    strict = retrieval.check_cache(_StubIndex(cache, drift=drift), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert strict and all("rerank_score differs by" in p for p in strict)
    assert retrieval.check_cache(_StubIndex(cache), retrieval.CACHE_PATH) == []  # type: ignore[arg-type]

    class Swapped(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            hits[1]["passage_id"], hits[2]["passage_id"] = (
                hits[2]["passage_id"],
                hits[1]["passage_id"],
            )
            return hits

    swapped = retrieval.check_cache(Swapped(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert swapped and all("ranked passages differ" in p for p in swapped)

    class Ranked(_StubIndex):
        def hits(self, query: str) -> list[dict[str, object]]:
            hits = super().hits(query)
            hits[1]["fused_rank"] = int(str(hits[1]["fused_rank"])) + 1
            hits[1]["semantic_score"] = float(str(hits[1]["semantic_score"])) + 1e-3
            return hits

    ranks = retrieval.check_cache(Ranked(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert any("fused_rank" in p for p in ranks) and any("semantic_score" in p for p in ranks)


def test_retrieval_cache_check_reports_another_reranker_model(
    cache: dict[str, list[dict[str, object]]], tmp_path: Path
) -> None:
    data = json.loads(retrieval.CACHE_PATH.read_text(encoding="utf-8"))
    data["model"] = "some/other-reranker"
    other = tmp_path / "cache.json"
    other.write_text(json.dumps(data), encoding="utf-8")
    problems = retrieval.check_cache(_StubIndex(cache), other)  # type: ignore[arg-type]
    assert any("some/other-reranker" in p and "reranker" in p for p in problems)


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_reports_short_or_empty_lists_without_crashing(
    cache: dict[str, list[dict[str, object]]], tmp_path: Path
) -> None:
    class Short(_StubIndex):
        def rerank(self, query: str) -> list[retrieval.RankedHit]:
            return super().rerank(query)[:3]

    short = retrieval.check_cache(Short(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert short and all("expected 5 ranked passages" in p for p in short)

    class Empty(_StubIndex):
        def rerank(self, query: str) -> list[retrieval.RankedHit]:
            return []

    empty = retrieval.check_cache(Empty(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert empty and all("expected 5 ranked passages" in p for p in empty)

    data = json.loads(retrieval.CACHE_PATH.read_text(encoding="utf-8"))
    first = sorted(data["queries"])[0]
    data["queries"][first] = data["queries"][first][:2]
    stored_short = tmp_path / "cache.json"
    stored_short.write_text(json.dumps(data), encoding="utf-8")
    problems = retrieval.check_cache(_StubIndex(cache), stored_short)  # type: ignore[arg-type]
    assert any(p.startswith(first) and "expected 5 ranked passages" in p for p in problems)


@pytest.mark.usefixtures("other_platform")
def test_retrieval_cache_check_reports_lists_longer_than_top(
    cache: dict[str, list[dict[str, object]]], tmp_path: Path
) -> None:
    class Long(_StubIndex):
        def rerank(self, query: str) -> list[retrieval.RankedHit]:
            hits = super().rerank(query)
            return [*hits, hits[-1].model_copy(update={"passage_id": "EXTRA-01"})]

    fresh_long = retrieval.check_cache(Long(cache), retrieval.CACHE_PATH)  # type: ignore[arg-type]
    assert fresh_long and all("expected 5 ranked passages" in p for p in fresh_long)

    data = json.loads(retrieval.CACHE_PATH.read_text(encoding="utf-8"))
    first = sorted(data["queries"])[0]
    data["queries"][first] = [*data["queries"][first], dict(data["queries"][first][-1])]
    stored_long = tmp_path / "cache.json"
    stored_long.write_text(json.dumps(data), encoding="utf-8")
    problems = retrieval.check_cache(_StubIndex(cache), stored_long)  # type: ignore[arg-type]
    assert any(p.startswith(first) and "expected 5 ranked passages" in p for p in problems)


def test_retrieval_cache_check_reports_a_required_query_missing_from_the_cache(
    cache: dict[str, list[dict[str, object]]], tmp_path: Path
) -> None:
    g2 = next(q["query"] for q in retrieval.load_fixed_queries() if q["id"] == "G2")
    data = json.loads(retrieval.CACHE_PATH.read_text(encoding="utf-8"))
    del data["queries"][g2]
    lacking = tmp_path / "cache.json"
    lacking.write_text(json.dumps(data), encoding="utf-8")
    problems = retrieval.check_cache(_StubIndex(cache), lacking)  # type: ignore[arg-type]
    assert any(p.startswith(g2) and "missing from the cache" in p for p in problems)
    assert retrieval.check_cache(_StubIndex(cache), retrieval.CACHE_PATH) == []  # type: ignore[arg-type]
