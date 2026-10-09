"""Generate original, redistributable PDFs used by the parser regression suite."""
from __future__ import annotations

import io
import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import FloatObject, NameObject, RectangleObject

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def lines(canvas, text, x, y, width=90, font="Times-Roman", size=10):
    import textwrap
    canvas.setFont(font, size)
    for line in textwrap.wrap(text, width):
        canvas.drawString(x, y, line)
        y -= size * 1.35
    return y


def make_paper(path: Path, two_columns=False):
    c = Canvas(str(path), pagesize=(612, 792), invariant=1)
    c.setTitle("Local Research Asset Extraction")
    c.setAuthor("Alice Chen; Bob Smith")
    c.setSubject("An original synthetic benchmark for PaperVault")
    c.setKeywords("document analysis, local software, research")
    c.setFont("Times-Bold", 20)
    c.drawCentredString(306, 745, "Local Research Asset Extraction")
    c.setFont("Times-Roman", 11)
    c.drawCentredString(306, 720, "Alice Chen and Bob Smith")
    c.drawCentredString(306, 704, "Example Research Laboratory, 2026")
    c.setFont("Times-Bold", 12)
    c.drawString(54, 675, "Abstract")
    lines(c, "We present a local document analysis system that preserves scientific figures and tables. "
          "The method detects complete vector diagrams and associates captions with structured table data. "
          "All experiments use synthetic documents created for reproducible software testing.", 54, 657)
    c.setFont("Times-Bold", 12)
    c.drawString(54, 590, "1 Introduction")
    paragraph = ("Research papers contain visual evidence that is difficult to find with text search alone. "
                 "Our approach retains source coordinates and extracts reusable figures and tables. "
                 "Figure 1 illustrates the analysis pipeline, while Table 1 reports example results.")
    if two_columns:
        lines(c, paragraph, 54, 570, width=44)
        lines(c, paragraph, 320, 570, width=44)
    else:
        lines(c, paragraph, 54, 570)
    # A true vector figure: filled rectangles, arrows, and text, no image XObject.
    figure_box = [72, 350, 540, 470]
    c.setStrokeColor(HexColor("#16324f"))
    for x, title, subtitle, color in [(85, "PDF INPUT", "Original document", "#dbeafe"),
                                      (245, "ANALYSIS", "Layout + tables", "#ccfbf1"),
                                      (405, "LIBRARY", "Searchable assets", "#fef3c7")]:
        c.setFillColor(HexColor(color))
        c.roundRect(x, 365, 125, 85, 10, stroke=1, fill=1)
        c.setFillColor(HexColor("#16324f"))
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x + 62.5, 415, title)
        c.setFont("Helvetica", 9)
        c.drawCentredString(x + 62.5, 393, subtitle)
    for x in (210, 370):
        c.line(x, 407, x + 32, 407)
        c.line(x + 32, 407, x + 25, 412)
        c.line(x + 32, 407, x + 25, 402)
    c.setFillColor(HexColor("#111111"))
    lines(c, "Figure 1: A fully local pipeline for extracting reusable research assets.", 72, 337, width=87)
    c.setFont("Times-Bold", 12)
    c.drawString(54, 295, "2 Results")
    lines(c, "The proposed workflow stores structured values as well as a faithful image of each table.", 54, 276)
    c.setFont("Times-Roman", 10)
    c.drawString(110, 240, "Table 1: Invented values for testing table extraction only.")
    data = [["Method", "Figures", "Tables", "Example value"],
            ["Method A", "8", "6", "0.70"],
            ["Method B", "10", "9", "0.95"],
            ["Reference", "10", "10", "1.00"]]
    x0, y0, colw, rowh = 100, 119, 103, 25
    for row_index, row in enumerate(data):
        yy = y0 + (len(data) - row_index - 1) * rowh
        if row_index == 0:
            c.setFillColor(HexColor("#e2e8f0"))
            c.rect(x0, yy, colw * 4, rowh, fill=1, stroke=0)
        c.setFillColor(HexColor("#111111"))
        c.setFont("Times-Bold" if row_index == 0 else "Times-Roman", 10)
        for col_index, value in enumerate(row):
            c.drawString(x0 + col_index * colw + 9, yy + 8, value)
    c.setStrokeColor(HexColor("#334155"))
    for r in range(5):
        c.line(x0, y0 + r * rowh, x0 + colw * 4, y0 + r * rowh)
    for col in range(5):
        c.line(x0 + col * colw, y0, x0 + col * colw, y0 + 100)
    c.setFont("Times-Roman", 9)
    c.drawCentredString(306, 40, "1")
    c.showPage()
    c.setFont("Times-Bold", 14)
    c.drawString(54, 735, "3 Discussion")
    lines(c, "Every extracted asset remains connected to its source page. Users may correct a caption or "
          "crop without changing the source PDF. This benchmark is intentionally small and does not "
          "represent the extraction quality of arbitrary academic papers.", 54, 710)
    c.setFont("Times-Bold", 12)
    c.drawString(54, 620, "References")
    lines(c, "[1] Chen, A. and Smith, B. Local Research Asset Extraction. Synthetic Test Proceedings, 2026.", 54, 600)
    c.save()
    return {"page_count": 2, "figure_bbox": figure_box, "table_bbox": [100, 119, 512, 219],
            "table_rows": data, "title": "Local Research Asset Extraction"}


