from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    reading_status: Literal["unread", "reading", "read"] = "unread"
    last_opened: str | None = None
    annotation_count: int = 0


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


class LibraryInfo(BaseModel):
    id: str | None = None
    path: str | None
    paper_count: int
    figure_count: int
    table_count: int


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


FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]
VersionNumber = Annotated[int, Field(strict=True, ge=0)]
PageNumber = Annotated[int, Field(strict=True, ge=0, le=1999)]


class ReadingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: VersionNumber
    page_index: PageNumber = Field(default=None)
    anchor: tuple[FiniteNumber, FiniteNumber] | None = None
    scale: Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0.05, le=8)] = Field(default=None)
    rotation: Literal[0, 90, 180, 270] = Field(default=None)
    fit_mode: Literal["custom", "width", "page"] = Field(default=None)
    status: Literal["unread", "reading", "read"] = Field(default=None)
    touch: bool = Field(default=False, strict=True)

    @model_validator(mode="before")
    @classmethod
    def explicit_nulls(cls, value):
        if isinstance(value, dict) and any(key in value and value[key] is None for key in
                                          ("page_index", "scale", "rotation", "fit_mode", "status", "touch")):
            raise ValueError("阅读状态字段不能为null，anchor除外")
        if isinstance(value, dict) and "rotation" in value and type(value["rotation"]) is not int:
            raise ValueError("旋转角度必须为整数")
        return value


class ReadingState(BaseModel):
    paper_id: str
    version: int
    page_index: int
    anchor: tuple[float, float] | None
    scale: float
    rotation: int
    fit_mode: Literal["custom", "width", "page"]
    status: Literal["unread", "reading", "read"]
    last_opened: str | None
    updated_at: str | None


class AnnotationLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_index: PageNumber
    bbox: tuple[FiniteNumber, FiniteNumber, FiniteNumber, FiniteNumber] | None = None

    @field_validator("bbox")
    @classmethod
    def positive_box(cls, value):
        if value is not None and (value[2] <= value[0] or value[3] <= value[1]):
            raise ValueError("定位框必须具有正宽度和正高度")
        return value


class AnnotationFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="", max_length=500)
    quote: str = Field(default="", max_length=20000)
    body: str = Field(default="", max_length=100000)
    color: Literal["amber", "green", "blue", "pink", "purple"] = "amber"
    tags: list[str] = Field(default_factory=list, max_length=50)
    locations: list[AnnotationLocation] = Field(default_factory=list, max_length=512)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values):
        result = []
        for value in values:
            value = value.strip()
            if not 1 <= len(value) <= 80:
                raise ValueError("标签需要1至80个字符")
            if value not in result:
                result.append(value)
        return result


class AnnotationCreate(AnnotationFields):
    kind: Literal["bookmark", "highlight", "note"]


class AnnotationPatch(AnnotationFields):
    expected_version: VersionNumber


class ExpectedVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: VersionNumber


class Annotation(AnnotationFields):
    model_config = ConfigDict(extra="allow")
    id: str
    paper_id: str
    paper_title: str
    kind: Literal["bookmark", "highlight", "note"]
    version: int
    deleted: bool
    created_at: str
    updated_at: str


class AnnotationList(BaseModel):
    items: list[Annotation]
    total: int


class AnnotationExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(default_factory=list, max_length=10000)
    paper_id: str | None = Field(default=None, max_length=128)
    format: Literal["markdown", "json"] = "markdown"
