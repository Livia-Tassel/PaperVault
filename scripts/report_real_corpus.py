"""Combine independent manual reviews with immutable real-paper run evidence."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import json
import os
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/real-corpus/installed-backend-report.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/real-corpus/quality-summary.json")
    args = parser.parse_args()
    baseline = read(args.report)
    reviews, truth = {}, {}
    review_paths = [ROOT / "artifacts/real-corpus" / f"quality-{name}.json" for name in ("control", "ml", "science")]
    for path in review_paths:
        for paper in read(path)["papers"]:
            if paper["id"] in reviews:
                raise ValueError("Duplicate review: " + paper["id"])
            reviews[paper["id"]] = paper
    for path in (ROOT / "tests/corpus").glob("ground-truth-*.json"):
        for paper in read(path)["papers"]:
            truth[paper["id"]] = paper
    papers, global_cells, objects = [], Counter(), []
    for parsed in baseline["papers"]:
        source = parsed["source"]
        review, gold = reviews[source["id"]], truth[source["id"]]
        expected = {(x["kind"], str(x["number"])) for x in gold["objects"]}
        reviewed = {(x["kind"], str(x["number"])) for x in review["objects"]}
        assert expected == reviewed and len(reviewed) == len(review["objects"]), source["id"]
        resources = {resource["id"]: resource for resource in parsed["resources"]}
        for obj in review["objects"]:
            assert set(obj["resource_ids"]) <= set(resources), obj
        cells = Counter(cell["status"] for cell in review.get("sample_cells", []))
        global_cells.update(cells)
        counts = Counter(x["kind"] for x in gold["objects"])
        extra = Counter(x["classification"] for x in review.get("extra_resources", []))
        def association(item):
            return item.get("caption_association") in (True, "correct")
        record = {"id": source["id"], "title": source["title"], "source_url": source["source_url"],
                  "license": source["license"], "pdf_sha256": parsed["source_pdf"]["sha256"],
                  "pages": parsed["page_count"], "parse_seconds": parsed["parse_seconds"],
                  "peak_backend_worker_rss_bytes": parsed["peak_backend_worker_rss_bytes"],
                  "workflow_passed": parsed["passed"], "expected": {kind: counts[kind] for kind in ("figure", "table")},
                  "observed": parsed["counts"], "whole_object_crop_across_segments": sum(x["crop_complete"] is True for x in review["objects"]),
                  "whole_object_single_resource": sum(x["crop_complete"] is True and len(x["resource_ids"]) == 1 for x in review["objects"]),
                  "complete_caption_associations": sum(association(x) for x in review["objects"]),
                  "predeclared_cell_status": dict(cells), "extra_resource_classifications": dict(extra),
                  "objects": review["objects"], "sample_cells": review.get("sample_cells", []), "notes": review.get("notes", [])}
        papers.append(record)
        objects.extend(review["objects"])
    assert set(reviews) == {p["id"] for p in papers}
    result = {"schema_version": 1, "status": "reviewed-with-quality-limitations", "baseline_version": "0.2.0",
              "baseline_run_id": baseline["run_id"], "backend_sha256": baseline["backend_sha256"],
              "method": "Independent source-page visual annotations, followed by per-object PNG/CSV/HTML review; snapshots remain unedited. A workflow pass is not a source-fidelity pass.",
              "scope": "Seven purposefully selected publisher PDFs, not a random sample or general accuracy guarantee. One pre-existing paper plus six new papers. Entire main PDFs including embedded appendices; separate supplements excluded.",
              "papers": papers, "summary": {"papers": len(papers), "pages": sum(p["pages"] for p in papers),
              "workflow_passed_papers": sum(p["workflow_passed"] for p in papers),
              "exported_resources": sum(p["observed"]["resources"] for p in papers),
              "expected_numbered_figures": sum(p["expected"]["figure"] for p in papers),
              "expected_numbered_tables": sum(p["expected"]["table"] for p in papers),
              "whole_object_crop_across_segments": sum(p["whole_object_crop_across_segments"] for p in papers),
              "whole_object_single_resource": sum(p["whole_object_single_resource"] for p in papers),
              "complete_caption_associations": sum(p["complete_caption_associations"] for p in papers),
              "predeclared_cell_status": dict(global_cells),
              "auxiliary_logo_resources": sum(p["extra_resource_classifications"].get("auxiliary_logo", 0) for p in papers)},
              "boundaries": ["Complete PNG body does not prove that table cell rows/columns/units are correct.",
                             "The 60 predefined cells are selected checkpoints, not every cell or a representative accuracy estimate.",
                             "Caption association is separate from exact text fidelity; wrong source Unicode can preserve association but corrupt units.",
                             "A multi-page logical table can cover all data in separate resources while still failing single-resource preservation.",
                             "Title repair is evaluated separately in 0.2.1; these immutable quality figures describe the installed 0.2.0 baseline."],
              "review_files": [{"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in review_paths]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    create_review_html(result, baseline, args.output.parent / "review.html")
    print(json.dumps(result["summary"], ensure_ascii=False))


def create_review_html(review, baseline, output):
    def link(path):
        path = Path(path)
        if not path.is_absolute():
            path = ROOT / path
        return quote(Path(os.path.relpath(path, output.parent)).as_posix(), safe="/:")

    def esc(value):
        return html.escape(str(value), quote=True)

    parsed = {p["source"]["id"]: p for p in baseline["papers"]}
    sections = []
    for paper in review["papers"]:
        run = parsed[paper["id"]]
        resources = {r["id"]: r for r in run["resources"]}
        rows = []
        for obj in paper["objects"]:
            issues = obj.get("issues", [])
            issue_text = []
            for issue in issues:
                issue_text.append(issue if isinstance(issue, str) else issue.get("description", issue.get("detail", str(issue))))
            pages = []
            for page in obj["page_indices"]:
                folder = ROOT / "artifacts/real-corpus/source-pages" / paper["id"]
                candidates = [folder / f"page-{page + 1}.png", folder / f"page-{page + 1:02}.png"]
                source = next(path for path in candidates if path.is_file())
                pages.append(f'<a href="{link(source)}"><img loading="lazy" src="{link(source)}" alt="原文第{page + 1}页"></a>')
            exports = []
            for identifier in obj["resource_ids"]:
                resource = resources[identifier]
                for file in resource["exports"]:
                    if file.get("dpi") == 300:
                        exports.append(f'<a href="{link(file["path"])}"><img loading="lazy" src="{link(file["path"])}" alt="实际300DPI导出"></a>')
                links = [f'<a href="{link(file["path"])}">{esc(file["format"].upper())}</a>' for file in resource["exports"] if file["format"] in ("csv", "html")]
                exports.append(" ".join(links))
            rows.append(f'''<article class="object" data-issue="{str(bool(issues)).lower()}">
<h3>{esc(obj['kind'].title())} {esc(obj['number'])} <small>PDF页 {', '.join(str(x+1) for x in obj['page_indices'])}</small></h3>
<p>{esc('；'.join(issue_text) if issues else '本次对象检查未发现问题；完整方法和抽样范围见JSON。')}</p>
<div class="compare"><div><h4>原始页面</h4>{''.join(pages)}</div><div><h4>自动导出</h4>{''.join(exports)}</div></div></article>''')
        sections.append(f'''<section id="{esc(paper['id'])}"><h2>{esc(paper['title'])}</h2>
<p>{paper['pages']}页 · 原文编号图/表 {paper['expected']['figure']}/{paper['expected']['table']} · 自动资源 {paper['observed']['figure']}/{paper['observed']['table']} · 解析 {paper['parse_seconds']:.1f}秒</p>
<p><a href="{esc(paper['source_url'])}">出版来源</a> · <a href="{link(run['source']['local_path'])}">原PDF</a> · {esc(paper['license'])}</p>
{''.join(rows) or '<p>原文没有科研图表，自动输出零结果。</p>'}</section>''')
    text = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PaperVault 真实论文逐项对照</title><style>
:root{color-scheme:light dark}body{font:15px/1.55 system-ui,sans-serif;max-width:1500px;margin:32px auto;padding:0 24px}a{color:#498bdb}header{position:sticky;top:0;background:Canvas;padding:12px 0;border-bottom:1px solid #888;z-index:1}h1{font-size:22px;margin:0 0 8px}h2{font-size:20px}h3{font-size:17px}h4{margin:4px 0}small{font-weight:normal;font-size:13px}section{border-top:2px solid #888;margin-top:30px;padding-top:12px}.object{border:1px solid #8886;padding:16px;margin:18px 0}.compare{display:grid;grid-template-columns:1fr 1fr;gap:18px}.compare img{display:block;max-width:100%;max-height:850px;object-fit:contain;background:white;margin-bottom:12px}body.issues-only .object[data-issue=false]{display:none}@media(max-width:750px){.compare{grid-template-columns:1fr}}
</style><header><h1>真实论文：原文与实际导出对照</h1><label><input id="issues" type="checkbox"> 只看已记录问题</label> · <a href="quality-summary.json">完整质量记录</a></header>
<p>7篇真实论文，71页。原始人工基准先于输出审核保存；图表能导出不等于内容识别准确。查看每张图表的原页、PNG及CSV/HTML，点图片可查看原尺寸。论文及图像的版权与开放许可属于各自作者；此页仅作本地验证。</p>'''
    text += "".join(sections) + "<script>document.getElementById('issues').addEventListener('change',e=>document.body.classList.toggle('issues-only',e.target.checked));</script></html>"
    output.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
