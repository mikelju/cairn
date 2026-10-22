"""Pin or verify the four public guideline PDFs used by guidance retrieval.

Same pattern as `cairn.fetch`: the first fetch of a guideline pins its SHA-256 in the
versioned manifest, every later fetch or local check must match it or fail.
"""

import datetime
import hashlib
import sys
import urllib.request
from pathlib import Path
from typing import Any

from cairn.canonical import canonical_sha256
from cairn.fetch import ChecksumMismatch, file_sha256, save_manifest
from cairn.fetch import load_manifest as _load

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDELINES_DIR = REPO_ROOT / "data" / "guidelines"
MANIFEST_PATH = GUIDELINES_DIR / "manifest.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

__all__ = [
    "GUIDELINES_DIR",
    "ChecksumMismatch",
    "fetch_guidelines",
    "load_manifest",
    "save_manifest",
    "snapshot_hash",
    "verify_dir",
]


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return _load(path)


def snapshot_hash(manifest: dict[str, Any]) -> str:
    """Hash over the guideline IDs and pinned SHA-256 values, independent of the URLs."""
    return canonical_sha256({key: e["sha256"] for key, e in manifest["guidelines"].items()})


def verify_dir(manifest: dict[str, Any], directory: Path) -> str:
    """Check every pinned PDF in a directory and return the snapshot hash."""
    for key, entry in sorted(manifest["guidelines"].items()):
        actual = file_sha256(directory / entry["filename"])
        if actual != entry["sha256"]:
            raise ChecksumMismatch(f"{key}: expected {entry['sha256']}, got {actual}")
    return snapshot_hash(manifest)


def fetch_guidelines(manifest: dict[str, Any], target: Path) -> tuple[dict[str, Any], list[str]]:
    """Download every guideline into target, pinning new entries and verifying pinned ones."""
    target.mkdir(parents=True, exist_ok=True)
    entries: dict[str, Any] = dict(manifest["guidelines"])
    pinned: list[str] = []
    for key, entry in sorted(entries.items()):
        request = urllib.request.Request(entry["source_url"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request) as response:
            content: bytes = response.read()
        actual = hashlib.sha256(content).hexdigest()
        if entry.get("sha256"):
            if entry["sha256"] != actual:
                raise ChecksumMismatch(f"{key}: expected {entry['sha256']}, got {actual}")
        else:
            entries[key] = {
                **entry,
                "sha256": actual,
                "bytes": len(content),
                "retrieved": datetime.date.today().isoformat(),
            }
            pinned.append(key)
        (target / entry["filename"]).write_bytes(content)
    return {**manifest, "guidelines": entries}, pinned


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    target = Path(args[0]) if args else GUIDELINES_DIR
    manifest, pinned = fetch_guidelines(load_manifest(), target)
    if pinned:
        save_manifest(manifest, MANIFEST_PATH)
    count = len(manifest["guidelines"])
    print(f"Fetched {count} guidelines into {target}; newly pinned: {len(pinned)}")
    print(f"Snapshot hash: {snapshot_hash(manifest)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
