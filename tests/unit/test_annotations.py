import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from conftest import publish_fixture
from papervault.annotation_export import export_annotations
from papervault.backup import create_backup, restore_backup
from papervault.exporting import export_assets
from papervault.library import Library
from papervault.reading import VersionConflict


def test_annotation_types_locations_and_cross_page_highlight(library):
    paper, _ = library.import_file(Path(__file__).parents[1] / "fixtures/geometry.pdf")
    note = library.create_annotation(paper["id"], {"kind": "note", "body": "论文级笔记"})
    bookmark = library.create_annotation(paper["id"], {"kind": "bookmark", "locations": [{"page_index": 2}]})
    highlight = library.create_annotation(paper["id"], {"kind": "highlight", "quote": "原文摘录", "body": "我的解释",
        "tags": [" 重点 ", "重点"], "locations": [{"page_index": 0, "bbox": [101, 131, 179, 189]}, {"page_index": 3, "bbox": [101, 131, 179, 189]}]})
    assert note["locations"] == [] and note["color"] == "amber"
    assert bookmark["locations"] == [{"page_index": 2, "bbox": None}]
    assert len(highlight["locations"]) == 2 and highlight["tags"] == ["重点"]
    assert library.paper(paper["id"])["annotation_count"] == 3
    assert library.annotations(q="我的解释", tag="重点")["total"] == 1
    hit = library.search("我的解释")["notes"][0]
    assert hit["id"] == highlight["id"] and hit["annotation_kind"] == "highlight"
    assert hit["locations"] == highlight["locations"]


@pytest.mark.parametrize("values", [{"kind": "bookmark"}, {"kind": "highlight"},
    {"kind": "bookmark", "locations": [{"page_index": 0}, {"page_index": 0}]},
    {"kind": "highlight", "locations": [{"page_index": 0}]},
    {"kind": "note", "locations": [{"page_index": 1}]},
    {"kind": "note", "locations": [{"page_index": 0, "bbox": [100, 100, 99, 110]}]},
    {"kind": "note", "locations": [{"page_index": 0, "bbox": [-1, 0, 10, 10]}]},
    {"kind": "note", "locations": [{"page_index": 0, "bbox": [0, 0, float('nan'), 10]}]},
    {"kind": "note", "title": "x" * 501}, {"kind": "note", "body": "x" * 100001},
    {"kind": "note", "quote": "x" * 20001}, {"kind": "note", "tags": [" "]},
    {"kind": "note", "tags": [str(i) for i in range(51)]}, {"kind": "note", "color": "red"},
    {"kind": "note", "locations": [{"page_index": 0}] * 513}])
def test_invalid_annotation_is_atomic(library, pdf_file, values):
    paper, _ = library.import_file(pdf_file)
    with pytest.raises(ValueError):
        library.create_annotation(paper["id"], values)
    assert library.annotations()["total"] == 0
    assert library.search("note")["notes"] == []


