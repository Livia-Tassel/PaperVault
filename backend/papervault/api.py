from __future__ import annotations

import asyncio
import json
import logging
import secrets
import shutil
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import __version__
from .backup import create_backup, restore_backup
from .exporting import export_assets
from .files import atomic_json, safe_path, uid
from .jobs import TaskManager
from .library import Library
from .reading import VersionConflict
from .annotation_export import export_annotations
from .schemas import (BackupRequest, CropRequest, ExportRequest, FolderRequest, ImportPaths, LibraryOpen,
                      Paper, PaperPatch, PathRequest, Resource, ResourcePatch, RestoreRequest)
from .schemas import (Annotation, AnnotationCreate, AnnotationExportRequest, AnnotationList,
                      AnnotationPatch, ExpectedVersion, LibraryInfo, ReadingPatch, ReadingState)


class AppState:
    def __init__(self, config_dir: Path, models_dir: Path | None = None, start_workers=True):
        from .model_manager import ModelManager
        self.config_dir = config_dir.resolve()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "settings.json"
        self.settings = json.loads(self.config_file.read_text(encoding="utf-8")) if self.config_file.exists() else {}
        self.models = ModelManager(models_dir or self.config_dir / "models")
        self.library: Library | None = None
        self.tasks: TaskManager | None = None
        self.start_workers = start_workers
        self.mutex = threading.RLock()
        self.download_thread = None

    def open(self, path: str, create=True):
        with self.mutex:
            requested = Path(path).expanduser().resolve()
            if self.library and self.library.root == requested:
                return self.library.info()
            candidate = Library(requested, create)
            if self.tasks and self.start_workers:
                self.tasks.stop()
            if self.library:
                self.library.close()
            self.library = candidate
            self.tasks = TaskManager(candidate, self.models)
            if self.start_workers:
                self.tasks.start()
            self.settings["library_path"] = str(requested)
            atomic_json(self.config_file, self.settings)
            return candidate.info()

    def close(self):
        with self.mutex:
            if self.tasks and self.start_workers:
                self.tasks.stop()
            if self.library:
                self.library.close()
                self.library = None

    def require_library(self):
        if self.library is None:
            raise HTTPException(409, "请先创建或打开论文库")
        return self.library


