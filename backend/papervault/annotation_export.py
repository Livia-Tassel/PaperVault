"""Portable user annotations; never include local absolute source paths."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

from .files import uid
from .reading import timestamp


def annotation_markdown(items, *, linked_pdf=False):
    lines = ["# 阅读笔记", ""]
    for item in items:
        title = item["title"] or {"bookmark": "页书签", "highlight": "文本高亮", "note": "笔记"}[item["kind"]]
        lines += ["## " + html.escape(title).replace("\n", " "), "",
                  "论文：" + html.escape(item["paper_title"]), "",
                  f"论文 ID：`{item['paper_id']}` · 笔记 ID：`{item['id']}`", "",
                  f"原PDF SHA-256：`{item['pdf_sha256']}`", "",
                  f"类型：{item['kind']} · 颜色：{item['color']} · 更新时间：{item['updated_at']}", ""]
        if item["tags"]:
            lines += ["标签：" + "、".join(html.escape(tag) for tag in item["tags"]), ""]
        for location in item["locations"]:
            page = location["page_index"] + 1
            source = f"[第 {page} 页](original.pdf#page={page})" if linked_pdf else f"第 {page} 页"
            lines += ["位置：" + source + (" · PDF坐标 `" + json.dumps(location["bbox"]) + "`" if location["bbox"] else ""), ""]
        if item["quote"]:
            lines += ["原文摘录：", "", *["> " + html.escape(line) for line in item["quote"].splitlines()], ""]
        if item["body"]:
            lines += ["笔记：", "", html.escape(item["body"]), ""]
        lines += ["---", ""]
    if not linked_pdf:
        lines += ["独立笔记导出不包含原PDF；可另行导出论文资源包。", ""]
    return "\n".join(lines)


def export_annotations(library, ids, paper_id=None, format_name="markdown") -> Path:
    if format_name not in ("markdown", "json") or len(ids) > 10000:
        raise ValueError("笔记导出请求无效")
    with library.mutex:
        if ids:
            items = [library.annotation(value) for value in dict.fromkeys(ids)]
        else:
            result = library.annotations(paper_id=paper_id, limit=10000)
            if result["total"] > 10000:
                raise ValueError("导出超过10000条，请分批或按论文导出")
            items = result["items"]
        if not items:
            raise ValueError("没有可导出的笔记")
        content = annotation_markdown(items) if format_name == "markdown" else json.dumps({
            "format": "papervault-annotations-v1", "created_at": timestamp(),
            "library_id": library.info()["id"], "annotations": items}, ensure_ascii=False, indent=2, allow_nan=False)
        suffix = "md" if format_name == "markdown" else "json"
        target = library.root / "exports" / f"notes-{uid()}.{suffix}"
        temporary = target.with_suffix(target.suffix + ".partial")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target
