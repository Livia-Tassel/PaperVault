"""Create an eight-paper demo library through the installed, offline backend API."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback
from uuid import uuid4

from pypdf import PdfReader

from test_real_corpus import FrozenBackend, ROOT, digest, file_evidence, list_resources, load_sources, write_json


SOURCE_IDS = [
    "bert-naacl2019", "sentence-bert-emnlp2019", "ml-bart-acl2020", "ml-scibert-emnlp2019",
    "ml-simcse-emnlp2021", "ml-mt5-naacl2021", "diverse-chinesebert", "diverse-macbert",
]
MANIFESTS = [ROOT / "tests/corpus/sources-ml.json", ROOT / "tests/corpus/expanded/sources-ml.json",
             ROOT / "tests/corpus/expanded/sources-diverse.json"]
QUERIES = ["BERT", "attention", "semantic similarity", "pre-training", "GLUE"]
GROUPS = ("papers", "figures", "tables", "content", "notes")


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/demo-library")
    parser.add_argument("--timeout", type=float, default=2400, help="Total real parsing timeout in seconds")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT / "artifacts"):
        raise ValueError("Evidence output must be inside the repository artifacts directory")
    for name in ("preparation.json", "source-manifest.json", "search-probes.json"):
        if (output / name).exists():
            raise FileExistsError(f"Refusing to overwrite previous preparation: {output / name}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    fixture = ROOT / ".test-data/demo-library" / stamp
    fixture.mkdir(parents=True, exist_ok=False)
    library_path = fixture / "研究论文库"
    release_path = ROOT / "docs/verification/0.2.2/release-manifest.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    binary = ROOT / ".test-data/installed/PaperVault/papervault-backend.exe"
    models = ROOT / ".cache/models"
    sources_by_id = {source["id"]: source for source in load_sources([str(value) for value in MANIFESTS], [])}
    sources = [sources_by_id[key] for key in SOURCE_IDS]
    report = {
        "passed": False, "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "fixture": str(fixture), "library_path": str(library_path), "output_directory": str(output),
        "release_manifest": file_evidence(release_path), "backend": file_evidence(binary),
        "models_manifest": file_evidence(models / "papervault-models.json"),
        "offline_environment": {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
        "scope": "Eight distinct publisher PDFs imported into one new empty library by the installed API; no database fabrication or baseline reuse.",
        "papers": [], "progress": [], "queries": {}, "manual_demo_notes": [], "errors": [],
    }
    assert release["version"] == "0.2.2"
    assert report["backend"]["sha256"].lower() == release["backend_sha256"].lower(), "Installed backend does not match the release"
    hashes = set()
    for source in sources:
        actual = digest(source["local_path"])
        assert actual == source["sha256"].lower(), f"Source hash mismatch: {source['id']}"
        assert actual not in hashes, "Duplicate source PDF"
        hashes.add(actual)
        assert len(PdfReader(source["local_path"]).pages) == source["pages"], source["id"]
        assert source.get("license") and (source.get("authors") or source.get("authors_citation")), source["id"]
    write_json(output / "source-manifest.json", {"schema_version": 1, "collection": "eight-paper-library-demo",
               "selection": "BERT family, sentence embeddings, denoising, scientific NLP and multilingual/Chinese pretraining; complete original publisher PDFs.",
               "papers": sources})

    def save():
        write_json(output / "preparation.json", report)

    save()
    backend = FrozenBackend(binary, fixture / "backend", models, "preparation", "0.2.2")
    started = time.monotonic()
    try:
        with backend:
            report["health"] = backend.health
            assert backend.call("GET", "/models").json()["ready"], "Offline models are not ready"
            library = backend.call("POST", "/library/open", json={"path": str(library_path)}).json()
            backend.scope(library)
            assert library["paper_count"] == 0, "Preparation must start with an empty library"
            report["library"] = library
            result = backend.call("POST", "/papers/import-paths", json={"paths": [source["local_path"] for source in sources]}).json()
            report["import_result"] = result
            assert len(result.get("items", [])) == len(sources) and not result.get("errors") and not result.get("duplicates"), result
            by_filename = {Path(source["local_path"]).name: source for source in sources}
            for imported in result["items"]:
                source = by_filename[imported["filename"]]
                report["papers"].append({"source_id": source["id"], "source": source, "paper_id": imported["id"], "status": imported["status"]})
            assert {paper["source_id"] for paper in report["papers"]} == set(SOURCE_IDS)
            emit({"event": "imported", "papers": len(sources), "pages": sum(source["pages"] for source in sources),
                  "fixture": str(fixture), "library_path": str(library_path)})
            save()
            paper_lookup = {paper["paper_id"]: paper for paper in report["papers"]}
            previous = {}
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                jobs = backend.call("GET", "/jobs").json()["items"]
                for job in jobs:
                    paper = paper_lookup.get(job["paper_id"])
                    if paper is None:
                        raise AssertionError("Unexpected paper in isolated preparation library")
                    state = {key: job.get(key) for key in ("id", "status", "phase", "pages_done", "pages_total", "resources_count", "error")}
                    if previous.get(job["id"]) != state:
                        previous[job["id"]] = state
                        event = {"seconds": round(time.monotonic() - started, 3), "source_id": paper["source_id"], **state}
                        report["progress"].append(event)
                        emit(event)
                    paper.update(status=job["status"], job=job)
                report["jobs"] = jobs
                save()
                failures = [job for job in jobs if job["status"] in ("failed", "cancelled", "interrupted")]
                if failures:
                    raise RuntimeError(f"A real parsing job failed: {failures}")
                if len(jobs) == len(sources) and all(job["status"] == "completed" for job in jobs):
                    break
                time.sleep(1)
            else:
                for job in report.get("jobs", []):
                    if job["status"] not in ("completed", "failed", "cancelled", "interrupted"):
                        backend.call("POST", f"/jobs/{job['id']}/cancel")
                raise TimeoutError("Library preparation exceeded its timeout; unfinished jobs were cancelled")

            for paper in report["papers"]:
                paper_id = paper["paper_id"]
                metadata = backend.call("GET", f"/papers/{paper_id}").json()
                resources = list_resources(backend, paper_id)
                original = library_path / "papers" / paper_id / "original.pdf"
                assert digest(original) == paper["source"]["sha256"]
                assert hashlib.sha256(backend.call("GET", f"/papers/{paper_id}/pdf").content).hexdigest() == paper["source"]["sha256"]
                assert not metadata.get("edited_fields"), "Automatic extraction has unexpected manual edits"
                paper.update(metadata=metadata, counts={kind: sum(resource["kind"] == kind for resource in resources) for kind in ("figure", "table")},
                             resources=resources, original_pdf=file_evidence(original), source_hash_preserved=True)
                paper["workers"] = backend.worker_observer.snapshot(original, settle_seconds=1)
                assert paper["workers"] and all(worker["exit_code"] == 0 for worker in paper["workers"]), "Missing or nonzero worker exit observation"
                write_json(output / "papers" / f"{paper['source_id']}.json", paper)
                emit({"event": "verified", "source_id": paper["source_id"], "title": metadata.get("title"), "counts": paper["counts"]})
                save()

            # Keep the demonstration library's content entirely from the real
            # parsed papers; the recording can add explicitly visible tags.
            for query in QUERIES:
                result = backend.call("GET", "/search", params={"q": query}).json()
                per_group = {}
                all_ids = set()
                for group in GROUPS:
                    ids = sorted({hit["paper_id"] for hit in result[group]})
                    all_ids.update(ids)
                    per_group[group] = {"hits": len(result[group]), "distinct_papers": len(ids), "paper_ids": ids,
                                        "source_ids": [paper_lookup[paper_id]["source_id"] for paper_id in ids]}
                report["queries"][query] = {"results": result, "groups": per_group, "distinct_papers": len(all_ids),
                                            "paper_ids": sorted(all_ids), "result_limit_per_group": 25}
                emit({"event": "search_probe", "query": query, "groups": {key: {"hits": value["hits"], "papers": value["distinct_papers"]} for key, value in per_group.items()}})
            candidates = {query: value for query, value in report["queries"].items() if value["distinct_papers"] >= 2}
            assert candidates, "No verified cross-paper query is available for the demonstration"
            preferred = "BERT" if "BERT" in candidates else max(candidates, key=lambda query: candidates[query]["distinct_papers"])
            report["recommended_query"] = preferred
            report["library"] = backend.call("GET", "/library").json()
            assert report["library"]["paper_count"] == len(sources)
            report["summary"] = {"papers": len(sources), "pages": sum(source["pages"] for source in sources),
                                 "figures": report["library"]["figure_count"], "tables": report["library"]["table_count"],
                                 "manual_demo_notes": len(report["manual_demo_notes"])}
            write_json(output / "search-probes.json", {"recommended_query": preferred, "queries": report["queries"]})
        report["shutdown"] = backend.shutdown
        assert backend.shutdown["returncode"] == 0 and backend.shutdown["backend_port_closed"] and not backend.forced_termination
        report["passed"] = True
    except Exception as error:
        report["errors"].append({"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()})
        raise
    finally:
        if hasattr(backend, "shutdown"):
            report["shutdown"] = backend.shutdown
        report["seconds"] = round(time.monotonic() - started, 3)
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        save()
        emit({"event": "finished", "passed": report["passed"], "report": str(output / "preparation.json"),
              "fixture": str(fixture), "library_path": str(library_path), "recommended_query": report.get("recommended_query")})


if __name__ == "__main__":
    main()
