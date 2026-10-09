import hashlib
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import FloatObject, NameObject, RectangleObject

from papervault.parsers.pdfium import extract_embedded_image

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
LOCATION = {"page_index": 0, "bbox": [74, 300, 538, 546.5]}


@pytest.mark.parametrize("rotated", [False, True])
def test_original_jpeg_bytes_are_preserved_for_unique_matching_image(tmp_path, rotated):
    source = FIXTURES / "embedded-jpeg.pdf"
    if rotated:
        page = PdfReader(source).pages[0]
        page.rotate(90)
        page.cropbox = RectangleObject([20, 20, 592, 772])
        page[NameObject("/UserUnit")] = FloatObject(2)
        writer = PdfWriter()
        writer.add_page(page)
        source = tmp_path / "rotated.pdf"
        writer.write(source)
    original = extract_embedded_image(source, LOCATION, tmp_path / "original")
    assert original["format"] == "jpeg"
    assert original["encoding_preserved"] is True
    assert original["match_iou"] == pytest.approx(1)
    assert hashlib.sha256(Path(original["path"]).read_bytes()).digest() == hashlib.sha256(
        (FIXTURES / "embedded-original.jpg").read_bytes()).digest()
    with Image.open(original["path"]) as image:
        assert image.format == "JPEG"
        assert image.size == (640, 340)


def test_ambiguous_overlapping_image_objects_are_not_associated(tmp_path):
    assert extract_embedded_image(FIXTURES / "embedded-jpeg-ambiguous.pdf", LOCATION, tmp_path / "original") is None
    assert not list(tmp_path.glob("original.*"))


def test_partial_match_and_vector_figure_have_no_original_image(tmp_path):
    assert extract_embedded_image(FIXTURES / "embedded-jpeg.pdf", {"page_index": 0, "bbox": [74, 300, 150, 350]},
                                  tmp_path / "partial") is None
    assert extract_embedded_image(FIXTURES / "academic.pdf", {"page_index": 0, "bbox": [83, 364, 531, 453]},
                                  tmp_path / "vector") is None


def test_flate_image_is_not_mislabeled_as_preserved_original_encoding(tmp_path):
    original = extract_embedded_image(FIXTURES / "mixed-assets.pdf",
                                      {"page_index": 0, "bbox": [96, 408, 516, 628.5]}, tmp_path / "flate")
    assert original["format"] == "png"
    assert original["encoding_preserved"] is False
    assert "FlateDecode" in original["source_filters"]
    with Image.open(original["path"]) as image:
        assert image.format == "PNG"
        assert image.size == (800, 420)
