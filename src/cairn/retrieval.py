"""Hybrid retrieval over the guideline passages: BM25 and bge-small embeddings fused by RRF.

Lexical search is `bm25s` over the passage text; semantic search is the cosine similarity of
bge-small-en-v1.5 (int8 ONNX, loaded from the verified cache by `cairn.weights`, never downloaded).
The two rankings are fused with reciprocal rank fusion, k = 60, and ties are broken by passage ID,
so the order does not depend on array layout or platform.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import bm25s  # type: ignore[import-untyped]
import numpy as np
from pydantic import BaseModel, ConfigDict

from cairn import weights
from cairn.passages import PASSAGES_PATH, Passage, load_passages

RRF_K = 60
# Depth of each ranking that enters the fusion, and size of the fused list returned.
DEPTH = 50
CANDIDATES = 20
# Scores of the same query agree to this absolute tolerance across runs and platforms.
# BM25 is float64 arithmetic over the same tokens and agrees to rounding; the int8 ONNX embeddings
# may differ in the last digits between Windows and Linux (cosine scores are in [-1, 1]).
# Ranks and fused scores are compared exactly except where two scores lie within this tolerance.
SCORE_TOLERANCE = 1e-4


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


@dataclass
class Index:
    ids: list[str]
    retriever: Any
    vectors: np.ndarray[Any, Any]
    embedder: Any

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
    texts = [p.text for p in passages]
    corpus = bm25s.tokenize(texts, stopwords="en", return_ids=False, show_progress=False)
    retriever = bm25s.BM25()
    retriever.index(corpus, show_progress=False)
    embedder = weights.load_embedder(models)
    vectors = np.asarray(list(embedder.embed(texts)), dtype=np.float64)
    return Index(ids=ids, retriever=retriever, vectors=vectors, embedder=embedder)
