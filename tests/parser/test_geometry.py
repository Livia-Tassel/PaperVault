from pathlib import Path

import pytest
from PIL import Image

from papervault.parsers.geometry import docling_to_pdf_bbox, pdf_to_display_bbox
from papervault.parsers.pdfium import inspect_pdf, render_region

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_canonical_round_trip_with_crop_offset(rotation):
    page = {"crop_box": [50, 70, 350, 450], "rotation": rotation}
    original = [100, 130, 180, 190]
    left, top, right, bottom = pdf_to_display_bbox(original, page)
    dw, dh = (380, 300) if rotation % 180 else (300, 380)
    prov = {"l": left * 2, "t": top * 2, "r": right * 2, "b": bottom * 2,
            "coord_origin": "TOPLEFT"}
    assert docling_to_pdf_bbox(prov, page, (dw * 2, dh * 2)) == pytest.approx(original)
    prov.update(t=(dh - top) * 2, b=(dh - bottom) * 2, coord_origin="BOTTOMLEFT")
    assert docling_to_pdf_bbox(prov, page, (dw * 2, dh * 2)) == pytest.approx(original)


@pytest.mark.parametrize("page_index", [0, 1, 2, 3])
def test_real_rotated_crop_renders_the_selected_red_rectangle(tmp_path, page_index):
    path = FIXTURES / "geometry.pdf"
    info = inspect_pdf(path)
    assert info["pages"][page_index]["user_unit"] == 2
    destination = tmp_path / "crop.png"
    render_region(path, {"page_index": page_index, "bbox": [101, 131, 179, 189]}, destination, dpi=72)
    with Image.open(destination) as image:
        expected = (116, 156) if page_index % 2 else (156, 116)
        assert abs(image.width - expected[0]) <= 1
        assert abs(image.height - expected[1]) <= 1
        red, green, blue = image.convert("RGB").getpixel((image.width // 2, image.height // 2))
        assert red > 220 and green < 100 and blue < 100


@pytest.mark.parametrize("filename", ["corrupt.pdf", "encrypted.pdf"])
def test_invalid_pdfs_fail_with_no_output(tmp_path, filename):
    with pytest.raises(Exception):
        render_region(FIXTURES / filename, {"page_index": 0}, tmp_path / "invalid.png")
    assert not (tmp_path / "invalid.png").exists()


def test_outside_crop_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        render_region(FIXTURES / "geometry.pdf", {"page_index": 0, "bbox": [0, 0, 10, 10]},
                      tmp_path / "outside.png")
