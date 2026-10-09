"""Persistent, single-worker parse queue with cancellable process isolation."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from .files import atomic_json, uid
from .library import encode, now


def run_worker(source: str, staging: str, models: str) -> int:
    def emit(event):
        print(json.dumps(event, ensure_ascii=True), flush=True)
    try:
        from .parsers import parse_pdf
        result = parse_pdf(Path(source), Path(staging), Path(models),
                           on_progress=lambda event: emit({"type": "progress", **event}))
        atomic_json(Path(staging) / "result.json", result)
        emit({"type": "result"})
        return 0
    except BaseException as exc:
        Path(staging, "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        emit({"type": "error", "error": f"{type(exc).__name__}: {exc}"})
        return 1


class TaskManager:
    def __init__(self, library, models):
        self.library, self.models = library, models
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="papervault-queue", daemon=True)
        self.process = None
        self.active_job = None

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=8)
        process = self.process
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)

    def cancel(self, job_id):
        with self.library.db.transaction() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError("任务不存在")
            if row["status"] in ("queued", "running", "publishing"):
                status = "cancelled" if row["status"] == "queued" else "cancel_requested"
                con.execute("UPDATE jobs SET status=?,phase='正在取消',updated_at=? WHERE id=?",
                            (status, now(), job_id))
                con.execute("UPDATE papers SET status='cancelled' WHERE id=?", (row["paper_id"],))
        return {"id": job_id, "status": status if row["status"] in ("queued", "running", "publishing") else row["status"]}

    def retry(self, job_id):
        with self.library.db.read() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError("任务不存在")
        return {"id": self.library.queue(row["paper_id"])}

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                with self.library.db.read() as con:
                    job = con.execute("SELECT j.* FROM jobs j JOIN papers p ON p.id=j.paper_id "
                                      "WHERE j.status='queued' AND p.removed=0 ORDER BY j.created_at LIMIT 1").fetchone()
                if job:
                    if self.models.status().get("ready"):
                        self._run(dict(job))
                    else:
                        with self.library.db.transaction() as con:
                            con.execute("UPDATE jobs SET phase='等待解析模型，请在设置中下载或导入' "
                                        "WHERE id=? AND status='queued'", (job["id"],))
            except Exception:
                # Record a supervisory error and retry the loop; one PDF never takes down the API.
                import logging
                logging.getLogger(__name__).exception("Parse queue supervisor error")
            self.stop_event.wait(0.5)

    def _set_terminal(self, job, status, phase, error=None):
        with self.library.db.transaction() as con:
            con.execute("UPDATE jobs SET status=?,phase=?,error=?,updated_at=? WHERE id=? "
                        "AND status!='completed'", (status, phase, error, now(), job["id"]))
            con.execute("UPDATE papers SET status=? WHERE id=?", (status, job["paper_id"]))

    def _run(self, job):
        with self.library.db.transaction() as con:
            changed = con.execute("UPDATE jobs SET status='running',phase='正在加载解析引擎',updated_at=? "
                                  "WHERE id=? AND status='queued'", (now(), job["id"])).rowcount
            if not changed:
                return
            con.execute("UPDATE papers SET status='running' WHERE id=?", (job["paper_id"],))
        staging = self.library.root / ".staging" / uid()
        staging.mkdir()
        events = queue.Queue()
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command += ["-m", "papervault"]
        command += ["--worker", "--source", str(self.library.pdf(job["paper_id"])),
                    "--output", str(staging), "--models", str(self.models.root)]
        worker_log = (staging / "worker.log").open("w", encoding="utf-8")
        process = None
        started, finished = time.monotonic(), False
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=worker_log,
                                       text=True, encoding="utf-8", errors="replace",
                                       env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.process, self.active_job = process, job["id"]
            def read_progress():
                for line in process.stdout:
                    try:
                        event = json.loads(line)
                        if isinstance(event, dict) and event.get("type") in ("progress", "error", "result"):
                            events.put(event)
                    except ValueError:
                        continue
            reader = threading.Thread(target=read_progress, daemon=True, name="parse-progress")
            reader.start()
            while not finished:
                with self.library.db.read() as con:
                    row = con.execute("SELECT status FROM jobs WHERE id=?", (job["id"],)).fetchone()
                if self.stop_event.is_set() or not row or row["status"] in ("cancel_requested", "cancelled"):
                    if process.poll() is None:
                        process.terminate()
                    self._set_terminal(job, "interrupted" if self.stop_event.is_set() else "cancelled",
                                       "应用退出，任务可重试" if self.stop_event.is_set() else "已取消")
                    break
                if time.monotonic() - started > 1800:
                    process.terminate()
                    self._set_terminal(job, "failed", "解析超时", "单篇论文解析超过30分钟限制，请拆分大型PDF")
                    break
                try:
                    event = events.get(timeout=0.2)
                except queue.Empty:
                    if process.poll() is not None:
                        if (staging / "result.json").is_file():
                            event = {"type": "result"}
                        else:
                            details = (staging / "error.txt").read_text(encoding="utf-8") if (staging / "error.txt").exists() else ""
                            self._set_terminal(job, "failed", "解析进程异常退出", f"进程退出码：{process.returncode} {details[-2000:]}")
                            break
                    else:
                        continue
                if event["type"] == "progress":
                    with self.library.db.transaction() as con:
                        previous = con.execute("SELECT progress_json FROM jobs WHERE id=?", (job["id"],)).fetchone()
                        progress = json.loads(previous[0]) if previous else {}
                        progress.update({k: v for k, v in event.items()
                                         if k in ("pages_done", "pages_total", "resources_count")})
                        con.execute("UPDATE jobs SET phase=?,progress_json=?,updated_at=? WHERE id=? AND status='running'",
                                    (event.get("message") or event.get("phase", "正在解析"), encode(progress), now(), job["id"]))
                elif event["type"] == "error":
                    self._set_terminal(job, "failed", "解析失败，可重试", event["error"])
                    finished = True
                elif event["type"] == "result":
                    # Windows cannot rename a revision directory while the stderr
                    # log is still open. Reap the worker and close all file handles
                    # before validating and atomically publishing its files.
                    process.wait(timeout=30)
                    reader.join(timeout=2)
                    worker_log.flush()
                    os.fsync(worker_log.fileno())
                    worker_log.close()
                    result = json.loads((staging / "result.json").read_text(encoding="utf-8"))
                    finished = self.library.publish(job["id"], job["attempt_token"], staging, result)
                    if not finished:
                        self._set_terminal(job, "cancelled", "已取消，解析结果未发布")
                    break
        except Exception as exc:
            self._set_terminal(job, "failed", "解析失败，可重试", str(exc))
        finally:
            if process is not None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=3)
                if process.stdout:
                    process.stdout.close()
            worker_log.close()
            self.process, self.active_job = None, None
