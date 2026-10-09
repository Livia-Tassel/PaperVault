import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event

from papervault.database import Database
from papervault.library import Library
from papervault.reading import VersionConflict


def test_reading_defaults_persist_and_never_reindex(library, pdf_file, monkeypatch):
    paper, _ = library.import_file(pdf_file)
    assert library.reading_state(paper["id"])["version"] == 0
    with library.db.read() as con:
        history_before = con.execute("SELECT count(*) FROM manual_revisions").fetchone()[0]
        automatic = con.execute("SELECT auto_json,overrides_json FROM papers").fetchone()
        fts_before = [tuple(row) for row in con.execute("SELECT * FROM search_entries")]
    monkeypatch.setattr(library, "_reindex", lambda *_: pytest.fail("Reading saves must not reindex"))
    result = library.update_reading_state(paper["id"], {"expected_version": 0, "page_index": 0,
        "anchor": [120, 300], "scale": 1.5, "rotation": 90, "fit_mode": "width", "status": "reading", "touch": True})
    assert result["version"] == 1 and result["last_opened"]
    assert library.papers(reading_status="reading")["total"] == 1
    assert library.paper(paper["id"])["reading_status"] == "reading"
    with library.db.read() as con:
        assert tuple(con.execute("SELECT auto_json,overrides_json FROM papers").fetchone()) == tuple(automatic)
        assert con.execute("SELECT count(*) FROM manual_revisions").fetchone()[0] == history_before
        assert [tuple(row) for row in con.execute("SELECT * FROM search_entries")] == fts_before
    identity, root = library.info()["id"], library.root
    library.close()
    reopened = Library(root)
    try:
        assert reopened.info()["id"] == identity
        assert reopened.reading_state(paper["id"]) == result
    finally:
        reopened.close()


def test_reading_versions_serialize_concurrent_writes(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    def save(scale):
        try:
            return library.update_reading_state(paper["id"], {"expected_version": 0, "scale": scale})
        except VersionConflict as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [1.5, 2]))
    assert sum(isinstance(value, dict) for value in results) == 1
    conflict = next(value for value in results if isinstance(value, VersionConflict))
    assert conflict.current["version"] == 1
    assert library.reading_state(paper["id"])["version"] == 1


@pytest.mark.parametrize("values", [{"scale": float("nan")}, {"scale": float("inf")}, {"scale": 0},
    {"scale": 9}, {"rotation": 45}, {"rotation": True}, {"page_index": -1}, {"page_index": 1},
    {"anchor": [999999, 0]}, {"anchor": [0, float("inf")]}, {"status": None}, {"fit_mode": "automatic"}])
def test_invalid_reading_values_do_not_create_state(library, pdf_file, values):
    paper, _ = library.import_file(pdf_file)
    with pytest.raises(ValueError):
        library.update_reading_state(paper["id"], {"expected_version": 0, **values})
    assert library.reading_state(paper["id"])["version"] == 0


def test_page_change_clears_anchor_and_validates_crop_origin(library):
    fixture = Path(__file__).parents[1] / "fixtures/geometry.pdf"
    paper, _ = library.import_file(fixture)
    first = library.update_reading_state(paper["id"], {"expected_version": 0, "anchor": [101, 131]})
    second = library.update_reading_state(paper["id"], {"expected_version": first["version"], "page_index": 3})
    assert second["anchor"] is None
    with pytest.raises(ValueError, match="坐标"):
        library.update_reading_state(paper["id"], {"expected_version": 2, "anchor": [49, 100]})
    assert library.reading_state(paper["id"])["version"] == 2


def create_v1_library(root, pdf_file):
    from papervault import search
    database_path = root / "database/papervault.db"
    database_path.parent.mkdir(parents=True)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[2] / "backend/papervault/migrations"))
    engine = create_engine("sqlite:///" + database_path.as_posix())
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
    engine.dispose()
    import sqlite3
    with sqlite3.connect(database_path) as con:
        con.execute("INSERT INTO papers(id,sha256,filename,overrides_json,status,created_at) VALUES(?,?,?,?,?,?)",
                    ("legacy-paper", "legacy-hash", pdf_file.name, json.dumps({"title": "旧论文", "notes": "旧版用户备注"}), "completed", "2026-01-01"))
        search.index_entry(con, "legacy-paper", "paper", "legacy-paper", "旧论文", "旧版用户备注")
    destination = root / "papers/legacy-paper"
    destination.mkdir(parents=True)
    shutil.copyfile(pdf_file, destination / "original.pdf")
    return database_path


def test_v1_upgrade_backs_up_and_preserves_legacy_notes(tmp_path, pdf_file):
    root = tmp_path / "old-library"
    path = create_v1_library(root, pdf_file)
    library = Library(root, create=False)
    try:
        assert library.paper("legacy-paper")["notes"] == "旧版用户备注"
        assert library.annotations()["total"] == 0
        assert library.reading_state("legacy-paper")["version"] == 0
        assert library.search("旧版")["papers"]
        backups = list((path.parent / "migration-backups").glob("before-upgrade-*.db"))
        assert len(backups) == 1
        import sqlite3
        with sqlite3.connect(backups[0]) as con:
            assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0001"
        with library.db.read() as con:
            assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"
    finally:
        library.close()


