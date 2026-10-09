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
from papervault.tables import safe_csv_cell
from .geometry import docling_to_pdf_bbox, pdf_to_display_bbox
from .pdfium import extract_embedded_image, inspect_pdf, render_region


def _label(item) -> str:
    value = getattr(item, "label", "text")
    return str(getattr(value, "value", value))


def _metadata(doc, pdf_info, blocks: list[dict], source: Path) -> dict:
    title = next((b["text"] for b in blocks if b["label"] == "title" and b["text"]), "")
    pdf_meta = pdf_info["metadata"]
    pdf_title = pdf_meta["title"]
    # Some publisher PDFs store an export identifier and page range here, e.g.
    # "pone.0031638 1..8". It is not a paper title and must not suppress the
    # independently located heading before the abstract. Keep the test narrow:
    # descriptive titles containing numbers/ranges are still valid metadata.
    if re.fullmatch(r"[^\s]+\.[^\s]+\s+\d+\s*\.\.\s*\d+", pdf_title.strip()):
        pdf_title = ""
    title_source = "docling_title" if title else "pdf_metadata" if pdf_title else "unknown"
    title = title or pdf_title or None
    if not title:
        first_page_headings = [b for b in blocks if b["label"] == "section_header" and b["location"]
                               and b["location"]["page_index"] == 0 and b["location"].get("bbox")
                               and b["location"].get("crop_box")]
        abstracts = [b for b in first_page_headings if b["text"].strip().casefold() in {"abstract", "摘要"}]
        if abstracts:
            abstract_y = min(pdf_to_display_bbox(b["location"]["bbox"], b["location"])[1] for b in abstracts)
            candidates = []
            for heading in first_page_headings:
                text = heading["text"].strip()
                box = pdf_to_display_bbox(heading["location"]["bbox"], heading["location"])
                if (box[3] < abstract_y and len(text) >= 10
                        and not re.match(r"(?:\d|version\b|contents\b)", text, re.I)):
                    candidates.append((max(1, box[3] - box[1]) / (text.count("\n") + 1), text))
            if candidates:
                title = max(candidates)[1]
                title_source = "layout_heading"
    author = pdf_meta["author"]
    authors = [a.strip() for a in re.split(r";|\band\b", author) if a.strip()]
    abstract_parts, sections, references = [], [], []
    section = ""
    for block in blocks:
        text = block["text"]
        if block["label"] in {"section_header", "title"}:
            section = text.casefold().strip()
            if block["label"] == "section_header":
                sections.append({"title": text, "level": block.get("level", 1), "location": block["location"]})
            continue
        if section in {"abstract", "摘要"}:
            abstract_parts.append(text)
        elif section in {"references", "bibliography", "参考文献"} or block["label"] == "reference":
            references.append(text)
        elif text.casefold().startswith("abstract"):
            abstract_parts.append(re.sub(r"^abstract\s*[:.—-]?\s*", "", text, flags=re.I))
    frontmatter = "\n".join(b["text"] for b in blocks[:12]
                            if b["location"] and b["location"]["page_index"] == 0
                            and b["label"] not in {"reference", "caption"})
    doi_match = re.search(r"(?:\bdoi\s*:?\s*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", frontmatter, re.I)
    arxiv_match = re.search(r"arxiv\s*:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", frontmatter, re.I)
    year_match = re.search(r"\b(?:published|publication year)\s*:?\s*((?:19|20)\d{2})\b", frontmatter, re.I)
    return {"title": title, "title_source": title_source, "authors": authors, "abstract": "\n".join(abstract_parts).strip(),
            "year": int(year_match[1]) if year_match else None, "venue": "",
            "doi": doi_match[1].rstrip(".,;") if doi_match else "",
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
        row = int(cell.start_row_offset_idx)
        col = int(cell.start_col_offset_idx)
        cells.append({"row": row, "col": col,
                      "row_span": max(1, int(cell.end_row_offset_idx) - row),
                      "col_span": max(1, int(cell.end_col_offset_idx) - col),
                      "text": cell.text, "is_header": bool(getattr(cell, "column_header", False)
                                                             or getattr(cell, "row_header", False)),
                      "raw": value})
        if 0 <= row < data.num_rows and 0 <= col < data.num_cols:
            rows[row][col] = cell.text
        if getattr(cell, "column_header", False):
            header_indices.update(range(row, int(cell.end_row_offset_idx)))
    header_rows = 0
    while header_rows in header_indices:
        header_rows += 1
    return {"rows": rows, "cells": cells, "header_rows": header_rows}


def parse_pdf(source: Path, output_dir: Path, models_dir: Path,
              on_progress: Callable[[dict], None] | None = None) -> dict:
    source, output_dir, models_dir = Path(source), Path(output_dir), Path(models_dir)
    start = time.monotonic()

    def progress(phase, **values):
        if on_progress:
            messages = {"validating_models": "正在校验离线模型", "reading_pdf": "正在读取 PDF", "parsing": "正在执行 CPU 版面识别与表格解析",
                        "exporting_assets": "正在导出图表", "saving_results": "正在保存解析结果", "completed": "解析完成"}
            on_progress({"phase": phase, "message": messages.get(phase, phase), **values})

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
    progress("parsing", pages_total=pdf_info["pages_count"])
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
        blocks.append({"id": item.self_ref, "label": label, "text": text, "level": getattr(item, "level", max(1, _level)),
                       "location": locations[0] if locations else None,
                       "locations": locations, "warnings": item_warnings})
        if not isinstance(item, (PictureItem, TableItem)):
            continue
        progress("exporting_assets", items_done=index + 1, items_total=len(items), resources_count=len(resources))
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
        elif (kind == "table" and re.match(r"\s*(?:fig(?:ure)?\.?|图)\s*[\dIVX]", caption, re.I)
              or kind == "figure" and re.match(r"\s*(?:table|表)\s*[\dIVX]", caption, re.I)):
            item_warnings.append("Detected resource type conflicts with its caption; manual review is required")
        files = {}
        original_image = None
        if kind == "figure" and len(locations) == 1:
            try:
                original_image = extract_embedded_image(source, locations[0], resource_dir / "original")
                if original_image:
                    files["original"] = Path(original_image.pop("path")).relative_to(output_dir).as_posix()
            except (OSError, ValueError, RuntimeError) as exc:
                item_warnings.append(f"Embedded image extraction failed; rendered PNG remains available: {exc}")
        if any(location["bbox"] for location in locations):
            try:
                destination = resource_dir / "image.png"
                segments = []
                for segment_index, location in enumerate(locations):
                    if not location["bbox"]:
                        item_warnings.append(f"Page {location['page_index'] + 1} has no crop coordinates; exported image omits this segment")
                        continue
                    segment_path = resource_dir / f"segment-{segment_index + 1}.png"
                    render_region(source, location, segment_path, dpi=150)
                    segments.append(segment_path)
                images = []
                try:
                    for path in segments:
                        with Image.open(path) as image:
                            images.append(image.convert("RGB"))
                    width = max(image.width for image in images)
                    height = sum(image.height for image in images) + 16 * (len(images) - 1)
                    if width * height > 80_000_000:
                        raise ValueError("Combined image exceeds the 80 megapixel limit")
                    combined = Image.new("RGB", (width, height), "white")
                    offset = 0
                    for image in images:
                        combined.paste(image, (0, offset))
                        offset += image.height + 16
                    combined.save(destination)
                    combined.close()
                finally:
                    for image in images:
                        image.close()
                for segment_index, path in enumerate(segments):
                    files[f"segment_{segment_index + 1}"] = path.relative_to(output_dir).as_posix()
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
                csv.writer(stream).writerows([[safe_csv_cell(v) for v in row] for row in table["rows"]])
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
                          "original_image": original_image,
                          "warnings": item_warnings, "docling_ref": item.self_ref})
    text_blocks = [b for b in blocks if b["text"].strip()]
    if not text_blocks:
        warnings.append("No text was extracted. This may be a scanned PDF; OCR is not enabled in this release.")
    progress("saving_results", resources_count=len(resources))
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
    if normalized["metadata"]["title_source"] == "layout_heading":
        warnings.append("Title inferred from the prominent heading before the abstract; please review metadata.")
    (output_dir / "structure.json").write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    progress("completed", resources_count=len(resources), pages_done=pdf_info["pages_count"])
    return normalized
