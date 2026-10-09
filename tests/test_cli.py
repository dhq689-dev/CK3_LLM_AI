"""Tests for the CLI / end-to-end pipeline."""

import os
import zipfile
from pathlib import Path

from ck3_strategist.cli import extract_gamestate, main, run_pipeline

FIXTURE = "tests/fixtures/small_gamestate.txt"


def test_run_pipeline_on_fixture():
    summaries, intents = run_pipeline(FIXTURE, tier=1)
    assert intents is None
    assert len(summaries) == 2  # king + emperor
    names = {s["ruler_name"] for s in summaries}
    assert "Blaz" in names


def test_run_pipeline_with_mock_llm():
    def mock_llm(prompt: str) -> str:
        return '{"five_year_goal": "X", "focus": "Military", "secondary_goal": "Y", "aggression_deviation": 0}'

    summaries, intents = run_pipeline(FIXTURE, tier=1, llm_call=mock_llm)
    assert intents is not None
    assert len(intents) == len(summaries)
    assert intents[0].focus == "Military"


def test_extract_gamestate_plaintext():
    path, is_temp = extract_gamestate(FIXTURE)
    assert path == FIXTURE
    assert is_temp is False


def test_extract_gamestate_from_zip(tmp_path):
    zip_path = tmp_path / "save.ck3"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(FIXTURE, "gamestate")
    path, is_temp = extract_gamestate(str(zip_path))
    assert is_temp is True
    assert Path(path).exists()
    os.unlink(path)


def test_main_writes_output(tmp_path):
    out = tmp_path / "out"
    main([FIXTURE, "--output", str(out), "--tier", "1"])
    assert (out / "summaries.json").exists()
    assert not (out / "intents.json").exists()  # no LLM requested


def test_main_with_llm_uses_injected_call(monkeypatch, tmp_path):
    from ck3_strategist import cli

    def fake_ollama(model="llama3", host="http://localhost:11434"):
        return lambda prompt: '{"five_year_goal": "X", "focus": "Diplomacy", "secondary_goal": "Y", "aggression_deviation": -1}'

    monkeypatch.setattr(cli, "ollama_call", fake_ollama, raising=False)
    # patch the import inside main
    import ck3_strategist.strategist as strat

    monkeypatch.setattr(strat, "ollama_call", fake_ollama)
    out = tmp_path / "out2"
    main([FIXTURE, "--output", str(out), "--llm", "ollama"])
    assert (out / "intents.json").exists()
