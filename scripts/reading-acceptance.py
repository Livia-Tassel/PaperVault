"""Real frozen Docling reparse must preserve user reading data and its backup.

This launches an independent authenticated backend/worker on a random port.
All annotations are written through the public API; no parser output or database
rows are fabricated. The PDF selection rectangles come from its actual text.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import tomllib
from urllib.parse import quote
from uuid import uuid4

import pypdfium2 as pdfium

from acceptance import Backend, ROOT


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def selection(pdf_path, page_index, text):
    """Use the source PDF's real text indexes and PDF-space rectangles."""
    document = pdfium.PdfDocument(pdf_path)
    page = document[page_index]
    textpage = page.get_textpage()
    search = textpage.search(text, match_case=True)
    try:
        match = search.get_next()
        assert match, f"Source selection not found: {text}"
        locations = [{"page_index": page_index, "bbox": list(textpage.get_rect(index))}
                     for index in range(textpage.count_rects(*match))]
        assert locations
        return {"quote": textpage.get_text_range(*match), "locations": locations}
    finally:
        search.close()
        textpage.close()
        page.close()
        document.close()


def wait_for_job(backend, job_id, timeout):
    started = time.perf_counter()
    deadline, previous = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        jobs = backend.call("GET", "/jobs").json()["items"]
        job = next(item for item in jobs if item["id"] == job_id)
        state = (job["status"], job["phase"])
        if state != previous:
            print(json.dumps({"job_id": job_id, "status": state[0], "phase": state[1]}, ensure_ascii=False), flush=True)
            previous = state
        backend.sample_memory()
        if job["status"] == "completed":
            return {"job": job, "seconds": round(time.perf_counter() - started, 3)}
        assert job["status"] not in {"failed", "cancelled", "interrupted"}, job
        time.sleep(.5)
    raise TimeoutError(f"Real frozen parser job {job_id} exceeded {timeout}s")


def set_scope(backend, library):
    backend.client.headers["X-PaperVault-Library"] = quote(f"{library['id']}:{library['path']}", safe="")


def read_annotations(backend, paper_id):
    result = backend.call("GET", "/annotations", params={"paper_id": paper_id, "limit": 200}).json()
    assert result["total"] == len(result["items"])
    return {item["id"]: item for item in result["items"]}


def assert_preserved(backend, paper_id, annotations, reading, source_hash, marker):
    actual = read_annotations(backend, paper_id)
    assert actual == annotations, "Annotation content, location, version or timestamp changed"
    for identifier, item in annotations.items():
        assert backend.call("GET", f"/annotations/{identifier}").json() == item
    assert backend.call("GET", f"/papers/{paper_id}/reading-state").json() == reading
    notes = backend.call("GET", "/search", params={"q": marker}).json()["notes"]
    assert {item["id"] for item in notes} == set(annotations), "Reindex lost note search hits"
    for item in notes:
        assert item["paper_id"] == paper_id
        assert item["locations"] == annotations[item["id"]]["locations"]
    assert hashlib.sha256(backend.call("GET", f"/papers/{paper_id}/pdf").content).hexdigest() == source_hash
    return {"annotations": len(actual), "notes_search_hits": len(notes), "reading_version": reading["version"],
            "all_annotation_fields_exactly_equal": True, "reading_all_fields_exactly_equal": True,
            "source_pdf_sha256": source_hash}


