"""Checked filesystem operations; never mutate import source files."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from uuid import uuid4


def uid() -> str:
    return str(uuid4())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    # Reject Windows aliases/ADS even when validating an archive on another OS.
    if not relative or "\\" in relative or ":" in relative:
        raise ValueError("无效的库内相对路径")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or any(x in ("..", ".") or x.endswith((".", " ")) for x in parts.parts):
        raise ValueError("路径超出论文库")
    resolved = (root / Path(*parts.parts)).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("路径超出论文库")
    return resolved


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def manifest(directory: Path) -> dict[str, str]:
    result = {}
    for file in sorted(directory.rglob("*")):
        if file.is_symlink():
            raise ValueError("资源目录包含链接")
        if file.is_file() and file.name != "manifest.json":
            result[file.relative_to(directory).as_posix()] = sha256(file)
    return result


def check_manifest(directory: Path, expected: dict[str, str]) -> None:
    for name, checksum in expected.items():
        file = safe_path(directory, name)
        if not file.is_file() or sha256(file) != checksum:
            raise ValueError(f"文件校验失败：{name}")
