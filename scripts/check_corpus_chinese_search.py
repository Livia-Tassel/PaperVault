"""Check predeclared real-PDF Chinese probes against the installed structured index."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pypdfium2 as pdfium

from test_real_corpus import FrozenBackend, ROOT, digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-report", type=Path, required=True)
    parser.add_argument("--truth", type=Path, default=ROOT / "tests/corpus/expanded/ground-truth-diverse.json")
    args = parser.parse_args()
    corpus = json.loads(args.corpus_report.read_text(encoding="utf-8"))
    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    sources = {p["source"]["id"]: p for p in corpus["papers"]}
    checks = [p for p in truth["papers"] if p["id"] in sources and p.get("search_probes")]
    assert checks and corpus["passed"]
    binary = Path(corpus["backend"])
    assert digest(binary) == corpus["backend_sha256"]
    directory = ROOT / ".test-data/expanded-search" / uuid4().hex
    directory.mkdir(parents=True)
    report = {"executed": False, "version": corpus["health"]["version"], "backend_sha256": digest(binary),
              "corpus_report": str(args.corpus_report), "ground_truth": str(args.truth),
              "ground_truth_sha256": digest(args.truth), "papers": [],
              "scope": "Read-only real API queries from source-PDF probes fixed before model inspection. A miss is recorded, never replaced by an easier query."}
    backend = FrozenBackend(binary, directory, ROOT / ".cache/models", expected_version=report["version"])
    with backend:
        library = backend.call("POST", "/library/open", json={"path": corpus["auto_baseline_library"]["path"]}).json()
        backend.scope(library)
        for reference in checks:
            parsed = sources[reference["id"]]
            before = backend.call("GET", f"/papers/{parsed['paper_id']}").json()
            data = backend.call("GET", f"/papers/{parsed['paper_id']}/pdf").content
            assert hashlib.sha256(data).hexdigest() == parsed["source_pdf"]["sha256"]
            structure = json.loads((Path(parsed["paper_json"]).parent / "structure.json").read_text(encoding="utf-8"))
            paper = {"id": reference["id"], "paper_id": parsed["paper_id"], "probes": []}
            document = pdfium.PdfDocument(data)
            try:
                for probe in reference["search_probes"]:
                    page = document[probe["page_index"]]
                    text_page = page.get_textpage()
                    try:
                        raw = text_page.get_text_range()
                    finally:
                        text_page.close()
                        page.close()
                    needle = "".join(probe["query"].split())
                    raw_contains = needle in "".join(raw.split())
                    matches = backend.call("GET", "/search", params={"q": probe["query"]}).json()
                    hits = [{"group": group, **hit} for group, items in matches.items() if isinstance(items, list)
                            for hit in items if hit.get("paper_id") == parsed["paper_id"] or hit.get("id") == parsed["paper_id"]]
                    page_blocks = [block for block in structure["blocks"] if block.get("location") and block["location"]["page_index"] == probe["page_index"]]
                    containing = [block for block in page_blocks if needle in "".join(block.get("text", "").split())]
                    paper["probes"].append({"source_probe": probe, "original_pdfium_text_contains_query": raw_contains,
                                            "structured_blocks_containing_query": [{"id": b["id"], "label": b["label"], "text": b["text"], "location": b["location"]} for b in containing],
                                            "matched_this_paper": bool(hits), "hits": hits,
                                            "correct_page_hit": any((hit.get("location") or {}).get("page_index") == probe["page_index"] for hit in hits),
                                            "diagnosis": "matched" if hits else "source_text_not_in_structured_blocks" if raw_contains and not containing else "requires_investigation"})
            finally:
                document.close()
            assert backend.call("GET", f"/papers/{parsed['paper_id']}").json() == before
            paper["paper_unchanged"] = True
            report["papers"].append(paper)
    report["executed"] = True
    report["shutdown"] = backend.shutdown
    probes = [probe for paper in report["papers"] for probe in paper["probes"]]
    report["summary"] = {"probes": len(probes), "matched": sum(p["matched_this_paper"] for p in probes),
                         "correct_page": sum(p["correct_page_hit"] for p in probes),
                         "missed": sum(not p["matched_this_paper"] for p in probes)}
    write_json(ROOT / "artifacts/real-corpus-expanded/chinese-search.json", report)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
