"""Highlighted pages (C13): boxes cover exactly the quoted characters, links, one PNG per entry."""

import json
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
import pytest
from PIL import Image

from cairn import highlight, retrieval
from cairn.guidelines import GUIDELINES_DIR, load_manifest
from cairn.passages import GUIDANCE_DIR, load_passages, normalize_whitespace


@pytest.fixture(scope="module")
def entries() -> list[dict[str, Any]]:
    return highlight.load_highlights()


@pytest.fixture(scope="module")
def pdfs() -> Any:
    manifest = load_manifest()["guidelines"]
    opened = {
        key: pdfium.PdfDocument(str(GUIDELINES_DIR / entry["filename"]))
        for key, entry in manifest.items()
    }
    yield opened
    for pdf in opened.values():
        pdf.close()


def test_highlight_covers_every_sentence_of_the_top_hits_of_the_fixed_queries(
    entries: list[dict[str, Any]],
) -> None:
    cache = json.loads(retrieval.CACHE_PATH.read_text(encoding="utf-8"))
    wanted = set(highlight.top_sentence_ids(load_passages(), cache))
    assert wanted
    assert {e["sentence_id"] for e in entries} == wanted


def test_highlight_characters_are_exactly_the_quoted_sentence(
    entries: list[dict[str, Any]], pdfs: Any
) -> None:
    sentences = {s.sentence_id: s.text for p in load_passages() for s in p.sentences}
    quoted: dict[str, list[str]] = {}
    for entry in entries:
        textpage = pdfs[entry["doc"]][entry["page"] - 1].get_textpage()
        chars = entry["chars"]
        picked = "".join(textpage.get_text_range(i, 1) for i in chars)
        quoted.setdefault(entry["sentence_id"], []).append(picked)
        assert entry["char_start"] == chars[0] and entry["char_end"] == chars[-1] + 1
    for sentence_id, parts in quoted.items():
        stripped = "".join(parts).replace(chr(0xFFFE), "-").replace(chr(2), "-")
        assert stripped == "".join(sentences[sentence_id].split()), sentence_id


def test_highlight_boxes_cover_the_quoted_characters_and_no_other(
    entries: list[dict[str, Any]], pdfs: Any
) -> None:
    for entry in entries:
        textpage = pdfs[entry["doc"]][entry["page"] - 1].get_textpage()
        chars = set(entry["chars"])

        def inside(point: tuple[float, float], boxes: list[list[float]] = entry["boxes"]) -> bool:
            return any(b[0] <= point[0] <= b[2] and b[1] <= point[1] <= b[3] for b in boxes)

        for index in range(textpage.count_chars()):
            left, bottom, right, top = textpage.get_charbox(index)
            center = ((left + right) / 2, (bottom + top) / 2)
            if textpage.get_text_range(index, 1).strip() == "":
                continue
            assert inside(center) == (index in chars), (entry["sentence_id"], index)


def test_highlight_link_names_the_cited_page(entries: list[dict[str, Any]]) -> None:
    manifest = load_manifest()["guidelines"]
    passages = {p.passage_id: p for p in load_passages()}
    for entry in entries:
        assert entry["link"] == f"{manifest[entry['doc']]['page_link_base']}#page={entry['page']}"
        passage = passages[entry["passage_id"]]
        assert passage.page_start <= entry["page"] <= passage.page_end


def test_highlight_has_a_png_per_entry_at_the_page_size(entries: list[dict[str, Any]]) -> None:
    names = [e["image"] for e in entries]
    assert len(set(names)) == len(entries)
    for entry in entries:
        path = GUIDANCE_DIR / entry["image"]
        with Image.open(path) as image:
            width, height = entry["page_size"]
            assert image.size == (round(width * entry["scale"]), round(height * entry["scale"]))
    assert len(list(highlight.IMAGES_DIR.glob("*.png"))) == len(entries)


def test_highlight_rebuild_equals_the_committed_file(tmp_path: Path) -> None:
    target = tmp_path / "highlights.json"
    count = highlight.write_highlights(path=target, images_dir=tmp_path / "images")
    assert target.read_text(encoding="utf-8") == highlight.HIGHLIGHTS_PATH.read_text(
        encoding="utf-8"
    )
    assert len(list((tmp_path / "images").glob("*.png"))) == count


def test_highlight_locate_fails_on_a_sentence_not_on_the_page() -> None:
    passage = next(p for p in load_passages() if p.passage_id == "FDA-IV-01")
    pages = {
        n: highlight.PageChars("nothing here ", list(range(13)))
        for n in range(passage.page_start, passage.page_end + 1)
    }
    with pytest.raises(ValueError, match="not found"):
        highlight.locate(passage, passage.sentences[0].sentence_id, pages)
    assert normalize_whitespace(" a  b ") == "a b"
