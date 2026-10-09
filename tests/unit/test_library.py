import csv
import json
import zipfile

import pytest

from conftest import publish_fixture
from papervault.backup import create_backup, restore_backup
from papervault.exporting import export_assets
from papervault.files import safe_path, sha256
from papervault.library import Library


def test_import_deduplicates_preserves_source_and_survives_restart(library, pdf_file):
    original = sha256(pdf_file)
    first, duplicate = library.import_file(pdf_file)
    second, duplicate2 = library.import_file(pdf_file)
    assert not duplicate and duplicate2
    assert first["id"] == second["id"]
    assert sha256(library.pdf(first["id"])) == original == sha256(pdf_file)
    root = library.root
    library.close()
    reopened = Library(root)
    try:
        assert reopened.info()["paper_count"] == 1
    finally:
        reopened.close()


def test_concurrent_library_open_is_rejected(library):
    with pytest.raises(ValueError, match="另一个"):
        Library(library.root)


def test_bad_file_is_not_imported(library, tmp_path):
    invalid = tmp_path / "bad.pdf"
    invalid.write_text("not a PDF")
    with pytest.raises(ValueError):
        library.import_file(invalid)
    assert library.info()["paper_count"] == 0


def test_user_changes_survive_reparse_and_update_indexes(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    resource = publish_fixture(library, paper["id"])
    library.update_paper(paper["id"], {"title": None, "notes": "用户备注", "tags": ["注意力"]})
    library.update_resource(resource["id"], {"caption": "人工图注 Cache架构"})
    library.queue(paper["id"])
    reparsed = publish_fixture(library, paper["id"], caption="new automatic caption")
    assert reparsed["id"] == resource["id"]
    assert reparsed["caption"] == "人工图注 Cache架构"
    assert library.paper(paper["id"])["title"] is None
    assert library.search("Cache架构")["figures"][0]["id"] == resource["id"]
    assert library.search("注意力")["figures"]
    assert not library.search("new automatic")["figures"]


def test_uncertain_rematch_preserves_edited_resource(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    old = publish_fixture(library, paper["id"])
    library.update_resource(old["id"], {"caption": "keep manual"})
    library.queue(paper["id"])
    publish_fixture(library, paper["id"], bbox=[5, 5, 25, 25])
    assert library.resource(old["id"])["caption"] == "keep manual"
    assert library.resource(old["id"])["needs_review"]
    assert library.resources()["total"] == 2


def test_table_edit_changes_csv_html_and_search(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    table = publish_fixture(library, paper["id"], table=True)
    library.update_resource(table["id"], {"table": {"rows": [["TTFT", "中文"], ["3.4e-5", "<script>"]], "header_rows": 1}})
    with library.resource_file(table["id"], "csv").open(encoding="utf-8-sig", newline="") as file:
        assert list(csv.reader(file))[1] == ["3.4e-5", "<script>"]
    assert "&lt;script&gt;" in library.resource_file(table["id"], "html").read_text(encoding="utf-8")
    assert library.search("中文")["tables"]


def test_cancelled_attempt_cannot_publish(library, pdf_file):
    from papervault.files import uid
    paper, _ = library.import_file(pdf_file)
    with library.db.transaction() as con:
        job = con.execute("SELECT * FROM jobs").fetchone()
        con.execute("UPDATE jobs SET status='cancel_requested' WHERE id=?", (job["id"],))
    staging = library.root / ".staging" / uid()
    staging.mkdir()
    assert not library.publish(job["id"], job["attempt_token"], staging, {})
    assert library.paper(paper["id"])["active_revision"] is None


def test_backup_restore_preserves_data_and_rejects_overwrite(library, pdf_file, tmp_path):
    paper, _ = library.import_file(pdf_file)
    table = publish_fixture(library, paper["id"], table=True)
    library.update_resource(table["id"], {"notes": "保留我"})
    backup = create_backup(library)
    destination = restore_backup(backup, tmp_path / "恢复库")
    restored = Library(destination, create=False)
    try:
        assert restored.resource(table["id"])["notes"] == "保留我"
        assert restored.search("TTFT")["tables"]
        assert sha256(restored.pdf(paper["id"])) == sha256(pdf_file)
    finally:
        restored.close()
    with pytest.raises(ValueError, match="空目录"):
        restore_backup(backup, destination)


def test_restore_rejects_zip_traversal(tmp_path):
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as file:
        file.writestr("../escaped.txt", "bad")
    with pytest.raises(ValueError):
        restore_backup(archive, tmp_path / "destination")
    assert not (tmp_path / "escaped.txt").exists()


@pytest.mark.parametrize("path", ["../outside", "C:/data", "/absolute", "a\\b", "file:stream", "folder./x"])
def test_paths_are_confined(tmp_path, path):
    with pytest.raises(ValueError):
        safe_path(tmp_path, path)


def test_remove_retains_source_and_updates_search(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    publish_fixture(library, paper["id"])
    library.remove(paper["id"])
    assert library.info()["paper_count"] == 0
    assert not library.search("Cache")["figures"]
    assert pdf_file.exists()
    restored, duplicate = library.import_file(pdf_file)
    assert duplicate and restored["id"] == paper["id"]
    library.remove(paper["id"], delete_files=True)
    assert pdf_file.exists()
    assert not (library.root / "papers" / paper["id"]).exists()


def test_exports_are_portable(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    table = publish_fixture(library, paper["id"], table=True)
    # Avoid testing parser rendering in this storage unit test; real E2E covers DPI exports.
    path = export_assets(library, [paper["id"]], [], "zip", dpi=None)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert f"papers/{paper['id']}/original.pdf" in names
        assert f"papers/{paper['id']}/resources/{table['id']}/table.csv" in names
        metadata = json.loads(archive.read(f"papers/{paper['id']}/resources/{table['id']}/metadata.json"))
        assert metadata["files"]["csv"] == "table.csv"
