"""Highlighted guideline pages: the quoted sentence drawn over its own characters on the PDF page.

The sentence is located in the page text the passages were built from (header lines and page
numbers dropped, whitespace runs collapsed), and each of its characters is mapped back to the
character index of pdfium's text page, so the boxes come from the characters themselves.
A sentence that runs over a page break gets one entry per page.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from PIL import Image, ImageDraw

from cairn.guidelines import GUIDELINES_DIR, load_manifest
from cairn.passages import (
    GUIDANCE_DIR,
    HEADER_PATTERNS,
    PAGE_NUMBER,
    Passage,
    load_passages,
    normalize_whitespace,
)

HIGHLIGHTS_PATH = GUIDANCE_DIR / "highlights.json"
IMAGES_DIR = GUIDANCE_DIR / "highlights"
SCALE = 1.0  # pixels per PDF point
HIGHLIGHT = (255, 214, 0)
TOP_HITS = 3  # the build highlights every sentence of the top hits of each fixed query
# pdfium marks a soft hyphen with U+0002 in bounded text and U+FFFE in range text.
SOFT_HYPHENS = (chr(2), chr(0xFFFE))
BREAKS = ("\r\n", "\n", "\r")


@dataclass
class PageChars:
    """One page: the normalised text and, for each of its characters, the pdfium char index."""

    text: str
    index: list[int]


def page_chars(raw: str, header: re.Pattern[str]) -> PageChars:
    """Clean a page like `passages.page_texts` and keep the raw char index of every character."""
    lines: list[tuple[int, str]] = []
    position = 0
    for part in re.split(r"(\r\n|\n|\r)", raw):
        stripped = part.strip()
        if part not in BREAKS and stripped:
            lines.append((position + len(part) - len(part.lstrip()), stripped))
        position += len(part)
    last = len(lines)
    kept = [
        (start, line)
        for number, (start, line) in enumerate(lines)
        if not header.match(line)
        and not (PAGE_NUMBER.match(line) and (number < 4 or number >= last - 3))
    ]
    text, index = "", []
    for start, line in kept:
        for offset, char in enumerate(line):
            char = "-" if char in SOFT_HYPHENS else char
            if char.isspace():
                if text and text[-1] != " ":
                    text += " "
                    index.append(start + offset)
            else:
                text += char
                index.append(start + offset)
        if text and text[-1] != " ":
            text += " "
            index.append(start + len(line))
    return PageChars(text, index)


def _line_boxes(boxes: list[tuple[float, float, float, float]]) -> list[list[float]]:
    """Merge consecutive character boxes into one rectangle per text line."""
    merged: list[list[float]] = []
    for left, bottom, right, top in boxes:
        if merged:
            line = merged[-1]
            if line[1] <= (bottom + top) / 2 <= line[3] and left >= line[0] - 1:
                line[:] = [
                    min(line[0], left),
                    min(line[1], bottom),
                    max(line[2], right),
                    max(line[3], top),
                ]
                continue
        merged.append([left, bottom, right, top])
    return [[round(v, 2) for v in box] for box in merged]


def locate(
    passage: Passage, sentence_id: str, pages: dict[int, PageChars]
) -> list[tuple[int, list[int]]]:
    """Per page, the pdfium char indices of the sentence (spaces excluded)."""
    sentence = next(s for s in passage.sentences if s.sentence_id == sentence_id)
    joined, owner = "", []
    for number in range(passage.page_start, passage.page_end + 1):
        for position, char in enumerate(pages[number].text):
            joined += char
            owner.append((number, pages[number].index[position]))
        if not joined.endswith(" "):
            joined += " "
            owner.append((number, -1))
    wanted = normalize_whitespace(sentence.text)
    start = joined.find(wanted)
    if start < 0:
        raise ValueError(f"{sentence_id} not found on its pages")
    found: dict[int, list[int]] = {}
    for position in range(start, start + len(wanted)):
        number, char_index = owner[position]
        if char_index >= 0 and not joined[position].isspace():
            found.setdefault(number, []).append(char_index)
    return list(found.items())


def _render(page: Any, boxes: list[list[float]], path: Path) -> None:
    """Render the page, draw the boxes in translucent yellow and save a small palette PNG."""
    image = page.render(scale=SCALE).to_pil().convert("RGBA")
    height = page.get_height()
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for left, bottom, right, top in boxes:
        draw.rectangle(
            [left * SCALE, (height - top) * SCALE, right * SCALE, (height - bottom) * SCALE],
            fill=(*HIGHLIGHT, 110),
        )
    Image.alpha_composite(image, layer).convert("RGB").quantize(colors=8).save(path, optimize=True)


def build_highlights(
    passages: list[Passage],
    sentence_ids: list[str],
    images_dir: Path = IMAGES_DIR,
    directory: Path = GUIDELINES_DIR,
) -> list[dict[str, Any]]:
    """Render the pages and return the highlight entries, writing one PNG per entry."""
    by_id = {p.passage_id: p for p in passages}
    manifest = load_manifest()["guidelines"]
    images_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    documents: dict[str, Any] = {}
    text_pages: dict[tuple[str, int], tuple[Any, PageChars]] = {}
    for sentence_id in sentence_ids:
        passage = by_id[sentence_id.rsplit(".", 1)[0]]
        key = passage.doc
        if key not in documents:
            documents[key] = pdfium.PdfDocument(str(directory / manifest[key]["filename"]))
        pdf = documents[key]
        pages: dict[int, PageChars] = {}
        for number in range(passage.page_start, passage.page_end + 1):
            if (key, number) not in text_pages:
                textpage = pdf[number - 1].get_textpage()
                raw = textpage.get_text_range()
                text_pages[(key, number)] = (textpage, page_chars(raw, HEADER_PATTERNS[key]))
            pages[number] = text_pages[(key, number)][1]
        for number, chars in locate(passage, sentence_id, pages):
            textpage = text_pages[(key, number)][0]
            boxes = _line_boxes([textpage.get_charbox(i) for i in chars])
            name = f"{sentence_id}@p{number}.png"
            page = pdf[number - 1]
            width, height = page.get_size()
            _render(page, boxes, images_dir / name)
            entries.append(
                {
                    "sentence_id": sentence_id,
                    "passage_id": passage.passage_id,
                    "doc": key,
                    "page": number,
                    "char_start": chars[0],
                    "char_end": chars[-1] + 1,
                    "chars": chars,
                    "text": textpage.get_text_range(chars[0], chars[-1] - chars[0] + 1),
                    "boxes": boxes,
                    "page_size": [round(width, 2), round(height, 2)],
                    "scale": SCALE,
                    "image": f"highlights/{name}",
                    "link": f"{manifest[key]['page_link_base']}#page={number}",
                }
            )
    for document in documents.values():
        document.close()
    return entries


def top_sentence_ids(
    passages: list[Passage], cache: dict[str, Any], top: int = TOP_HITS
) -> list[str]:
    """Every sentence of the top hits of each cached query, sorted and without repeats."""
    by_id = {p.passage_id: p for p in passages}
    ids = {
        s.sentence_id
        for hits in cache["queries"].values()
        for hit in hits[:top]
        for s in by_id[hit["passage_id"]].sentences
    }
    return sorted(ids)


def highlights_json(entries: list[dict[str, Any]]) -> str:
    return json.dumps({"highlights": entries}, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def write_highlights(
    cache_path: Path | None = None,
    path: Path = HIGHLIGHTS_PATH,
    images_dir: Path = IMAGES_DIR,
) -> int:
    """Write `highlights.json` and the PNGs for the top hits of the cached queries."""
    from cairn import retrieval

    cache = json.loads((cache_path or retrieval.CACHE_PATH).read_text(encoding="utf-8"))
    passages = load_passages()
    entries = build_highlights(passages, top_sentence_ids(passages, cache), images_dir)
    path.write_text(highlights_json(entries), encoding="utf-8", newline="\n")
    kept = {Path(str(e["image"])).name for e in entries}
    for stale in images_dir.glob("*.png"):
        if stale.name not in kept:
            stale.unlink()
    return len(entries)


def load_highlights(path: Path = HIGHLIGHTS_PATH) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["highlights"]
    return entries
