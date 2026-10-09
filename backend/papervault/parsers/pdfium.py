"""Local PDF inspection and bounded raster rendering, with no PDF scripting."""
from __future__ import annotations

import math
import threading
from pathlib import Path

from .geometry import display_size, pdf_to_display_bbox, validate_bbox

# PDFium is process-global and not thread-safe, even between different PDFs.
PDFIUM_LOCK = threading.RLock()
MAX_RENDER_PIXELS = 80_000_000


def inspect_pdf(source: Path) -> dict:
    from pypdf import PdfReader

    source = Path(source)
    if source.stat().st_size > 512 * 1024 * 1024:
        raise ValueError("PDF exceeds the 512 MB size limit")
    reader = PdfReader(source, strict=False)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("Password-protected PDF is not supported; import an unlocked copy")
    if len(reader.pages) > 2000:
        raise ValueError("PDF exceeds the 2,000-page limit")
    pages = []
    for index, page in enumerate(reader.pages):
        media = [float(v) for v in page.mediabox]
        crop = [float(v) for v in page.cropbox]
        # PDF viewers render the intersection of the media and crop boxes.
        crop = [max(media[0], crop[0]), max(media[1], crop[1]),
                min(media[2], crop[2]), min(media[3], crop[3])]
        validate_bbox(crop)
        rotation = int(page.get("/Rotate", 0)) % 360
        unit = float(page.get("/UserUnit", 1))
        if rotation not in (0, 90, 180, 270) or not math.isfinite(unit) or unit <= 0:
            raise ValueError(f"Unsupported page geometry on page {index + 1}")
        pages.append({"page_index": index, "crop_box": crop, "media_box": media,
                      "rotation": rotation, "user_unit": unit,
                      "width": crop[2] - crop[0], "height": crop[3] - crop[1]})
    metadata = reader.metadata or {}
    return {"pages": pages, "pages_count": len(pages), "metadata": {
        "title": str(metadata.get("/Title", "") or ""),
        "author": str(metadata.get("/Author", "") or ""),
        "subject": str(metadata.get("/Subject", "") or ""),
        "keywords": str(metadata.get("/Keywords", "") or ""),
    }}


def render_region(source: Path, location: dict, destination: Path, dpi: int = 300) -> None:
    import pypdfium2 as pdfium

    if not isinstance(dpi, int) or not 36 <= dpi <= 600:
        raise ValueError("DPI must be an integer between 36 and 600")
    info = inspect_pdf(source)
    index = int(location.get("page_index", 0))
    if index < 0 or index >= info["pages_count"]:
        raise ValueError("Page index is outside the PDF")
    geometry = info["pages"][index]
    bbox = location.get("bbox") or geometry["crop_box"]
    x0, y0, x1, y1 = validate_bbox(bbox)
    cx0, cy0, cx1, cy1 = geometry["crop_box"]
    clipped = [max(cx0, x0), max(cy0, y0), min(cx1, x1), min(cy1, y1)]
    validate_bbox(clipped)
    left, top, right, bottom = pdf_to_display_bbox(clipped, geometry)
    dw, dh = display_size(geometry)
    scale = dpi / 72 * geometry["user_unit"]
    if (right - left) * (bottom - top) * scale * scale > MAX_RENDER_PIXELS:
        raise ValueError("Requested image exceeds the 80 megapixel rendering limit")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(source)
        try:
            page = pdf[index]
            try:
                # PDFium crop values are distances from the displayed edges,
                # in page units, ordered left, bottom, right, top.
                pw, ph = page.get_size()
                sx, sy = pw / dw, ph / dh
                bitmap = page.render(scale=scale / sx, crop=(left * sx, (dh - bottom) * sy,
                                                            (dw - right) * sx, top * sy))
                try:
                    image = bitmap.to_pil().copy()
                finally:
                    bitmap.close()
                image.save(destination, format="PNG")
            finally:
                page.close()
        finally:
            pdf.close()
