"""Fetch the PDS2014 SEND XPT files and pin or verify them in the manifest.

The first fetch of a file pins its SHA-256 in the versioned manifest.
Every later fetch must match the pinned hash or it fails.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

from cairn.canonical import canonical_sha256

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"
VENDORED_DIR = REPO_ROOT / "data" / "pds2014"
RAW_DIR = REPO_ROOT / "data" / "raw" / "pds2014"
DOMAINS = ("DM", "TX", "TS", "DS", "MI", "BW", "PP", "PC")


class ChecksumMismatch(Exception):
    """A fetched or local file does not match its pinned SHA-256."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def save_manifest(manifest: dict[str, Any], path: Path = MANIFEST_PATH) -> None:
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def file_url(manifest: dict[str, Any], name: str) -> str:
    source = manifest["source"]
    return f"{source['base_url']}/{source['commit']}/{source['path']}/{name}"


def snapshot_hash(manifest: dict[str, Any]) -> str:
    """Hash over the pinned file names and SHA-256 values, independent of the source URL."""
    files = {name: entry["sha256"] for name, entry in manifest["files"].items()}
    return canonical_sha256(files)


def verify_dir(manifest: dict[str, Any], directory: Path) -> str:
    """Check every pinned file in a directory and return the snapshot hash."""
    for name, entry in sorted(manifest["files"].items()):
        actual = file_sha256(directory / name)
        if actual != entry["sha256"]:
            raise ChecksumMismatch(f"{name}: expected {entry['sha256']}, got {actual}")
    return snapshot_hash(manifest)


def fetch(manifest: dict[str, Any], target: Path) -> tuple[dict[str, Any], list[str]]:
    """Download every domain into target, pinning new files and verifying pinned ones."""
    target.mkdir(parents=True, exist_ok=True)
    files: dict[str, Any] = dict(manifest.get("files", {}))
    pinned: list[str] = []
    for domain in DOMAINS:
        name = f"{domain.lower()}.xpt"
        destination = target / name
        with urllib.request.urlopen(file_url(manifest, name)) as response:
            destination.write_bytes(response.read())
        actual = file_sha256(destination)
        if name in files:
            if files[name]["sha256"] != actual:
                destination.unlink()
                raise ChecksumMismatch(f"{name}: expected {files[name]['sha256']}, got {actual}")
        else:
            files[name] = {"domain": domain, "sha256": actual, "bytes": destination.stat().st_size}
            pinned.append(name)
    return {**manifest, "files": files}, pinned


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    target = Path(args[0]) if args else RAW_DIR
    manifest, pinned = fetch(load_manifest(), target)
    if pinned:
        save_manifest(manifest)
    print(f"Fetched {len(DOMAINS)} files into {target}; newly pinned: {len(pinned)}")
    print(f"Snapshot hash: {snapshot_hash(manifest)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
