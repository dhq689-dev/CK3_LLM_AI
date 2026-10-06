"""Tests for the section indexer."""

from ck3_strategist.indexer import SectionIndex


def test_index_fixture(tmp_path):
    fixture = "tests/fixtures/small_gamestate.txt"
    idx = SectionIndex.build(fixture)

    for name in ("meta_data", "landed_titles", "dynasties", "living", "wars"):
        assert name in idx, f"missing section {name}"

    # offsets are monotonically increasing
    ordered = [idx.get(n).byte_offset for n in
               ("meta_data", "landed_titles", "dynasties", "living", "wars")]
    assert ordered == sorted(ordered)

    # line numbers are positive and increasing
    lines = [idx.get(n).line for n in
             ("meta_data", "landed_titles", "dynasties", "living", "wars")]
    assert all(l > 0 for l in lines)
    assert lines == sorted(lines)


def test_get_returns_none_for_unknown():
    idx = SectionIndex.build("tests/fixtures/small_gamestate.txt")
    assert idx.get("nonexistent") is None
    assert "nonexistent" not in idx


def test_byte_range(tmp_path):
    import os
    fixture = "tests/fixtures/small_gamestate.txt"
    idx = SectionIndex.build(fixture)
    size = os.path.getsize(fixture)

    start, end = idx.byte_range("landed_titles", size)
    assert 0 <= start < end <= size


def test_column_zero_entries_not_indexed():
    # Title/character entries sit at column 0 in the real save; they must not
    # be mistaken for top-level sections.
    idx = SectionIndex.build("tests/fixtures/small_gamestate.txt")
    names = {s.name for s in idx._ordered}
    assert "0" not in names
    assert "16801936" not in names
    assert "469762048" not in names
    # only the real top-level sections are present
    assert names == {
        "meta_data",
        "landed_titles",
        "dynasties",
        "living",
        "wars",
        "character_memory_manager",
    }
