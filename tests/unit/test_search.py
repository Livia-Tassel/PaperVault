import sqlite3

import pytest

from papervault.search import compile_query, find, index_entry, snippet, tokenize


@pytest.mark.parametrize("query", ["深", "深度", "深度 KV", "Cache架构", "architecture", '"深度"'])
def test_mixed_query_matches_original(query):
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE VIRTUAL TABLE search_entries USING fts5(entity_id UNINDEXED,kind UNINDEXED,"
                "paper_id UNINDEXED,title UNINDEXED,raw_text UNINDEXED,location_json UNINDEXED,tokens)")
    index_entry(con, "r", "figure", "p", "Caption", "这是深度学习 KV Cache架构 architecture")
    assert find(con, query)[0]["id"] == "r"
    con.close()


def test_phrases_do_not_match_disconnected_characters():
    assert compile_query("深度 KV") == '"深 度" AND "kv"'
    assert tokenize("Cache架构 1.2e-3") == "cache 架 构 1 2e 3"


def test_highlight_is_text_and_preserves_unicode():
    result = snippet("🙂 <script> 深度学习", "深度")
    assert "".join(part["text"] for part in result) == "🙂 <script> 深度学习"
    assert [part["text"] for part in result if part["matched"]] == ["深度"]


def test_fts_operators_are_literal_words():
    assert compile_query('" OR *') == '"or"'
    assert compile_query("***") == ""
