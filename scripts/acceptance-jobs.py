"""Real queued PDF failures, running cancellation and retry isolation."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from acceptance import Backend, ROOT
from papervault.files import uid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, default=ROOT / ".cache/models")
    parser.add_argument("--backend", type=Path)
    args = parser.parse_args()
    directory = ROOT / ".test-data" / ("queue-acceptance-" + uid())
    directory.mkdir(parents=True)
    report = {"passed": False, "real_files": ["academic.pdf", "corrupt.pdf", "mixed-assets.pdf"],
              "work_directory": str(directory), "frozen_backend": bool(args.backend)}
    try:
        with Backend(directory, args.models.resolve(), args.backend) as backend:
            backend.call("POST", "/library/open", json={"path": str(directory / "library")})
            started = time.perf_counter()
            result = backend.call("POST", "/papers/import-paths", json={"paths": [str(ROOT / "tests/fixtures" / name)
                                                                                  for name in report["real_files"]]}).json()
            assert len(result["items"]) == 3 and not result["errors"]
            report["three_file_import_seconds"] = time.perf_counter()-started
            papers = {p["filename"]: p["id"] for p in result["items"]}
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                jobs = backend.call("GET", "/jobs").json()["items"]
                first = next(j for j in jobs if j["paper_id"] == papers["academic.pdf"])
                if first["status"] == "running":
                    break
                time.sleep(.1)
            else:
                raise TimeoutError("First queued PDF did not start")
            backend.call("POST", f"/jobs/{first['id']}/cancel")
            while time.monotonic() < deadline:
                first = next(j for j in backend.call("GET", "/jobs").json()["items"] if j["id"] == first["id"])
                if first["status"] == "cancelled":
                    break
                time.sleep(.1)
            assert first["status"] == "cancelled"
            assert backend.call("GET", f"/resources?paper_id={papers['academic.pdf']}").json()["total"] == 0
            retried = backend.call("POST", f"/jobs/{first['id']}/retry").json()["id"]
            assert retried != first["id"]
            print("Running parse cancelled without publication; retry enqueued", flush=True)
            deadline, last = time.monotonic()+600, None
            while time.monotonic() < deadline:
                jobs = backend.call("GET", "/jobs").json()["items"]
                statuses = [(j["paper_title"], j["status"]) for j in jobs]
                if statuses != last:
                    print(json.dumps(statuses, ensure_ascii=False), flush=True)
                    last = statuses
                if all(j["status"] in ("completed", "failed", "cancelled") for j in jobs):
                    break
                time.sleep(.5)
            else:
                raise TimeoutError("Queue did not finish")
            assert next(j for j in jobs if j["id"] == retried)["status"] == "completed", jobs
            assert next(j for j in jobs if j["paper_id"] == papers["corrupt.pdf"])["status"] == "failed", jobs
            assert next(j for j in jobs if j["paper_id"] == papers["mixed-assets.pdf"])["status"] == "completed", jobs
            assert backend.call("GET", "/library").json()["paper_count"] == 3
            report.update(passed=True, jobs=jobs, queue_seconds=time.perf_counter()-started)
            print("PASS: failed PDF did not block later tasks; retry produced real assets", flush=True)
    finally:
        target = ROOT / "artifacts/queue-acceptance.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
