"""Explicit model provisioning with progress, resumable files and local checksums.

Conversion never calls this downloader. A bundle can be prepared once online,
then copied to another machine through import_directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from pathlib import Path, PurePosixPath

import httpx
from filelock import FileLock

MANIFEST_NAME = "papervault-models.json"
MODEL_REPOSITORIES = (
    {"id": "docling-project/docling-layout-heron", "revision": "main", "prefix": ""},
    {"id": "docling-project/docling-models", "revision": "v2.3.0", "prefix": "model_artifacts/tableformer/accurate/"},
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative or ":" in relative:
        raise ValueError("Invalid model bundle path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("Model path escapes its bundle")
    return path


def validate_bundle(root: Path, *, hashes: bool = True) -> dict:
    root = Path(root)
    manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not manifest.get("files"):
        raise ValueError("Missing or unsupported model manifest")
    names = {str(item.get("path", "")) for item in manifest["files"]}
    required = ["docling-project--docling-layout-heron/config.json",
                "docling-project--docling-layout-heron/preprocessor_config.json",
                "docling-project--docling-layout-heron/model.safetensors",
                "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
                "docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors"]
    if not all(item in names for item in required):
        raise ValueError("The bundle does not contain all required layout and TableFormer model files")
    for item in manifest["files"]:
        path = _safe_path(root, item["path"])
        if not path.is_file() or path.stat().st_size != item["size"]:
            raise ValueError(f"Missing or incomplete model file: {item['path']}")
        if hashes and _sha256(path) != item["sha256"]:
            raise ValueError(f"Model checksum mismatch: {item['path']}")
    return manifest


class ModelManager:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._state = {"ready": False, "phase": "missing", "error": None,
                       "bytes_done": 0, "bytes_total": 0, "downloaded_files": 0,
                       "total_files": 0, "current_file": None}
        self._validated_signature = None
        self._active = False

    def _update(self, **values):
        with self._lock:
            self._state.update(values)

    def status(self) -> dict:
        with self._lock:
            if self._active:
                return dict(self._state)
            manifest_path = self.root / MANIFEST_NAME
            if not manifest_path.exists():
                return dict(self._state)
            try:
                manifest = validate_bundle(self.root, hashes=False)
                signature = (manifest_path.stat().st_mtime_ns,
                             tuple((_safe_path(self.root, f["path"]).stat().st_mtime_ns,
                                    _safe_path(self.root, f["path"]).stat().st_size)
                                   for f in manifest["files"]))
                if signature != self._validated_signature:
                    validate_bundle(self.root)
                    self._validated_signature = signature
                total = sum(f["size"] for f in manifest["files"])
                self._state.update(ready=True, phase="ready", error=None,
                                   bytes_done=total, bytes_total=total,
                                   downloaded_files=len(manifest["files"]), total_files=len(manifest["files"]))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self._state.update(ready=False, phase="invalid", error=str(exc))
            return dict(self._state)

    def _begin(self, phase: str):
        with self._lock:
            if self._active:
                raise RuntimeError("A model operation is already running")
            self._active = True
            self._state.update(ready=False, phase=phase, error=None, bytes_done=0,
                               bytes_total=0, downloaded_files=0, total_files=0)

    def _write_manifest(self, manifest):
        temp = self.root / (MANIFEST_NAME + ".tmp")
        temp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temp.replace(self.root / MANIFEST_NAME)

    def download(self) -> dict:
        self._begin("preparing")
        try:
            with FileLock(str(self.root / ".download.lock"), timeout=0):
                with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(90, connect=20)) as client:
                    plan, repositories = [], []
                    for spec in MODEL_REPOSITORIES:
                        response = client.get(f"https://huggingface.co/api/models/{spec['id']}/revision/{spec['revision']}",
                                              params={"blobs": "true"})
                        response.raise_for_status()
                        info = response.json()
                        revision = info["sha"]
                        repositories.append({"id": spec["id"], "revision": revision})
                        for entry in info.get("siblings", []):
                            name = entry["rfilename"]
                            if name.startswith("."):
                                continue
                            if spec["prefix"] and not name.startswith(spec["prefix"]) and not name.upper().startswith("LICENSE"):
                                continue
                            if not spec["prefix"] and ("/" in name or name.endswith((".png", ".jpg", ".onnx"))):
                                continue
                            relative = spec["id"].replace("/", "--") + "/" + name
                            _safe_path(self.root, relative)
                            lfs = entry.get("lfs") or {}
                            plan.append({"path": relative, "size": int(entry.get("size", lfs.get("size", 0))),
                                         "sha256": lfs.get("sha256"),
                                         "url": f"https://huggingface.co/{spec['id']}/resolve/{revision}/{name}"})
                    if not plan or any(p["size"] <= 0 for p in plan):
                        raise ValueError("Model server returned an incomplete file inventory")
                    self._update(phase="downloading", bytes_total=sum(p["size"] for p in plan), total_files=len(plan))
                    completed_bytes, files = 0, []
                    for item in plan:
                        target = _safe_path(self.root, item["path"])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        self._update(current_file=item["path"])
                        if target.is_file() and target.stat().st_size == item["size"]:
                            digest = _sha256(target)
                            valid = not item["sha256"] or digest == item["sha256"]
                        else:
                            valid = False
                        if not valid:
                            self._download_file(client, item, target, completed_bytes)
                            digest = _sha256(target)
                        files.append({"path": item["path"], "size": item["size"], "sha256": digest})
                        completed_bytes += item["size"]
                        self._update(bytes_done=completed_bytes, downloaded_files=len(files))
                    manifest = {"schema_version": 1, "engine": "docling", "created_at": time.time(),
                                "repositories": repositories, "files": files}
                    self._write_manifest(manifest)
                    self._update(phase="verifying")
                    validate_bundle(self.root)
        except Exception as exc:
            self._update(phase="error", ready=False, error=str(exc))
        finally:
            with self._lock:
                self._active = False
        return self.status()

    def _download_file(self, client, item, target, completed_bytes):
        temporary = target.with_name(target.name + ".part")
        for attempt in range(3):
            try:
                offset = temporary.stat().st_size if temporary.exists() else 0
                if offset >= item["size"]:
                    temporary.unlink()
                    offset = 0
                headers = {"Range": f"bytes={offset}-"} if offset else {}
                with client.stream("GET", item["url"], headers=headers) as response:
                    response.raise_for_status()
                    if response.status_code != 206:
                        offset = 0
                    with temporary.open("ab" if offset else "wb") as stream:
                        for chunk in response.iter_bytes(1024 * 1024):
                            stream.write(chunk)
                            offset += len(chunk)
                            self._update(bytes_done=completed_bytes + offset)
                            if offset > item["size"]:
                                raise ValueError("Model download exceeded the advertised size")
                if temporary.stat().st_size != item["size"]:
                    raise ValueError("Incomplete model download; retry is available")
                if item["sha256"] and _sha256(temporary) != item["sha256"]:
                    temporary.unlink()
                    raise ValueError("Downloaded model checksum does not match the server manifest")
                os.replace(temporary, target)
                return
            except (httpx.HTTPError, OSError, ValueError):
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)

    def import_directory(self, path) -> dict:
        self._begin("importing")
        try:
            source = Path(path).resolve()
            if source == self.root:
                validate_bundle(source)
            else:
                manifest = validate_bundle(source)
                self._update(bytes_total=sum(f["size"] for f in manifest["files"]), total_files=len(manifest["files"]))
                with FileLock(str(self.root / ".download.lock"), timeout=0):
                    done = 0
                    for index, item in enumerate(manifest["files"]):
                        target = _safe_path(self.root, item["path"])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        temporary = target.with_name(target.name + ".part")
                        shutil.copyfile(_safe_path(source, item["path"]), temporary)
                        os.replace(temporary, target)
                        done += item["size"]
                        self._update(bytes_done=done, downloaded_files=index + 1, current_file=item["path"])
                    self._write_manifest(manifest)
                    validate_bundle(self.root)
        except Exception as exc:
            self._update(phase="error", ready=False, error=str(exc))
        finally:
            with self._lock:
                self._active = False
        return self.status()
