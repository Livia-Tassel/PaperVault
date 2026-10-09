from __future__ import annotations

import csv
import html
from pathlib import Path


def validate_table(table: dict) -> dict:
    if not isinstance(table, dict):
        raise ValueError("表格内容必须包含rows结构")
    rows = table.get("rows", [])
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError("表格行数无效或超过10000行")
    width = max((len(row) for row in rows if isinstance(row, list)), default=0)
    if width > 1000 or any(not isinstance(row, list) for row in rows):
        raise ValueError("表格列结构无效")
    normalized = [[str(value) if value is not None else "" for value in row] + [""] * (width-len(row))
                  for row in rows]
    return {**table, "rows": normalized, "header_rows": max(0, min(int(table.get("header_rows", 1)), len(rows)))}


def write_table(table: dict, directory: Path, caption: str = "") -> dict[str, str]:
    table = validate_table(table)
    directory.mkdir(parents=True, exist_ok=True)
    csv_path, html_path = directory / "table.csv", directory / "table.html"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        csv.writer(stream).writerows(table["rows"])
    cells = table.get("cells") or []
    cell_map = {(int(c.get("row", -1)), int(c.get("col", -1))): c for c in cells}
    occupied = set()
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Table</title>',
             '<style>table{border-collapse:collapse}td,th{border:1px solid #888;padding:6px;white-space:pre-wrap}</style>',
             "<table><caption>" + html.escape(caption or "") + "</caption>"]
    for r, row in enumerate(table["rows"]):
        parts.append("<tr>")
        for c, value in enumerate(row):
            if (r, c) in occupied:
                continue
            cell = cell_map.get((r, c), {})
            rs = max(1, min(int(cell.get("row_span", 1)), len(table["rows"]) - r))
            cs = max(1, min(int(cell.get("col_span", 1)), len(row) - c))
            for rr in range(r, r+rs):
                for cc in range(c, c+cs):
                    occupied.add((rr, cc))
            tag = "th" if r < table["header_rows"] or cell.get("is_header") else "td"
            parts.append(f'<{tag} rowspan="{rs}" colspan="{cs}">{html.escape(value)}</{tag}>')
        parts.append("</tr>")
    parts.append("</table></html>")
    html_path.write_text("\n".join(parts), encoding="utf-8")
    return {"csv": str(csv_path), "html": str(html_path)}
