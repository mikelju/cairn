"""Per-page text, sections, passages and sentences of the four pinned guidelines.

Pipeline: pdfium page text -> noise-free page text -> sections from the guideline numbering ->
passages (one per section, or per group of paragraphs when a section is above `WORD_LIMIT` words)
-> sentences.
Everything is deterministic: same PDFs, same code, byte-identical `data/guidance/passages.json`.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from cairn.guidelines import GUIDELINES_DIR, load_manifest, snapshot_hash

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDANCE_DIR = REPO_ROOT / "data" / "guidance"
PASSAGES_PATH = GUIDANCE_DIR / "passages.json"

WORD_LIMIT = 300

# Short code used in passage IDs, for each manifest key.
DOC_CODES = {"fda-2005": "FDA", "ich-m3r2": "M3", "ich-m4sr2": "M4S", "ich-s9": "S9"}

# Page header lines repeated on every page, removed from the page text.
HEADER_PATTERNS: dict[str, re.Pattern[str]] = {
    "fda-2005": re.compile(r"^Contains Nonbinding Recommendations$"),
    "ich-m3r2": re.compile(
        r"^(Guidance on Nonclinical Safety Studies|"
        r"for the Conduct of Human Clinical Trials and Marketing Authorization for "
        r"Pharmaceuticals)$"
    ),
    "ich-m4sr2": re.compile(r"^The Common Technical Document - Safety$"),
    "ich-s9": re.compile(r"^Nonclinical Evaluation for Anticancer Pharmaceuticals$"),
}
# Lone page numbers (arabic or roman) within the first 4 or last 3 lines of a page are removed.
PAGE_NUMBER = re.compile(r"^(\d{1,3}|[ivxl]+)$")
# The first heading of the body (earlier matches are cover pages, histories or contents).
# The appendices of M4S(R2) and the FDA guidance are example tables and derivations: not indexed.
STOP_PATTERNS: dict[str, re.Pattern[str]] = {
    "fda-2005": re.compile(r"^APPENDIX A"),
    "ich-m4sr2": re.compile(r"^APPENDIX A"),
}
FIRST_SECTION: dict[str, tuple[int, ...]] = {
    "ich-m3r2": (1,),
    "ich-m4sr2": (2, 4),
    "ich-s9": (1,),
}
# M4S(R2) 4.2 lists the Module 4 headings: its sub-numbers stay body text of section 4.2.
NO_SUBSECTIONS: dict[str, tuple[int, ...]] = {"ich-m4sr2": (4, 2)}
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")
UNNUMBERED_FDA = ("REFERENCES", "GLOSSARY")

NUMBERED_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,4})\.?\s+([A-Z].*)$")
ROMAN_HEADING = re.compile(r"^(I{1,3}|IV|VI{0,3}|IX)\.\s+([A-Z].*)$")
LETTER_HEADING = re.compile(r"^([A-H])\.\s+([A-Z].*)$")
DOT_LEADERS = re.compile(r"\.{6,}")
SENTENCE_END = re.compile(r"(?<=[.?!])\s+(?=[A-Z0-9(\[])")
ABBREVIATIONS = ("e.g.", "i.e.", "vs.", "et al.", "Fig.", "Figs.", "No.", "Nos.", "Refs.", "Ref.")


def normalize_whitespace(text: str) -> str:
    """The one normalisation used to compare text: every run of whitespace becomes one space.

    Python whitespace (spaces, tabs, line breaks, no-break spaces) collapses to a single space and
    the ends are stripped.
    Nothing else changes: no case folding, no punctuation or hyphen edits, no Unicode folding.
    """
    return " ".join(text.split())


class Sentence(BaseModel):
    model_config = ConfigDict(frozen=True)

    sentence_id: str
    text: str


class Passage(BaseModel):
    model_config = ConfigDict(frozen=True)

    passage_id: str
    doc: str
    section: str
    page_start: int
    page_end: int
    text: str
    sentences: list[Sentence]


def _clean_page(raw: str, header: re.Pattern[str]) -> str:
    lines = [line.strip() for line in raw.replace("\x02", "-").splitlines()]
    lines = [line for line in lines if line and not header.match(line)]
    last = len(lines)
    kept = [
        line
        for index, line in enumerate(lines)
        if not (PAGE_NUMBER.match(line) and (index < 4 or index >= last - 3))
    ]
    return "\n".join(kept)


def page_texts(key: str, directory: Path = GUIDELINES_DIR) -> list[str]:
    """Text of every page of a guideline (index 0 is page 1), headers and page numbers removed.

    pdfium's soft-hyphen marker (U+0002) becomes a hyphen; line breaks are kept.
    """
    entry = load_manifest()["guidelines"][key]
    pdf = pdfium.PdfDocument(str(directory / entry["filename"]))
    try:
        pages = []
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            pages.append(_clean_page(textpage.get_text_bounded(), HEADER_PATTERNS[key]))
            textpage.close()
            page.close()
        return pages
    finally:
        pdf.close()


Line = tuple[int, str]  # (page number, text of one line)


@dataclass
class Section:
    section: str
    lines: list[Line] = field(default_factory=list)


def _follows(new: tuple[int, ...], current: tuple[int, ...]) -> bool:
    """Whether a numbered heading can come right after the current one in the document."""
    if new <= current:
        return False
    if new[: len(current)] == current:
        return len(new) <= len(current) + 2 and new[len(current)] <= 2
    index = next(i for i, (a, b) in enumerate(zip(new, current, strict=False)) if a != b)
    gap = new[index] - current[index]
    return gap <= (1 if index == 0 and len(new) == 1 else 2 if index == 0 else 3)


def _is_toc(page: str) -> bool:
    return sum(1 for line in page.splitlines() if DOT_LEADERS.search(line)) >= 3


def _wrapped(title: str, nxt: str) -> bool:
    """Whether the next line continues a heading that wraps over two lines."""
    if not nxt or nxt.endswith(".") or len(nxt.split()) > 6:
        return False
    if title.count("(") > title.count(")"):
        return True
    if title.isupper():
        return nxt.isupper()
    if title.split()[-1].lower() in WRAP_WORDS and nxt[0].isalpha():
        return True
    return all(
        word[0].isupper() or word[0].isdigit() or word in SMALL_WORDS for word in nxt.split()
    )


SMALL_WORDS = {"and", "or", "of", "to", "the", "for", "in", "on", "at", "by", "with"}
WRAP_WORDS = {"and", "or", "of", "to", "the", "for", "in", "into", "with", "on", "by", "at", "from"}


def split_sections(key: str, pages: list[str]) -> list[Section]:
    """Cut the body of a guideline into sections following its own heading numbering."""
    stop = STOP_PATTERNS.get(key)
    sections: list[Section] = []
    numbered: tuple[int, ...] | None = None
    roman = -1
    letter = ""
    skip = 0
    for number, page in enumerate(pages, start=1):
        if _is_toc(page):
            continue
        lines = page.splitlines()
        for index, line in enumerate(lines):
            if skip:
                skip -= 1
                continue
            if stop and stop.match(line):
                return sections
            found, title = _heading(key, line, numbered, roman, letter)
            if found is None:
                if sections:
                    sections[-1].lines.append((number, line))
                continue
            if isinstance(found, tuple):
                numbered = found
                label = ".".join(str(part) for part in found)
            else:
                label = found
                roman, letter = _roman_state(found)
            following = lines[index + 1 :]
            while following and _wrapped(title, following[0]):
                title += " " + following.pop(0)
                skip += 1
            sections.append(Section(label))
    return sections


def _roman_state(label: str) -> tuple[int, str]:
    if label in UNNUMBERED_FDA:
        return 99, ""
    head, _, tail = label.partition(".")
    return ROMAN.index(head), tail


def _heading(
    key: str, line: str, numbered: tuple[int, ...] | None, roman: int, letter: str
) -> tuple[tuple[int, ...] | str | None, str]:
    if key == "fda-2005":
        return _heading_fda(line, roman, letter)
    match = NUMBERED_HEADING.match(line)
    if not match or len(match.group(2).split()) > 14 or match.group(2).endswith((";", ",")):
        return None, ""
    parts = tuple(int(part) for part in match.group(1).split("."))
    if len(parts) == 1 and not match.group(2).isupper():
        return None, ""
    if parts[: len(NO_SUBSECTIONS.get(key, ()))] == NO_SUBSECTIONS.get(key) and len(parts) > len(
        NO_SUBSECTIONS[key]
    ):
        return None, ""
    allowed = parts == FIRST_SECTION[key] if numbered is None else _follows(parts, numbered)
    return (parts, match.group(2)) if allowed else (None, "")


def _heading_fda(line: str, roman: int, letter: str) -> tuple[str | None, str]:
    if line in UNNUMBERED_FDA:
        return line, line
    match = ROMAN_HEADING.match(line)
    if match and ROMAN.index(match.group(1)) == roman + 1:
        return match.group(1), match.group(2)
    match = LETTER_HEADING.match(line)
    if match and 0 <= roman < len(ROMAN):
        expected = "A" if not letter else chr(ord(letter) + 1)
        if match.group(1) == expected:
            return f"{ROMAN[roman]}.{expected}", match.group(2)
    return None, ""


def _words(lines: list[Line]) -> int:
    return sum(len(text.split()) for _, text in lines)


def _paragraphs(lines: list[Line]) -> list[list[Line]]:
    """Group lines into paragraphs: a short line ending a sentence closes its paragraph."""
    longest: dict[int, int] = {}
    for page, text in lines:
        longest[page] = max(longest.get(page, 0), len(text))
    paragraphs: list[list[Line]] = [[]]
    for index, (page, text) in enumerate(lines):
        paragraphs[-1].append((page, text))
        ends = text.endswith((".", "?", "!", ":")) and len(text) < 0.8 * longest[page]
        if ends and index + 1 < len(lines):
            paragraphs.append([])
    return [p for p in paragraphs if p]


def _cut(lines: list[Line]) -> list[list[Line]]:
    """Split one long paragraph into pieces of at most WORD_LIMIT words, cutting at line ends."""
    pieces: list[list[Line]] = []
    current: list[Line] = []
    for line in lines:
        if current and _words(current) + len(line[1].split()) > WORD_LIMIT:
            at = max(
                (i + 1 for i, (_, t) in enumerate(current) if t.endswith((".", "?", "!"))),
                default=0,
            )
            at = at if at else len(current)
            pieces.append(current[:at])
            current = current[at:]
        current.append(line)
    return [*pieces, current] if current else pieces


def chunk_section(lines: list[Line]) -> list[list[Line]]:
    """One chunk for a section up to WORD_LIMIT words, else paragraphs packed up to WORD_LIMIT."""
    if _words(lines) <= WORD_LIMIT:
        return [lines]
    chunks: list[list[Line]] = []
    current: list[Line] = []
    for paragraph in _paragraphs(lines):
        for piece in _cut(paragraph) if _words(paragraph) > WORD_LIMIT else [paragraph]:
            if current and _words(current) + _words(piece) > WORD_LIMIT:
                chunks.append(current)
                current = []
            current = [*current, *piece]
    return [*chunks, current] if current else chunks


def split_sentences(text: str) -> list[str]:
    """Split normalised text into sentences; every sentence is a literal substring of the text."""
    sentences: list[str] = []
    start = 0
    for match in SENTENCE_END.finditer(text):
        before = text[start : match.start()]
        if before.endswith(ABBREVIATIONS) or re.search(r"(?:^|\s)[A-Z]\.$", before):
            continue
        sentences.append(before)
        start = match.end()
    sentences.append(text[start:])
    return [s for s in sentences if s]


def build_passages(directory: Path = GUIDELINES_DIR) -> list[Passage]:
    passages: list[Passage] = []
    for key in sorted(DOC_CODES):
        for section in split_sections(key, page_texts(key, directory)):
            for number, chunk in enumerate(chunk_section(section.lines), start=1):
                text = normalize_whitespace(" ".join(line for _, line in chunk))
                if not text:
                    continue
                passage_id = f"{DOC_CODES[key]}-{section.section}-{number:02d}"
                passages.append(
                    Passage(
                        passage_id=passage_id,
                        doc=key,
                        section=section.section,
                        page_start=chunk[0][0],
                        page_end=chunk[-1][0],
                        text=text,
                        sentences=[
                            Sentence(sentence_id=f"{passage_id}.s{i}", text=sentence)
                            for i, sentence in enumerate(split_sentences(text), start=1)
                        ],
                    )
                )
    return passages


def passages_json(passages: list[Passage], directory: Path = GUIDELINES_DIR) -> str:
    manifest = load_manifest(directory / "manifest.json") if directory != GUIDELINES_DIR else None
    snapshot = snapshot_hash(manifest or load_manifest())
    payload: dict[str, Any] = {
        "guidelines_snapshot": snapshot,
        "passages": [p.model_dump() for p in passages],
    }
    return json.dumps(payload, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def write_passages(path: Path = PASSAGES_PATH, directory: Path = GUIDELINES_DIR) -> int:
    """Build every passage from the pinned PDFs and write the file; returns the passage count."""
    passages = build_passages(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(passages_json(passages, directory).encode("utf-8"))
    return len(passages)


def load_passages(path: Path = PASSAGES_PATH) -> list[Passage]:
    return [Passage.model_validate(p) for p in json.loads(path.read_text("utf-8"))["passages"]]


def verify_sentences(
    passages: list[Passage], loader: Callable[[str], list[str]] = page_texts
) -> list[str]:
    """Return one problem per sentence not found literally on the text of its page range."""
    cache: dict[str, list[str]] = {}
    problems: list[str] = []
    for passage in passages:
        pages = cache.setdefault(passage.doc, loader(passage.doc))
        span = normalize_whitespace(" ".join(pages[passage.page_start - 1 : passage.page_end]))
        problems.extend(
            f"{s.sentence_id}: not on pages {passage.page_start}-{passage.page_end}"
            for s in passage.sentences
            if normalize_whitespace(s.text) not in span
        )
    return problems
