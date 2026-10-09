from pathlib import Path

from pypdf import PdfReader


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_mixed_fixture_contains_real_raster_and_native_merged_table_text():
    page = PdfReader(FIXTURES / "mixed-assets.pdf").pages[0]
    assert list(page.images)
    text = page.extract_text()
    assert all(word in text for word in ("Counts", "Train", "Test", "Method C", "160"))


def test_scanned_fixture_has_no_native_text():
    page = PdfReader(FIXTURES / "scanned.pdf").pages[0]
    assert not page.extract_text().strip()
    assert list(page.images)
