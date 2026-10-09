"""User reading data, independent from replaceable parser revisions."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import search
from .files import uid
from .schemas import AnnotationCreate, AnnotationPatch, ReadingPatch


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class VersionConflict(Exception):
    def __init__(self, current):
        super().__init__("记录已被更新，请重新读取后重试")
        self.current = current


class ReadingStore:
    def __init__(self, library):
        self.library = library

    def _paper(self, con, paper_id):
        row = con.execute("SELECT * FROM papers WHERE id=? AND removed=0", (paper_id,)).fetchone()
        if not row:
            raise KeyError("论文不存在")
        return row

    def _geometry(self, paper_id):
        from .parsers import inspect_pdf
        from pypdf.errors import PyPdfError
        try:
            return inspect_pdf(self.library.pdf(paper_id))["pages"]
        except PyPdfError as error:
            raise ValueError("无法读取原始PDF页面，请检查文件是否完整或已解锁") from error

    def _page(self, pages, index):
        if not 0 <= index < len(pages):
            raise ValueError("页码超出原始PDF范围")
        return pages[index]["crop_box"]

    @staticmethod
    def _bounded(values, bounds):
        result = []
        for value, lower, upper in zip(values, bounds[0], bounds[1]):
            if not lower - 0.01 <= value <= upper + 0.01:
                raise ValueError("位置坐标超出原始PDF页面范围")
            result.append(min(upper, max(lower, value)))
        return result

    @staticmethod
    def _state(row, paper_id):
        if row is None:
            return {"paper_id": paper_id, "version": 0, "page_index": 0, "anchor": None, "scale": 1.0,
                    "rotation": 0, "fit_mode": "custom", "status": "unread", "last_opened": None, "updated_at": None}
        data = dict(row)
        data["anchor"] = json.loads(data.pop("anchor_json"))
        return data

    def state(self, paper_id):
        with self.library.mutex, self.library.db.read() as con:
            self._paper(con, paper_id)
            return self._state(con.execute("SELECT * FROM reading_states WHERE paper_id=?", (paper_id,)).fetchone(), paper_id)

    def update_state(self, paper_id, values):
        values = ReadingPatch.model_validate(values).model_dump(exclude_unset=True)
        expected = values.pop("expected_version")
        touch = values.pop("touch", False)
        with self.library.mutex, self.library.db.transaction() as con:
            self._paper(con, paper_id)
            current = self._state(con.execute("SELECT * FROM reading_states WHERE paper_id=?", (paper_id,)).fetchone(), paper_id)
            if current["version"] != expected:
                raise VersionConflict(current)
            if not values and not touch:
                return current
            next_state = {**current, **values}
            if "page_index" in values and values["page_index"] != current["page_index"] and "anchor" not in values:
                next_state["anchor"] = None
            if "page_index" in values or "anchor" in values:
                bounds = self._page(self._geometry(paper_id), next_state["page_index"])
                if next_state["anchor"] is not None:
                    next_state["anchor"] = self._bounded(next_state["anchor"], ([bounds[0], bounds[1]], [bounds[2], bounds[3]]))
            now = timestamp()
            next_state.update(version=current["version"] + 1, updated_at=now)
            if touch:
                next_state["last_opened"] = now
            con.execute("""INSERT INTO reading_states(paper_id,page_index,anchor_json,scale,rotation,fit_mode,status,version,last_opened,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(paper_id) DO UPDATE SET page_index=excluded.page_index,
              anchor_json=excluded.anchor_json,scale=excluded.scale,rotation=excluded.rotation,fit_mode=excluded.fit_mode,
              status=excluded.status,version=excluded.version,last_opened=excluded.last_opened,updated_at=excluded.updated_at""",
              (paper_id, next_state["page_index"], encode(next_state["anchor"]), next_state["scale"], next_state["rotation"],
               next_state["fit_mode"], next_state["status"], next_state["version"], next_state["last_opened"], now))
            return next_state

    def _validate_locations(self, paper_id, kind, locations):
        if kind == "bookmark" and len(locations) != 1:
            raise ValueError("书签必须有且只有一个页面位置")
        if kind == "highlight" and (not locations or any(location.get("bbox") is None for location in locations)):
            raise ValueError("高亮的每个位置必须具有定位框")
        if not locations:
            return []
        pages = self._geometry(paper_id)
        result = []
        for location in locations:
            bounds = self._page(pages, location["page_index"])
            box = location.get("bbox")
            if box is not None:
                box = self._bounded(box, ([bounds[0], bounds[1], bounds[0], bounds[1]], [bounds[2], bounds[3], bounds[2], bounds[3]]))
                if box[2] <= box[0] or box[3] <= box[1]:
                    raise ValueError("定位框必须具有正宽度和正高度")
            result.append({"page_index": location["page_index"], "bbox": box})
        return result

    @staticmethod
    def _annotation(row):
        value = dict(row)
        value["tags"] = json.loads(value.pop("tags_json"))
        value["locations"] = json.loads(value.pop("locations_json"))
        value["deleted"] = bool(value["deleted"])
        automatic = json.loads(value.pop("paper_auto"))
        override = json.loads(value.pop("paper_override"))
        value["paper_title"] = {**automatic, **override}.get("title") or value["paper_filename"]
        return value

    @staticmethod
    def _base_query():
        return ("SELECT a.*,p.filename paper_filename,p.sha256 pdf_sha256,p.auto_json paper_auto,p.overrides_json paper_override "
                "FROM annotations a JOIN papers p ON p.id=a.paper_id ")

    def _get(self, con, annotation_id, allow_deleted=False):
        row = con.execute(self._base_query() + "WHERE a.id=? AND p.removed=0" + ("" if allow_deleted else " AND a.deleted=0"), (annotation_id,)).fetchone()
        if not row:
            raise KeyError("笔记不存在或已删除")
        return self._annotation(row)

    def annotation(self, annotation_id, allow_deleted=False):
        with self.library.mutex, self.library.db.read() as con:
            return self._get(con, annotation_id, allow_deleted)

    def annotations(self, q="", paper_id=None, kind=None, tag=None, offset=0, limit=30, deleted=False):
        if len(q) > 1000 or not 0 <= offset or not 1 <= limit <= 10000:
            raise ValueError("笔记查询范围无效")
        if kind is not None and kind not in ("bookmark", "highlight", "note"):
            raise ValueError("笔记类型无效")
        where, args = ["p.removed=0", "a.deleted=?"], [int(deleted)]
        for field, value in (("a.paper_id", paper_id), ("a.kind", kind)):
            if value:
                where.append(field + "=?")
                args.append(value)
        if tag:
            where.append("EXISTS(SELECT 1 FROM json_each(a.tags_json) WHERE value=?)")
            args.append(tag)
        expression = search.compile_query(q) if q else ""
        if q and not expression:
            return {"items": [], "total": 0}
        if expression:
            if deleted:
                # Deleted notes deliberately have no searchable FTS entries.
                raise ValueError("请恢复笔记后进行全文搜索")
            where.append("a.id IN(SELECT entity_id FROM search_entries WHERE search_entries MATCH ? AND kind='notes')")
            args.append(expression)
        conditions = " WHERE " + " AND ".join(where)
        with self.library.mutex, self.library.db.read() as con:
            if paper_id:
                self._paper(con, paper_id)
            total = con.execute("SELECT count(*) FROM annotations a JOIN papers p ON p.id=a.paper_id" + conditions, args).fetchone()[0]
            rows = con.execute(self._base_query() + conditions + " ORDER BY a.updated_at DESC,a.id LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
            return {"items": [self._annotation(row) for row in rows], "total": total}

    @staticmethod
    def _index(con, item):
        con.execute("DELETE FROM search_entries WHERE entity_id=? AND kind='notes'", (item["id"],))
        if item["deleted"]:
            return
        title = item["title"] or item["quote"][:80] or item["body"][:80] or {"bookmark": "页书签", "highlight": "文本高亮", "note": "笔记"}[item["kind"]]
        text = "\n".join([item["paper_title"], item["title"], item["quote"], item["body"], " ".join(item["tags"])])
        search.index_entry(con, item["id"], "notes", item["paper_id"], title, text, item["locations"][0] if item["locations"] else None)

    def reindex(self, con, paper_id):
        for row in con.execute(self._base_query() + "WHERE a.paper_id=? AND a.deleted=0 AND p.removed=0", (paper_id,)).fetchall():
            self._index(con, self._annotation(row))

    def create(self, paper_id, values):
        values = AnnotationCreate.model_validate(values).model_dump()
        with self.library.mutex, self.library.db.transaction() as con:
            self._paper(con, paper_id)
            values["locations"] = self._validate_locations(paper_id, values["kind"], values["locations"])
            annotation_id, now = uid(), timestamp()
            con.execute("""INSERT INTO annotations(id,paper_id,kind,title,quote,body,color,tags_json,locations_json,version,deleted,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,1,0,?,?)""", (annotation_id, paper_id, values["kind"], values["title"], values["quote"], values["body"], values["color"], encode(values["tags"]), encode(values["locations"]), now, now))
            item = self._get(con, annotation_id)
            self._index(con, item)
            return item

    def update(self, annotation_id, values):
        values = AnnotationPatch.model_validate(values).model_dump(exclude_unset=True)
        expected = values.pop("expected_version")
        with self.library.mutex, self.library.db.transaction() as con:
            current = self._get(con, annotation_id, True)
            if current["version"] != expected:
                raise VersionConflict(current)
            if current["deleted"]:
                raise KeyError("笔记已删除，请先恢复")
            if not values:
                return current
            next_value = {**current, **values}
            next_value["locations"] = self._validate_locations(current["paper_id"], current["kind"], next_value["locations"])
            con.execute("""UPDATE annotations SET title=?,quote=?,body=?,color=?,tags_json=?,locations_json=?,version=version+1,updated_at=? WHERE id=? AND version=?""",
                        (next_value["title"], next_value["quote"], next_value["body"], next_value["color"], encode(next_value["tags"]), encode(next_value["locations"]), timestamp(), annotation_id, expected))
            item = self._get(con, annotation_id)
            self._index(con, item)
            return item

    def set_deleted(self, annotation_id, expected, deleted):
        if type(expected) is not int or expected < 0:
            raise ValueError("expected_version必须为非负整数")
        with self.library.mutex, self.library.db.transaction() as con:
            current = self._get(con, annotation_id, True)
            if current["version"] != expected:
                raise VersionConflict(current)
            if current["deleted"] == deleted:
                return current
            con.execute("UPDATE annotations SET deleted=?,version=version+1,updated_at=? WHERE id=? AND version=?",
                        (int(deleted), timestamp(), annotation_id, expected))
            item = self._get(con, annotation_id, True)
            self._index(con, item)
            return item