def test_failed_migration_rolls_back_all_ddl_and_can_retry(tmp_path, pdf_file):
    from sqlalchemy.engine import Engine
    path = create_v1_library(tmp_path / "old", pdf_file)
    def fail(connection, cursor, statement, parameters, context, executemany):
        if "CREATE TABLE annotations" in statement:
            raise RuntimeError("Injected migration failure")
    event.listen(Engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="Injected"):
            Database(path)
    finally:
        event.remove(Engine, "before_cursor_execute", fail)
    import sqlite3
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0001"
        assert not con.execute("SELECT 1 FROM sqlite_master WHERE name='library_meta'").fetchone()
        assert not con.execute("SELECT 1 FROM sqlite_master WHERE name='reading_states'").fetchone()
    upgraded = Database(path)
    with upgraded.read() as con:
        assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"


def test_reading_last_opened_order_and_hard_delete(library, pdf_file, tmp_path):
    from reportlab.pdfgen import canvas
    second_pdf = tmp_path / "second.pdf"
    writer = canvas.Canvas(str(second_pdf))
    writer.drawString(70, 700, "Different content")
    writer.save()
    first, _ = library.import_file(pdf_file)
    second, _ = library.import_file(second_pdf)
    assert library.papers(reading_status="unread")["total"] == 2
    library.update_reading_state(first["id"], {"expected_version": 0, "status": "read", "touch": True})
    assert library.papers(sort="last_opened")["items"][0]["id"] == first["id"]
    library.update_reading_state(second["id"], {"expected_version": 0, "status": "reading", "touch": True})
    assert library.papers(sort="last_opened")["items"][0]["id"] == second["id"]
    assert library.papers(reading_status="read")["total"] == 1
    library.remove(first["id"])
    with pytest.raises(KeyError):
        library.update_reading_state(first["id"], {"expected_version": 1, "touch": True})
    library.import_file(pdf_file)
    assert library.reading_state(first["id"])["status"] == "read"
    library.remove(first["id"], delete_files=True)
    with library.db.read() as con:
        assert con.execute("SELECT count(*) FROM reading_states WHERE paper_id=?", (first["id"],)).fetchone()[0] == 0


def test_opening_corrupt_pdf_can_record_history_but_cannot_save_false_position(library):
    paper, _ = library.import_file(Path(__file__).parents[1] / "fixtures/corrupt.pdf")
    state = library.update_reading_state(paper["id"], {"expected_version": 0, "touch": True})
    assert state["last_opened"] and state["status"] == "unread"
    with pytest.raises(ValueError, match="无法读取"):
        library.update_reading_state(paper["id"], {"expected_version": 1, "page_index": 0, "anchor": [50, 50]})
    assert library.reading_state(paper["id"])["version"] == 1


def test_v1_backup_restores_then_migrates_without_inventing_reading_data(tmp_path, pdf_file):
    import zipfile
    from papervault.backup import restore_backup
    from papervault.files import atomic_json, manifest
    source = tmp_path / "v1-snapshot"
    create_v1_library(source, pdf_file)
    atomic_json(source / "manifest.json", {"version": 1, "files": manifest(source)})
    archive_path = tmp_path / "v1-backup.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for file in source.rglob("*"):
            if file.is_file():
                archive.write(file, file.relative_to(source).as_posix())
    destination = restore_backup(archive_path, tmp_path / "restored-v1")
    restored = Library(destination, create=False)
    try:
        assert restored.info()["id"]
        assert restored.paper("legacy-paper")["notes"] == "旧版用户备注"
        assert restored.reading_state("legacy-paper")["version"] == 0
        assert restored.annotations()["total"] == 0
        assert list((destination / "database/migration-backups").glob("before-upgrade-*.db"))
    finally:
        restored.close()


def test_opened_filter_tracks_history_not_reading_status(library, pdf_file):
    first, _ = library.import_file(pdf_file)
    second, _ = library.import_file(Path(__file__).parents[1] / "fixtures/geometry.pdf")
    library.update_reading_state(first["id"], {"expected_version": 0, "status": "reading", "scale": 1.5})
    assert library.papers(opened=True)["total"] == 0
    assert library.papers(opened=False)["total"] == 2
    library.update_reading_state(first["id"], {"expected_version": 1, "touch": True})
    library.update_reading_state(second["id"], {"expected_version": 0, "status": "read", "touch": True})
    library.update_reading_state(second["id"], {"expected_version": 1, "status": "unread"})
    recent = library.papers(opened=True, sort="last_opened")
    assert recent["total"] == 2 and recent["items"][0]["id"] == second["id"]
    assert library.papers(opened=True, reading_status="unread")["items"][0]["id"] == second["id"]
    assert library.papers(opened=False)["total"] == 0
    library.remove(second["id"])
    assert library.papers(opened=True)["total"] == 1
