"""Combine immutable review reports without broadening their review scope."""
import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts/real-corpus-expanded"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def evidence(path):
    path = Path(path)
    return {"path": relative(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def bool_counts(objects, field):
    # bool(None) must never turn an unreviewed observation into a scored result.
    values = [o.get(field) for o in objects]
    return {"true": sum(v is True for v in values), "false": sum(v is False for v in values),
            "not_graded": sum(v is None for v in values),
            "other_status": dict(collections.Counter(str(v) for v in values if v is not True and v is not False and v is not None))}


def caption_counts(objects):
    values = [o.get("caption_association") for o in objects]
    return {"unqualified_correct": sum(v is True or v == "correct" for v in values),
            "status_counts": dict(collections.Counter("true" if v is True else "false" if v is False else "not_graded" if v is None else str(v) for v in values)),
            "policy": "Only boolean true and the exact status 'correct' count as unqualified correct. Qualified/contaminated/partial statuses remain separate, not silently upgraded."}


def group_summary(papers):
    objects = [o for p in papers for o in p["objects"]]
    samples = [c for p in papers for c in p.get("sample_cells", [])]
    deep = bool(papers) and all(p["review_level"] == "deep_review" for p in papers)
    summary = {"papers": len(papers), "paper_ids": [p["id"] for p in papers],
        "pages": sum(p["pages"] for p in papers), "logical_numbered_objects": len(objects),
        "expected_counts": dict(collections.Counter(o["kind"] for o in objects)),
        "objects_with_resource_match": sum(bool(o.get("resource_ids")) for o in objects),
        "objects_without_resource_match": sum(not o.get("resource_ids") for o in objects),
        "correct_type": bool_counts(objects, "correct_type"), "correct_number": bool_counts(objects, "correct_number"),
        "caption_association": caption_counts(objects),
        "predeclared_sample_cells": len(samples),
        "sample_status_counts": dict(collections.Counter(c["status"] for c in samples))}
    if deep:
        summary.update(crop_complete=bool_counts(objects, "crop_complete"),
            complete_as_single_resource=bool_counts(objects, "complete_as_single_resource"),
            clean_separate_crop=bool_counts(objects, "clean_separate_crop"))
    else:
        summary.update(crop_complete=None, complete_as_single_resource=None, clean_separate_crop=None,
            limitation="Inventory-only papers are not included in crop/cell quality denominators. Explicit spot-check issues remain visible in per-object source records.")
    return summary


review_paths = [OUT / f"quality-{name}.json" for name in ("ml", "diverse", "science")]
assert all(p.is_file() for p in review_paths), "All three complete quality reports are required before summarizing."
workflow_path = OUT / "workflow-summary.json"
workflow = read(workflow_path)
sources = {p["id"]: p for f in (ROOT / "tests/corpus/expanded").glob("sources-*.json") for p in read(f)["papers"]}
baselines = {}
for batch in workflow["batches"]:
    path = ROOT / batch["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == batch["sha256"]
    for p in read(path)["papers"]:
        assert p["source"]["id"] not in baselines
        baselines[p["source"]["id"]] = p

papers, review_documents = [], []
for path in review_paths:
    document = read(path)
    assert document.get("review_complete", True)
    review_documents.append(document)
    for paper in document["papers"]:
        ident = paper["id"]
        source, baseline = sources[ident], baselines[ident]
        assert source["sha256"] == baseline["source"]["sha256"]
        assert paper["review_level"] in ("deep_review", "inventory_only")
        objects = paper.get("objects", paper.get("inventory_matches"))
        assert isinstance(objects, list), (ident, "missing object inventory")
        entry = {"id": ident, "title": source["title"], "pages": source["pages"],
            "review_level": paper["review_level"], "source_sha256": source["sha256"],
            "quality_report": relative(path), "workflow_passed": baseline["passed"],
            "observed_counts": baseline["counts"], "objects": objects,
            "sample_cells": paper.get("sample_cells", []), "extra_resources": paper.get("extra_resources", []),
            "notes": paper.get("notes", []), "issues": paper.get("issues", []),
            "worker_exit_coverage": baseline.get("worker_exit_coverage", "unknown"),
            "worker_processes": baseline.get("worker_processes", [])}
        papers.append(entry)

assert len(papers) == len({p["id"] for p in papers}) == 20
assert {p["id"] for p in papers} == set(sources) == set(baselines)
assert sum(p["pages"] for p in papers) == 243
deep = [p for p in papers if p["review_level"] == "deep_review"]
inventory = [p for p in papers if p["review_level"] == "inventory_only"]
assert len(deep) == 6 and len(inventory) == 14
assert not any(p["sample_cells"] for p in inventory), "Inventory-only sample cells would need an explicit scope decision."
workers = [w for p in papers for w in p["worker_processes"]]
extra = [e for p in papers for e in p["extra_resources"]]
previous = read(ROOT / "artifacts/real-corpus/quality-summary.json")
summary = {"schema_version": 1, "status": "reviewed-with-quality-limitations", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "baseline_version": workflow["application_version"], "backend_sha256": workflow["backend_sha256"],
    "scope": "Twenty newly downloaded complete publisher PDFs. Six deep-reviewed papers and fourteen inventory-only papers are kept in separate quality denominators. This summary describes the unchanged installed 0.2.1 baseline with its original caption-number failures. The final frozen 0.2.2 repair is evaluated in separate evidence reports.",
    "workflow": {"new_papers": len(papers), "pages": sum(p["pages"] for p in papers),
        "workflow_passed_papers": sum(p["workflow_passed"] is True for p in papers),
        "observed_resource_counts": {kind: sum(p["observed_counts"].get(kind, 0) for p in papers) for kind in ("figure", "table", "resources")},
        "worker_records": len(workers), "worker_exit_code_counts": dict(collections.Counter(str(w["exit_code"]) for w in workers)),
        "worker_exit_coverage_complete": all(p["worker_exit_coverage"] == "captured" for p in papers),
        "native_diagnostic_log_matches": workflow.get("native_diagnostic_log_matches", []),
        "limitation": "Workflow completion, readable exports and captured zero worker exits do not establish content accuracy or resolve the previously observed source-suite native diagnostic."},
    "deep_review": group_summary(deep), "inventory_only": group_summary(inventory),
    "numbered_inventory": {"logical_objects": sum(len(p["objects"]) for p in papers),
        "expected_counts": dict(collections.Counter(o["kind"] for p in papers for o in p["objects"])),
        "limitation": "Inventory coverage is broader than deep-quality coverage; these totals must not serve as the denominator for an all-object crop or cell accuracy percentage."},
    "extra_resource_classifications": dict(collections.Counter(e.get("classification", "unclassified") for e in extra)),
    "extra_resource_policy": "Valid unnumbered notation tables lie outside the numbered-object denominator and are not false positives. Logos/page furniture, blank detections, equations and unreviewed extras retain separate classifications; no blanket scientific false-positive rate is inferred.",
    "cumulative_source_coverage": {"previous_papers": previous["summary"]["papers"], "previous_pages": previous["summary"]["pages"],
        "new_papers": len(papers), "new_pages": sum(p["pages"] for p in papers),
        "total_distinct_papers": previous["summary"]["papers"] + len(papers), "total_pages": previous["summary"]["pages"] + sum(p["pages"] for p in papers),
        "limitation": "Only source coverage is added across rounds. Different review depths and baseline versions are not combined into a universal extraction-accuracy percentage."},
    "review_files": [evidence(p) for p in review_paths], "workflow_report": evidence(workflow_path),
    "review_field_semantics": {path.stem: doc.get("field_semantics", {"crop_policy": doc.get("crop_policy"), "scope": doc.get("scope")}) for path, doc in zip(review_paths, review_documents)},
    "papers": papers,
    "boundaries": [
        "A found fragment is an inventory match, not a complete logical object.",
        "Merged resources can retain both objects' content while failing clean/separate extraction.",
        "ML deep crop judgements include printed subpanel labels/explanations; diagram-only coverage is separately retained in quality-ml.json.",
        "Predeclared cell checks are selected semantic checkpoints, not all table cells or a representative general accuracy estimate.",
        "Exact numeric samples do not override lost grouping/headers, missing tables, contaminated captions or scientific-symbol defects.",
        "The nine appendix-number fixes belong to separate 0.2.2 verification; the original 0.2.1 baseline failures remain recorded here.",
        "The caption-number patch does not fix title selection, table structure, crop completeness, missing objects or caption association. This report makes no all-titles-correct claim.",
    ]}
assert summary["cumulative_source_coverage"]["total_distinct_papers"] == 27
assert summary["cumulative_source_coverage"]["total_pages"] == 314
destination = OUT / "quality-summary.json"
destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: summary[k] for k in ("workflow", "deep_review", "inventory_only", "extra_resource_classifications", "cumulative_source_coverage")}, ensure_ascii=False, indent=2))
