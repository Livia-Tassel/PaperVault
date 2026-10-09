from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from papervault.library import Library


@pytest.fixture
def pdf_file(tmp_path):
    path = tmp_path / "中文 paper.pdf"
    doc = canvas.Canvas(str(path))
    doc.setTitle("PaperVault fixture")
    doc.drawString(70, 750, "A real PDF fixture for import and file integrity tests")
    doc.rect(100, 500, 200, 120)
    doc.drawString(100, 480, "Figure 1: KV Cache architecture")
    doc.save()
    return path


@pytest.fixture
def library(tmp_path):
    lib = Library(tmp_path / "资料库 with spaces")
    yield lib
    lib.close()


def publish_fixture(library, paper_id, caption="深度学习 KV Cache architecture", table=False, bbox=None):
    """Storage unit-test input, deliberately not a parser/accuracy acceptance fixture."""
    from PIL import Image
    from papervault.files import uid
    from papervault.tables import write_table
    with library.db.transaction() as con:
        job = con.execute("SELECT * FROM jobs WHERE paper_id=? AND status='queued' ORDER BY created_at DESC", (paper_id,)).fetchone()
        con.execute("UPDATE jobs SET status='running' WHERE id=?", (job["id"],))
    staging = library.root / ".staging" / uid()
    staging.mkdir()
    Image.new("RGB", (200, 100), "white").save(staging / "figure.png")
    (staging / "fulltext.md").write_text("论文正文 深度学习\n![Figure](figure.png)", encoding="utf-8")
    (staging / "structure.json").write_text("{}")
    (staging / "docling.json").write_text("{}")
    files = {"png": "figure.png", "thumbnail": "figure.png"}
    data = {"rows": [["Metric", "Value"], ["TTFT", "1.2e-3"]], "header_rows": 1, "cells": []}
    if table:
        for key, value in write_table(data, staging, caption).items():
            files[key] = Path(value).relative_to(staging).as_posix()
    location = {"page_index": 0, "bbox": bbox or [100, 500, 300, 620]}
    result = {"metadata": {"title": "Test paper", "authors": ["Fixture Author"]}, "pages_count": 1,
              "engine": {"name": "unit-test-fixture", "version": "1"},
              "blocks": [{"text": "深度学习 improves latency", "label": "paragraph", "location": location}],
              "resources": [{"id": uid(), "kind": "table" if table else "figure", "name": "Resource 1",
                             "caption": caption, "locations": [location], "files": files,
                             "table": data if table else None}], "warnings": []}
    assert library.publish(job["id"], job["attempt_token"], staging, result)
    return library.resources(paper_id=paper_id)["items"][0]
