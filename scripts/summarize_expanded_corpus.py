"""Combine frozen corpus batches without converting workflow passes into accuracy."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--expected", type=int, default=20)
    args = parser.parse_args()
    release = read(ROOT / "docs/verification/0.2.1/release-manifest.json")
    source_files = sorted((ROOT / "tests/corpus/expanded").glob("sources-*.json"))
    expected = {p["id"]: p for path in source_files for p in read(path)["papers"]}
    records, batches, diagnostics = {}, [], []
    for path in sorted((ROOT / "artifacts/real-corpus-expanded/batches").glob("batch-*/report.json")):
        report = read(path)
        assert report["backend_sha256"].lower() == release["backend_sha256"].lower()
        assert report["health"]["version"] == release["version"]
        batches.append({"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "run_id": report["run_id"], "passed": report["passed"], "shutdown": report.get("shutdown"),
                        "errors": report["errors"], "copy_exercise_passed": report.get("copy_exercise", {}).get("restart_and_baseline_isolation_passed")})
        for paper in report["papers"]:
            identifier = paper["source"]["id"]
            if identifier in records:
                raise ValueError("Duplicate paper across final batches: " + identifier)
            assert paper["source_pdf"]["sha256"] == expected[identifier]["sha256"]
            errors = [error for resource in paper["resources"] for error in resource["errors"]]
            workers = paper.get("worker_processes", [])
            for artifact in paper.get("parser_artifacts", []):
                source = Path(artifact["baseline_copy"]["path"])
                if source.name == "worker.log":
                    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
                    diagnostic_lines = [line for line in lines if "access violation" in line.lower() or "windows fatal exception" in line.lower()]
                    if diagnostic_lines:
                        diagnostics.append({"id": identifier, "path": str(source), "lines": diagnostic_lines})
            records[identifier] = {"source": expected[identifier], "paper_id": paper.get("paper_id"),
                                   "batch_report": str(path.relative_to(ROOT)), "paper_json": paper.get("paper_json"),
                                   "job_status": paper.get("job", {}).get("status", "in_progress"),
                                   "workflow_passed": paper["passed"], "pages": paper.get("page_count"),
                                   "counts": paper.get("counts"), "parse_seconds": paper.get("parse_seconds"),
                                   "peak_backend_worker_rss_bytes": paper.get("peak_backend_worker_rss_bytes"),
                                   "warnings": paper.get("warnings", []), "errors": paper["errors"],
                                   "resource_errors": errors, "worker_exit_coverage": paper.get("worker_exit_coverage", "unknown"),
                                   "worker_processes": workers}
    missing = sorted(set(expected) - set(records))
    finished = [p for p in records.values() if p["job_status"] != "in_progress"]
    resources = Counter()
    for paper in finished:
        resources.update(paper["counts"] or {})
    exits = Counter(str(w["exit_code"]) for p in records.values() for w in p["worker_processes"])
    complete = len(expected) == args.expected and not missing and len(finished) == len(expected) and all(b["shutdown"] for b in batches)
    output = {"status": "workflow-reviewed" if complete else "in_progress", "application_version": release["version"],
              "backend_sha256": release["backend_sha256"], "source_manifests": [str(path.relative_to(ROOT)) for path in source_files],
              "expected_new_papers": args.expected, "selected_papers": len(expected), "completed_papers": len(finished),
              "pages": sum(p["pages"] or 0 for p in finished), "workflow_passed_papers": sum(p["workflow_passed"] for p in finished),
              "resource_counts": dict(resources), "worker_exit_code_counts": dict(exits),
              "worker_exit_coverage_complete": complete and all(p["worker_exit_coverage"] == "captured" for p in finished),
              "native_diagnostic_log_matches": diagnostics, "missing_sources": missing, "batches": batches,
              "papers": list(records.values()),
              "accuracy_scope": "This file summarizes integrity, exports, searches and actual process outcomes. Human inventory/deep reviews are separate; successful decoding or exit 0 never implies all text/cells/captions are correct.",
              "diagnostic_scope": "Worker exit codes are read through handles acquired while the owned processes are alive. Absence of log messages does not establish faulthandler was enabled or resolve previous source-pytest diagnostics."}
    path = ROOT / "artifacts/real-corpus-expanded/workflow-summary.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps({key: output[key] for key in ("status", "selected_papers", "completed_papers", "pages", "workflow_passed_papers", "resource_counts", "worker_exit_code_counts")}, ensure_ascii=False))
    if args.require_complete and not complete:
        raise SystemExit("Corpus incomplete: do not declare all requested samples tested")


if __name__ == "__main__":
    main()
