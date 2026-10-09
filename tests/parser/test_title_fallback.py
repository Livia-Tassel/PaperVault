from pathlib import Path

from papervault.parsers.docling_parser import _metadata


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