def test_annotation_search_survives_reparse_metadata_edits_and_paper_restore(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    old = publish_fixture(library, paper["id"])
    note = library.create_annotation(paper["id"], {"kind": "note", "body": "独立知识记录", "locations": old["locations"]})
    library.update_paper(paper["id"], {"title": "人工标题"})
    assert library.search("独立知识")["notes"][0]["id"] == note["id"]
    library.queue(paper["id"])
    publish_fixture(library, paper["id"], bbox=[5, 5, 25, 25])
    assert library.annotation(note["id"])["locations"] == note["locations"]
    assert library.annotation(note["id"])["version"] == 1
    assert library.search("独立知识")["notes"]
    library.remove(paper["id"])
    assert library.annotations()["total"] == 0 and library.search("独立知识")["notes"] == []
    with pytest.raises(KeyError):
        library.annotation(note["id"])
    library.import_file(pdf_file)
    assert library.search("独立知识")["notes"][0]["id"] == note["id"]
    library.remove(paper["id"], delete_files=True)
    with library.db.read() as con:
        assert con.execute("SELECT count(*) FROM annotations").fetchone()[0] == 0


def test_soft_delete_undo_and_stale_editor_conflict(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    note = library.create_annotation(paper["id"], {"kind": "note", "body": "可撤销标记"})
    edited = library.update_annotation(note["id"], {"expected_version": 1, "body": "已改标记"})
    with pytest.raises(VersionConflict) as error:
        library.update_annotation(note["id"], {"expected_version": 1, "body": "过期覆盖"})
    assert error.value.current["body"] == "已改标记"
    deleted = library.delete_annotation(note["id"], edited["version"])
    assert deleted["deleted"] and deleted["version"] == 3
    assert library.search("标记")["notes"] == []
    assert library.annotations(deleted=True)["total"] == 1
    with pytest.raises(VersionConflict):
        library.restore_annotation(note["id"], 2)
    restored = library.restore_annotation(note["id"], 3)
    assert restored["version"] == 4 and not restored["deleted"]
    assert library.search("已改标记")["notes"]


def test_concurrent_annotation_writes_accept_only_one_version(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    note = library.create_annotation(paper["id"], {"kind": "note", "body": "original"})
    def update(body):
        try:
            return library.update_annotation(note["id"], {"expected_version": 1, "body": body})
        except VersionConflict as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["A", "B"]))
    assert sum(isinstance(value, VersionConflict) for value in results) == 1
    assert library.annotation(note["id"])["version"] == 2


def test_failed_annotation_index_write_rolls_back_body_and_version(library, pdf_file, monkeypatch):
    paper, _ = library.import_file(pdf_file)
    note = library.create_annotation(paper["id"], {"kind": "note", "body": "保留原始"})
    def fail(*_):
        raise OSError("injected index failure")
    monkeypatch.setattr(library.reading, "_index", fail)
    with pytest.raises(OSError):
        library.update_annotation(note["id"], {"expected_version": 1, "body": "不应发布"})
    assert library.annotation(note["id"])["body"] == "保留原始"
    assert library.annotation(note["id"])["version"] == 1
    assert library.search("保留原始")["notes"]


def test_backup_and_portable_exports_include_annotations_and_state(library, pdf_file, tmp_path):
    paper, _ = library.import_file(pdf_file)
    note = library.create_annotation(paper["id"], {"kind": "note", "quote": "<script>quoted</script>", "body": "用户笔记", "locations": [{"page_index": 0}]})
    state = library.update_reading_state(paper["id"], {"expected_version": 0, "status": "read", "touch": True})
    source_id = library.info()["id"]
    backup = create_backup(library)
    restored = Library(restore_backup(backup, tmp_path / "restored"), create=False)
    try:
        assert restored.info()["id"] == source_id
        assert restored.annotation(note["id"])["body"] == "用户笔记"
        assert restored.reading_state(paper["id"]) == state
    finally:
        restored.close()
    exported = json.loads(export_annotations(library, [note["id"]], format_name="json").read_text(encoding="utf-8"))
    assert exported["annotations"][0]["pdf_sha256"] == paper["sha256"]
    markdown = export_annotations(library, [], paper["id"], "markdown").read_text(encoding="utf-8")
    assert "用户笔记" in markdown and "第 1 页" in markdown and "<script>" not in markdown
    archive = export_assets(library, [paper["id"]], [], dpi=None)
    with zipfile.ZipFile(archive) as contents:
        prefix = f"papers/{paper['id']}/"
        assert json.loads(contents.read(prefix + "annotations.json"))[0]["id"] == note["id"]
        assert json.loads(contents.read(prefix + "reading-state.json"))["status"] == "read"
        assert "original.pdf#page=1" in contents.read(prefix + "notes.md").decode()


def test_annotation_filters_pagination_and_duplicate_ids_in_export(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    first = library.create_annotation(paper["id"], {"kind": "note", "body": "深度 KV Cache", "tags": ["分析"]})
    second = library.create_annotation(paper["id"], {"kind": "bookmark", "title": "书签", "locations": [{"page_index": 0}]})
    assert library.annotations(q="深度 KV", tag="分析", kind="note")["total"] == 1
    assert library.annotations(kind="bookmark")["items"][0]["id"] == second["id"]
    page_one = library.annotations(limit=1)
    page_two = library.annotations(limit=1, offset=1)
    assert page_one["total"] == page_two["total"] == 2
    assert page_one["items"][0]["id"] != page_two["items"][0]["id"]
    exported = json.loads(export_annotations(library, [first["id"], first["id"]], format_name="json").read_text(encoding="utf-8"))
    assert len(exported["annotations"]) == 1
    library.delete_annotation(first["id"], 1)
    with pytest.raises(KeyError):
        export_annotations(library, [first["id"]], format_name="markdown")
    assert library.annotations(q="深度")["total"] == 0


def test_annotation_atomic_backup_captures_deleted_history(library, pdf_file, tmp_path):
    paper, _ = library.import_file(pdf_file)
    note = library.create_annotation(paper["id"], {"kind": "note", "body": "可恢复的删除记录"})
    deleted = library.delete_annotation(note["id"], 1)
    archive = create_backup(library)
    restored = Library(restore_backup(archive, tmp_path / "restore-deleted"), create=False)
    try:
        assert restored.annotations()["total"] == 0
        assert restored.annotations(deleted=True)["items"][0]["body"] == "可恢复的删除记录"
        restored.restore_annotation(note["id"], deleted["version"])
        assert restored.search("可恢复")["notes"]
    finally:
        restored.close()
