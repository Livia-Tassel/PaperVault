"""Docling CPU adapter. Models must already be provisioned and verified locally."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import time
import uuid
from importlib.metadata import version
from pathlib import Path
from typing import Callable

from PIL import Image

from papervault.model_manager import validate_bundle
from .geometry import docling_to_pdf_bbox
from .pdfium import inspect_pdf, render_region


def _label(item) -> str:
    value = getattr(item, "label", "text")
    return str(getattr(value, "value", value))


def _metadata(doc, pdf_info, blocks: list[dict], source: Path) -> dict:
    title = next((b["text"] for b in blocks if b["label"] == "title" and b["text"]), "")
    pdf_meta = pdf_info["metadata"]
    title = title or pdf_meta["title"] or source.stem
    author = pdf_meta["author"]
    authors = [a.strip() for a in re.split(r";|\band\b", author) if a.strip()]
    abstract_parts, sections, references = [], [], []
    section = ""
    for block in blocks:
        text = block["text"]
        if block["label"] in {"section_header", "title"}:
            section = text.casefold().strip()
            if block["label"] == "section_header":
                sections.append(text)
            continue
        if section in {"abstract", "摘要"}:
            abstract_parts.append(text)
        elif section in {"references", "bibliography", "参考文献"} or block["label"] == "reference":
            references.append(text)
        elif text.casefold().startswith("abstract"):
            abstract_parts.append(re.sub(r"^abstract\s*[:.—-]?\s*", "", text, flags=re.I))
    fulltext = "\n".join(b["text"] for b in blocks)
    doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", fulltext, re.I)
    arxiv_match = re.search(r"arxiv\s*:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", fulltext, re.I)
    year_match = re.search(r"\b((?:19|20)\d{2})\b", "\n".join(b["text"] for b in blocks[:15]))
    return {"title": title, "authors": authors, "abstract": "\n".join(abstract_parts).strip(),
            "year": int(year_match[1]) if year_match else None, "venue": "",
            "doi": doi_match[0].rstrip(".,;") if doi_match else "",
            "arxiv_id": arxiv_match[1] if arxiv_match else "",
            "keywords": [s.strip() for s in re.split(r"[,;]", pdf_meta["keywords"]) if s.strip()],
            "sections": sections, "references": references}


def _locations(item, document, pages, warnings):
    locations = []
    for provenance in getattr(item, "prov", []):
        page_index = int(provenance.page_no) - 1
        if page_index < 0 or page_index >= len(pages):
            warnings.append("Parser returned an invalid page number; location requires review")
            continue
        geometry = pages[page_index]
        raw = provenance.model_dump(mode="json")
        location = {**geometry, "bbox": None, "coordinate_space": "pdf_user_space", "docling_provenance": raw}
        try:
            size = document.pages[provenance.page_no].size
            location["bbox"] = docling_to_pdf_bbox(raw["bbox"], geometry, (size.width, size.height))
        except (ValueError, KeyError, AttributeError, TypeError) as exc:
            warnings.append(f"Bounding box unavailable; page-only navigation is available: {exc}")
        locations.append(location)
    if not locations:
        warnings.append("Source coordinates were not detected; manual review is required")
    return locations


def _table_data(item):
    data = item.data
    rows = [["" for _ in range(data.num_cols)] for _ in range(data.num_rows)]
    cells = []
    header_indices = set()
    for cell in data.table_cells:
        value = cell.model_dump(mode="json")
        cells.append(value)
        row = int(cell.start_row_offset_idx)
        col = int(cell.start_col_offset_idx)
        if 0 <= row < data.num_rows and 0 <= col < data.num_cols:
            rows[row][col] = cell.text
        if getattr(cell, "column_header", False):
            header_indices.update(range(row, int(cell.end_row_offset_idx)))
    header_rows = 0
    while header_rows in header_indices:
        header_rows += 1
    return {"rows": rows, "cells": cells, "header_rows": header_rows}


def _safe_csv_cell(value):
    text = str(value)
    # Spreadsheet applications may execute formula-like values when opening CSV.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def parse_pdf(source: Path, output_dir: Path, models_dir: Path,
              on_progress: Callable[[dict], None] | None = None) -> dict:
    source, output_dir, models_dir = Path(source), Path(output_dir), Path(models_dir)
    start = time.monotonic()

    def progress(phase, **values):
        if on_progress:
            on_progress({"phase": phase, **values})

    progress("validating_models")
    try:
        manifest = validate_bundle(models_dir)
    except (OSError, ValueError, KeyError) as exc:
        raise RuntimeError("Local parser models are missing or invalid. Download or import models in Settings before parsing.") from exc
    progress("reading_pdf")
    pdf_info = inspect_pdf(source)
    # Disable all network-backed model resolution before importing Transformers.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import PictureItem, TableItem

    options = PdfPipelineOptions(artifacts_path=models_dir.resolve())
    options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU,
                                                      num_threads=min(4, os.cpu_count() or 1))
    options.do_ocr = False
    options.do_table_structure = True
    options.table_structure_options.mode = TableFormerMode.ACCURATE
    options.enable_remote_services = False
    options.generate_page_images = False
    options.generate_picture_images = False
    options.document_timeout = 1200
    converter = DocumentConverter(allowed_formats=[InputFormat.PDF], format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    progress("parsing", pages_total=pdf_info["pages_count"], message="CPU layout analysis and table recognition")
    result = converter.convert(source, raises_on_error=True, max_num_pages=2000)
    document = result.document
    status = str(getattr(result.status, "value", result.status))
    if status not in ("success", "partial_success"):
        raise RuntimeError(f"Docling conversion failed: {status}")
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings = ["OCR is disabled; scanned pages may have incomplete or missing text."]
    for error in getattr(result, "errors", []):
        warnings.append(str(getattr(error, "error_message", error)))
    if status == "partial_success":
        warnings.append("Some pages could not be parsed; extracted results require review.")
    blocks, resources = [], []
    current_section = ""
    items = list(document.iterate_items())
    for index, (item, _level) in enumerate(items):
        label = _label(item)
        text = str(getattr(item, "text", ""))
        if label == "section_header":
            current_section = text
        item_warnings = []
        locations = _locations(item, document, pdf_info["pages"], item_warnings)
        blocks.append({"id": item.self_ref, "label": label, "text": text,
                       "location": locations[0] if locations else None,
                       "locations": locations, "warnings": item_warnings})
        if not isinstance(item, (PictureItem, TableItem)):
            continue
        progress("exporting_assets", items_done=index + 1, items_total=len(items), resources_done=len(resources))
        kind = "table" if isinstance(item, TableItem) else "figure"
        identifier = str(uuid.uuid4())
        resource_dir = output_dir / "resources" / identifier
        resource_dir.mkdir(parents=True, exist_ok=True)
        caption = item.caption_text(document).strip()
        pattern = r"(?:table|表)\s*([\dIVX]+(?:[.\-]\d+)?)" if kind == "table" else r"(?:fig(?:ure)?\.?|图)\s*([\dIVX]+(?:[.\-]\d+)?(?:\([a-z]\))?)"
        number_match = re.search(pattern, caption, re.I)
        number = number_match[1] if number_match else ""
        if not caption:
            item_warnings.append("No caption association was detected; manual review is required")
        files = {}
        if locations and locations[0]["bbox"]:
            try:
                destination = resource_dir / "image.png"
                render_region(source, locations[0], destination, dpi=150)
                files["png"] = destination.relative_to(output_dir).as_posix()
                with Image.open(destination) as image:
                    image.thumbnail((512, 384))
                    image.convert("RGB").save(resource_dir / "thumbnail.png")
                files["thumbnail"] = (resource_dir / "thumbnail.png").relative_to(output_dir).as_posix()
            except (OSError, ValueError, RuntimeError) as exc:
                item_warnings.append(f"Image rendering failed: {exc}")
        table = None
        if isinstance(item, TableItem):
            table = _table_data(item)
            destination = resource_dir / "table.csv"
            with destination.open("w", newline="", encoding="utf-8-sig") as stream:
                csv.writer(stream).writerows([[_safe_csv_cell(v) for v in row] for row in table["rows"]])
            files["csv"] = destination.relative_to(output_dir).as_posix()
            destination = resource_dir / "table.html"
            try:
                table_html = item.export_to_html(doc=document)
            except (TypeError, AttributeError):
                table_html = "<table>" + "".join("<tr>" + "".join("<td>" + html.escape(v) + "</td>" for v in row)
                                                         + "</tr>" for row in table["rows"]) + "</table>"
            destination.write_text(table_html, encoding="utf-8")
            files["html"] = destination.relative_to(output_dir).as_posix()
        resources.append({"id": identifier, "kind": kind, "number": number, "caption": caption,
                          "name": f"{kind.title()} {number}".strip(), "locations": locations,
                          "section": current_section, "files": files, "table": table,
                          "warnings": item_warnings, "docling_ref": item.self_ref})
    text_blocks = [b for b in blocks if b["text"].strip()]
    if not text_blocks:
        warnings.append("No text was extracted. This may be a scanned PDF; OCR is not enabled in this release.")
    progress("saving_results", resources_done=len(resources))
    document_json = document.model_dump(mode="json")
    (output_dir / "docling.json").write_text(json.dumps(document_json, ensure_ascii=False), encoding="utf-8")
    (output_dir / "fulltext.md").write_text(document.export_to_markdown(), encoding="utf-8")
    normalized = {"metadata": _metadata(document, pdf_info, blocks, source),
                  "pages_count": pdf_info["pages_count"], "pages": pdf_info["pages"],
                  "blocks": blocks, "resources": resources, "warnings": warnings,
                  "engine": {"name": "docling", "version": version("docling-slim"), "device": "cpu", "ocr": False,
                             "elapsed_seconds": round(time.monotonic() - start, 3),
                             "model_manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                             "coordinate_space": "pdf_user_space"}}
    (output_dir / "structure.json").write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    progress("completed", resources_done=len(resources), pages_done=pdf_info["pages_count"])
    return normalized
