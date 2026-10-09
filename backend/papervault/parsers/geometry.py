"""Conversions between PDF user space and the rotated, top-left display frame.

The persisted frame is the one PDF.js accepts in convertToViewportRectangle:
unrotated PDF user coordinates, including the CropBox offset, before UserUnit.
"""
from __future__ import annotations

import math
from typing import Iterable


def validate_bbox(bbox: Iterable[float]) -> list[float]:
    values = [float(value) for value in bbox]
    if len(values) != 4 or not all(math.isfinite(value) for value in values):
        raise ValueError("Bounding box must contain four finite numbers")
    x0, y0, x1, y1 = values
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Bounding box must have positive width and height")
    return values


def display_size(page: dict) -> tuple[float, float]:
    x0, y0, x1, y1 = page["crop_box"]
    w, h = x1 - x0, y1 - y0
    return (h, w) if page.get("rotation", 0) % 180 else (w, h)


def pdf_to_display_point(x: float, y: float, page: dict) -> tuple[float, float]:
    x0, y0, x1, y1 = page["crop_box"]
    rotation = page.get("rotation", 0) % 360
    if rotation == 90:
        return y - y0, x - x0
    if rotation == 180:
        return x1 - x, y - y0
    if rotation == 270:
        return y1 - y, x1 - x
    return x - x0, y1 - y


def display_to_pdf_point(x: float, y: float, page: dict) -> tuple[float, float]:
    x0, y0, x1, y1 = page["crop_box"]
    rotation = page.get("rotation", 0) % 360
    if rotation == 90:
        return x0 + y, y0 + x
    if rotation == 180:
        return x1 - x, y0 + y
    if rotation == 270:
        return x1 - y, y1 - x
    return x0 + x, y1 - y


def _envelope(points: list[tuple[float, float]]) -> list[float]:
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def pdf_to_display_bbox(bbox: Iterable[float], page: dict) -> list[float]:
    x0, y0, x1, y1 = validate_bbox(bbox)
    return _envelope([pdf_to_display_point(x, y, page)
                      for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))])


def docling_to_pdf_bbox(bbox: dict, page: dict, docling_size: tuple[float, float]) -> list[float]:
    """Docling provenance is relative to the rotated visible page.

    Scale from its actual page size instead of assuming pixels, points, or that
    its parser applied UserUnit. This also absorbs legitimate backend scaling.
    """
    dw, dh = docling_size
    if dw <= 0 or dh <= 0:
        raise ValueError("Docling page size is missing or invalid")
    left, top, right, bottom = (float(bbox[k]) for k in ("l", "t", "r", "b"))
    if str(bbox.get("coord_origin", "TOPLEFT")).upper().endswith("BOTTOMLEFT"):
        top, bottom = dh - top, dh - bottom
    vw, vh = display_size(page)
    rect = [left * vw / dw, top * vh / dh, right * vw / dw, bottom * vh / dh]
    x0, y0, x1, y1 = validate_bbox(rect)
    return _envelope([display_to_pdf_point(x, y, page)
                      for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))])
