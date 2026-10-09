"""Repeatable search/pagination stress test, explicitly using synthetic metadata.

This measures indexing/query cost. It is not a PDF parsing accuracy benchmark.
"""
from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from papervault.files import uid  # noqa: E402
from papervault.library import Library, encode, now  # noqa: E402


def main():
    count = 1000
    root = ROOT / ".test-data" / ("benchmark-" + uid())
    library = Library(root)
    started = time.perf_counter()
    try:
        with library.db.transaction() as con:
            for index in range(count):
                paper_id = uid()
                metadata = {"title": f"Synthetic paper {index}: 深度学习和 KV Cache", "authors": ["Synthetic benchmark"],
                            "abstract": "本记录仅用于性能压力测试。 " + "Local research assets and reproducible experiments. " * 8,
                            "tags": ["benchmark"], "year": 2026}
                con.execute("INSERT INTO papers(id,sha256,filename,auto_json,status,created_at) VALUES(?,?,?,?,?,?)",
                            (paper_id, uid()+uid(), f"synthetic-{index}.pdf", encode(metadata), "completed", now()))
                for number in range(5):
                    kind = "figure" if number < 3 else "table"
                    resource = {"caption": f"KV Cache Architecture 深度学习 {index}-{number}",
                                "locations": [{"page_index": 0, "bbox": [10, 10, 100, 100]}], "files": {},
                                "table": {"rows": [["TTFT", "1.2e-3"]]} if kind == "table" else None}
                    con.execute("INSERT INTO resources(id,paper_id,kind,auto_json) VALUES(?,?,?,?)",
                                (uid(), paper_id, kind, encode(resource)))
                con.execute("INSERT INTO blocks VALUES(?,?,?,?,?,?)",
                            (uid(), paper_id, "paragraph", "深度学习 improves KV Cache latency. "*20,
                             encode({"page_index": 0, "bbox": [0, 0, 10, 10]}), None))
                library._reindex(con, paper_id)
        build_seconds = time.perf_counter()-started
        latency, pages = [], []
        for index in range(50):
            started = time.perf_counter()
            hits = library.search(["深度 KV", "Cache", "TTFT", "学习", "reproducible"][index % 5])
            assert any(hits.values())
            latency.append((time.perf_counter()-started)*1000)
            started = time.perf_counter()
            result = library.resources(kind="figure", offset=index*30, limit=30)
            assert len(result["items"]) == 30
            pages.append((time.perf_counter()-started)*1000)
        def summary(samples):
            return {"p50_ms": round(statistics.median(samples), 3),
                    "p95_ms": round(sorted(samples)[int(len(samples)*.95)-1], 3),
                    "max_ms": round(max(samples), 3)}
        report = {"dataset": "Explicit synthetic metadata, not a parser accuracy result",
                  "papers": count, "resources": count*5, "text_blocks": count,
                  "machine": {"platform": platform.platform(), "cpu": platform.processor(),
                              "logical_cpus": psutil.cpu_count(), "ram_bytes": psutil.virtual_memory().total},
                  "index_build_seconds": round(build_seconds, 3), "queries": len(latency),
                  "grouped_search": summary(latency), "gallery_page_30": summary(pages),
                  "process_rss_bytes": psutil.Process().memory_info().rss,
                  "database_bytes": library.db.path.stat().st_size}
        target = ROOT / "artifacts/search-benchmark.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        library.close()


if __name__ == "__main__":
    main()
