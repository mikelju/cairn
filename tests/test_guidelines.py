import shutil
from pathlib import Path

import pytest

from cairn import fetch, guidelines

FIELDS = (
    "title",
    "filename",
    "source_url",
    "sha256",
    "bytes",
    "license_note",
    "retrieved",
    "page_link_base",
)


def test_guidelines_manifest_has_four_complete_entries() -> None:
    manifest = guidelines.load_manifest()
    entries = manifest["guidelines"]
    assert sorted(entries) == ["fda-2005", "ich-m3r2", "ich-m4sr2", "ich-s9"]
    for entry in entries.values():
        for field in FIELDS:
            assert entry[field], field
        assert len(entry["sha256"]) == 64
        assert entry["source_url"].startswith("https://")
        assert entry["page_link_base"].startswith("https://")


def test_guidelines_manifest_file_hashes_match() -> None:
    manifest = guidelines.load_manifest()
    first = guidelines.verify_dir(manifest, guidelines.GUIDELINES_DIR)
    assert first == guidelines.snapshot_hash(manifest)
    for entry in manifest["guidelines"].values():
        path = guidelines.GUIDELINES_DIR / entry["filename"]
        assert path.stat().st_size == entry["bytes"]


def test_guideline_checksum_mismatch(tmp_path: Path) -> None:
    manifest = guidelines.load_manifest()
    shutil.copytree(guidelines.GUIDELINES_DIR, tmp_path / "g")
    victim = manifest["guidelines"]["ich-s9"]["filename"]
    with (tmp_path / "g" / victim).open("ab") as handle:
        handle.write(b"x")
    with pytest.raises(fetch.ChecksumMismatch):
        guidelines.verify_dir(manifest, tmp_path / "g")


def local_manifest(source_dir: Path, pinned: bool) -> dict[str, object]:
    manifest = guidelines.load_manifest()
    for entry in manifest["guidelines"].values():
        entry["source_url"] = (source_dir / entry["filename"]).as_uri()
        if not pinned:
            entry["sha256"] = ""
    return manifest


def test_guideline_fetch_pins_then_verifies(tmp_path: Path) -> None:
    pinned_manifest, pinned = guidelines.fetch_guidelines(
        local_manifest(guidelines.GUIDELINES_DIR, pinned=False), tmp_path / "a"
    )
    assert len(pinned) == 4
    assert [e["sha256"] for e in pinned_manifest["guidelines"].values()] == [
        e["sha256"] for e in guidelines.load_manifest()["guidelines"].values()
    ]
    _, again = guidelines.fetch_guidelines(pinned_manifest, tmp_path / "b")
    assert again == []


def test_guideline_fetch_rejects_a_changed_source(tmp_path: Path) -> None:
    source = tmp_path / "src"
    shutil.copytree(guidelines.GUIDELINES_DIR, source)
    with (source / "S9_Guideline.pdf").open("ab") as handle:
        handle.write(b"x")
    with pytest.raises(fetch.ChecksumMismatch):
        guidelines.fetch_guidelines(local_manifest(source, pinned=True), tmp_path / "out")
