"""Build an explicitly synthetic gallery load using a real rendered PDF crop.

The library is created offline before any backend opens it. This is a browser
rendering workload, never evidence of 1,000 successfully parsed figures.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from papervault.files import sha256, uid  # noqa: E402
from papervault.library import Library, encode  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=ROOT / ".test-data/gallery-benchmark-library")
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()
    root = args.library.resolve()
    if (root / "database/papervault.db").exists():
        raise SystemExit("Benchmark library already exists; use a new --library path. No existing data changed.")
    if not 24 <= args.count <= 10000:
        raise SystemExit("Use 24–10,000 synthetic resources.")
    source = ROOT / "tests/fixtures/academic.pdf"
    started = time.perf_counter()
    library = Library(root)
    try:
        paper, _ = library.import_file(source)
        location = {"page_index": 0, "bbox": [72, 350, 540, 470]}
        seed = library.crop(paper["id"], location, dpi=150, kind="figure",
                            name="Synthetic Figure 0001 [benchmark]",
                            caption="合成图库负载：复用真实 PDF 的矢量架构图裁剪；不代表解析准确率。")
        with library.mutex, library.db.transaction() as con:
            con.execute("UPDATE jobs SET status='cancelled',phase='Synthetic benchmark fixture; parser not invoked'")
            metadata = {"title": "[SYNTHETIC LOAD] Real PDF crop gallery benchmark",
                        "authors": ["PaperVault benchmark generator"], "year": 2026,
                        "tags": ["synthetic-benchmark"], "warnings": ["Synthetic metadata; one genuine PDF crop reused."]}
            con.execute("UPDATE papers SET auto_json=?,status='completed' WHERE id=?", (encode(metadata), paper["id"]))
            for index in range(1, args.count):
                resource = {"name": f"Synthetic Figure {index + 1:04d} [benchmark]",
                            "number": str(index + 1),
                            "caption": f"明确标注的合成性能负载 {index + 1:04d}. PDF INPUT → ANALYSIS → LIBRARY. "
                                       "复用真实 PNG，用于测量分页、图片解码与图库滚动，不用于解析质量评估。",
                            "locations": [location], "files": seed["files"], "tags": [f"topic-{index % 10}"],
                            "notes": "Synthetic browser benchmark record", "table": None}
                con.execute("INSERT INTO resources(id,paper_id,kind,auto_json,manual) VALUES(?,?,'figure',?,1)",
                            (uid(), paper["id"], encode(resource)))
            library._reindex(con, paper["id"])
        png = root / seed["files"]["png"]
        thumbnail = root / seed["files"]["thumbnail"]
        report = {"synthetic_metadata": True, "description": f"{args.count} metadata rows share one real PDFium crop and thumbnail; not parser accuracy evidence",
                  "library": str(root), "papers": 1, "figures": args.count,
                  "source_pdf": str(source.relative_to(ROOT)), "source_pdf_sha256": sha256(source),
                  "source_location": location, "png_sha256": sha256(png), "thumbnail_sha256": sha256(thumbnail),
                  "png_bytes": png.stat().st_size, "thumbnail_bytes": thumbnail.stat().st_size,
                  "generation_seconds": round(time.perf_counter() - started, 3),
                  "machine": {"platform": platform.platform(), "cpu": platform.processor(),
                              "logical_cpus": psutil.cpu_count(), "ram_bytes": psutil.virtual_memory().total}}
        (root / "benchmark-dataset.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        library.close()


if __name__ == "__main__":
    main()
