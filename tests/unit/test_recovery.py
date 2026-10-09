import json

import pytest

from conftest import publish_fixture
from papervault.files import uid
from papervault.library import Library


def test_worker_crash_is_interrupted_on_restart(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    with library.db.transaction() as con:
        con.execute("UPDATE jobs SET status='running',phase='parsing'")
    path = library.root
    library.close()
    reopened = Library(path)
    try:
        assert reopened.jobs()["items"][0]["status"] == "interrupted"
        assert reopened.paper(paper["id"])["status"] == "interrupted"
        assert reopened.queue(paper["id"]) != reopened.jobs()["items"][-1]["id"]
    finally:
        reopened.close()


def test_failed_publication_keeps_previous_revision(library, pdf_file, monkeypatch):
    paper, _ = library.import_file(pdf_file)
    old = publish_fixture(library, paper["id"])
    old_revision = library.paper(paper["id"])["active_revision"]
    library.queue(paper["id"])
    with library.db.transaction() as con:
        job = con.execute("SELECT * FROM jobs WHERE status='queued'").fetchone()
        con.execute("UPDATE jobs SET status='running' WHERE id=?", (job["id"],))
    staging = library.root / ".staging" / uid()
    staging.mkdir()
    (staging / "fulltext.md").write_text("new revision")
    def fail_index(*_):
        raise OSError("injected disk write failure")
    monkeypatch.setattr(library, "_reindex", fail_index)
    with pytest.raises(OSError, match="injected"):
        library.publish(job["id"], job["attempt_token"], staging,
                        {"metadata": {"title": "must not appear"}, "resources": [], "blocks": []})
    assert library.paper(paper["id"])["active_revision"] == old_revision
    assert library.resource(old["id"])["caption"] == old["caption"]
    assert library.search("Cache")["figures"]


def test_missing_parser_output_does_not_commit(library, pdf_file):
    paper, _ = library.import_file(pdf_file)
    with library.db.transaction() as con:
        job = con.execute("SELECT * FROM jobs").fetchone()
        con.execute("UPDATE jobs SET status='running'")
    staging = library.root / ".staging" / uid()
    staging.mkdir()
    with pytest.raises(ValueError, match="缺失"):
        library.publish(job["id"], job["attempt_token"], staging,
                        {"resources": [{"kind": "figure", "files": {"png": "missing.png"}}]})
    assert library.paper(paper["id"])["active_revision"] is None


def test_backup_corruption_does_not_replace_destination(library, pdf_file, tmp_path):
    import zipfile
    from papervault.backup import create_backup, restore_backup
    library.import_file(pdf_file)
    archive = create_backup(library)
    corrupt = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(corrupt, "w") as target:
        for item in source.infolist():
            data = source.read(item)
            if item.filename == "manifest.json":
                manifest = json.loads(data)
                manifest["files"]["database/papervault.db"] = "0" * 64
                data = json.dumps(manifest).encode()
            target.writestr(item, data)
    destination = tmp_path / "restored"
    with pytest.raises(ValueError, match="校验"):
        restore_backup(corrupt, destination)
    assert not destination.exists()
    assert library.info()["paper_count"] == 1


def test_explicit_backup_zip_filename_is_a_file(library, pdf_file, tmp_path):
    from papervault.backup import create_backup, restore_backup
    library.import_file(pdf_file)
    target = tmp_path / "用户指定的备份.zip"
    assert create_backup(library, target) == target
    assert target.is_file()
    assert create_backup(library, target) == target
    assert restore_backup(target, tmp_path / "恢复目录").is_dir()


def test_backup_detects_a_missing_live_resource(library, pdf_file):
    from papervault.backup import create_backup
    paper, _ = library.import_file(pdf_file)
    resource = publish_fixture(library, paper["id"])
    library.resource_file(resource["id"], "png").unlink()
    with pytest.raises(ValueError, match="缺少资源"):
        create_backup(library)
    assert not list((library.root / "backups").glob("*.zip"))