def create_app(token: str, config_dir: Path, library_path: Path | None = None,
               models_dir: Path | None = None, start_workers=True) -> FastAPI:
    state = AppState(config_dir, models_dir, start_workers)
    library_mutations = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        selected = library_path or state.settings.get("library_path")
        if selected:
            try:
                state.open(str(selected), create=bool(library_path))
            except (ValueError, OSError):
                logging.getLogger(__name__).exception("Previous library could not be opened")
        yield
        state.close()

    app = FastAPI(title="PaperVault Local API", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.services = state
    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.method != "OPTIONS":
            supplied = request.headers.get("authorization", "")
            if not secrets.compare_digest(supplied, f"Bearer {token}"):
                return JSONResponse({"detail": "本地服务认证失败，请重新启动应用"}, status_code=401)
        if request.url.hostname not in ("127.0.0.1", "localhost", "testserver"):
            return JSONResponse({"detail": "仅允许本地服务请求"}, status_code=400)
        route = request.url.path
        is_library_mutation = (request.method in ("POST", "PATCH", "DELETE")
                               and route.startswith("/api/v1/")
                               and not route.startswith("/api/v1/models/")
                               and route != "/api/v1/settings")
        if is_library_mutation:
            # Keep the scope check and synchronous handler execution inside one
            # event-loop lock. A threading.RLock across await cannot provide this.
            async with library_mutations:
                encoded_scope = request.headers.get("x-papervault-library")
                if encoded_scope is not None and route != "/api/v1/library/open":
                    try:
                        supplied_scope = unquote(encoded_scope, encoding="utf-8", errors="strict")
                    except UnicodeError:
                        supplied_scope = ""
                    current = f"{state.library.id}:{state.library.root}" if state.library else None
                    if supplied_scope != current:
                        return JSONResponse({"detail": "论文库已切换，旧操作未执行", "code": "library_switched"}, status_code=409)
                return await call_next(request)
        return await call_next(request)

    # CORS wraps authentication so the desktop can read an expired-session 401.
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:1420", "http://127.0.0.1:1420",
                       "http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"],
                       allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "Range", "X-PaperVault-Library"],
                       expose_headers=["Content-Disposition", "Content-Length", "Content-Range", "Accept-Ranges"])

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": str(exc).strip("'")}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(VersionConflict)
    async def version_conflict(request, exc):
        return JSONResponse({"detail": str(exc), "current": exc.current}, status_code=409)

    @app.exception_handler(FileNotFoundError)
    async def missing_file(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(sqlite3.IntegrityError)
    async def conflict(request, exc):
        return JSONResponse({"detail": "该名称或记录已存在，或关联对象已被删除"}, status_code=409)

    @app.exception_handler(OSError)
    async def file_error(request, exc):
        logging.getLogger(__name__).exception("Filesystem operation failed")
        return JSONResponse({"detail": f"文件操作失败，请检查磁盘空间、目录权限或文件占用：{exc.strerror or exc}"}, status_code=500)

    prefix = "/api/v1"

    @app.get(prefix + "/health")
    def health():
        return {"status": "ok", "version": __version__, "protocol": 1}

    @app.get(prefix + "/openapi.json")
    def openapi():
        return app.openapi()

    @app.get(prefix + "/library", response_model=LibraryInfo)
    def library_info():
        return state.library.info() if state.library else {"path": None, "paper_count": 0, "figure_count": 0, "table_count": 0}

    @app.post(prefix + "/library/open", response_model=LibraryInfo)
    def library_open(body: LibraryOpen):
        return state.open(body.path, body.create)

    @app.get(prefix + "/papers")
    def papers(q: str = "", tag: str | None = None, folder: str | None = None, favorite: bool | None = None,
               year: int | None = None, sort: str = "recent", offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=1000),
               reading_status: str | None = None, opened: bool | None = None):
        return state.require_library().papers(q, tag, folder, favorite, year, sort, offset, limit, reading_status, opened)

    @app.post(prefix + "/papers/import-paths")
    def import_paths(body: ImportPaths):
        library = state.require_library()
        paths, seen = [], set()
        for value in body.paths:
            path = Path(value).expanduser().resolve()
            if path.is_dir():
                candidates = path.rglob("*") if body.recursive else path.glob("*")
                found = [p for p in candidates if p.is_file() and not p.is_symlink() and p.suffix.lower() == ".pdf"]
            else:
                found = [path]
            for item in found:
                if str(item) not in seen:
                    paths.append(item)
                    seen.add(str(item))
        if len(paths) > 10000:
            raise ValueError("单次导入超过10000个文件，请分批导入")
        result = {"items": [], "duplicates": [], "errors": []}
        for path in paths:
            try:
                paper, duplicate = library.import_file(path)
                result["duplicates" if duplicate else "items"].append(paper)
            except (OSError, ValueError) as exc:
                result["errors"].append({"path": str(path), "error": str(exc)})
        return result

    @app.post(prefix + "/papers/import")
    def import_upload(files: list[UploadFile] = File(...)):
        library = state.require_library()
        result = {"items": [], "duplicates": [], "errors": []}
        for upload in files:
            directory = library.root / ".staging" / uid()
            directory.mkdir()
            try:
                filename = Path(PureWindowsPath(upload.filename or "document.pdf").name).name
                path = directory / filename
                total = 0
                with path.open("wb") as stream:
                    for chunk in iter(lambda: upload.file.read(1024*1024), b""):
                        total += len(chunk)
                        if total > 512*1024*1024:
                            raise ValueError("PDF超过512 MiB导入上限")
                        stream.write(chunk)
                paper, duplicate = library.import_file(path)
                result["duplicates" if duplicate else "items"].append(paper)
            except (OSError, ValueError) as exc:
                result["errors"].append({"path": upload.filename, "error": str(exc)})
            finally:
                upload.file.close()
                shutil.rmtree(directory)
        return result

    @app.get(prefix + "/papers/{paper_id}", response_model=Paper)
    def paper(paper_id: str):
        library = state.require_library()
        return {**library.paper(paper_id), "similar_papers": library.similar_papers(paper_id)}

    @app.patch(prefix + "/papers/{paper_id}", response_model=Paper)
    def paper_edit(paper_id: str, body: PaperPatch):
        return state.require_library().update_paper(paper_id, body.model_dump(exclude_unset=True))

    @app.delete(prefix + "/papers/{paper_id}")
    def paper_delete(paper_id: str, delete_files: bool = False):
        state.require_library().remove(paper_id, delete_files)
        return {"removed": True, "deleted_managed_files": delete_files}

    @app.post(prefix + "/papers/{paper_id}/reparse")
    def reparse(paper_id: str):
        return {"id": state.require_library().queue(paper_id)}

    @app.get(prefix + "/papers/{paper_id}/pdf")
    def pdf(paper_id: str):
        return FileResponse(state.require_library().pdf(paper_id), media_type="application/pdf")

    @app.get(prefix + "/papers/{paper_id}/reading-state", response_model=ReadingState)
    def reading_state(paper_id: str):
        return state.require_library().reading_state(paper_id)

    @app.patch(prefix + "/papers/{paper_id}/reading-state", response_model=ReadingState)
    def update_reading_state(paper_id: str, body: ReadingPatch):
        return state.require_library().update_reading_state(paper_id, body.model_dump(exclude_unset=True))

    @app.get(prefix + "/annotations", response_model=AnnotationList)
    def annotations(q: str = Query("", max_length=1000), paper_id: str | None = None, kind: str | None = None,
                    tag: str | None = Query(None, max_length=80), offset: int = Query(0, ge=0),
                    limit: int = Query(30, ge=1, le=200), deleted: bool = False):
        return state.require_library().annotations(q=q, paper_id=paper_id, kind=kind, tag=tag, offset=offset, limit=limit, deleted=deleted)

    @app.post(prefix + "/papers/{paper_id}/annotations", response_model=Annotation)
    def create_annotation(paper_id: str, body: AnnotationCreate):
        return state.require_library().create_annotation(paper_id, body.model_dump())

    @app.post(prefix + "/annotations/export")
    def annotation_export(body: AnnotationExportRequest):
        result = export_annotations(state.require_library(), body.ids, body.paper_id, body.format)
        return FileResponse(result, filename=result.name, media_type="application/json" if body.format == "json" else "text/markdown; charset=utf-8")

    @app.get(prefix + "/annotations/{annotation_id}", response_model=Annotation)
    def annotation(annotation_id: str):
        return state.require_library().annotation(annotation_id)

    @app.patch(prefix + "/annotations/{annotation_id}", response_model=Annotation)
    def update_annotation(annotation_id: str, body: AnnotationPatch):
        return state.require_library().update_annotation(annotation_id, body.model_dump(exclude_unset=True))

    @app.delete(prefix + "/annotations/{annotation_id}", response_model=Annotation)
    def delete_annotation(annotation_id: str, expected_version: int = Query(..., ge=0)):
        return state.require_library().delete_annotation(annotation_id, expected_version)

    @app.post(prefix + "/annotations/{annotation_id}/restore", response_model=Annotation)
    def restore_annotation(annotation_id: str, body: ExpectedVersion):
        return state.require_library().restore_annotation(annotation_id, body.expected_version)

    @app.get(prefix + "/papers/{paper_id}/text")
    def text(paper_id: str):
        library = state.require_library()
        paper = library.paper(paper_id)
        if not paper.get("active_revision"):
            return {"markdown": "", "sections": []}
        path = safe_path(library.root, f"papers/{paper_id}/revisions/{paper['active_revision']}/fulltext.md")
        return {"markdown": path.read_text(encoding="utf-8"), "sections": paper.get("sections", [])}

    @app.get(prefix + "/resources")
    def resources(kind: str | None = None, paper_id: str | None = None, q: str = "", tag: str | None = None,
                  year: int | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=1000)):
        return state.require_library().resources(kind, paper_id, q, tag, year, offset, limit)

    @app.get(prefix + "/resources/{resource_id}", response_model=Resource)
    def resource(resource_id: str):
        return state.require_library().resource(resource_id)

    @app.patch(prefix + "/resources/{resource_id}", response_model=Resource)
    def edit_resource(resource_id: str, body: ResourcePatch):
        return state.require_library().update_resource(resource_id, body.model_dump(exclude_unset=True))

    @app.get(prefix + "/resources/{resource_id}/files/{format_name}")
    def resource_file(resource_id: str, format_name: str, dpi: int | None = None):
        path = state.require_library().resource_file(resource_id, format_name, dpi)
        media = {"png": "image/png", "thumbnail": "image/png" if path.suffix == ".png" else "image/jpeg",
                 "csv": "text/csv; charset=utf-8", "html": "text/html; charset=utf-8"}
        return FileResponse(path, media_type=media.get(format_name), filename=path.name if format_name in ("csv", "html") else None,
                            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"} if format_name == "html" else None)

    @app.post(prefix + "/resources/{resource_id}/crop", response_model=Resource)
    def crop_resource(resource_id: str, body: CropRequest):
        library = state.require_library()
        resource = library.resource(resource_id)
        return library.crop(resource["paper_id"], body.location.model_dump(), body.dpi, resource_id)

    @app.post(prefix + "/papers/{paper_id}/resources", response_model=Resource)
    def manual_resource(paper_id: str, body: CropRequest):
        return state.require_library().crop(paper_id, body.location.model_dump(), body.dpi,
                                           kind=body.kind, name=body.name, caption=body.caption)

    @app.post(prefix + "/exports")
    def export(body: ExportRequest):
        path = export_assets(state.require_library(), body.paper_ids, body.resource_ids, body.format, body.dpi)
        return FileResponse(path, filename=path.name)

    @app.get(prefix + "/search")
    def search_all(q: str = Query("", max_length=1000)):
        return state.require_library().search(q)

    @app.get(prefix + "/jobs")
    def jobs():
        return state.require_library().jobs()

    @app.post(prefix + "/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        state.require_library()
        return state.tasks.cancel(job_id)

    @app.post(prefix + "/jobs/{job_id}/retry")
    def retry_job(job_id: str):
        state.require_library()
        return state.tasks.retry(job_id)

    @app.get(prefix + "/models")
    def models():
        return state.models.status()

    @app.post(prefix + "/models/download")
    def download_models():
        with state.mutex:
            if not state.download_thread or not state.download_thread.is_alive():
                def download():
                    try:
                        state.models.download()
                    except Exception:
                        logging.getLogger(__name__).exception("Model download failed")
                state.download_thread = threading.Thread(target=download, daemon=True, name="model-download")
                state.download_thread.start()
        return state.models.status()

    @app.post(prefix + "/models/import")
    def import_models(body: PathRequest):
        return state.models.import_directory(Path(body.path))

    @app.get(prefix + "/folders")
    def folders():
        return state.require_library().folders()

    @app.post(prefix + "/folders")
    def add_folder(body: FolderRequest):
        return state.require_library().add_folder(body.name)

    @app.delete(prefix + "/folders/{folder_id}")
    def delete_folder(folder_id: str):
        with state.require_library().db.transaction() as con:
            con.execute("DELETE FROM folders WHERE id=?", (folder_id,))
        return {"deleted": True}

    @app.post(prefix + "/backups")
    def backup(body: BackupRequest):
        return {"path": str(create_backup(state.require_library(), Path(body.destination) if body.destination else None))}

    @app.post(prefix + "/backups/restore")
    def restore(body: RestoreRequest):
        result = restore_backup(Path(body.path), Path(body.destination))
        return state.open(str(result), create=False)

    @app.get(prefix + "/settings")
    def settings():
        return state.settings

    @app.patch(prefix + "/settings")
    def edit_settings(body: dict):
        allowed = {key: value for key, value in body.items() if key in ("theme", "language", "export_dpi")}
        state.settings.update(allowed)
        atomic_json(state.config_file, state.settings)
        return state.settings

    return app
