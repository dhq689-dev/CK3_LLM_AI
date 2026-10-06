"""Smoke test: package imports and fixture is present."""

from pathlib import Path

import ck3_strategist


def test_package_imports():
    assert ck3_strategist.__version__ == "0.1.0"


def test_fixture_exists():
    fixture = Path(__file__).parent / "fixtures" / "small_gamestate.txt"
    assert fixture.is_file()
    assert fixture.stat().st_size > 0
