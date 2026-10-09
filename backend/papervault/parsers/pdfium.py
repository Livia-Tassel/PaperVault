"""Local PDF inspection and bounded raster rendering, with no PDF scripting."""
from __future__ import annotations

import math
import threading
from functools import lru_cache
from pathlib import Path

from .geometry import display_size, pdf_to_display_bbox, validate_bbox

# PDFium is process-global and not thread-safe, even between different PDFs.
PDFIUM_LOCK = threading.RLock()
MAX_RENDER_PIXELS = 80_000_000


def extract_embedded_image(source: Path, location: dict, destination_prefix: Path) -> dict | None:
    """Extract only a unique image object overlapping the figure by IoU >= 0.8.

    JPEG/JP2 retain their encoded image stream. Other filters produce a native
    resolution lossless image and explicitly report that encoding was changed.
    The rendered region remains authoritative for clipping, masks and overlays.
    """
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    if not location.get("bbox"):
        return None
    wanted = validate_bbox(location["bbox"])
    info = inspect_pdf(source)
    index = int(location["page_index"])
    if not 0 <= index < info["pages_count"]:
        return None
    with PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(source)
        try:
            page = pdf[index]
            try:
                candidates = []
                for obj in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE]):
                    # Form matrices may change the coordinate frame of nested
                    # image bounds. Do not guess when uniqueness is uncertain.
                    if obj.container is not None:
                        return None
                    bounds = validate_bbox(obj.get_bounds())
                    intersection = max(0, min(wanted[2], bounds[2]) - max(wanted[0], bounds[0])) * max(
                        0, min(wanted[3], bounds[3]) - max(wanted[1], bounds[1]))
                    union = ((wanted[2] - wanted[0]) * (wanted[3] - wanted[1])
                             + (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) - intersection)
                    score = intersection / union
                    if score >= 0.8:
                        candidates.append((obj, bounds, score))
                if len(candidates) != 1:
                    return None
                obj, bounds, score = candidates[0]
                width, height = obj.get_px_size()
                if width * height > MAX_RENDER_PIXELS:
                    raise ValueError("Embedded image exceeds the 80 megapixel extraction limit")
                filters = obj.get_filters()
                complex_filters = [f for f in filters if f not in obj.SIMPLE_FILTERS]
                if complex_filters == ["DCTDecode"]:
                    extension, image_format, preserved = "jpg", "jpeg", True
                elif complex_filters == ["JPXDecode"]:
                    extension, image_format, preserved = "jp2", "jpeg2000", True
                else:
                    metadata = obj.get_metadata()
                    extension = "tiff" if metadata.colorspace == raw.FPDF_COLORSPACE_DEVICECMYK else "png"
                    image_format, preserved = extension, False
                destination_prefix = Path(destination_prefix)
                destination_prefix.parent.mkdir(parents=True, exist_ok=True)
                obj.extract(destination_prefix, fb_format=extension)
                destination = destination_prefix.with_name(destination_prefix.name + "." + extension)
                if not destination.is_file() or destination.stat().st_size == 0:
                    raise RuntimeError("PDFium did not produce the expected embedded image")
                return {"path": str(destination), "format": image_format, "extension": extension,
                        "width": width, "height": height, "source_filters": filters,
                        "encoding_preserved": preserved, "page_index": index, "bbox": bounds,
                        "match_iou": round(score, 6), "includes_page_effects": False}
            finally:
                page.close()
        finally:
            pdf.close()


def inspect_pdf(source: Path) -> dict:
    source = Path(source).resolve()
    stat = source.stat()
    return _inspect_pdf_cached(str(source), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=16)
def _inspect_pdf_cached(source_name: str, file_size: int, modified_ns: int) -> dict:
    from pypdf import PdfReader

    source = Path(source_name)
    if file_size > 512 * 1024 * 1024:
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
