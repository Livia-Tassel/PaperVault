from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock, Timeout

from . import search
from .database import Database
from .files import atomic_json, check_manifest, manifest, safe_path, sha256, uid
from .tables import validate_table, write_table


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


PAPER_DEFAULTS = {"title": None, "authors": [], "abstract": None, "year": None, "venue": None,
                  "doi": None, "arxiv_id": None, "keywords": [], "tags": [], "folders": [],
                  "favorite": False, "notes": "", "sections": [], "references": [], "warnings": []}
PAPER_EDITABLE = set(PAPER_DEFAULTS) - {"warnings"}
RESOURCE_EDITABLE = {"name", "number", "caption", "tags", "notes", "table", "needs_review"}


def bbox_iou(left: dict, right: dict) -> float:
    try:
        a, b = left["locations"][0], right["locations"][0]
        if a["page_index"] != b["page_index"]:
            return 0
        x0, y0, x1, y1 = a["bbox"]
        u0, v0, u1, v1 = b["bbox"]
        overlap = max(0, min(x1, u1)-max(x0, u0)) * max(0, min(y1, v1)-max(y0, v0))
        union = (x1-x0)*(y1-y0) + (u1-u0)*(v1-v0) - overlap
        return overlap / union if union > 0 else 0
    except (KeyError, TypeError, ValueError, IndexError):
        return 0


