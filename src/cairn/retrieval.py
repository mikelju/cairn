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
# Scores of the same query agree to this absolute tolerance across runs and platforms.
# BM25 is float64 arithmetic over the same tokens and agrees to rounding; the int8 ONNX embeddings
# may differ in the last digits between Windows and Linux (cosine scores are in [-1, 1]).
# Ranks and fused scores are compared exactly except where two scores lie within this tolerance.
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
# and platforms. The abstention margin (half the gap between the calibration ranges) is far larger.
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
# swapped places at the foot of the top 5. The image check allows these, and nothing larger.
PLATFORM_RERANK_TOLERANCE = 0.5
PLATFORM_SEMANTIC_TOLERANCE = 1e-3
# D113: on linux/amd64 near-tied cosine scores moved a passage by one semantic rank, which moves
# its fused rank by one and its RRF score by at most 1/(60+r) - 1/(61+r), under 3e-4 for r >= 1.
PLATFORM_RANK_SHIFT = 1
PLATFORM_FUSED_TOLERANCE = 5e-4


def check_cache(index: Index, path: Path = CACHE_PATH) -> list[str]:
    """Differences between the committed cache and a fresh retrieval of every cached query.

    Built for the image build, which may run on another platform than the one that wrote the cache.
    Per query: the best passage is the same; at most one of the five passages differs (the last one;
    foot of the top 5); the reranker score at every position agrees within
    `PLATFORM_RERANK_TOLERANCE`; for passages in both lists, lexical and fused scores agree within
    `SCORE_TOLERANCE`, fused scores within `PLATFORM_FUSED_TOLERANCE`, semantic scores within
    `PLATFORM_SEMANTIC_TOLERANCE`; the lexical rank is equal and the semantic and fused ranks differ
    by at most `PLATFORM_RANK_SHIFT`. An empty list means the cache is current.
    """
    problems: list[str] = []
    for query, stored in sorted(_read(path)["queries"].items()):
        fresh = index.rerank(query)
        old_ids = [h["passage_id"] for h in stored]
        new_ids = [h.passage_id for h in fresh]
        found = {h.passage_id: h for h in fresh}
        common = [h for h in stored if h["passage_id"] in found]
        if old_ids[0] != new_ids[0] or len(common) < len(stored) - 1:
            problems.append(f"{query}: ranked passages differ: {old_ids} vs {new_ids}")
            continue
        for position, (old, new) in enumerate(zip(stored, fresh, strict=True), start=1):
            delta = abs(old["rerank_score"] - new.rerank_score)
            if delta > PLATFORM_RERANK_TOLERANCE:
                problems.append(f"{query}: position {position} rerank_score differs by {delta:.4f}")
        for old in common:
            new = found[old["passage_id"]]
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
