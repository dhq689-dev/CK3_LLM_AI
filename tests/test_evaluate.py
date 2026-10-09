"""Tests for observer-mode evaluation (Milestone 20)."""

from pathlib import Path

from ck3_strategist.evaluate import compare, load_graph, realm_growth, wars_delta

FIXTURE = Path("tests/fixtures/small_gamestate.txt")

_NEW_WAR = """900000001={
	attacker={
		participants={
		}
	}
	defender={
		participants={
		}
	}
	start_date=919.2.1
	casus_belli={
		type=pressed_claim_cb
		targeted_titles={ 1 }
		attacker=16801936
		defender=47802
	}
}
"""


def _after_save(tmp_path):
    """A save one cycle later: a war for c_colmar starts and it shifts realm."""
    text = FIXTURE.read_text(encoding="utf-8")
    text = text.replace(
        "wars={\nactive_wars={\n", "wars={\nactive_wars={\n" + _NEW_WAR
    )
    text = text.replace(
        "key=c_colmar\n\tholder=47802\n\tde_facto_liege=0",
        "key=c_colmar\n\tholder=47802\n\tde_facto_liege=3",
    )
    path = tmp_path / "after.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_wars_delta_detects_started_war(tmp_path):
    before = load_graph(FIXTURE)
    after = load_graph(_after_save(tmp_path))
    started, ended = wars_delta(before, after)
    assert started == [900000001]
    assert ended == []


def test_realm_growth_reflects_realm_shift(tmp_path):
    before = load_graph(FIXTURE)
    after = load_graph(_after_save(tmp_path))
    growth = {r.ruler_name: r.delta for r in realm_growth(before, after)}
    assert growth["Basileios"] == 1
    assert growth["Blaz"] == -1


def test_plan_adherence_scores_war_moves(tmp_path):
    records = [
        {
            "ruler_name": "Blaz",
            "intent": {
                "moves": [
                    {"kind": "war", "ref": "c_colmar"},
                    {"kind": "war", "ref": "k_venice"},
                ]
            },
        }
    ]
    ev = compare(FIXTURE, _after_save(tmp_path), records)
    assert ev.wars_started == [900000001]
    rows = {(a.ref, a.adhered) for a in ev.adherence}
    assert rows == {("c_colmar", True), ("k_venice", False)}
    assert ev.adherence_rate == 0.5


def test_compare_without_records_has_no_adherence(tmp_path):
    ev = compare(FIXTURE, _after_save(tmp_path))
    assert ev.adherence == []
    assert ev.adherence_rate == 0.0
    assert "wars_started" in ev.to_dict()


def test_compare_arms_scores_each(tmp_path):
    from ck3_strategist.evaluate import compare_arms

    llm_after = _after_save(tmp_path)
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    arms = compare_arms(FIXTURE, {"llm": llm_after, "baseline": baseline})
    assert set(arms) == {"llm", "baseline"}
    assert arms["llm"].wars_started == [900000001]
    assert arms["baseline"].wars_started == []
