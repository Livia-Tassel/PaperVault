"""FTS5 preprocessing with deterministic mixed CJK/Latin phrase queries."""
from __future__ import annotations

import json
import unicodedata


def is_cjk(char: str) -> bool:
    number = ord(char)
    return (0x3400 <= number <= 0x9FFF or 0x20000 <= number <= 0x323AF
            or 0x3040 <= number <= 0x30FF or 0xAC00 <= number <= 0xD7AF)


def token_spans(text: str):
    start = None
    for index, char in enumerate(text):
        if is_cjk(char):
            if start is not None:
                yield text[start:index].casefold(), start, index
                start = None
            yield char.casefold(), index, index + 1
        elif char.isalnum() or unicodedata.category(char).startswith("M"):
            if start is None:
                start = index
        elif start is not None:
            yield text[start:index].casefold(), start, index
            start = None
    if start is not None:
        yield text[start:].casefold(), start, len(text)


def tokenize(text: str) -> str:
    return " ".join(token for token, _, _ in token_spans(text))


def compile_query(query: str) -> str:
    groups = [tokenize(part) for part in query[:1000].split()]
    return " AND ".join('"' + group.replace('"', '""') + '"' for group in groups if group)


def snippet(text: str, query: str, length: int = 260) -> list[dict]:
    tokens = list(token_spans(text))
    ranges = []
    values = [value[0] for value in tokens]
    for part in query.split():
        wanted = [value[0] for value in token_spans(part)]
        if not wanted:
            continue
        for i in range(len(values) - len(wanted) + 1):
            if values[i:i + len(wanted)] == wanted:
                ranges.append((tokens[i][1], tokens[i + len(wanted) - 1][2]))
    ranges.sort()
    start = max(0, ranges[0][0] - 70) if ranges else 0
    end = min(len(text), start + length)
    segments = []
    if start:
        segments.append({"text": "…", "matched": False})
    position = start
    for left, right in ranges:
        left, right = max(left, position), min(right, end)
        if left >= right:
            continue
        if left > position:
            segments.append({"text": text[position:left], "matched": False})
        segments.append({"text": text[left:right], "matched": True})
        position = right
    if position < end:
        segments.append({"text": text[position:end], "matched": False})
    if end < len(text):
        segments.append({"text": "…", "matched": False})
    return segments


def index_entry(con, entity_id, kind, paper_id, title, text, location=None):
    con.execute(
        "INSERT INTO search_entries(entity_id,kind,paper_id,title,raw_text,location_json,tokens) "
        "VALUES (?,?,?,?,?,?,?)",
        (entity_id, kind, paper_id, title or "", text, json.dumps(location), tokenize(text)),
    )


def find(con, query: str, limit: int = 100, kind: str | None = None):
    expression = compile_query(query)
    if not expression:
        return []
    kind_filter = " AND kind=?" if kind else ""
    args = [expression, kind, limit] if kind else [expression, limit]
    rows = con.execute(
        "SELECT *,bm25(search_entries) AS rank FROM search_entries "
        "WHERE search_entries MATCH ?" + kind_filter + " ORDER BY rank LIMIT ?", args
    ).fetchall()
    return [{"id": row["entity_id"], "kind": row["kind"], "paper_id": row["paper_id"],
             "title": row["title"], "location": json.loads(row["location_json"] or "null"),
             "snippet": snippet(row["raw_text"], query), "rank": row["rank"]} for row in rows]
