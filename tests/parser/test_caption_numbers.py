import pytest

from papervault.parsers.docling_parser import _caption_number


@pytest.mark.parametrize("kind,caption,expected", [
    ("table", "Table A.1: STS results", "A.1"),
    ("table", "Table B.1: Learning rates", "B.1"),
    ("table", "Table B.2: Training data", "B.2"),
    ("table", "Table B.3: Batch sizes", "B.3"),
    ("table", "Table C.1: Ablation study", "C.1"),
    ("table", "Table D.1: Examples", "D.1"),
    ("table", "Table D.2: More examples", "D.2"),
    ("table", "Table E.1: Reproduction results", "E.1"),
    ("figure", "Figure G.1: Embedding analysis", "G.1"),
    ("figure", "Fig. S1. Additional view", "S1"),
    ("table", "Table A-1. Summary", "A-1"),
    ("table", "Table 12. Ordinary caption", "12"),
    ("figure", "Figure 2(a): Panel detail", "2(a)"),
    ("table", "Table IV: Runtime", "IV"),
    ("table", "Table XL: Late appendix", "XL"),
    ("figure", "图 3.2 实验结果", "3.2"),
    ("table", "表 2 数据", "2"),
    ("figure", "", ""),
    ("figure", "An unnumbered diagram", ""),
    ("table", "Table of contents", ""),
    ("table", "Table XGBoost comparison", ""),
    ("figure", "Configuration 1 is shown", ""),
])
def test_caption_number_preserves_printed_identifiers_without_guessing(kind, caption, expected):
    assert _caption_number(caption, kind) == expected
