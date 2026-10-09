from fastapi.testclient import TestClient

from papervault.api import create_app


def test_authenticated_import_edit_search_restart_and_backup(tmp_path, pdf_file):
    config, path = tmp_path / "config", tmp_path / "library"
    app = create_app("test-token", config, start_workers=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 401
        unauthorized = client.get("/api/v1/health", headers={"Origin": "http://tauri.localhost"})
        assert unauthorized.headers["access-control-allow-origin"] == "http://tauri.localhost"
        client.headers["Authorization"] = "Bearer test-token"
        assert client.get("/api/v1/library").json()["path"] is None
        assert client.post("/api/v1/library/open", json={"path": str(path)}).status_code == 200
        response = client.post("/api/v1/papers/import", files={"files": (pdf_file.name, pdf_file.read_bytes(), "application/pdf")})
        assert response.status_code == 200, response.text
        paper = response.json()["items"][0]
        response = client.patch(f"/api/v1/papers/{paper['id']}", json={"title": "中文深度学习", "favorite": True})
        assert response.status_code == 200, response.text
        assert client.get("/api/v1/search", params={"q": "深度"}).json()["papers"]
        assert client.get(f"/api/v1/papers/{paper['id']}/pdf").content == pdf_file.read_bytes()
        job = client.get("/api/v1/jobs").json()["items"][0]
        assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 200
        assert client.post("/api/v1/backups", json={}).status_code == 200
    with TestClient(create_app("different-token", config, start_workers=False)) as client:
        client.headers["Authorization"] = "Bearer different-token"
        assert client.get("/api/v1/papers").json()["items"][0]["title"] == "中文深度学习"


def test_path_import_reports_errors_and_duplicates(tmp_path, pdf_file):
    app = create_app("token", tmp_path / "config", tmp_path / "library", start_workers=False)
    with TestClient(app, headers={"Authorization": "Bearer token"}) as client:
        first = client.post("/api/v1/papers/import-paths", json={"paths": [str(pdf_file), str(tmp_path / 'missing.pdf')]}).json()
        assert len(first["items"]) == 1 and len(first["errors"]) == 1
        second = client.post("/api/v1/papers/import-paths", json={"paths": [str(pdf_file)]}).json()
        assert len(second["duplicates"]) == 1
