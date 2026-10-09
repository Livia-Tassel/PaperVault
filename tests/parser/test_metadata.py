from pathlib import Path

from papervault.parsers.docling_parser import _metadata


def info(**metadata):
    return {"metadata": {"title": "", "author": "", "keywords": "", **metadata}}


def block(text, label="text", page_index=0, **extra):
    return {"text": text, "label": label, "location": {"page_index": page_index, "bbox": None}, **extra}


def test_unknown_title_and_reference_year_are_not_fabricated():
    metadata = _metadata(None, info(), [block("Prior work from 1998 established this result."),
                                       block("10.1000/not-the-paper", "reference", page_index=1)], Path("original.pdf"))
    assert metadata["title"] is None
    assert metadata["year"] is None
    assert not metadata["doi"]


def test_explicit_frontmatter_and_navigable_sections():
    metadata = _metadata(None, info(author="Alice Chen; Bob Smith"),
                         [block("A Real Paper", "title"), block("Published: 2024; DOI: 10.1000/paper"),
                          block("1 Introduction", "section_header", level=2)], Path("original.pdf"))
    assert metadata["authors"] == ["Alice Chen", "Bob Smith"]
    assert metadata["year"] == 2024
    assert metadata["doi"] == "10.1000/paper"
    assert metadata["sections"] == [{"title": "1 Introduction", "level": 2,
                                     "location": {"page_index": 0, "bbox": None}}]
