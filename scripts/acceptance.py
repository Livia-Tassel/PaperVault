"""Real PDF -> isolated backend/worker -> exports -> restart -> restore acceptance.

No parser or API mocks. Requires an installed parser and a verified model bundle.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import platform
import queue
import secrets
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

import httpx
import psutil
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from papervault.files import sha256, uid  # noqa: E402


class Backend:
    def __init__(self, directory: Path, models: Path, binary: Path | None):
        self.directory, self.models, self.binary = directory, models, binary
        self.process = None
        self.peak_memory = 0

    def __enter__(self):
        token = secrets.token_hex(32)
        environment = {**os.environ, "PYTHONPATH": str(ROOT / "backend"), "PYTHONUTF8": "1",
                       "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        command = [str(self.binary)] if self.binary else [sys.executable, "-m", "papervault"]
        self.started = time.perf_counter()
        self.process = subprocess.Popen(command, cwd=ROOT, env=environment, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                        encoding="utf-8", errors="replace",
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.lines, self.errors = queue.Queue(), []
        threading.Thread(target=lambda: [self.lines.put(line) for line in self.process.stdout], daemon=True).start()
        def capture_errors():
            with (self.directory / "backend-live.log").open("w", encoding="utf-8") as log:
                for line in self.process.stderr:
                    self.errors.append(line)
                    log.write(line)
                    log.flush()
        threading.Thread(target=capture_errors, daemon=True).start()
        self.process.stdin.write(json.dumps({"token": token, "config_path": str(self.directory / "config"),
                                             "models_path": str(self.models)}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("Backend failed: " + "".join(self.errors)[-8000:])
            try:
                event = json.loads(self.lines.get(timeout=.2))
            except (queue.Empty, ValueError):
                continue
            if event.get("type") == "ready":
                self.client = httpx.Client(base_url=f"http://127.0.0.1:{event['port']}/api/v1",
                                           headers={"Authorization": "Bearer " + token}, timeout=120,
                                           trust_env=False)
                for _ in range(50):
                    try:
                        self.call("GET", "/health")
                        self.startup_seconds = time.perf_counter()-self.started
                        return self
                    except httpx.TransportError:
                        time.sleep(.1)
        raise TimeoutError("Backend did not become ready")

    def call(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise AssertionError(f"{method} {path}: {response.status_code} {response.text[:3000]}")
        return response

    def sample_memory(self):
        try:
            parent = psutil.Process(self.process.pid)
            processes = [parent, *parent.children(recursive=True)]
            self.peak_memory = max(self.peak_memory, sum(p.memory_info().rss for p in processes if p.is_running()))
        except psutil.Error:
            pass

    def __exit__(self, *_):
        if hasattr(self, "client"):
            self.client.close()
        if self.process and self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        (self.directory / "backend.log").write_text("".join(self.errors), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=ROOT / "tests/fixtures/academic.pdf")
    parser.add_argument("--models", type=Path, default=ROOT / ".cache/models")
    parser.add_argument("--backend", type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    directory = ROOT / ".test-data" / ("acceptance-" + uid())
    directory.mkdir(parents=True)
    original_hash = sha256(args.pdf)
    report = {"pdf": str(args.pdf), "sha256": original_hash, "work_directory": str(directory),
              "machine": {"platform": platform.platform(), "cpu": platform.processor(),
                          "logical_cpus": psutil.cpu_count(), "memory_bytes": psutil.virtual_memory().total},
              "frozen_backend": bool(args.backend), "steps": [], "passed": False}
    def step(name):
        report["steps"].append(name)
        print(name, flush=True)
    try:
        with Backend(directory, args.models.resolve(), args.backend) as backend:
            report["backend_startup_seconds"] = backend.startup_seconds
            assert backend.call("GET", "/models").json()["ready"]
            backend.call("POST", "/library/open", json={"path": str(directory / "论文库")})
            step("Created a real library with verified local models")
            start = time.perf_counter()
            imported = backend.call("POST", "/papers/import-paths", json={"paths": [str(args.pdf.resolve())]}).json()
            assert not imported["errors"]
            paper_id = imported["items"][0]["id"]
            deadline, last = time.monotonic() + args.timeout, None
            while time.monotonic() < deadline:
                job = backend.call("GET", "/jobs").json()["items"][0]
                if (job["status"], job["phase"]) != last:
                    print(json.dumps({"status": job["status"], "phase": job["phase"]}, ensure_ascii=False), flush=True)
                    last = (job["status"], job["phase"])
                backend.sample_memory()
                if job["status"] == "completed":
                    break
                if job["status"] in ("failed", "cancelled", "interrupted"):
                    raise AssertionError(job)
                time.sleep(.5)
            else:
                raise TimeoutError("Real parsing exceeded the acceptance timeout")
            report["import_parse_publish_seconds"] = time.perf_counter()-start
            report["peak_backend_worker_rss_bytes"] = backend.peak_memory
            step("PDF imported and parsed by the real isolated Docling CPU worker")
            resources = backend.call("GET", "/resources", params={"paper_id": paper_id, "limit": 1000}).json()["items"]
            figures = [r for r in resources if r["kind"] == "figure"]
            tables = [r for r in resources if r["kind"] == "table"]
            assert figures and tables, {"figures": len(figures), "tables": len(tables)}
            report["figure_count"], report["table_count"] = len(figures), len(tables)
            figure = next(r for r in figures if r.get("caption") and r.get("locations") and r["locations"][0].get("bbox"))
            table = next(r for r in tables if r.get("table", {}).get("rows") and r.get("locations") and r["locations"][0].get("bbox"))
            for resource in (figure, table):
                assert resource["locations"] and resource["locations"][0]["bbox"]
                binary = backend.call("GET", f"/resources/{resource['id']}/files/png", params={"dpi": 300}).content
                with Image.open(io.BytesIO(binary)) as image:
                    assert min(image.size) > 20
                (directory / f"{resource['kind']}.png").write_bytes(binary)
            csv_data = backend.call("GET", f"/resources/{table['id']}/files/csv").content
            assert len(list(csv.reader(io.StringIO(csv_data.decode("utf-8-sig"))))) >= 2
            assert b"<table" in backend.call("GET", f"/resources/{table['id']}/files/html").content
            step("Figure PNG and Table PNG/CSV/HTML contain real extracted assets")
            phrase = " ".join(figure["caption"].split()[2:5])
            assert phrase, "Expected a source caption"
            results = backend.call("GET", "/search", params={"q": phrase}).json()
            assert any(r["id"] == figure["id"] for r in results["figures"])
            assert backend.call("GET", f"/papers/{paper_id}/pdf").content == args.pdf.read_bytes()
            step("Caption search returns the figure and its source PDF coordinates")
            backend.call("PATCH", f"/resources/{figure['id']}", json={"caption": "人工修正 深度 KV Cache架构"})
            rows = table["table"]["rows"]
            rows[-1][-1] = "-1.2e-3"
            backend.call("PATCH", f"/resources/{table['id']}", json={"table": {"rows": rows, "cells": [], "header_rows": 1}})
            assert "-1.2e-3" in backend.call("GET", f"/resources/{table['id']}/files/csv").text
            backend.call("POST", f"/resources/{figure['id']}/crop", json={"location": figure["locations"][0], "dpi": 300})
            backend.call("PATCH", f"/papers/{paper_id}", json={"tags": ["验收"], "favorite": True, "notes": "本地持久化"})
            step("Manual caption, table, crop and paper edits are persisted")
            exported = backend.call("POST", "/exports", json={"paper_ids": [paper_id], "format": "zip"}).content
            (directory / "export.zip").write_bytes(exported)
            with zipfile.ZipFile(io.BytesIO(exported)) as archive:
                assert any(n.endswith("table.csv") for n in archive.namelist())
                assert any(n.endswith("fulltext.md") for n in archive.namelist())
            backup = backend.call("POST", "/backups", json={}).json()["path"]
            backend.call("POST", "/backups/restore", json={"path": backup, "destination": str(directory / "恢复后的库")})
            step("Portable archive exported and full backup restored to a new library")
        with Backend(directory, args.models.resolve(), args.backend) as backend:
            assert backend.call("GET", f"/papers/{paper_id}").json()["favorite"]
            assert backend.call("GET", f"/resources/{figure['id']}").json()["caption"] == "人工修正 深度 KV Cache架构"
            assert backend.call("GET", "/search", params={"q": "深度 KV"}).json()["figures"]
            assert backend.call("GET", f"/papers/{paper_id}/pdf").content == args.pdf.read_bytes()
            step("Restart retained the restored library, manual edits, PDF and search index")
        assert sha256(args.pdf) == original_hash
        report["passed"] = True
    finally:
        target = args.report or ROOT / "artifacts" / ("acceptance-frozen.json" if args.backend else "acceptance-source.json")
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {target}", flush=True)


if __name__ == "__main__":
    main()
