"""Make a local, filterable catalogue of actual expanded-corpus outputs."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "artifacts/real-corpus-expanded/review.html"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def link(value):
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    assert path.is_file(), path
    return quote(Path(os.path.relpath(path, OUTPUT.parent)).as_posix(), safe="/:")


def issues_text(obj):
    return [issue if isinstance(issue, str) else issue.get("description", issue.get("detail", str(issue)))
            for issue in obj.get("issues", [])]


def source_pages(identifier, indices):
    links = []
    for index in sorted(set(indices)):
        folder = OUTPUT.parent / "source-pages" / identifier
        candidates = [folder / f"page-{index + 1:02d}.png", folder / f"page-{index + 1}.png"]
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        assert path is not None, (identifier, index)
        links.append(f'<a href="{link(path)}">原页 {index + 1}</a>')
    return " · ".join(links)


def main():
    truth = {p["id"]: p for file in (ROOT / "tests/corpus/expanded").glob("ground-truth-*.json") for p in read(file)["papers"]}
    reviews = {p["id"]: p for file in OUTPUT.parent.glob("quality-*.json") if file.name != "quality-summary.json" for p in read(file)["papers"]}
    papers = [p for file in sorted((OUTPUT.parent / "batches").glob("*/report.json")) for p in read(file)["papers"]]
    assert len(papers) == 20 and len(truth) == 20 and len(reviews) == 20, "Wait for all independent reviews before publishing the catalogue"
    esc = html.escape
    sections, index = [], []
    for paper in papers:
        source = paper["source"]
        identifier = source["id"]
        gold, review = truth[identifier], reviews[identifier]
        deep = gold.get("review_level", source.get("review_level")) == "deep_review"
        level = "深入核对" if deep else "图表清单核对"
        expected = {kind: sum(o["kind"] == kind for o in gold["objects"]) for kind in ("figure", "table")}
        index.append(f'<tr><td><a href="#{esc(identifier)}">{esc(source["title"])}</a></td><td>{paper["page_count"]}</td><td>{expected["figure"]}/{expected["table"]}</td><td>{paper["counts"]["figure"]}/{paper["counts"]["table"]}</td><td>{level}</td></tr>')
        issue_map = {}
        object_rows = []
        for obj in review.get("objects", []):
            text = issues_text(obj)
            for resource_id in obj.get("resource_ids", []):
                issue_map.setdefault(resource_id, []).extend(text)
            matched = len(obj.get("resource_ids", []))
            status = f"{matched} 个对应资源" if matched else "未提取"
            object_rows.append(f'<tr><td>{esc(obj["kind"].title())} {esc(str(obj["number"]))}</td><td>{source_pages(identifier, obj["page_indices"])}</td><td>{status}</td><td>{esc("；".join(text) or "本清单未记录问题；审核范围见上方")}</td></tr>')
        for extra in review.get("extra_resources", []):
            resource_id = extra.get("resource_id", extra.get("id"))
            if resource_id:
                issue_map.setdefault(resource_id, []).append(extra.get("reason", extra.get("classification", "额外资源，见质量记录")))
        cards = []
        for resource in paper["resources"]:
            data = read(Path(resource["auto_json"]))
            png = next(file for file in resource["exports"] if file.get("dpi") == 300)
            title = f'{data["kind"].title()} {data.get("number") or "（未提取编号）"}'
            warnings = issue_map.get(resource["id"], [])
            files = [f'<a href="{link(f["path"])}">{esc(f["format"].upper())}</a>' for f in resource["exports"] if f["format"] in ("csv", "html")]
            cards.append(f'''<article class="asset" data-issue="{str(bool(warnings)).lower()}"><h3>{esc(title)}</h3>
<a href="{link(png['path'])}"><img loading="lazy" src="{link(png['path'])}" alt="实际300DPI导出"></a>
<p>{source_pages(identifier, [item['page_index'] for item in data['locations']])} · {' · '.join(files)}</p>
<details><summary>图注与记录</summary><p>{esc(data.get('caption') or '无图注')}</p><p>{esc('；'.join(warnings) or ('本资源未记录问题，但预选单元格不代表全表正确。' if deep else '本篇仅核图表清单；没有给出逐像素/逐单元格准确性结论。'))}</p></details></article>''')
        sections.append(f'''<section id="{esc(identifier)}" data-title="{esc(source['title'].lower())}" data-level="{'deep' if deep else 'inventory'}">
<h2>{esc(source['title'])}</h2><p>{level} · {paper['page_count']}页 · 解析{paper['parse_seconds']:.1f}秒 · <a href="{link(source['local_path'])}">原始PDF</a> · <a href="{esc(source['source_url'], quote=True)}">官方来源</a></p>
<p>{esc(source.get('authors_citation', ', '.join(source.get('authors', []))))} · {esc(source['license'])}</p>
<details><summary>原文图表清单（包括未提取的对象）</summary><table><thead><tr><th>对象</th><th>原文</th><th>匹配</th><th>已记录问题</th></tr></thead><tbody>{''.join(object_rows)}</tbody></table></details>
<div class="assets">{''.join(cards) or '<p>未输出图表资源；是否符合原文见独立清单。</p>'}</div></section>''')
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PaperVault 扩展真实论文测试</title>
<style>:root{color-scheme:light dark}body{font:14px/1.55 system-ui,sans-serif;max-width:1500px;margin:24px auto;padding:0 22px}header{position:sticky;top:0;background:Canvas;border-bottom:1px solid #888;padding:10px 0;z-index:1}h1{font-size:21px;margin:0 0 8px}h2{font-size:19px}h3{font-size:15px}a{color:#4389cc}input,select{font:inherit;padding:5px 8px}table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid #8885;padding:7px}section{border-top:2px solid #888;margin-top:35px;padding-top:10px;scroll-margin-top:100px}.assets{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}.asset{border:1px solid #8885;padding:12px;min-width:0}.asset img{width:100%;height:260px;object-fit:contain;background:white}.asset p{overflow-wrap:anywhere}details p{white-space:normal}.hidden{display:none}body.issues-only .asset[data-issue=false]{display:none}</style>
<header><h1>20篇真实论文扩展测试 · 243页</h1><input id="query" aria-label="筛选论文" placeholder="输入论文标题"><select id="level" aria-label="审核范围"><option value="all">全部范围</option><option value="deep">仅深入核对</option><option value="inventory">仅清单核对</option></select> <label><input id="issues" type="checkbox">仅显示已记录问题资源</label></header>
<p>本页展示安装版0.2.1的原始自动输出。20篇流程检查通过不等于内容准确；6篇深入核对，14篇只核图表清单。资源数包含拆分、出版标志及无编号对象。附录编号的软件修复由0.2.2另行验证，旧输出保留。</p>
<details><summary>论文目录（原文图/表 vs 自动图/表）</summary><table><thead><tr><th>论文</th><th>页</th><th>原文编号图/表</th><th>自动资源图/表</th><th>人工范围</th></tr></thead><tbody>'''
    document += "".join(index) + "</tbody></table></details>" + "".join(sections)
    document += '''<script>const filter=()=>{const q=document.getElementById('query').value.toLowerCase(),l=document.getElementById('level').value;document.querySelectorAll('section').forEach(s=>s.classList.toggle('hidden',!s.dataset.title.includes(q)||(l!=='all'&&s.dataset.level!==l)))};document.getElementById('query').addEventListener('input',filter);document.getElementById('level').addEventListener('change',filter);document.getElementById('issues').addEventListener('change',e=>document.body.classList.toggle('issues-only',e.target.checked));</script></html>'''
    OUTPUT.write_text(document, encoding="utf-8", newline="\n")
    print(f"Generated {len(papers)} paper sections and {sum(len(p['resources']) for p in papers)} actual resources")


if __name__ == "__main__":
    main()
