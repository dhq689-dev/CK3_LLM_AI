"""Validate translation names against a ``script_docs`` dump (review v4 §2).

The hard actions in ``reference_data/translation.json`` have never run in-game,
so their effect names are unverified. This module is the correctness gate the
review asked for: given CK3's ``script_docs`` output (normalised to JSON), it
reports every effect name the generator would emit that does not exist.

We cannot run ``script_docs`` here, so the dump is optional and the checks are
only as good as the dump. Expected normalised shape::

    {"effects": ["start_war", ...], "triggers": [...], "modifiers": [...]}

A raw text dump must first be converted to that shape; the adapter is left until
a real dump from the target version exists. Run directly::

    python -m ck3_strategist.validate path/to/script_docs.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .translation import load_translation_table


def load_dump(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize(dump: dict) -> dict[str, set[str]]:
    return {
        key: {str(name) for name in (value or [])}
        for key, value in (dump or {}).items()
    }


def check_effects(table: dict, dump: dict) -> dict[str, str]:
    """Return ``{move kind: effect}`` for effect names absent from the dump."""
    known = normalize(dump).get("effects", set())
    missing: dict[str, str] = {}
    for kind, spec in (table.get("actions") or {}).items():
        effect = str(spec.get("effect", ""))
        if effect and effect not in known:
            missing[kind] = effect
    return missing


def check_tiers(table: dict, dump: dict) -> list[str]:
    """Tier modifier names absent from the dump (only meaningful with the mod
    loaded during ``script_docs``)."""
    from .translation import all_tier_names

    known = normalize(dump).get("modifiers", set())
    return sorted(t for t in all_tier_names(table) if t not in known)


def check(table: dict, dump: dict) -> dict:
    missing_effects = check_effects(table, dump)
    report: dict = {}
    if missing_effects:
        report["effects"] = missing_effects
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ck3_strategist.validate",
        description="Check translation.json names against a script_docs dump.",
    )
    parser.add_argument("dump", help="normalised script_docs JSON")
    parser.add_argument(
        "--table",
        default=None,
        help="translation table to check (default: reference_data/translation.json)",
    )
    args = parser.parse_args(argv)

    table = load_translation_table(args.table)
    report = check(table, load_dump(args.dump))
    if report:
        print(json.dumps(report, indent=2))
        sys.exit(1)
    print("all translation names found in the dump")


if __name__ == "__main__":
    main()
