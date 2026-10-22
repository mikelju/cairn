import hashlib
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cairn import passages
from cairn.cli import app
from cairn.passages import Passage, Sentence

ID_FORM = re.compile(r"^(M4S|M3|S9|FDA)-[A-Z0-9.]+-\d{2}$")
FIELDS = ("passage_id", "doc", "section", "page_start", "page_end", "text", "sentences")


@pytest.fixture(scope="module")
def built() -> list[Passage]:
    return passages.build_passages()


def test_passages_every_field_present(built: list[Passage]) -> None:
    assert {p.doc for p in built} == set(passages.DOC_CODES)
    for passage in built:
        dumped = passage.model_dump()
        assert tuple(dumped) == FIELDS
        assert passage.text and passage.sentences and passage.section
        assert 1 <= passage.page_start <= passage.page_end


def test_passages_ids_unique_and_well_formed(built: list[Passage]) -> None:
    ids = [p.passage_id for p in built]
    assert len(set(ids)) == len(ids)
    for passage in built:
        assert ID_FORM.match(passage.passage_id), passage.passage_id
        assert passage.passage_id.startswith(
            f"{passages.DOC_CODES[passage.doc]}-{passage.section}-"
        )
        for number, sentence in enumerate(passage.sentences, start=1):
            assert sentence.sentence_id == f"{passage.passage_id}.s{number}"
        assert " ".join(s.text for s in passage.sentences) == passage.text


def test_passages_none_above_word_limit(built: list[Passage]) -> None:
    assert max(len(p.text.split()) for p in built) <= passages.WORD_LIMIT


def test_passages_m4s_repeat_dose_section_exists(built: list[Passage]) -> None:
    found = [p for p in built if p.doc == "ich-m4sr2" and p.section == "2.6.6.3"]
    assert [p.passage_id for p in found] == ["M4S-2.6.6.3-01"]
    assert "Studies should be summarised in order by species" in found[0].text
    assert (found[0].page_start, found[0].page_end) == (13, 13)


def test_passages_fda_noael_definition_exists(built: list[Passage]) -> None:
    found = [p for p in built if p.doc == "fda-2005" and p.section == "IV"]
    definition = [
        s for p in found for s in p.sentences if "Several definitions of NOAEL exist" in s.text
    ]
    assert len(definition) == 1
    assert (
        "the highest dose level that does not produce a significant increase" in definition[0].text
    )


def test_passages_split_sections_by_paragraph_when_long(built: list[Passage]) -> None:
    long_section = [p for p in built if p.doc == "ich-m3r2" and p.section == "7.3"]
    assert len(long_section) > 1
    assert [p.passage_id for p in long_section][:2] == ["M3-7.3-01", "M3-7.3-02"]


def test_passages_headers_and_page_numbers_removed() -> None:
    for key, header in (
        ("ich-m4sr2", "The Common Technical Document - Safety"),
        ("fda-2005", "Contains"),
    ):
        assert all(header not in page for page in passages.page_texts(key))


def test_passages_split_sentences_keeps_abbreviations() -> None:
    text = "Use e.g. a rodent. Then proceed (see Ref. 3). Done."
    assert passages.split_sentences(text) == [
        "Use e.g. a rodent.",
        "Then proceed (see Ref. 3).",
        "Done.",
    ]


def test_passages_normalize_whitespace() -> None:
    assert passages.normalize_whitespace(" a \n\tb\u00a0 c ") == "a b c"


def test_passages_rebuild_hash_equals_committed_file(tmp_path: Path) -> None:
    rebuilt = tmp_path / "passages.json"
    count = passages.write_passages(rebuilt)
    committed = passages.PASSAGES_PATH.read_bytes()
    assert hashlib.sha256(rebuilt.read_bytes()).hexdigest() == hashlib.sha256(committed).hexdigest()
    assert count == len(passages.load_passages())


def test_passages_cli_build_writes_file(tmp_path: Path) -> None:
    target = tmp_path / "passages.json"
    result = CliRunner().invoke(app, ["guidance", "build", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert target.read_bytes() == passages.PASSAGES_PATH.read_bytes()


def test_index_sentences_verbatim() -> None:
    assert passages.verify_sentences(passages.load_passages()) == []


def test_index_sentences_verbatim_fails_on_altered_sentence() -> None:
    original = passages.load_passages()[0]
    altered = Sentence(
        sentence_id=original.sentences[0].sentence_id, text=original.sentences[0].text + " not"
    )
    planted = original.model_copy(update={"sentences": [altered, *original.sentences[1:]]})
    problems = passages.verify_sentences([planted])
    assert len(problems) == 1
    assert problems[0].startswith(altered.sentence_id)
