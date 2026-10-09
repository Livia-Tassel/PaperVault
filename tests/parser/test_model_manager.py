import hashlib
import json
from pathlib import Path

import pytest

from papervault.model_manager import MANIFEST_NAME, ModelManager, validate_bundle
from papervault.parsers import parse_pdf


def make_bundle(root: Path):
    root.mkdir()
    files = []
    for name in ["docling-project--docling-layout-heron/config.json",
                 "docling-project--docling-layout-heron/preprocessor_config.json",
                 "docling-project--docling-layout-heron/model.safetensors",
                 "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
                 "docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors"]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = b"test file; not an actual model"
        path.write_bytes(content)
        files.append({"path": name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    (root / MANIFEST_NAME).write_text(json.dumps({"schema_version": 1, "files": files}), encoding="utf-8")
    return root


def test_import_checksums_and_offline_status(tmp_path):
    source = make_bundle(tmp_path / "source")
    manager = ModelManager(tmp_path / "models")
    assert manager.status()["phase"] == "missing"
    assert manager.import_directory(source)["ready"]
    target = manager.root / "docling-project--docling-layout-heron/config.json"
    # Same-size corruption still invalidates readiness via the digest, not just file size.
    target.write_bytes(b"x" * target.stat().st_size)
    assert manager.status()["phase"] == "invalid"


def test_import_rejects_path_traversal(tmp_path):
    source = make_bundle(tmp_path / "source")
    path = source / MANIFEST_NAME
    manifest = json.loads(path.read_text())
    manifest["files"].append({"path": "../outside", "size": 1, "sha256": "0" * 64})
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="path"):
        validate_bundle(source)


def test_missing_models_fail_before_pdf_or_network_access(tmp_path):
    with pytest.raises(RuntimeError, match="models are missing"):
        parse_pdf(tmp_path / "not-even-opened.pdf", tmp_path / "output", tmp_path / "models")
    assert not (tmp_path / "output").exists()


def test_failed_import_keeps_error_visible(tmp_path):
    manager = ModelManager(tmp_path / "models")
    state = manager.import_directory(tmp_path / "missing")
    assert not state["ready"]
    assert state["phase"] == "error"
    assert state["error"]
