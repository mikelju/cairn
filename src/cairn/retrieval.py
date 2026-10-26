"""Hybrid retrieval over the guideline passages: BM25 and bge-small embeddings fused by RRF.

Lexical search is `bm25s` over the passage text; semantic search is the cosine similarity of
bge-small-en-v1.5 (int8 ONNX, loaded from the verified cache by `cairn.weights`, never downloaded).
The two rankings are fused with reciprocal rank fusion, k = 60, and ties are broken by passage ID,
so the order does not depend on array layout or platform.
"""

import json
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bm25s  # type: ignore[import-untyped]
import numpy as np
from pydantic import BaseModel, ConfigDict

from cairn import weights
from cairn.passages import GUIDANCE_DIR, PASSAGES_PATH, Passage, load_passages
from cairn.recording import RECORDINGS_DIR

RRF_K = 60
# Depth of each ranking that enters the fusion, and size of the fused list returned.
DEPTH = 50
CANDIDATES = 20
# Scores of the same query agree to this absolute tolerance across runs on the same platform.
# BM25 is float64 arithmetic over the same tokens and agrees to rounding; the int8 ONNX embeddings
# are deterministic on one machine (cosine scores are in [-1, 1]). Across platforms the looser
# PLATFORM_* tolerances below apply (D113, D114).
SCORE_TOLERANCE = 1e-4

# The reranker (bge-reranker-v2-m3, int8) rescores the RRF top `CANDIDATES`; `TOP` are returned.
TOP = 5
# int8 dynamic quantisation makes a pair's score depend on its batch (measured up to 0.59 between
# batch compositions, E138), so each pair is scored alone: the score no longer depends on the
# order of the candidates, which can shift when near-tied RRF scores resolve differently.
# Four threads were measured faster than the 12 of this laptop (oversubscription); scores agree.
RERANK_BATCH = 1
RERANK_THREADS = 4
# Reranker logits span about -10..10; the same query agrees to this absolute tolerance across runs
# on the same platform (across platforms see PLATFORM_RERANK_TOLERANCE). The abstention margin
# (half the gap between the calibration ranges) is far larger.
RERANK_TOLERANCE = 1e-2
CALIBRATION_PATH = GUIDANCE_DIR / "calibration.json"
CALIBRATION_SETS = ("in_library", "out_of_library")
ABSTENTION = "no supporting passage in the library"
FIXED_QUERIES_PATH = GUIDANCE_DIR / "fixed_queries.json"
CACHE_PATH = GUIDANCE_DIR / "retrieval_cache.json"
STALE_CACHE = "stale retrieval cache: rebuild"


class Hit(BaseModel):
    """One fused result with the rank each retriever gave it (None when outside its depth)."""

    model_config = ConfigDict(frozen=True)

    passage_id: str
    fused_rank: int
    fused_score: float
    lexical_rank: int | None
    lexical_score: float
    semantic_rank: int | None
    semantic_score: float


