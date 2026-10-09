from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceLocation(BaseModel):
    model_config = ConfigDict(extra="allow")
    page_index: int = Field(ge=0)
    bbox: tuple[float, float, float, float] | None = None


class PaperPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    authors: list[str] | None = None
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    keywords: list[str] | None = None
    tags: list[str] | None = None
    folders: list[str] | None = None
    favorite: bool | None = None
    notes: str | None = None
    sections: list[dict] | None = None
    references: list[str] | None = None


class TableData(BaseModel):
    model_config = ConfigDict(extra="allow")
    rows: list[list[str]]
    cells: list[dict] = Field(default_factory=list)
    header_rows: int = 1


class ResourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    number: str | None = None
    caption: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    table: TableData | None = None
    needs_review: bool | None = None


class Paper(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    filename: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    status: str
    figure_count: int = 0
    table_count: int = 0


class Resource(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    paper_id: str
    paper_title: str
    kind: Literal["figure", "table"]
    locations: list[SourceLocation] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)
    table: TableData | None = None


class LibraryOpen(BaseModel):
    path: str
    create: bool = True


class ImportPaths(BaseModel):
    paths: list[str] = Field(max_length=10000)
    recursive: bool = True


class CropRequest(BaseModel):
    location: SourceLocation
    dpi: Literal[150, 300, 600] = 300
    kind: Literal["figure", "table"] = "figure"
    name: str = ""
    caption: str = ""


class ExportRequest(BaseModel):
    paper_ids: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    format: Literal["zip", "png", "csv", "html"] = "zip"
    dpi: Literal[150, 300, 600] = 300


class PathRequest(BaseModel):
    path: str


class BackupRequest(BaseModel):
    destination: str | None = None


class RestoreRequest(BaseModel):
    path: str
    destination: str


class FolderRequest(BaseModel):
    name: str
