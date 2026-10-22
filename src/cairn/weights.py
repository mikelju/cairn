"""Pinned model weights: download with SHA-256 checks, offline loading from the cache only.

`data/guidance/weights.json` pins, per model, the Hugging Face repo, the commit revision and the
SHA-256 of every file fastembed reads.
`download_weights` is the only code that touches the network; the loaders verify the cache and
load with `specific_model_path`, so a missing or altered file stops the run before any download.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download

from cairn.passages import GUIDANCE_DIR

WEIGHTS_PATH = GUIDANCE_DIR / "weights.json"
EMBEDDER = "BAAI/bge-small-en-v1.5"
RERANKER = "BAAI/bge-reranker-v2-m3-int8"
MISSING = "weights missing: run make weights"

_verified: dict[tuple[str, str], Path] = {}


class WeightsError(Exception):
    pass


def load_weights(path: Path = WEIGHTS_PATH) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return manifest


def models_dir() -> Path:
    """The cache folder: `CAIRN_MODELS`, or `~/.cache/cairn/models`."""
    configured = os.environ.get("CAIRN_MODELS")
    return Path(configured) if configured else Path.home() / ".cache" / "cairn" / "models"


def snapshot_folder(entry: dict[str, Any], models: Path) -> Path:
    """The folder `huggingface_hub` fills for the pinned revision of one repo."""
    repo_folder = "models--" + str(entry["repo"]).replace("/", "--")
    return models / repo_folder / "snapshots" / str(entry["revision"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_file(path: Path, expected: str) -> None:
    if _sha256(path) != expected:
        raise WeightsError(f"hash mismatch for {path.name}: refusing weights that are not pinned")


def verify_model(name: str, models: Path, manifest: dict[str, Any] | None = None) -> Path:
    """Check every pinned file of one model and return its snapshot folder."""
    manifest = manifest if manifest is not None else load_weights()
    entry = manifest[name]
    folder = snapshot_folder(entry, models)
    key = (name, str(folder))
    if key in _verified:
        return folder
    for relative, info in sorted(entry["files"].items()):
        path = folder / relative
        if not path.is_file():
            raise WeightsError(MISSING)
        _check_file(path, info["sha256"])
    _verified[key] = folder
    return folder


def download_weights(
    models: Path, manifest: dict[str, Any] | None = None
) -> list[tuple[str, str, int]]:
    """Download every pinned file at its pinned revision and refuse any hash mismatch."""
    manifest = manifest if manifest is not None else load_weights()
    done: list[tuple[str, str, int]] = []
    for name, entry in sorted(manifest.items()):
        for relative, info in sorted(entry["files"].items()):
            path = Path(
                hf_hub_download(
                    entry["repo"], relative, revision=entry["revision"], cache_dir=str(models)
                )
            )
            try:
                _check_file(path, info["sha256"])
            except WeightsError:
                path.unlink(missing_ok=True)
                raise
            done.append((name, relative, path.stat().st_size))
    return done


def _offline() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"


def load_embedder(models: Path | None = None) -> Any:
    """bge-small-en-v1.5 (int8 ONNX) from the verified cache; never downloads."""
    _offline()
    from fastembed import TextEmbedding

    folder = verify_model(EMBEDDER, models or models_dir())
    return TextEmbedding(EMBEDDER, specific_model_path=str(folder), local_files_only=True)


def load_reranker(models: Path | None = None) -> Any:
    """bge-reranker-v2-m3 (int8 ONNX) from the verified cache; never downloads."""
    _offline()
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    folder = verify_model(RERANKER, models or models_dir())
    return TextCrossEncoder(RERANKER, specific_model_path=str(folder), local_files_only=True)
