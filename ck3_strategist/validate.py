"""Validate translation names against a ``script_docs`` dump (review v4 §2/CG1).

CK3's ``script_docs`` console command writes ``effects.log``, ``triggers.log``
and ``modifiers.log`` into the user ``logs`` folder. This module reads those
(``--logs``) or a normalised JSON dump (``--dump``) and checks every game name
the translation layer relies on against them. The names are declared in
``reference_data/translation.json`` under ``validated_names`` so this stays a
data check, not a parser of our own generated script.

Run directly::

    python -m ck3_strategist.validate --logs "...\\Crusader Kings III\\logs"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .translation import load_translation_table

# block headers look like "<name> - description"
_NAME_LINE = re.compile(r"^([a-z_][a-z0-9_]*)\s+-\s")


def load_dump(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_named_log(path: str | Path) -> set[str]:
    """Names from an ``effects.log`` / ``triggers.log`` (``<name> - ...``)."""
    names: set[str] = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _NAME_LINE.match(line)
            if m:
                names.add(m.group(1))
    return names


def parse_modifier_log(path: str | Path) -> set[str]:
    """Names from ``modifiers.log`` (``Tag: <name>``)."""
    names: set[str] = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("Tag: "):
                names.add(line[5:].strip())
    return names


def load_script_docs(logs_dir: str | Path) -> dict:
    """Build the normalised dump from a CK3 ``logs`` folder."""
    d = Path(logs_dir)
    return {
        "effects": sorted(parse_named_log(d / "effects.log")),
        "triggers": sorted(parse_named_log(d / "triggers.log")),
        "modifiers": sorted(parse_modifier_log(d / "modifiers.log")),
    }


def normalize(dump: dict) -> dict[str, set[str]]:
    return {
        key: {str(name) for name in (value or [])}
        for key, value in (dump or {}).items()
    }


def _declared(table: dict, kind: str) -> list[str]:
    return [
        str(n)
        for n in ((table.get("validated_names") or {}).get(kind) or [])
    ]


def missing_effects(table: dict, dump: dict) -> list[str]:
    known = normalize(dump).get("effects", set())
    return sorted(n for n in _declared(table, "effects") if n not in known)


def missing_triggers(table: dict, dump: dict) -> list[str]:
    known = normalize(dump).get("triggers", set())
    return sorted(n for n in _declared(table, "triggers") if n not in known)


def check_tiers(table: dict, dump: dict) -> list[str]:
    """Tier modifier names absent from the dump (only meaningful with the mod
    loaded during ``script_docs``)."""
    from .translation import all_tier_names

    known = normalize(dump).get("modifiers", set())
    return sorted(t for t in all_tier_names(table) if t not in known)


def check(table: dict, dump: dict) -> dict:
    report: dict = {}
    effects = missing_effects(table, dump)
    if effects:
        report["effects"] = effects
    triggers = missing_triggers(table, dump)
    if triggers:
        report["triggers"] = triggers
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ck3_strategist.validate",
        description="Check translation names against a script_docs dump.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--logs", help="CK3 logs folder containing effects.log etc.")
    source.add_argument("--dump", help="normalised script_docs JSON")
    parser.add_argument(
        "--table",
        default=None,
        help="translation table to check (default: reference_data/translation.json)",
    )
    args = parser.parse_args(argv)

    dump = load_script_docs(args.logs) if args.logs else load_dump(args.dump)
    table = load_translation_table(args.table)
    report = check(table, dump)
    if report:
        print(json.dumps(report, indent=2))
        sys.exit(1)
    print("all declared effect and trigger names found in the dump")


if __name__ == "__main__":
    main()
