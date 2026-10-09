"""Validate translation names against a ``script_docs`` dump (review v4 §2/CG1).

CK3's ``script_docs`` console command writes ``effects.log``, ``triggers.log``
and ``modifiers.log`` into the user ``logs`` folder. This module reads those
(``--logs``) or a normalised JSON dump (``dump``) and reports every effect name
and guard trigger the translation layer would emit that does not exist.

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
# trigger names inside guard templates look like "<token> ="
_GUARD_TOKEN = re.compile(r"\b([a-z_][a-z0-9_]*)\s*=")
_IGNORED_GUARD_TOKENS = {
    "not",
    "target",
    "modifier",
    "var",
    "name",
    "value",
    "title",
    "character",
    "scope",
    "ratio",
    "this",
    "root",
    "yes",
    "no",
}


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


def check_effects(table: dict, dump: dict) -> dict[str, str]:
    """Return ``{move kind: effect}`` for effect names absent from the dump."""
    known = normalize(dump).get("effects", set())
    missing: dict[str, str] = {}
    for kind, spec in (table.get("actions") or {}).items():
        effect = str(spec.get("effect", ""))
        if effect and effect not in known:
            missing[kind] = effect
    return missing


def guard_trigger_names(table: dict) -> set[str]:
    """Best-effort trigger names referenced in guard templates."""
    names: set[str] = set()
    for spec in (table.get("actions") or {}).values():
        for guard in spec.get("guards", []):
            for token in _GUARD_TOKEN.findall(guard):
                if token not in _IGNORED_GUARD_TOKENS:
                    names.add(token)
    return names


def check_tiers(table: dict, dump: dict) -> list[str]:
    """Tier modifier names absent from the dump (only meaningful with the mod
    loaded during ``script_docs``)."""
    from .translation import all_tier_names

    known = normalize(dump).get("modifiers", set())
    return sorted(t for t in all_tier_names(table) if t not in known)


def check(table: dict, dump: dict) -> dict:
    docs = normalize(dump)
    report: dict = {}
    missing_effects = check_effects(table, dump)
    if missing_effects:
        report["effects"] = missing_effects
    missing_triggers = sorted(
        t for t in guard_trigger_names(table) if t not in docs.get("triggers", set())
    )
    if missing_triggers:
        report["triggers"] = missing_triggers
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ck3_strategist.validate",
        description="Check translation.json names against a script_docs dump.",
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
    print(
        "all translation effect and trigger names found in the dump "
        f"({len(normalize(dump).get('effects', set()))} effects, "
        f"{len(normalize(dump).get('triggers', set()))} triggers)"
    )


if __name__ == "__main__":
    main()
