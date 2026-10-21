import shutil
from pathlib import Path
from typing import Any

import pytest

from cairn import fetch


def local_manifest(source_dir: Path, files: dict[str, Any] | None = None) -> dict[str, Any]:
    pinned = fetch.load_manifest()
    return {
        "source": {
            "base_url": source_dir.parent.as_uri(),
            "commit": source_dir.name,
            "path": ".",
            "study": "PDS2014",
        },
        "files": pinned["files"] if files is None else files,
    }


def test_manifest_pins_exactly_the_eight_domains() -> None:
    manifest = fetch.load_manifest()
    assert sorted(entry["domain"] for entry in manifest["files"].values()) == sorted(fetch.DOMAINS)
    assert all(len(entry["sha256"]) == 64 for entry in manifest["files"].values())


def test_vendored_files_match_manifest_and_hash_is_stable() -> None:
    manifest = fetch.load_manifest()
    first = fetch.verify_dir(manifest, fetch.VENDORED_DIR)
    second = fetch.verify_dir(fetch.load_manifest(), fetch.VENDORED_DIR)
    assert first == second == fetch.snapshot_hash(manifest)


def test_first_fetch_pins_and_second_fetch_verifies(tmp_path: Path) -> None:
    manifest = local_manifest(fetch.VENDORED_DIR, files={})
    pinned_manifest, pinned = fetch.fetch(manifest, tmp_path / "a")
    assert len(pinned) == 8
    assert pinned_manifest["files"] == fetch.load_manifest()["files"]
    again, pinned_again = fetch.fetch(pinned_manifest, tmp_path / "b")
    assert pinned_again == []
    assert fetch.snapshot_hash(again) == fetch.snapshot_hash(pinned_manifest)


def test_fetch_rejects_a_changed_file(tmp_path: Path) -> None:
    source = tmp_path / "src"
    shutil.copytree(fetch.VENDORED_DIR, source)
    with (source / "pp.xpt").open("ab") as handle:
        handle.write(b"x")
    with pytest.raises(fetch.ChecksumMismatch, match=r"pp\.xpt"):
        fetch.fetch(local_manifest(source), tmp_path / "out")
    assert not (tmp_path / "out" / "pp.xpt").exists()


def test_verify_dir_rejects_a_changed_file(tmp_path: Path) -> None:
    shutil.copytree(fetch.VENDORED_DIR, tmp_path / "copy")
    (tmp_path / "copy" / "dm.xpt").write_bytes(b"tampered")
    with pytest.raises(fetch.ChecksumMismatch, match=r"dm\.xpt"):
        fetch.verify_dir(fetch.load_manifest(), tmp_path / "copy")


def test_main_saves_only_when_pinning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    saved: list[dict[str, Any]] = []
    empty = local_manifest(fetch.VENDORED_DIR, {})
    monkeypatch.setattr(fetch, "load_manifest", lambda: empty)
    monkeypatch.setattr(fetch, "save_manifest", lambda manifest: saved.append(manifest))
    assert fetch.main([str(tmp_path)]) == 0
    assert len(saved) == 1


def test_save_manifest_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    fetch.save_manifest(fetch.load_manifest(), path)
    assert fetch.load_manifest(path) == fetch.load_manifest()