def make_mixed_assets(path: Path):
    chart = Image.new("RGB", (800, 420), "white")
    draw = ImageDraw.Draw(chart)
    font = ImageFont.load_default(size=24)
    draw.text((235, 16), "SYNTHETIC OBSERVATIONS", fill="#17324d", font=font)
    for index, value in enumerate((40, 80, 120, 160)):
        y = 350 - index * 75
        draw.line((90, y, 730, y), fill="#cbd5e1", width=2)
        draw.text((25, y - 13), str(value), fill="#334155", font=font)
    for index, height in enumerate((125, 230, 170, 265)):
        x = 145 + index * 145
        draw.rectangle((x, 350 - height, x + 75, 350), fill=("#2563eb", "#0d9488", "#f59e0b", "#7c3aed")[index])
        draw.text((x + 19, 365), chr(65 + index), fill="#334155", font=font)
    draw.line((90, 65, 90, 350, 730, 350), fill="#334155", width=3)
    c = Canvas(str(path), pagesize=(612, 792), invariant=1)
    c.setTitle("Embedded Images and Merged Headers")
    c.setAuthor("PaperVault Synthetic Fixture Authors")
    c.setFont("Times-Bold", 18)
    c.drawCentredString(306, 742, "Embedded Images and Merged Headers")
    c.setFont("Times-Bold", 12)
    c.drawString(54, 700, "1 Embedded image")
    lines(c, "The bar chart below is an embedded raster image, not native PDF vector graphics. "
          "Its values are invented only to test extraction and are not product measurements.", 54, 680)
    c.drawImage(ImageReader(chart), 96, 408, width=420, height=220.5)
    lines(c, "Figure 1: Embedded raster chart containing four synthetic observations.", 72, 385)
    c.setFont("Times-Bold", 12)
    c.drawString(54, 345, "2 Merged table headers")
    lines(c, "Table 1 has a column group and a row-spanning first header cell. No recognition "
          "benchmark results are represented by these invented counts.", 54, 325)
    c.setFont("Times-Roman", 10)
    c.drawCentredString(306, 288, "Table 1: Synthetic counts with merged row and column headers.")
    x0, x1, x2, x3 = 72, 228, 384, 540
    bottom, top, row_height = 115, 265, 30
    c.setFillColor(HexColor("#dbeafe"))
    c.rect(x0, top - 60, x3 - x0, 60, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#334155"))
    c.rect(x0, bottom, x3 - x0, top - bottom, fill=0, stroke=1)
    c.line(x1, bottom, x1, top)
    c.line(x2, bottom, x2, top - row_height)
    c.line(x1, top - row_height, x3, top - row_height)
    for index in (2, 3, 4):
        c.line(x0, top - index * row_height, x3, top - index * row_height)
    c.setFillColor(HexColor("#111111"))
    c.setFont("Times-Bold", 12)
    c.drawCentredString(150, 231, "Method")
    c.drawCentredString(384, 246, "Counts")
    c.drawCentredString(306, 216, "Train")
    c.drawCentredString(462, 216, "Test")
    c.setFont("Times-Roman", 11)
    for index, row in enumerate([["Method A", "120", "30"], ["Method B", "140", "35"], ["Method C", "160", "40"]]):
        for x, value in zip((150, 306, 462), row):
            c.drawCentredString(x, 186 - index * row_height, value)
    c.save()
    chart.close()


def make_scanned_page(path: Path):
    page = Image.new("RGB", (900, 1200), "white")
    draw = ImageDraw.Draw(page)
    draw.text((85, 100), "Scanned page fixture", fill="black", font=ImageFont.load_default(size=46))
    for index, text in enumerate(("This page contains no native PDF text.",
                                  "OCR is intentionally disabled in the first release.",
                                  "The application must keep the source and explain the limitation.")):
        draw.text((85, 230 + index * 75), text, fill="black", font=ImageFont.load_default(size=24))
    c = Canvas(str(path), pagesize=(612, 792), invariant=1)
    c.drawImage(ImageReader(page), 0, 0, width=612, height=792)
    c.save()
    page.close()


def make_jpeg_assets():
    image = Image.new("RGB", (640, 340), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, 638, 338), outline="#334155", width=3)
    font = ImageFont.load_default(size=19)
    for index in range(1, 5):
        draw.line((42, index * 60, 615, index * 60), fill="#cbd5e1", width=2)
    draw.line((42, 18, 42, 290, 615, 290), fill="#334155", width=3)
    for index, height in enumerate((125, 205, 165, 245)):
        x = 85 + index * 135
        draw.rectangle((x, 290 - height, x + 68, 290), fill=("#2563eb", "#0d9488", "#d97706", "#7c3aed")[index])
        draw.text((x + 24, 307), chr(65 + index), fill="#334155", font=font)
    original = ROOT / "embedded-original.jpg"
    image.save(original, format="JPEG", quality=91, subsampling=0)
    image.close()
    for ambiguous in (False, True):
        path = ROOT / ("embedded-jpeg-ambiguous.pdf" if ambiguous else "embedded-jpeg.pdf")
        c = Canvas(str(path), pagesize=(612, 792), invariant=1)
        c.setTitle("Original Embedded JPEG Fixture")
        c.setFont("Times-Bold", 18)
        c.drawCentredString(306, 735, "Original Embedded JPEG Fixture")
        c.setFont("Times-Bold", 12)
        c.drawString(54, 680, "1 Raster figure")
        lines(c, "This PDF embeds a JPEG image without changing its encoded bytes. The diagram is "
              "synthetic and its four values are not product measurements. Original-format extraction "
              "must only associate an image when its geometric match is unique.", 54, 659)
        for _ in range(2 if ambiguous else 1):
            c.drawImage(ImageReader(str(original)), 74, 300, width=464, height=246.5)
        lines(c, "Figure 1: A directly embedded JPEG with four synthetic values.", 74, 280)
        c.save()


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    truth = make_paper(ROOT / "academic.pdf")
    make_paper(ROOT / "two-column.pdf", two_columns=True)
    make_mixed_assets(ROOT / "mixed-assets.pdf")
    make_scanned_page(ROOT / "scanned.pdf")
    make_jpeg_assets()
    # Exact geometry fixture with nonzero page origin, crop offset, rotations and UserUnit.
    buffer = io.BytesIO()
    c = Canvas(buffer, pagesize=(400, 500), invariant=1)
    c.setFillColor(HexColor("#ef4444"))
    c.rect(100, 130, 80, 60, fill=1, stroke=0)
    c.setFillColor(HexColor("#2563eb"))
    c.rect(210, 280, 55, 70, fill=1, stroke=0)
    c.save()
    writer = PdfWriter()
    for rotation in (0, 90, 180, 270):
        page = PdfReader(io.BytesIO(buffer.getvalue())).pages[0]
        page.mediabox = RectangleObject([20, 30, 400, 500])
        page.cropbox = RectangleObject([50, 70, 350, 450])
        page[NameObject("/UserUnit")] = FloatObject(2)
        if rotation:
            page.rotate(rotation)
        writer.add_page(page)
    with (ROOT / "geometry.pdf").open("wb") as f:
        writer.write(f)
    encrypted = PdfWriter()
    encrypted.add_page(PdfReader(ROOT / "academic.pdf").pages[0])
    encrypted.encrypt("papervault-test-password")
    with (ROOT / "encrypted.pdf").open("wb") as f:
        encrypted.write(f)
    (ROOT / "corrupt.pdf").write_bytes(b"%PDF-1.7\nIntentionally invalid parser fixture\n")
    (ROOT / "expected.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    (ROOT / "LICENSE.txt").write_text("All PDF and image fixtures were generated by scripts/generate_fixtures.py.\n"
                                    "These original synthetic documents are released under CC0-1.0.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
