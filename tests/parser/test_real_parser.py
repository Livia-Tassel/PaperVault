import csv
import json
import os
from pathlib import Path

import pytest

from papervault.parsers import parse_pdf

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def intersection_over_union(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return intersection / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection)


@pytest.mark.real_parser
@pytest.mark.parametrize("fixture_name", ["academic.pdf", "two-column.pdf"])
def test_real_cpu_figures_tables_and_source_locations(tmp_path, fixture_name):
    models = os.environ.get("PAPERVAULT_TEST_MODELS")
    if not models:
        pytest.skip("Set PAPERVAULT_TEST_MODELS to a verified local model bundle")
    progress = []
    parsed = parse_pdf(FIXTURES / fixture_name, tmp_path, Path(models), progress.append)
    assert parsed["pages_count"] == 2
    assert "Local Research" in parsed["metadata"]["title"]
    figures = [r for r in parsed["resources"] if r["kind"] == "figure"]
    tables = [r for r in parsed["resources"] if r["kind"] == "table"]
    assert figures, "Synthetic vector diagram must be identified as a figure"
    assert tables, "Synthetic ruled data table must be identified as a table"
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    assert len(figures) == len(tables) == 1
    assert intersection_over_union(figures[0]["locations"][0]["bbox"], expected["figure_bbox"]) > 0.5
    assert intersection_over_union(tables[0]["locations"][0]["bbox"], expected["table_bbox"]) > 0.8
    assert any("local pipeline" in r["caption"].lower() for r in figures)
    assert any("Method B" in str(r["table"]["rows"]) for r in tables)
    assert tables[0]["table"]["rows"] == expected["table_rows"]
    for resource in figures + tables:
        assert all(isinstance(path, str) for path in resource["files"].values())
        assert resource["locations"][0]["coordinate_space"] == "pdf_user_space"
        assert resource["locations"][0]["bbox"]
        assert (tmp_path / resource["files"]["png"]).is_file()
    assert "original" not in figures[0]["files"], "Vector graphics must not get a fabricated embedded original"
    with (tmp_path / tables[0]["files"]["csv"]).open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.reader(stream))
    assert (tmp_path / "fulltext.md").is_file()
    assert json.loads((tmp_path / "docling.json").read_text(encoding="utf-8"))
    assert progress[-1]["phase"] == "completed"


@pytest.mark.real_parser
def test_real_embedded_image_and_merged_table_headers(tmp_path):
    models = os.environ.get("PAPERVAULT_TEST_MODELS")
    if not models:
        pytest.skip("Set PAPERVAULT_TEST_MODELS to a verified local model bundle")
    parsed = parse_pdf(FIXTURES / "mixed-assets.pdf", tmp_path, Path(models))
    figures = [r for r in parsed["resources"] if r["kind"] == "figure"]
    tables = [r for r in parsed["resources"] if r["kind"] == "table"]
    assert len(figures) == len(tables) == 1
    assert "Embedded raster" in figures[0]["caption"]
    assert (tmp_path / figures[0]["files"]["png"]).is_file()
    cells = tables[0]["table"]["cells"]
    assert any(c["text"] == "Counts" and c["col_span"] == 2 for c in cells)
    assert any(c["text"] == "Method" and c["row_span"] == 2 for c in cells)
    assert tables[0]["table"]["rows"][-1] == ["Method C", "160", "40"]
    assert 'colspan="2"' in (tmp_path / tables[0]["files"]["html"]).read_text(encoding="utf-8")


@pytest.mark.real_parser
def test_real_scanned_page_reports_no_ocr_without_fabricating_text(tmp_path):
    models = os.environ.get("PAPERVAULT_TEST_MODELS")
    if not models:
        pytest.skip("Set PAPERVAULT_TEST_MODELS to a verified local model bundle")
    parsed = parse_pdf(FIXTURES / "scanned.pdf", tmp_path, Path(models))
    assert parsed["pages_count"] == 1
    assert not any(b["text"].strip() for b in parsed["blocks"])
    assert any("No text was extracted" in warning for warning in parsed["warnings"])


@pytest.mark.real_parser
def test_real_figure_preserves_original_jpeg_bytes_when_match_is_unique(tmp_path):
    models = os.environ.get("PAPERVAULT_TEST_MODELS")
    if not models:
        pytest.skip("Set PAPERVAULT_TEST_MODELS to a verified local model bundle")
    parsed = parse_pdf(FIXTURES / "embedded-jpeg.pdf", tmp_path, Path(models))
    figures = [resource for resource in parsed["resources"] if resource["kind"] == "figure"]
    assert len(figures) == 1
    figure = figures[0]
    assert figure["original_image"]["match_iou"] >= 0.8
    assert figure["original_image"]["format"] == "jpeg"
    assert figure["original_image"]["encoding_preserved"] is True
    assert (tmp_path / figure["files"]["original"]).read_bytes() == (FIXTURES / "embedded-original.jpg").read_bytes()
    assert (tmp_path / figure["files"]["png"]).is_file()