def export_notes(backend, directory, label, library_id, paper_id, annotations):
    exported = {}
    for format_name, suffix in (("json", "json"), ("markdown", "md")):
        response = backend.call("POST", "/annotations/export", json={"paper_id": paper_id, "format": format_name})
        target = directory / f"{label}-notes.{suffix}"
        target.write_bytes(response.content)
        if format_name == "json":
            data = response.json()
            assert data["format"] == "papervault-annotations-v1"
            assert data["library_id"] == library_id
            assert {item["id"]: item for item in data["annotations"]} == annotations
        else:
            text = response.content.decode("utf-8")
            for item in annotations.values():
                assert item["id"] in text and paper_id in text
                assert html.escape(item["body"]) in text and item["pdf_sha256"] in text
                assert f"颜色：{item['color']}" in text
                for tag in item["tags"]:
                    assert html.escape(tag) in text
                for location in item["locations"]:
                    assert f"第 {location['page_index'] + 1} 页" in text
                    if location["bbox"]:
                        assert json.dumps(location["bbox"]) in text
                for line in item["quote"].splitlines():
                    assert "> " + html.escape(line) in text
            assert "独立笔记导出不包含原PDF" in text
        exported[format_name] = {"path": str(target), "bytes": target.stat().st_size, "sha256": digest(target)}
    return exported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--expect-version", default=tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"],
                        help="Expected frozen application version; defaults to the repository project version")
    parser.add_argument("--models", type=Path, default=ROOT / ".cache/models")
    parser.add_argument("--pdf", type=Path, default=ROOT / "tests/fixtures/academic.pdf")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/reading-reparse-frozen-v02.json")
    args = parser.parse_args()
    args.backend, args.models, args.pdf = args.backend.resolve(), args.models.resolve(), args.pdf.resolve()
    assert args.backend.is_file() and args.backend.suffix.lower() == ".exe", "A real frozen executable is required"
    directory = ROOT / ".test-data" / ("reading-frozen-" + uuid4().hex)
    directory.mkdir(parents=True)
    started = time.perf_counter()
    original_hash = digest(args.pdf)
    report = {"passed": False, "started_at": datetime.now(timezone.utc).isoformat(),
              "command": subprocess.list2cmdline([sys.executable, *sys.argv]),
              "work_directory": str(directory), "frozen_backend": str(args.backend),
              "frozen_backend_sha256": digest(args.backend), "model_path": str(args.models),
              "model_manifest_sha256": digest(args.models / "papervault-models.json"),
              "offline_environment": {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
              "source_pdf": str(args.pdf), "source_sha256_before": original_hash,
              "machine": {"platform": platform.platform(), "python": platform.python_version()},
              "stages": [], "exports": {}, "synthetic_parser_or_database_writes": False}

    def step(name, **evidence):
        report["stages"].append({"name": name, **evidence})
        print(name, flush=True)

    try:
        with Backend(directory, args.models, args.backend) as backend:
            report["health"] = backend.call("GET", "/health").json()
            assert report["health"]["version"] == args.expect_version, "Frozen reading release version differs from expectation"
            assert backend.call("GET", "/models").json()["ready"]
            report["backend_port"] = backend.client.base_url.port
            assert report["backend_port"] != 8765, "Must not use the shared development service"
            library = backend.call("POST", "/library/open", json={"path": str(directory / "原始论文库")}).json()
            set_scope(backend, library)
            report["library"] = library
            imported = backend.call("POST", "/papers/import-paths", json={"paths": [str(args.pdf)]}).json()
            assert len(imported["items"]) == 1 and not imported["errors"] and not imported["duplicates"]
            paper_id = imported["items"][0]["id"]
            report["paper_id"] = paper_id
            jobs = backend.call("GET", "/jobs").json()["items"]
            assert len(jobs) == 1
            step("initial_real_docling_parse", **wait_for_job(backend, jobs[0]["id"], args.timeout))
            before_paper = backend.call("GET", f"/papers/{paper_id}").json()
            assert before_paper["engine"]["name"].lower() == "docling"
            assert before_paper["figure_count"] == before_paper["table_count"] == 1
            report["parser_engine"] = before_paper["engine"]

            first = selection(args.pdf, 0, "Local Research Asset Extraction")
            second = selection(args.pdf, 1, "Every extracted asset remains connected to its source page.")
            marker = "追溯验收" + uuid4().hex[:8]
            figure = next(item for item in backend.call("GET", "/resources", params={"paper_id": paper_id}).json()["items"]
                          if item["kind"] == "figure")
            specifications = [
                {"kind": "highlight", "title": "真实标题高亮", **first, "color": "amber"},
                {"kind": "highlight", "title": "跨页原文高亮", "quote": first["quote"] + "\n" + second["quote"],
                 "locations": first["locations"] + second["locations"], "color": "green"},
                {"kind": "bookmark", "title": "第二页书签", "locations": [{"page_index": 1, "bbox": None}], "color": "blue"},
                {"kind": "note", "title": "架构图区域笔记", "quote": figure["caption"],
                 "locations": [{"page_index": location["page_index"], "bbox": location["bbox"]}
                               for location in figure["locations"]], "color": "pink"},
                {"kind": "note", "title": "论文级笔记", "quote": "", "locations": [], "color": "purple"},
            ]
            for index, spec in enumerate(specifications):
                item = backend.call("POST", f"/papers/{paper_id}/annotations", json={
                    **spec, "body": f"{marker} 用户记录 {index + 1}", "tags": ["真实解析", f"样本{index + 1}"]}).json()
                edited = backend.call("PATCH", f"/annotations/{item['id']}", json={
                    "expected_version": item["version"], "body": item["body"] + "\n人工二次修改，重新解析必须保留。"}).json()
                assert edited["version"] == 2
            state = backend.call("PATCH", f"/papers/{paper_id}/reading-state", json={
                "expected_version": 0, "page_index": 0, "anchor": [100, 700], "scale": 1.25,
                "rotation": 0, "fit_mode": "custom", "status": "reading", "touch": True}).json()
            reading = backend.call("PATCH", f"/papers/{paper_id}/reading-state", json={
                "expected_version": state["version"], "page_index": 1, "anchor": [108, 650],
                "scale": 1.35, "rotation": 90, "fit_mode": "width", "status": "read", "touch": True}).json()
            annotations = read_annotations(backend, paper_id)
            assert len(annotations) == 5
            report["baseline"] = {"annotations": annotations, "reading_state": reading, "search_query": marker}
            step("baseline_user_data", **assert_preserved(backend, paper_id, annotations, reading, original_hash, marker))
            report["exports"]["before_reparse"] = export_notes(backend, directory, "before-reparse", library["id"], paper_id, annotations)

            job_id = backend.call("POST", f"/papers/{paper_id}/reparse").json()["id"]
            assert job_id != jobs[0]["id"]
            step("real_docling_reparse", **wait_for_job(backend, job_id, args.timeout))
            after_paper = backend.call("GET", f"/papers/{paper_id}").json()
            assert after_paper["active_revision"] != before_paper["active_revision"], "No new parser publication"
            assert after_paper["engine"]["name"].lower() == "docling"
            report["parser_revisions"] = [before_paper["active_revision"], after_paper["active_revision"]]
            step("reparse_user_data_preserved", **assert_preserved(backend, paper_id, annotations, reading, original_hash, marker))
            report["exports"]["after_reparse"] = export_notes(backend, directory, "after-reparse", library["id"], paper_id, annotations)
            assert report["exports"]["before_reparse"]["markdown"]["sha256"] == report["exports"]["after_reparse"]["markdown"]["sha256"]

            backup = backend.call("POST", "/backups", json={"destination": str(directory / "reading-backup.zip")}).json()["path"]
            report["backup"] = {"path": backup, "sha256": digest(backup)}
            restored = backend.call("POST", "/backups/restore", json={"path": backup, "destination": str(directory / "恢复论文库")}).json()
            assert restored["id"] == library["id"] and restored["path"] != library["path"]
            set_scope(backend, restored)
            report["restored_library"] = restored
            step("backup_restore_user_data_preserved", **assert_preserved(backend, paper_id, annotations, reading, original_hash, marker))
            report["exports"]["after_restore"] = export_notes(backend, directory, "after-restore", restored["id"], paper_id, annotations)
            assert report["exports"]["after_restore"]["markdown"]["sha256"] == report["exports"]["before_reparse"]["markdown"]["sha256"]
            report["peak_backend_worker_rss_bytes"] = backend.peak_memory
        report["source_sha256_after"] = digest(args.pdf)
        assert report["source_sha256_after"] == original_hash
        assert digest(args.backend) == report["frozen_backend_sha256"], "Frozen executable changed during acceptance"
        report["passed"] = True
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["duration_seconds"] = round(time.perf_counter() - started, 3)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Report: {args.report}", flush=True)


if __name__ == "__main__":
    main()
