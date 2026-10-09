from papervault.files import sha256
from papervault.library import Library
from papervault.parsers import render_region


def test_long_unicode_library_import_and_render(tmp_path, pdf_file):
    root = tmp_path / ("长路径 with spaces " * 6).strip() / ("research collection " * 5).strip()
    library = Library(root)
    try:
        paper, _ = library.import_file(pdf_file)
        original = library.pdf(paper["id"])
        assert len(str(original)) > 260
        assert sha256(original) == sha256(pdf_file)
        render_region(original, {"page_index": 0, "bbox": [100, 500, 300, 620]}, tmp_path / "long-path.png", 150)
        assert (tmp_path / "long-path.png").stat().st_size > 100
    finally:
        library.close()