def rrf(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Reciprocal rank fusion: score(id) = sum of 1 / (k + rank), ranks starting at 1.

    Sorted by descending score, ties broken by ascending passage ID.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, passage_id in enumerate(ranking, start=1):
            scores[passage_id] = scores.get(passage_id, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def _order(scores: np.ndarray[Any, Any], ids: list[str], depth: int) -> list[int]:
    """Indexes by descending score, ties by passage ID."""
    order = sorted(range(len(ids)), key=lambda i: (-float(scores[i]), ids[i]))
    return order[:depth]


class RankedHit(Hit):
    """A hit rescored by the reranker, with the ranks of the RRF stage it came from."""

    rerank_rank: int
    rerank_score: float


class Guidance(BaseModel):
    """What `search_guidance` returns: the top hits, or an explicit abstention with no passage."""

    model_config = ConfigDict(frozen=True)

    query: str
    abstained: bool
    best_score: float
    threshold: float
    message: str | None
    hits: list[RankedHit]


def _read(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def load_calibration(path: Path = CALIBRATION_PATH) -> dict[str, Any]:
    return _read(path)


def load_threshold(path: Path = CALIBRATION_PATH) -> float:
    return float(_read(path)["threshold"])


def compute_threshold(in_library_best: list[float], out_of_library_best: list[float]) -> float:
    """Midpoint between the lowest in-library and the highest out-of-library best score."""
    lowest, highest = min(in_library_best), max(out_of_library_best)
    if lowest <= highest:
        raise ValueError(
            f"in-library and out-of-library best scores overlap: lowest in-library {lowest:.4f}, "
            f"highest out-of-library {highest:.4f}"
        )
    return (lowest + highest) / 2


def decide(query: str, hits: list[RankedHit], threshold: float | None = None) -> Guidance:
    """Abstain when the best reranker score is below the threshold; the RRF score never decides."""
    limit = load_threshold() if threshold is None else threshold
    best = hits[0].rerank_score if hits else float("-inf")
    abstained = best < limit
    return Guidance(
        query=query,
        abstained=abstained,
        best_score=best,
        threshold=limit,
        message=ABSTENTION if abstained else None,
        hits=[] if abstained else hits,
    )


@dataclass
class Index:
    ids: list[str]
    retriever: Any
    vectors: np.ndarray[Any, Any]
    embedder: Any
    texts: dict[str, str] = field(default_factory=dict)
    models: Path | None = None
    reranker: Any = None

    def rerank(self, query: str) -> list[RankedHit]:
        """The RRF top 20 rescored by the cross-encoder; the best `TOP` by reranker score."""
        candidates = self.search(query, CANDIDATES)
        if self.reranker is None:
            self.reranker = _load_reranker(self.models)
        scores = list(
            self.reranker.rerank(
                query, [self.texts[h.passage_id] for h in candidates], batch_size=RERANK_BATCH
            )
        )
        ordered = sorted(
            zip(candidates, scores, strict=True), key=lambda c: (-c[1], c[0].passage_id)
        )
        return [
            RankedHit(**hit.model_dump(), rerank_rank=rank, rerank_score=float(score))
            for rank, (hit, score) in enumerate(ordered[:TOP], start=1)
        ]

    def search(self, query: str, limit: int = CANDIDATES) -> list[Hit]:
        tokens = bm25s.tokenize(query, stopwords="en", return_ids=False, show_progress=False)
        lexical = np.asarray(self.retriever.get_scores(tokens[0]), dtype=np.float64)
        vector = np.asarray(next(iter(self.embedder.embed([query]))), dtype=np.float64)
        semantic = self.vectors @ vector
        lexical_order = [i for i in _order(lexical, self.ids, DEPTH) if lexical[i] > 0.0]
        semantic_order = _order(semantic, self.ids, DEPTH)
        lexical_rank = {self.ids[i]: rank for rank, i in enumerate(lexical_order, start=1)}
        semantic_rank = {self.ids[i]: rank for rank, i in enumerate(semantic_order, start=1)}
        fused = rrf([[self.ids[i] for i in lexical_order], [self.ids[i] for i in semantic_order]])
        position = {passage_id: i for i, passage_id in enumerate(self.ids)}
        hits: list[Hit] = []
        for rank, (passage_id, score) in enumerate(fused[:limit], start=1):
            i = position[passage_id]
            hits.append(
                Hit(
                    passage_id=passage_id,
                    fused_rank=rank,
                    fused_score=score,
                    lexical_rank=lexical_rank.get(passage_id),
                    lexical_score=float(lexical[i]),
                    semantic_rank=semantic_rank.get(passage_id),
                    semantic_score=float(semantic[i]),
                )
            )
        return hits


def build_index(path: Path = PASSAGES_PATH, models: Path | None = None) -> Index:
    """Index the committed passages; embeds them with the cached bge-small weights."""
    passages: list[Passage] = sorted(load_passages(path), key=lambda p: p.passage_id)
    ids = [p.passage_id for p in passages]
    texts = [p.indexed_text for p in passages]
    corpus = bm25s.tokenize(texts, stopwords="en", return_ids=False, show_progress=False)
    retriever = bm25s.BM25()
    retriever.index(corpus, show_progress=False)
    embedder = weights.load_embedder(models)
    vectors = np.asarray(list(embedder.embed(texts)), dtype=np.float64)
    return Index(
        ids=ids,
        retriever=retriever,
        vectors=vectors,
        embedder=embedder,
        texts=dict(zip(ids, texts, strict=True)),
        models=models,
    )


def _load_reranker(models: Path | None) -> Any:
    """The int8 cross-encoder from the verified cache (offline), on `RERANK_THREADS` threads."""
    import os

    os.environ["HF_HUB_OFFLINE"] = "1"
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    folder = weights.verify_model(weights.RERANKER, models or weights.models_dir())
    return TextCrossEncoder(
        weights.RERANKER,
        specific_model_path=str(folder),
        local_files_only=True,
        threads=RERANK_THREADS,
    )


def search_guidance(index: Index, query: str, threshold: float | None = None) -> Guidance:
    """Hybrid retrieval, reranking and abstention for one query (live path, needs the weights)."""
    return decide(query, index.rerank(query), threshold)


def build_platform() -> str:
    """The system and machine the scores are computed on, recorded in the generated files."""
    return f"{platform.system()}-{platform.machine()}".lower()


def calibrate(index: Index, path: Path = CALIBRATION_PATH) -> str:
    """The calibration file as JSON text: best score of each stored question and the threshold."""
    data = _read(path)
    best: dict[str, list[float]] = {}
    for key in CALIBRATION_SETS:
        for entry in data[key]:
            entry["best_score"] = round(index.rerank(entry["question"])[0].rerank_score, 4)
        best[key] = [e["best_score"] for e in data[key]]
    data["model"] = weights.RERANKER
    data["platform"] = build_platform()
    data["method"] = (
        "threshold = midpoint between the lowest in-library and the highest out-of-library "
        "best reranker score (decision O4); abstain when the best score is below it"
    )
    data["threshold"] = round(compute_threshold(best["in_library"], best["out_of_library"]), 4)
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class StaleRetrievalCache(Exception):
    """Replay asked for a query the cache does not hold: rebuild it with `cairn guidance build`."""

    def __init__(self, query: str):
        super().__init__(f"{STALE_CACHE} (query: {query!r})")


def load_fixed_queries(path: Path = FIXED_QUERIES_PATH) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = _read(path)["queries"]
    return queries


def recorded_queries(directory: Path = RECORDINGS_DIR) -> list[str]:
    """Every distinct `search_guidance` query in the recordings of a folder, sorted."""
    found: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        for call in _read(path).get("calls", []):
            for block in call["response"].get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "search_guidance":
                    found.add(str(block["input"]["query"]))
    return sorted(found)


def build_cache(
    index: Index, fixed: Path = FIXED_QUERIES_PATH, recordings: Path = RECORDINGS_DIR
) -> str:
    """The cache as JSON text: the reranked top hits of every fixed and recorded query."""
    queries = sorted(
        {q["query"] for q in load_fixed_queries(fixed)} | set(recorded_queries(recordings))
    )
    results = {
        query: [
            {k: round(v, 6) if isinstance(v, float) else v for k, v in hit.model_dump().items()}
            for hit in index.rerank(query)
        ]
        for query in queries
    }
    data = {"model": weights.RERANKER, "platform": build_platform(), "queries": results}
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def cached_guidance(
    query: str, path: Path = CACHE_PATH, threshold: float | None = None
) -> Guidance:
    """Replay lookup by exact query string; never loads the embedder or the reranker."""
    stored = _read(path)["queries"].get(query)
    if stored is None:
        raise StaleRetrievalCache(query)
    return decide(query, [RankedHit(**hit) for hit in stored], threshold)


# Linux arm64 against the Windows build of the cache (measured at the image build): reranker logits
# moved by up to 0.28, cosine scores by up to 4.2e-4, and passages with near-equal reranker scores
# swapped places at the foot of the top 5. On linux/amd64 CI with single-pair batches (E139, D114)
# the largest logit difference over the cache queries and the calibration questions was 0.5406, so
# the tolerance is that measurement plus a margin of about 0.06. The abstention margin (half the
# gap between the calibration ranges, about 2.5) stays more than four times this tolerance.
PLATFORM_RERANK_TOLERANCE = 0.6
PLATFORM_SEMANTIC_TOLERANCE = 1e-3
# D113: on linux/amd64 near-tied cosine scores moved a passage by one semantic rank, which moves
# its fused rank by one and its RRF score by at most 1/(60+r) - 1/(61+r), under 3e-4 for r >= 1.
PLATFORM_RANK_SHIFT = 1
PLATFORM_FUSED_TOLERANCE = 5e-4


def _same_top(
    stored: list[dict[str, Any]], fresh: list[RankedHit], found: dict[str, RankedHit]
) -> bool:
    """Whether two top-5 lists agree up to near-ties (scores within the platform tolerance).

    At most one passage may be lost and one gained (D112: at most one of five differs).
    """
    # each list may be off by the tolerance from the other platform's value, so a tie spans twice
    tolerance = 2 * PLATFORM_RERANK_TOLERANCE
    best = stored[0]["passage_id"]
    if best != fresh[0].passage_id and (
        best not in found or fresh[0].rerank_score - found[best].rerank_score > tolerance
    ):
        return False
    foot_old, foot_new = stored[-1]["rerank_score"], fresh[-1].rerank_score
    kept = {h.passage_id for h in fresh}
    lost = [h for h in stored if h["passage_id"] not in kept]
    gained = [h for h in fresh if h.passage_id not in {s["passage_id"] for s in stored}]
    if len(lost) > 1 or len(gained) > 1:
        return False
    # a passage only in one list sits near the foot of its own list; and as it is missing from the
    # other list, its score there is at most that list's foot plus one platform tolerance, so a lost
    # passage that scored well above the new foot is a real change, not a near-tie at the cut
    return (
        all(h["rerank_score"] - foot_old <= tolerance for h in lost)
        and all(h.rerank_score - foot_new <= tolerance for h in gained)
        and all(h["rerank_score"] - foot_new <= PLATFORM_RERANK_TOLERANCE for h in lost)
        and all(h.rerank_score - foot_old <= PLATFORM_RERANK_TOLERANCE for h in gained)
    )


def _strict_differences(
    query: str, stored: list[dict[str, Any]], fresh: list[RankedHit]
) -> list[str]:
    """Same-platform comparison (D113): same ordered passages, scores within the run tolerances."""
    old_ids = [h["passage_id"] for h in stored]
    new_ids = [h.passage_id for h in fresh]
    if old_ids != new_ids:
        return [f"{query}: ranked passages differ: {old_ids} vs {new_ids}"]
    problems: list[str] = []
    for old, new in zip(stored, fresh, strict=True):
        for name, tolerance in (
            ("rerank_score", RERANK_TOLERANCE),
            ("fused_score", SCORE_TOLERANCE),
            ("lexical_score", SCORE_TOLERANCE),
            ("semantic_score", SCORE_TOLERANCE),
        ):
            delta = abs(old[name] - getattr(new, name))
            if delta > tolerance:
                problems.append(f"{query}: {new.passage_id} {name} differs by {delta:.6f}")
        for name in ("rerank_rank", "fused_rank", "lexical_rank", "semantic_rank"):
            was, now = old[name], getattr(new, name)
            if was != now:
                problems.append(f"{query}: {new.passage_id} {name} {was} vs {now}")
    return problems


def check_cache(index: Index, path: Path = CACHE_PATH) -> list[str]:
    """Differences between the committed cache and a fresh retrieval of every cached query.

    On the platform that wrote the cache (`build_platform()`) the comparison is strict: the same
    ordered passages and ranks, reranker scores within `RERANK_TOLERANCE`, the other scores within
    `SCORE_TOLERANCE`. Elsewhere (the image build may run on another platform) near-ties are
    tolerated: the best passage is the same, or the other list's best scores within twice
    `PLATFORM_RERANK_TOLERANCE` of it; at most one passage is in only one of the two top 5 lists,
    and it scores within twice that tolerance of the foot of its list (a near-tie at the cut, E138);
    the reranker score agrees within `PLATFORM_RERANK_TOLERANCE` at every position and for every
    passage in both lists; for passages in both lists, lexical scores agree within
    `SCORE_TOLERANCE`, fused scores within `PLATFORM_FUSED_TOLERANCE`, semantic scores within
    `PLATFORM_SEMANTIC_TOLERANCE`; the lexical rank is equal and the semantic and fused ranks
    differ by at most `PLATFORM_RANK_SHIFT`. A cache written by another reranker, or a list with
    fewer than `TOP` passages, is a problem. An empty list means the cache is current.
    """
    data = _read(path)
    problems: list[str] = []
    if data.get("model") != weights.RERANKER:
        problems.append(
            f"cache model {data.get('model')!r} is not the reranker {weights.RERANKER!r}"
        )
    strict = data.get("platform") == build_platform()
    for query, stored in sorted(data["queries"].items()):
        fresh = index.rerank(query)
        if len(stored) < TOP or len(fresh) < TOP:
            problems.append(
                f"{query}: expected {TOP} ranked passages, the cache has {len(stored)} "
                f"and a fresh retrieval {len(fresh)}"
            )
            continue
        if strict:
            problems.extend(_strict_differences(query, stored, fresh))
            continue
        old_ids = [h["passage_id"] for h in stored]
        new_ids = [h.passage_id for h in fresh]
        found = {h.passage_id: h for h in fresh}
        common = [h for h in stored if h["passage_id"] in found]
        if not _same_top(stored, fresh, found):
            old_scores = [round(h["rerank_score"], 3) for h in stored]
            new_scores = [round(h.rerank_score, 3) for h in fresh]
            problems.append(
                f"{query}: ranked passages differ: {old_ids} {old_scores} vs {new_ids} {new_scores}"
            )
            continue
        for position, (old, new) in enumerate(zip(stored, fresh, strict=True), start=1):
            delta = abs(old["rerank_score"] - new.rerank_score)
            if delta > PLATFORM_RERANK_TOLERANCE:
                problems.append(f"{query}: position {position} rerank_score differs by {delta:.4f}")
        for old in common:
            new = found[old["passage_id"]]
            delta = abs(old["rerank_score"] - new.rerank_score)
            if delta > PLATFORM_RERANK_TOLERANCE:
                problems.append(f"{query}: {new.passage_id} rerank_score differs by {delta:.4f}")
            for name, tolerance in (
                ("fused_score", PLATFORM_FUSED_TOLERANCE),
                ("lexical_score", SCORE_TOLERANCE),
                ("semantic_score", PLATFORM_SEMANTIC_TOLERANCE),
            ):
                delta = abs(old[name] - getattr(new, name))
                if delta > tolerance:
                    problems.append(f"{query}: {new.passage_id} {name} differs by {delta:.6f}")
            for name in ("fused_rank", "lexical_rank", "semantic_rank"):
                was, now = old[name], getattr(new, name)
                shift = PLATFORM_RANK_SHIFT if name != "lexical_rank" else 0
                if (was is None) != (now is None) or (was is not None and abs(was - now) > shift):
                    problems.append(f"{query}: {new.passage_id} {name} {was} vs {now}")
    return problems
