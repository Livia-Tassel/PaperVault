from pathlib import Path

from papervault.parsers.docling_parser import _metadata


def visible_heading(text, box):
    return {"label": "section_header", "text": text, "location": {
        "page_index": 0, "crop_box": [0, 0, 612, 792], "bbox": box}}


def test_publisher_export_identifier_does_not_hide_the_visible_paper_title():
    # Reproduced in the original PLOS ONE PDF, DOI 10.1371/journal.pone.0031638.
    title = "Fluorescence Cell Imaging and Manipulation Using Conventional Halogen Lamp Microscopy"
    blocks = [visible_heading(title, [58, 693, 508, 733]),
              visible_heading("Abstract", [74, 593, 114, 602])]
    result = _metadata(None, {"metadata": {"title": "pone.0031638 1..8", "author": "", "keywords": ""}},
                       blocks, Path("original.pdf"))
    assert result["title"] == title
    assert result["title_source"] == "layout_heading"


def test_export_identifier_without_visible_title_stays_unknown():
    result = _metadata(None, {"metadata": {"title": "pone.0031638 1..8", "author": "", "keywords": ""}},
                       [], Path("original.pdf"))
    assert result["title"] is None
    assert result["title_source"] == "unknown"


def test_descriptive_pdf_title_with_numeric_range_remains_authoritative():
    title = "Analysis of networks in the 1..8 range"
    blocks = [visible_heading("Supplementary results", [58, 693, 508, 733]),
              visible_heading("Abstract", [74, 593, 114, 602])]
    result = _metadata(None, {"metadata": {"title": title, "author": "", "keywords": ""}},
                       blocks, Path("original.pdf"))
    assert result["title"] == title
    assert result["title_source"] == "pdf_metadata"


def test_title_can_be_grounded_in_prominent_heading_before_abstract():
    def heading(text, box):
        return {"label": "section_header", "text": text, "location": {
            "page_index": 0, "crop_box": [0, 0, 612, 792], "bbox": box}}

    blocks = [heading("Docling Technical Report", [210, 550, 400, 567]),
              heading("Version 1.0", [280, 503, 330, 512]),
              heading("Abstract", [280, 380, 330, 393])]
    result = _metadata(None, {"metadata": {"title": "", "author": "", "keywords": ""}}, blocks, Path("original.pdf"))
    assert result["title"] == "Docling Technical Report"
    assert result["title_source"] == "layout_heading"
