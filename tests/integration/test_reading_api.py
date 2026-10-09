from fastapi.testclient import TestClient

from papervault.api import create_app
from urllib.parse import quote


def test_authenticated_reading_annotation_search_export_and_version_conflicts(tmp_path, pdf_file):
    app = create_app("secret", tmp_path / "config", tmp_path / "library", start_workers=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/annotations").status_code == 401
        client.headers["Authorization"] = "Bearer secret"
        paper = client.post("/api/v1/papers/import-paths", json={"paths": [str(pdf_file)]}).json()["items"][0]
        base = f"/api/v1/papers/{paper['id']}"
        assert client.get("/api/v1/library").json()["id"]
        assert client.get("/api/v1/papers", params={"opened": "true"}).json()["total"] == 0
        assert client.get("/api/v1/papers", params={"opened": "false"}).json()["total"] == 1
        assert client.get(base + "/reading-state").json()["version"] == 0
        assert client.patch(base + "/reading-state", json={"scale": 1.5}).status_code == 422
        first = client.patch(base + "/reading-state", json={"expected_version": 0, "status": "reading", "touch": True})
        assert first.status_code == 200, first.text
        conflict = client.patch(base + "/reading-state", json={"expected_version": 0, "status": "read"})
        assert conflict.status_code == 409 and conflict.json()["current"]["version"] == 1
        assert client.get("/api/v1/papers", params={"reading_status": "reading", "sort": "last_opened"}).json()["total"] == 1
        assert client.get("/api/v1/papers", params={"opened": "true", "sort": "last_opened"}).json()["total"] == 1
        invalid = client.post(base + "/annotations", json={"kind": "highlight", "locations": [{"page_index": 0}]})
        assert invalid.status_code == 400
        response = client.post(base + "/annotations", json={"kind": "highlight", "body": "可追溯中文笔记", "quote": "Original quotation",
            "locations": [{"page_index": 0, "bbox": [100, 500, 200, 600]}]})
        assert response.status_code == 200, response.text
        note = response.json()
        assert client.get("/api/v1/annotations", params={"q": "中文"}).json()["total"] == 1
        assert client.get("/api/v1/search", params={"q": "可追溯"}).json()["notes"][0]["id"] == note["id"]
        assert client.patch(f"/api/v1/annotations/{note['id']}", json={"expected_version": 0, "body": "stale"}).status_code == 409
        export = client.post("/api/v1/annotations/export", json={"ids": [note["id"]], "format": "markdown"})
        assert export.status_code == 200 and "可追溯中文笔记" in export.text
        assert "attachment;" in export.headers["content-disposition"]
        deleted = client.delete(f"/api/v1/annotations/{note['id']}", params={"expected_version": 1})
        assert deleted.status_code == 200 and deleted.json()["deleted"]
        assert client.get("/api/v1/annotations").json()["total"] == 0
        restored = client.post(f"/api/v1/annotations/{note['id']}/restore", json={"expected_version": 2})
        assert restored.status_code == 200 and restored.json()["version"] == 3
        assert client.delete(base).status_code == 200
        assert client.get("/api/v1/annotations").json()["total"] == 0
        assert client.get(f"/api/v1/annotations/{note['id']}").status_code == 404


def scope_header(info):
    return {"X-PaperVault-Library": quote(f"{info['id']}:{info['path']}", safe="-_.!~*'()")}


def test_encoded_library_scope_rejects_late_write_to_restored_clone(tmp_path, pdf_file):
    app = create_app("secret", tmp_path / "config", tmp_path / "中文源库", start_workers=False)
    with TestClient(app, headers={"Authorization": "Bearer secret"}) as client:
        original = client.get("/api/v1/library").json()
        scope = scope_header(original)
        assert "%" in scope["X-PaperVault-Library"]
        paper = client.post("/api/v1/papers/import-paths", headers=scope, json={"paths": [str(pdf_file)]}).json()["items"][0]
        endpoint = f"/api/v1/papers/{paper['id']}/reading-state"
        assert client.patch(endpoint, headers=scope, json={"expected_version": 0, "status": "reading"}).status_code == 200
        archive = client.post("/api/v1/backups", headers=scope, json={}).json()["path"]
        restored = client.post("/api/v1/backups/restore", headers=scope, json={"path": archive, "destination": str(tmp_path / "中文恢复副本")})
        assert restored.status_code == 200, restored.text
        current = restored.json()
        assert current["id"] == original["id"] and current["path"] != original["path"]
        assert client.get(endpoint).json()["version"] == 1
        late = client.patch(endpoint, headers=scope, json={"expected_version": 1, "status": "read"})
        assert late.status_code == 409 and late.json()["code"] == "library_switched"
        assert "current" not in late.json()
        assert client.get(endpoint).json()["status"] == "reading"
        # Old clients without the optional header remain compatible.
        assert client.patch(endpoint, json={"expected_version": 1, "status": "read"}).status_code == 200
        assert client.patch(endpoint, headers=scope_header(current), json={"expected_version": 2, "touch": True}).status_code == 200
        preflight = client.options(endpoint, headers={"Origin": "http://tauri.localhost", "Access-Control-Request-Method": "PATCH", "Access-Control-Request-Headers": "X-PaperVault-Library"})
        assert preflight.status_code == 200 and "x-papervault-library" in preflight.headers["access-control-allow-headers"].lower()
        # Explicit switching is allowed even with the previous scope attached.
        assert client.post("/api/v1/library/open", headers=scope, json={"path": original["path"], "create": False}).status_code == 200


def test_switch_waits_until_scoped_mutation_handler_finishes(tmp_path, pdf_file, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from papervault.library import Library
    app = create_app("secret", tmp_path / "config", tmp_path / "first", start_workers=False)
    with TestClient(app, headers={"Authorization": "Bearer secret"}) as client:
        original = client.get("/api/v1/library").json()
        scope = scope_header(original)
        paper = client.post("/api/v1/papers/import-paths", json={"paths": [str(pdf_file)]}).json()["items"][0]
        services = app.state.services
        entered, release, switched = threading.Event(), threading.Event(), threading.Event()
        save = services.library.update_reading_state
        open_library = services.open
        def slow_save(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test gate timed out")
            return save(*args, **kwargs)
        def observe_switch(*args, **kwargs):
            switched.set()
            return open_library(*args, **kwargs)
        monkeypatch.setattr(services.library, "update_reading_state", slow_save)
        monkeypatch.setattr(services, "open", observe_switch)
        with ThreadPoolExecutor(max_workers=2) as pool:
            saving = pool.submit(client.patch, f"/api/v1/papers/{paper['id']}/reading-state", headers=scope,
                                 json={"expected_version": 0, "status": "read"})
            assert entered.wait(3)
            switching = pool.submit(client.post, "/api/v1/library/open", headers=scope, json={"path": str(tmp_path / "second")})
            try:
                assert not switched.wait(0.2), "Library changed between scope validation and write completion"
            finally:
                release.set()
            assert saving.result(timeout=5).status_code == 200
            assert switching.result(timeout=5).status_code == 200
        old_library = Library(tmp_path / "first", create=False)
        try:
            assert old_library.reading_state(paper["id"])["status"] == "read"
            assert app.state.services.library.info()["paper_count"] == 0
        finally:
            old_library.close()