class Library:
    """A single-process writer with immutable automatic and manual file revisions."""

    def __init__(self, root: Path, create: bool = True):
        self.root = root.expanduser().resolve()
        if not create and not (self.root / "database/papervault.db").exists():
            raise ValueError("所选目录不是 PaperVault 论文库")
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(self.root / ".library.lock", thread_local=False)
        try:
            self.lock.acquire(timeout=0)
        except Timeout as exc:
            raise ValueError("论文库正在被另一个 PaperVault 进程使用") from exc
        try:
            self.db = Database(self.root / "database/papervault.db")
            self.mutex = threading.RLock()
            for name in ("papers", "exports", "backups", ".staging", ".trash"):
                (self.root / name).mkdir(exist_ok=True)
            self.recover()
        except BaseException:
            self.lock.release()
            raise

    def close(self):
        self.lock.release()

    def recover(self):
        with self.db.transaction() as con:
            con.execute("UPDATE jobs SET status='interrupted',phase='上次运行被中断，请重试',updated_at=? "
                        "WHERE status IN ('running','publishing')", (now(),))
            con.execute("UPDATE jobs SET status='cancelled',phase='已取消',updated_at=? "
                        "WHERE status='cancel_requested'", (now(),))
            con.execute("UPDATE papers SET status='interrupted' WHERE id IN "
                        "(SELECT paper_id FROM jobs WHERE status='interrupted') AND active_revision IS NULL")
        # Incomplete staging directories are never visible. Keep them for diagnosis;
        # a later retry always receives a new attempt token and staging directory.

    def info(self):
        with self.db.read() as con:
            counts = {row["kind"]: row["n"] for row in con.execute(
                "SELECT r.kind,count(*) n FROM resources r JOIN papers p ON p.id=r.paper_id "
                "WHERE r.active=1 AND p.removed=0 GROUP BY r.kind")}
            papers = con.execute("SELECT count(*) FROM papers WHERE removed=0").fetchone()[0]
        return {"path": str(self.root), "paper_count": papers,
                "figure_count": counts.get("figure", 0), "table_count": counts.get("table", 0)}

    def _paper(self, con, row) -> dict:
        if row is None:
            raise KeyError("论文不存在")
        result = {**PAPER_DEFAULTS, **json.loads(row["auto_json"]), **json.loads(row["overrides_json"])}
        result.update({k: row[k] for k in ("id", "sha256", "filename", "status", "created_at", "active_revision")})
        counts = {r["kind"]: r["n"] for r in con.execute(
            "SELECT kind,count(*) n FROM resources WHERE paper_id=? AND active=1 GROUP BY kind", (row["id"],))}
        result["figure_count"], result["table_count"] = counts.get("figure", 0), counts.get("table", 0)
        result["folders"] = [r[0] for r in con.execute("SELECT folder_id FROM paper_folders WHERE paper_id=?", (row["id"],))]
        result["edited_fields"] = list(json.loads(row["overrides_json"]))
        return result

    def paper(self, paper_id: str):
        with self.db.read() as con:
            return self._paper(con, con.execute("SELECT * FROM papers WHERE id=? AND removed=0", (paper_id,)).fetchone())

    def papers(self, q="", tag=None, folder=None, favorite=None, year=None, sort="recent", offset=0, limit=50):
        with self.db.read() as con:
            rows = con.execute("SELECT * FROM papers WHERE removed=0 ORDER BY created_at DESC").fetchall()
            items = [self._paper(con, row) for row in rows]
            if q:
                ids = {r["paper_id"] for r in search.find(con, q, 100000)}
                items = [p for p in items if p["id"] in ids]
        if tag:
            items = [p for p in items if tag in p.get("tags", [])]
        if folder == "unfiled":
            items = [p for p in items if not p["folders"] and not p.get("tags")]
        elif folder:
            items = [p for p in items if folder in p["folders"]]
        if favorite is not None:
            items = [p for p in items if bool(p.get("favorite")) == favorite]
        if year is not None:
            items = [p for p in items if p.get("year") == year]
        if sort == "title":
            items.sort(key=lambda p: (p.get("title") or p["filename"]).casefold())
        elif sort == "year":
            items.sort(key=lambda p: p.get("year") or 0, reverse=True)
        return {"items": items[offset:offset+limit], "total": len(items)}

    def import_file(self, path: Path):
        path = path.expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".pdf":
            raise ValueError("请选择 PDF 文件")
        if path.stat().st_size > 512 * 1024 * 1024:
            raise ValueError("PDF 超过512 MiB导入上限")
        with path.open("rb") as stream:
            if b"%PDF-" not in stream.read(1024):
                raise ValueError("文件不是有效的PDF")
        paper_id = uid()
        staging = self.root / ".staging" / paper_id
        staging.mkdir()
        copied = staging / "original.pdf"
        try:
            shutil.copyfile(path, copied)
            digest = sha256(copied)
            with self.mutex, self.db.transaction() as con:
                duplicate = con.execute("SELECT * FROM papers WHERE sha256=?", (digest,)).fetchone()
                if duplicate:
                    if duplicate["removed"]:
                        con.execute("UPDATE papers SET removed=0 WHERE id=?", (duplicate["id"],))
                        self._reindex(con, duplicate["id"])
                    return self._paper(con, duplicate), True
                destination = self.root / "papers" / paper_id
                os.replace(staging, destination)
                con.execute("INSERT INTO papers(id,sha256,filename,created_at) VALUES(?,?,?,?)",
                            (paper_id, digest, path.name, now()))
                self._queue(con, paper_id)
                self._reindex(con, paper_id)
            return self.paper(paper_id), False
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def _queue(self, con, paper_id):
        job_id, timestamp = uid(), now()
        current = con.execute("SELECT id FROM jobs WHERE paper_id=? AND status IN "
                              "('queued','running','publishing','cancel_requested')", (paper_id,)).fetchone()
        if current:
            return current[0]
        con.execute("INSERT INTO jobs(id,paper_id,status,phase,attempt_token,created_at,updated_at) "
                    "VALUES(?,?,'queued','等待解析',?,?,?)", (job_id, paper_id, uid(), timestamp, timestamp))
        con.execute("UPDATE papers SET status='queued' WHERE id=?", (paper_id,))
        return job_id

    def queue(self, paper_id):
        self.paper(paper_id)
        with self.db.transaction() as con:
            return self._queue(con, paper_id)

    def update_paper(self, paper_id, changes):
        unknown = set(changes) - PAPER_EDITABLE
        if unknown:
            raise ValueError("不支持修改字段：" + ",".join(sorted(unknown)))
        for key in ("tags", "authors", "keywords", "folders"):
            if key in changes and (not isinstance(changes[key], list) or any(not isinstance(x, str) for x in changes[key])):
                raise ValueError(f"{key} 必须是文本列表")
        if "year" in changes and changes["year"] is not None:
            if not isinstance(changes["year"], int) or not 1000 <= changes["year"] <= 3000:
                raise ValueError("年份无效")
        with self.mutex, self.db.transaction() as con:
            row = con.execute("SELECT * FROM papers WHERE id=? AND removed=0", (paper_id,)).fetchone()
            if not row:
                raise KeyError("论文不存在")
            overrides = {**json.loads(row["overrides_json"]), **changes}
            if "folders" in changes:
                con.execute("DELETE FROM paper_folders WHERE paper_id=?", (paper_id,))
                for folder_id in changes["folders"]:
                    con.execute("INSERT INTO paper_folders VALUES(?,?)", (paper_id, folder_id))
            con.execute("UPDATE papers SET overrides_json=? WHERE id=?", (encode(overrides), paper_id))
            con.execute("INSERT INTO manual_revisions VALUES(?,?,?,?,?)", (uid(), paper_id, "paper", encode(changes), now()))
            self._reindex(con, paper_id)
        self._metadata_snapshot(paper_id)
        return self.paper(paper_id)

    def _metadata_snapshot(self, paper_id):
        atomic_json(self.root / "papers" / paper_id / "metadata.json", self.paper(paper_id))

    def _resource(self, con, row):
        if row is None:
            raise KeyError("资源不存在")
        result = {"tags": [], "notes": "", "number": None, "name": "", "caption": "", "table": None,
                  "locations": [], "files": {}, "warnings": [], **json.loads(row["auto_json"]),
                  **json.loads(row["overrides_json"])}
        result.update({"id": row["id"], "paper_id": row["paper_id"], "kind": row["kind"],
                       "needs_review": bool(row["needs_review"]), "manual": bool(row["manual"])})
        paper = con.execute("SELECT * FROM papers WHERE id=?", (row["paper_id"],)).fetchone()
        data = {**json.loads(paper["auto_json"]), **json.loads(paper["overrides_json"])}
        result["paper_title"] = data.get("title") or paper["filename"]
        result["paper_year"] = data.get("year")
        result["paper_tags"] = data.get("tags", [])
        result["edited_fields"] = list(json.loads(row["overrides_json"]))
        return result

    def resource(self, resource_id):
        with self.db.read() as con:
            row = con.execute("SELECT r.* FROM resources r JOIN papers p ON p.id=r.paper_id "
                              "WHERE r.id=? AND r.active=1 AND p.removed=0", (resource_id,)).fetchone()
            return self._resource(con, row)

    def resources(self, kind=None, paper_id=None, q="", tag=None, year=None, offset=0, limit=50):
        conditions, args = ["r.active=1", "p.removed=0"], []
        for field, value in (("r.kind", kind), ("r.paper_id", paper_id)):
            if value:
                conditions.append(f"{field}=?")
                args.append(value)
        with self.db.read() as con:
            rows = con.execute("SELECT r.* FROM resources r JOIN papers p ON p.id=r.paper_id WHERE " +
                               " AND ".join(conditions) + " ORDER BY p.created_at DESC,r.rowid", args).fetchall()
            items = [self._resource(con, row) for row in rows]
            if q:
                ids = {r["id"] for r in search.find(con, q, 100000)}
                items = [r for r in items if r["id"] in ids]
        if tag:
            items = [r for r in items if tag in r.get("tags", []) or tag in r["paper_tags"]]
        if year:
            items = [r for r in items if r["paper_year"] == year]
        return {"items": items[offset:offset+limit], "total": len(items)}

    def update_resource(self, resource_id, changes):
        if set(changes) - RESOURCE_EDITABLE:
            raise ValueError("包含不可修改的资源字段")
        with self.mutex:
            resource = self.resource(resource_id)
            if "table" in changes or ("caption" in changes and resource.get("table")):
                if resource["kind"] != "table":
                    raise ValueError("此资源不是表格")
                table = validate_table(changes.get("table", resource["table"]))
                revision_dir = self.root / "papers" / resource["paper_id"] / "manual" / uid()
                generated = write_table(table, revision_dir, changes.get("caption", resource["caption"]))
                changes = {**changes, "table": table, "files": {**resource["files"], **{
                    k: Path(v).relative_to(self.root).as_posix() for k, v in generated.items()}}}
            self._save_resource_override(resource_id, changes)
        return self.resource(resource_id)

    def _save_resource_override(self, resource_id, changes):
        with self.db.transaction() as con:
            row = con.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
            overrides = {**json.loads(row["overrides_json"]), **changes}
            con.execute("UPDATE resources SET overrides_json=?,needs_review=? WHERE id=?",
                        (encode(overrides), int(changes.get("needs_review", row["needs_review"])), resource_id))
            con.execute("INSERT INTO manual_revisions VALUES(?,?,?,?,?)",
                        (uid(), resource_id, "resource", encode(changes), now()))
            self._reindex(con, row["paper_id"])

    def crop(self, paper_id, location, dpi=300, resource_id=None, kind="figure", name="", caption=""):
        from .parsers import render_region
        from PIL import Image
        self.paper(paper_id)
        if dpi not in (150, 300, 600):
            raise ValueError("DPI仅支持150、300和600")
        if kind not in ("figure", "table"):
            raise ValueError("资源类型无效")
        with self.mutex:
            directory = self.root / "papers" / paper_id / "manual" / uid()
            directory.mkdir(parents=True)
            render_region(self.pdf(paper_id), location, directory / "image.png", dpi)
            with Image.open(directory / "image.png") as image:
                image.thumbnail((480, 360))
                image.convert("RGB").save(directory / "thumbnail.jpg", quality=85)
            files = {"png": (directory / "image.png").relative_to(self.root).as_posix(),
                     "thumbnail": (directory / "thumbnail.jpg").relative_to(self.root).as_posix()}
            if resource_id:
                resource = self.resource(resource_id)
                if resource["paper_id"] != paper_id:
                    raise ValueError("资源与论文不匹配")
                self._save_resource_override(resource_id, {"locations": [location],
                                                          "files": {**resource["files"], **files}})
            else:
                resource_id = uid()
                data = {"name": name, "caption": caption, "locations": [location], "files": files,
                        "table": {"rows": [[""]], "cells": [], "header_rows": 1} if kind == "table" else None}
                with self.db.transaction() as con:
                    con.execute("INSERT INTO resources(id,paper_id,kind,auto_json,manual) VALUES(?,?,?,?,1)",
                                (resource_id, paper_id, kind, encode(data)))
                    self._reindex(con, paper_id)
        return self.resource(resource_id)

    def pdf(self, paper_id):
        self.paper(paper_id)
        path = safe_path(self.root, f"papers/{paper_id}/original.pdf")
        if not path.is_file():
            raise FileNotFoundError("托管PDF缺失，请从备份恢复")
        return path

    def resource_file(self, resource_id, format_name, dpi=None):
        if format_name not in ("png", "thumbnail", "csv", "html"):
            raise ValueError("不支持的导出格式")
        resource = self.resource(resource_id)
        if dpi and format_name == "png" and resource["locations"]:
            if dpi not in (150, 300, 600):
                raise ValueError("DPI无效")
            from .parsers import render_region
            directory = self.root / "exports" / uid()
            directory.mkdir()
            path = directory / "image.png"
            render_region(self.pdf(resource["paper_id"]), resource["locations"][0], path, dpi)
            return path
        relative = resource["files"].get(format_name)
        if not relative:
            raise FileNotFoundError("此资源未生成所选格式，请检查解析警告或编辑后导出")
        path = safe_path(self.root, relative)
        if not path.is_file():
            raise FileNotFoundError("资源文件缺失，请重新解析或恢复备份")
        return path

    def _reindex(self, con, paper_id):
        con.execute("DELETE FROM search_entries WHERE paper_id=?", (paper_id,))
        row = con.execute("SELECT * FROM papers WHERE id=? AND removed=0", (paper_id,)).fetchone()
        if not row:
            return
        paper = self._paper(con, row)
        title = paper.get("title") or paper["filename"]
        def flatten(value):
            if isinstance(value, list):
                return " ".join(flatten(v) for v in value)
            return str(value) if value is not None else ""
        text = "\n".join(flatten(paper.get(k)) for k in
                         ("title", "filename", "authors", "abstract", "tags", "keywords", "notes", "doi", "arxiv_id"))
        search.index_entry(con, paper_id, "paper", paper_id, title, text)
        for row in con.execute("SELECT * FROM resources WHERE paper_id=? AND active=1", (paper_id,)).fetchall():
            resource = self._resource(con, row)
            values = [title, resource.get("name"), resource.get("number"), resource.get("caption"),
                      resource.get("tags"), resource.get("notes"), paper.get("tags")]
            if resource.get("table"):
                values.extend(resource["table"].get("rows", []))
            location = resource["locations"][0] if resource["locations"] else None
            search.index_entry(con, row["id"], row["kind"], paper_id,
                               resource.get("name") or resource.get("caption") or title,
                               "\n".join(flatten(v) for v in values), location)
        for row in con.execute("SELECT * FROM blocks WHERE paper_id=?", (paper_id,)).fetchall():
            search.index_entry(con, row["id"], "content", paper_id, title, row["text"],
                               json.loads(row["location_json"] or "null"))

    def search(self, query):
        groups = {"papers": [], "figures": [], "tables": [], "content": []}
        mapping = {"paper": "papers", "figure": "figures", "table": "tables", "content": "content"}
        with self.db.read() as con:
            for result in search.find(con, query):
                groups[mapping[result["kind"]]].append(result)
        return groups

    def publish(self, job_id, attempt_token, staging: Path, result: dict):
        """The DB transaction is the visibility boundary; never publish a partial revision."""
        with self.mutex:
            with self.db.read() as con:
                job = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job or job["status"] != "running" or job["attempt_token"] != attempt_token:
                return False
            paper_id, run_id = job["paper_id"], uid()
            expected = manifest(staging)
            check_manifest(staging, expected)
            atomic_json(staging / "manifest.json", expected)
            destination = self.root / "papers" / paper_id / "revisions" / run_id
            destination.parent.mkdir(exist_ok=True)
            # Validate all parser references before any database updates.
            resources = result.get("resources", [])
            for resource in resources:
                if resource.get("kind") not in ("figure", "table"):
                    raise ValueError("解析器返回无效资源类型")
                for path in resource.get("files", {}).values():
                    if not safe_path(staging, path).is_file():
                        raise ValueError("解析器返回缺失的资源文件")
            os.replace(staging, destination)
            with self.db.transaction() as con:
                current = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
                if not current or current["status"] != "running" or current["attempt_token"] != attempt_token:
                    return False
                old = con.execute("SELECT * FROM resources WHERE paper_id=? AND manual=0 AND active=1", (paper_id,)).fetchall()
                scores = [[bbox_iou(json.loads(previous["auto_json"]), new) if previous["kind"] == new["kind"] else 0
                           for previous in old] for new in resources]
                used = set()
                for index, resource in enumerate(resources):
                    candidates = sorted(enumerate(scores[index]), key=lambda pair: pair[1], reverse=True)
                    previous = None
                    if candidates and candidates[0][1] >= 0.8:
                        best, value = candidates[0]
                        gap = value - (candidates[1][1] if len(candidates) > 1 else 0)
                        reverse_scores = sorted((row[best] for row in scores), reverse=True)
                        reverse_gap = value - (reverse_scores[1] if len(reverse_scores) > 1 else 0)
                        if gap >= 0.15 and reverse_gap >= 0.15 and best not in used:
                            previous = old[best]
                            used.add(best)
                    resource_id = previous["id"] if previous else uid()
                    data = {**resource, "id": resource_id, "files": {
                        key: (destination / value).relative_to(self.root).as_posix()
                        for key, value in resource.get("files", {}).items()}}
                    if previous:
                        con.execute("UPDATE resources SET auto_json=?,revision=?,active=1 WHERE id=?",
                                    (encode(data), run_id, resource_id))
                    else:
                        con.execute("INSERT INTO resources(id,paper_id,kind,auto_json,revision,needs_review) "
                                    "VALUES(?,?,?,?,?,?)", (resource_id, paper_id, data["kind"], encode(data), run_id,
                                                            int(bool(data.get("warnings") or not data.get("caption")))))
                for index, previous in enumerate(old):
                    if index not in used:
                        edited = bool(json.loads(previous["overrides_json"]))
                        con.execute("UPDATE resources SET active=?,needs_review=? WHERE id=?",
                                    (int(edited), int(edited), previous["id"]))
                metadata = {**result.get("metadata", {}), "warnings": result.get("warnings", []),
                            "pages_count": result.get("pages_count"), "engine": result.get("engine", {})}
                con.execute("UPDATE papers SET auto_json=?,active_revision=?,status='completed' WHERE id=?",
                            (encode(metadata), run_id, paper_id))
                con.execute("DELETE FROM blocks WHERE paper_id=?", (paper_id,))
                for block in result.get("blocks", []):
                    con.execute("INSERT INTO blocks VALUES(?,?,?,?,?,?)", (uid(), paper_id, block.get("label", "text"),
                                block.get("text", ""), encode(block.get("location")), run_id))
                con.execute("INSERT INTO parse_runs VALUES(?,?,?,?,?)",
                            (run_id, paper_id, encode(result.get("engine", {})), encode(expected), now()))
                con.execute("UPDATE jobs SET status='completed',phase='解析完成',progress_json=?,updated_at=? WHERE id=?",
                            (encode({"pages_done": result.get("pages_count"), "pages_total": result.get("pages_count"),
                                     "resources_count": len(resources)}), now(), job_id))
                self._reindex(con, paper_id)
            self._metadata_snapshot(paper_id)
            return True

    def remove(self, paper_id, delete_files=False):
        self.paper(paper_id)
        with self.mutex, self.db.transaction() as con:
            con.execute("UPDATE jobs SET status='cancelled',phase='论文已移除',updated_at=? "
                        "WHERE paper_id=? AND status IN ('queued','running','cancel_requested')", (now(), paper_id))
            con.execute("UPDATE papers SET removed=1 WHERE id=?", (paper_id,))
            self._reindex(con, paper_id)
        if delete_files:
            # Remove DB references first: a crash may retain an unreferenced file,
            # never a live entry pointing at an intentionally deleted PDF.
            with self.db.transaction() as con:
                con.execute("DELETE FROM papers WHERE id=?", (paper_id,))
            directory = safe_path(self.root, f"papers/{paper_id}")
            if directory.is_dir():
                shutil.rmtree(directory)

    def folders(self):
        with self.db.read() as con:
            return {"items": [dict(row) for row in con.execute("SELECT * FROM folders ORDER BY name")]}

    def add_folder(self, name):
        name = name.strip()
        if not name or len(name) > 120:
            raise ValueError("收藏夹名称需要1至120个字符")
        folder_id = uid()
        with self.db.transaction() as con:
            con.execute("INSERT INTO folders VALUES(?,?)", (folder_id, name))
        return {"id": folder_id, "name": name}

    def jobs(self):
        with self.db.read() as con:
            rows = con.execute("SELECT j.*,p.filename,p.auto_json,p.overrides_json FROM jobs j "
                               "JOIN papers p ON p.id=j.paper_id WHERE p.removed=0 ORDER BY j.created_at DESC").fetchall()
        items = []
        for row in rows:
            data = {**json.loads(row["auto_json"]), **json.loads(row["overrides_json"])}
            item = {k: row[k] for k in ("id", "paper_id", "status", "phase", "error", "created_at", "updated_at")}
            item.update({"paper_title": data.get("title") or row["filename"], "pages_done": None,
                         "pages_total": None, "resources_count": 0, **json.loads(row["progress_json"])})
            items.append(item)
        return {"items": items, "total": len(items)}
