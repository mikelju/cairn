"""E4: guidance retrieval against hand-labelled questions, offline.

Every question runs once per session (the reranker takes about 9 s a query on CPU).
In-library questions are labelled by guideline, passage and anchor sentence; the metrics are
recall@5 and MRR over the top 5, with the reranker and without it (the RRF order alone).
Out-of-library questions must abstain; quotations must be stored sentences found verbatim
on the cited pages.
"""

import json
import socket
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from cairn import retrieval
from cairn.content import QuoteRef
from cairn.passages import load_passages, normalize_whitespace, page_texts
from cairn.render import quote_data

E4_PATH = Path(__file__).parent / "e4_questions.json"
RECALL_FLOOR = 0.9
TOP = retrieval.TOP


@dataclass
class Report:
    questions: list[dict[str, Any]]
    fused: dict[str, list[str]]
    reranked: dict[str, list[retrieval.RankedHit]]
    guidance: dict[str, retrieval.Guidance]
    seconds: float


def _refuse(*args: object, **kwargs: object) -> None:
    raise RuntimeError("network blocked in this test")


def _rank(ids: list[str], wanted: str) -> int | None:
    return ids.index(wanted) + 1 if wanted in ids else None


def _recall_mrr(ranks: list[int | None]) -> tuple[float, float]:
    found = [r for r in ranks if r is not None]
    return len(found) / len(ranks), sum(1 / r for r in found) / len(ranks)


@pytest.fixture(scope="module")
def e4() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(E4_PATH.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def report(e4: dict[str, Any]) -> Iterator[Report]:
    """Retrieve every question once with sockets blocked for the whole module."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket, "connect", _refuse)
        patch.setattr(socket.socket, "connect_ex", _refuse)
        patch.setattr(socket, "getaddrinfo", _refuse)
        started = time.perf_counter()
        index = retrieval.build_index()
        questions = e4["in_library"] + e4["out_of_library"]
        fused: dict[str, list[str]] = {}
        reranked: dict[str, list[retrieval.RankedHit]] = {}
        guidance: dict[str, retrieval.Guidance] = {}
        for entry in questions:
            query = entry["question"]
            fused[query] = [h.passage_id for h in index.search(query, TOP)]
            reranked[query] = index.rerank(query)
            guidance[query] = retrieval.decide(query, reranked[query])
        yield Report(questions, fused, reranked, guidance, time.perf_counter() - started)


def test_e4_labels_match_the_stored_passages(e4: dict[str, Any]) -> None:
    passages = {p.passage_id: p for p in load_passages()}
    assert 20 <= len(e4["in_library"]) <= 30
    assert len(e4["out_of_library"]) == 5
    guidelines = set()
    for entry in e4["in_library"]:
        passage = passages[entry["passage_id"]]
        assert passage.doc == entry["guideline"]
        assert (passage.page_start, passage.page_end) == (entry["page_start"], entry["page_end"])
        assert entry["anchor_sentence_id"] in {s.sentence_id for s in passage.sentences}
        guidelines.add(entry["guideline"])
    assert len(guidelines) == 4
    questions = [e["question"] for e in e4["in_library"] + e4["out_of_library"]]
    assert len(set(questions)) == len(questions)


def test_e4_questions_disjoint_from_the_fixed_and_calibration_queries(e4: dict[str, Any]) -> None:
    own = {e["question"].casefold() for e in e4["in_library"] + e4["out_of_library"]}
    fixed = {q["query"].casefold() for q in retrieval.load_fixed_queries()}
    calibration = retrieval.load_calibration()
    used = {e["question"].casefold() for k in retrieval.CALIBRATION_SETS for e in calibration[k]}
    assert not own & (fixed | used)


def test_e4_retrieval_report(report: Report, e4: dict[str, Any]) -> None:
    labelled = e4["in_library"]
    with_rerank: list[int | None] = []
    without: list[int | None] = []
    lines = []
    for entry in labelled:
        query, wanted = entry["question"], entry["passage_id"]
        r_rank = _rank([h.passage_id for h in report.reranked[query]], wanted)
        f_rank = _rank(report.fused[query], wanted)
        with_rerank.append(r_rank)
        without.append(f_rank)
        lines.append(f"  {wanted:16} rerank {r_rank or '-'}  rrf {f_rank or '-'}  {query[:70]}")
    recall, mrr = _recall_mrr(with_rerank)
    base_recall, base_mrr = _recall_mrr(without)
    verbatim, quoted = _verbatim(report, labelled)
    abstained = sum(report.guidance[e["question"]].abstained for e in e4["out_of_library"])
    wrongly = [e["question"] for e in labelled if report.guidance[e["question"]].abstained]
    print("\nE4 report")
    print("\n".join(lines))
    print(f"  in-library questions {len(labelled)}, out-of-library {len(e4['out_of_library'])}")
    print(f"  with reranker    recall@{TOP} {recall:.3f}  MRR {mrr:.3f}")
    print(f"  without reranker recall@{TOP} {base_recall:.3f}  MRR {base_mrr:.3f}")
    print(f"  quotation verbatim rate {verbatim}/{quoted}")
    print(f"  abstained on out-of-library {abstained}/{len(e4['out_of_library'])}")
    print(f"  in-library abstentions {len(wrongly)}")
    print(f"  runtime {report.seconds:.0f} s for {len(report.questions)} questions")
    assert recall >= RECALL_FLOOR
    assert verbatim == quoted
    assert abstained == len(e4["out_of_library"])


def _verbatim(report: Report, labelled: list[dict[str, Any]]) -> tuple[int, int]:
    """Quote every sentence of each question's best passage; count those verbatim on its pages."""
    passages = {p.passage_id: p for p in load_passages()}
    pages: dict[str, list[str]] = {}
    found = total = 0
    for entry in labelled:
        hits = report.reranked[entry["question"]]
        passage = passages[hits[0].passage_id]
        doc_pages = pages.setdefault(passage.doc, page_texts(passage.doc))
        span = normalize_whitespace(" ".join(doc_pages[passage.page_start - 1 : passage.page_end]))
        for sentence in passage.sentences:
            ref = QuoteRef(passage_id=passage.passage_id, sentence_ids=[sentence.sentence_id])
            total += 1
            found += normalize_whitespace(str(quote_data(ref)["text"])) in span
    return found, total
