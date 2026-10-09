"""Tests for the CLI / end-to-end pipeline."""

import os
import zipfile
from pathlib import Path

from ck3_strategist.cli import extract_gamestate, main, run_pipeline

FIXTURE = "tests/fixtures/small_gamestate.txt"


def test_run_pipeline_on_fixture():
    summaries, intents, plans = run_pipeline(FIXTURE, tier=1)
    assert intents is None
    assert plans is None
    assert len(summaries) == 2  # king + emperor
    names = {s["ruler_name"] for s in summaries}
    assert "Blaz" in names


def test_run_pipeline_with_mock_llm():
    def mock_llm(prompt: str) -> str:
        return '{"five_year_goal": "X", "focus": "Military", "secondary_goal": "Y", "aggression_deviation": 0}'

    summaries, intents, plans = run_pipeline(FIXTURE, tier=1, llm_call=mock_llm)
    assert intents is not None
    assert plans is not None
    assert len(intents) == len(summaries)
    assert len(plans) == len(summaries)
    assert intents[0].focus == "Military"
    assert plans[0].ruler_scope.startswith("title:")


def test_run_pipeline_falls_back_when_llm_fails(tmp_path):
    def bad_llm(prompt: str) -> str:
        raise RuntimeError("ollama down")

    log_dir = tmp_path / "logs"
    summaries, intents, plans = run_pipeline(
        FIXTURE, tier=1, llm_call=bad_llm, log_dir=str(log_dir)
    )
    assert len(intents) == len(summaries)
    assert all(i.moves == [] for i in intents)  # deterministic fallback
    from ck3_strategist.runlog import load_cycle

    records = load_cycle(log_dir / "cycle_918-11-5.jsonl")
    assert all(r["fallback"] for r in records)


def test_run_pipeline_isolates_one_bad_ruler(tmp_path):
    calls = {"n": 0}

    def flaky(prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return (
                '{"five_year_goal": "X", "focus": "Military", '
                '"secondary_goal": "Y", "aggression_deviation": 0}'
            )
        raise RuntimeError("boom")

    log_dir = tmp_path / "logs"
    summaries, intents, plans = run_pipeline(
        FIXTURE, tier=1, llm_call=flaky, log_dir=str(log_dir)
    )
    assert len(intents) == 2
    from ck3_strategist.runlog import load_cycle

    records = load_cycle(log_dir / "cycle_918-11-5.jsonl")
    assert records[0]["fallback"] is False
    assert records[1]["fallback"] is True


def test_run_pipeline_with_baseline_backend():
    from ck3_strategist.strategist import baseline_intent

    summaries, intents, plans = run_pipeline(
        FIXTURE, tier=1, planner=baseline_intent
    )
    assert intents is not None
    assert plans is not None
    assert all(i.moves == [] for i in intents)


def test_run_pipeline_with_mock_backend_picks_moves():
    from ck3_strategist.strategist import mock_intent

    summaries, intents, plans = run_pipeline(
        FIXTURE, tier=1, planner=mock_intent
    )
    assert intents is not None
    assert plans is not None
    assert any(i.moves for i in intents)


def test_run_pipeline_excludes_player(tmp_path):
    text = Path(FIXTURE).read_text(encoding="utf-8")
    text = text.replace(
        "meta_data={",
        'played_character={\n\tcharacter=16801936\n}\nmeta_data={',
        1,
    )
    save = tmp_path / "save.txt"
    save.write_text(text, encoding="utf-8")
    summaries, intents, plans = run_pipeline(str(save), tier=1)
    names = {s["ruler_name"] for s in summaries}
    assert "Blaz" not in names  # the player's ruler is not planned
    assert "Basileios" in names


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

    def fake_ollama(model="llama3", host="http://localhost:11434", **kwargs):
        return lambda prompt: '{"five_year_goal": "X", "focus": "Diplomacy", "secondary_goal": "Y", "aggression_deviation": -1}'

    monkeypatch.setattr(cli, "ollama_call", fake_ollama, raising=False)
    # patch the import inside main
    import ck3_strategist.strategist as strat

    monkeypatch.setattr(strat, "ollama_call", fake_ollama)
    out = tmp_path / "out2"
    mod_dir = tmp_path / "mod"
    log_dir = tmp_path / "logs"
    main(
        [
            FIXTURE,
            "--output",
            str(out),
            "--llm",
            "ollama",
            "--mod-dir",
            str(mod_dir),
            "--log-dir",
            str(log_dir),
            "--seed",
            "1234",
        ]
    )
    assert (out / "intents.json").exists()
    assert (out / "plans.json").exists()
    effect = mod_dir / "common" / "scripted_effects" / "ck3llm_plans.txt"
    assert effect.exists()
    assert effect.read_bytes().startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    loc = mod_dir / "localization" / "english" / "ck3llm_l_english.yml"
    assert loc.exists()
    assert loc.read_bytes().startswith(b"\xef\xbb\xbf")
    log = log_dir / "cycle_918-11-5.jsonl"
    assert log.exists()
