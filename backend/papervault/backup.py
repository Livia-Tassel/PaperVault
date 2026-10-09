from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import zipfile
from pathlib import Path

from .files import atomic_json, check_manifest, manifest, safe_path, uid


def create_backup(library, destination: Path | None = None) -> Path:
    destination = destination or library.root / "backups"
    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"papervault-{uid()}.zip"
    staging = library.root / ".staging" / uid()
    staging.mkdir()
    try:
        with library.mutex:
            (staging / "database").mkdir()
            with library.db.read() as source:
                backup = sqlite3.connect(staging / "database/papervault.db")
                try:
                    source.backup(backup)
                    ids = [row[0] for row in backup.execute("SELECT id FROM papers")]
                finally:
                    backup.close()
            for paper_id in ids:
                source = safe_path(library.root, f"papers/{paper_id}")
                if source.exists():
                    for item in source.rglob("*"):
                        if item.is_symlink():
                            raise ValueError("论文库含符号链接，无法安全备份")
                    shutil.copytree(source, staging / "papers" / paper_id)
            atomic_json(staging / "manifest.json", {"version": 1, "files": manifest(staging)})
        temporary = target.with_suffix(".zip.partial")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in staging.rglob("*"):
                if file.is_file():
                    archive.write(file, file.relative_to(staging).as_posix())
        os.replace(temporary, target)
        return target
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def restore_backup(archive_path: Path, destination: Path) -> Path:
    archive_path, destination = archive_path.resolve(), destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("恢复目标必须是新的空目录，原论文库不会被覆盖")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".papervault-restore-{uid()}"
    staging.mkdir()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            total, names = 0, set()
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                total += entry.file_size
                if total > 100 * 1024**3:
                    raise ValueError("备份解压大小超过100 GiB限制")
                file = safe_path(staging, entry.filename)
                canonical = str(file).casefold()
                if canonical in names or stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError("备份包含重复路径或链接")
                names.add(canonical)
                file.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, file.open("xb") as target:
                    shutil.copyfileobj(source, target)
        data = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
        if data.get("version") != 1:
            raise ValueError("不支持的备份格式")
        expected = data["files"]
        check_manifest(staging, expected)
        if set(manifest(staging)) != set(expected):
            raise ValueError("备份清单与文件不一致")
        db = staging / "database/papervault.db"
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or con.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("备份数据库完整性校验失败")
            for paper_id, removed in con.execute("SELECT id,removed FROM papers"):
                if not removed and not safe_path(staging, f"papers/{paper_id}/original.pdf").is_file():
                    raise ValueError("备份缺少原始PDF")
            for auto, override in con.execute("SELECT auto_json,overrides_json FROM resources WHERE active=1"):
                resource = {**json.loads(auto), **json.loads(override)}
                for relative in resource.get("files", {}).values():
                    if not safe_path(staging, relative).is_file():
                        raise ValueError("备份缺少资源文件")
        finally:
            con.close()
        if destination.exists():
            destination.rmdir()  # Verified empty above; fails safely if it changed.
        os.replace(staging, destination)
        return destination
    finally:
        if staging.exists():
            shutil.rmtree(staging)
