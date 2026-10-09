"""Tests for cycle logging (Milestone 20)."""

from ck3_strategist.runlog import cycle_filename, load_cycle, write_cycle


def test_cycle_filename():
    assert cycle_filename("918.11.5") == "cycle_918-11-5.jsonl"
    assert cycle_filename("") == "cycle_unknown.jsonl"


def test_write_and_load_cycle_roundtrip(tmp_path):
    path = tmp_path / "logs" / "cycle.jsonl"
    write_cycle(path, "918.11.5", [{"ruler_name": "Blaz"}])
    write_cycle(path, "918.11.5", [{"ruler_name": "Basileios"}])
    loaded = load_cycle(path)
    assert [e["ruler_name"] for e in loaded] == ["Blaz", "Basileios"]
    assert all(e["date"] == "918.11.5" for e in loaded)


def test_load_cycle_ignores_blank_lines(tmp_path):
    path = tmp_path / "cycle.jsonl"
    path.write_text('{"ruler_name": "A"}\n\n', encoding="utf-8")
    assert [e["ruler_name"] for e in load_cycle(path)] == ["A"]
