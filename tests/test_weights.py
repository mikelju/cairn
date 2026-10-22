"""Pinned model weights: hash checks, the missing-weights error and offline loading."""

import hashlib
import json
from pathlib import Path

import pytest

from cairn import weights

pytestmark = pytest.mark.usefixtures("block_sockets")


def fake_manifest(tmp_path: Path, content: bytes = b"weights") -> tuple[dict[str, object], Path]:
    models = tmp_path / "models"
    manifest: dict[str, object] = {
        "fake/model": {
            "repo": "org/fake",
            "revision": "r1",
            "model_file": "m.onnx",
            "files": {"m.onnx": {"sha256": hashlib.sha256(content).hexdigest(), "bytes": 7}},
        }
    }
    return manifest, models


def place(models: Path, content: bytes) -> None:
    folder = models / "models--org--fake" / "snapshots" / "r1"
    folder.mkdir(parents=True)
    (folder / "m.onnx").write_bytes(content)


def test_weights_manifest_pins_both_models() -> None:
    manifest = weights.load_weights()
    assert set(manifest) == {"BAAI/bge-small-en-v1.5", "BAAI/bge-reranker-v2-m3-int8"}
    for entry in manifest.values():
        assert len(entry["revision"]) == 40
        assert entry["model_file"] in entry["files"]
        for info in entry["files"].values():
            assert len(info["sha256"]) == 64
            assert info["bytes"] > 0
    assert json.loads(weights.WEIGHTS_PATH.read_text()) == manifest


def test_weights_missing_gives_run_make_weights(tmp_path: Path) -> None:
    manifest, models = fake_manifest(tmp_path)
    with pytest.raises(weights.WeightsError, match="weights missing: run make weights"):
        weights.verify_model("fake/model", models, manifest)


def test_weights_hash_mismatch_refused(tmp_path: Path) -> None:
    manifest, models = fake_manifest(tmp_path)
    place(models, b"altered")
    with pytest.raises(weights.WeightsError, match="hash mismatch"):
        weights.verify_model("fake/model", models, manifest)


def test_weights_verify_returns_snapshot_folder(tmp_path: Path) -> None:
    manifest, models = fake_manifest(tmp_path)
    place(models, b"weights")
    folder = weights.verify_model("fake/model", models, manifest)
    assert folder == models / "models--org--fake" / "snapshots" / "r1"


def test_weights_download_refuses_mismatch_and_removes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, models = fake_manifest(tmp_path)

    def fake_download(repo: str, filename: str, revision: str, cache_dir: str) -> str:
        assert (repo, filename, revision) == ("org/fake", "m.onnx", "r1")
        place(Path(cache_dir), b"altered")
        return str(Path(cache_dir) / "models--org--fake" / "snapshots" / "r1" / filename)

    monkeypatch.setattr(weights, "hf_hub_download", fake_download)
    with pytest.raises(weights.WeightsError, match="hash mismatch"):
        weights.download_weights(models, manifest)
    assert not (models / "models--org--fake" / "snapshots" / "r1" / "m.onnx").exists()


def test_weights_models_dir_reads_cairn_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAIRN_MODELS", str(tmp_path))
    assert weights.models_dir() == tmp_path
    monkeypatch.delenv("CAIRN_MODELS")
    assert weights.models_dir().name == "models"


def test_weights_embedder_loads_offline() -> None:
    model = weights.load_embedder()
    vector = next(iter(model.embed(["maximum safe starting dose"])))
    assert vector.shape == (384,)


def test_weights_reranker_loads_offline() -> None:
    model = weights.load_reranker()
    query = "What is the highest dose with no observed adverse effect?"
    documents = [
        "The NOAEL is the highest dose level that does not produce adverse effects.",
        "Rain.",
    ]
    scores = list(model.rerank(query, documents))
    assert scores[0] > scores[1]
