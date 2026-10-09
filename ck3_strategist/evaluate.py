"""Milestone 20: observer-mode evaluation of LLM-guided runs.

CK3 itself runs the A/B experiment (the same save, observer mode, once with
vanilla AI and once with the LLM layer). This module scores the artifacts the
run leaves behind -- the before/after gamestates and the logged plan cycle:

- ``wars_delta``     -- wars started / ended between the two saves.
- ``realm_growth``   -- per-ruler change in the number of titles in the realm.
- ``plan_adherence`` -- for each logged ``war`` move, did a war for that target
  title actually start within the window?

Run directly::

    python -m ck3_strategist.evaluate before.txt after.txt \\
        --cycle logs/cycle_918-11-5.jsonl
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .extract import SaveReader
from .graph import WorldGraph
from .runlog import load_cycle


@dataclass
class RealmChange:
    ruler_id: int
    ruler_name: str
    before: int
    after: int

    @property
    def delta(self) -> int:
        return self.after - self.before


@dataclass
class AdherenceRow:
    ruler_name: str
    kind: str
    ref: str
    adhered: bool


@dataclass
class Evaluation:
    wars_started: list[int] = field(default_factory=list)
    wars_ended: list[int] = field(default_factory=list)
    realm_growth: list[RealmChange] = field(default_factory=list)
    adherence: list[AdherenceRow] = field(default_factory=list)

    @property
    def adherence_rate(self) -> float:
        if not self.adherence:
            return 0.0
        return sum(1 for a in self.adherence if a.adhered) / len(self.adherence)

    def to_dict(self) -> dict:
        return {
            "wars_started": self.wars_started,
            "wars_ended": self.wars_ended,
            "realm_growth": [
                asdict(r) | {"delta": r.delta} for r in self.realm_growth
            ],
            "adherence": [asdict(a) for a in self.adherence],
            "adherence_rate": self.adherence_rate,
        }


def load_graph(path: str | Path) -> WorldGraph:
    return WorldGraph.from_save(SaveReader(str(path)))


def wars_delta(
    before: WorldGraph, after: WorldGraph
) -> tuple[list[int], list[int]]:
    """Return ``(wars_started, wars_ended)`` by war id."""
    started = sorted(set(after.wars) - set(before.wars))
    ended = sorted(set(before.wars) - set(after.wars))
    return started, ended


def realm_growth(before: WorldGraph, after: WorldGraph) -> list[RealmChange]:
    """Per-ruler change in realm title count, biggest swings first."""
    rows: list[RealmChange] = []
    for cid, char in after.characters.items():
        b = len(before.get_realm_titles(cid))
        a = len(after.get_realm_titles(cid))
        if b == 0 and a == 0:
            continue
        rows.append(RealmChange(cid, char.name, b, a))
    return sorted(rows, key=lambda r: (-abs(r.delta), r.ruler_name))


def _title_ids_by_key(graph: WorldGraph) -> dict[str, int]:
    return {t.key: t.id for t in graph.titles.values() if t.key}


def plan_adherence(
    records: list[dict],
    before: WorldGraph,
    after: WorldGraph,
) -> list[AdherenceRow]:
    """Score logged ``war`` moves against wars started in the window."""
    started, _ = wars_delta(before, after)
    targeted: set[int] = set()
    for war_id in started:
        war = after.wars.get(war_id)
        if war is not None:
            targeted.update(war.targeted_titles)

    key_to_id = _title_ids_by_key(before)
    rows: list[AdherenceRow] = []
    for record in records:
        name = str(record.get("ruler_name", ""))
        moves = (record.get("intent") or {}).get("moves") or []
        for move in moves:
            if move.get("kind") != "war":
                continue
            ref = str(move.get("ref", ""))
            title_id = key_to_id.get(ref)
            rows.append(
                AdherenceRow(
                    ruler_name=name,
                    kind="war",
                    ref=ref,
                    adhered=title_id is not None and title_id in targeted,
                )
            )
    return rows


def _evaluate(
    before: WorldGraph, after: WorldGraph, records: list[dict] | None
) -> Evaluation:
    started, ended = wars_delta(before, after)
    return Evaluation(
        wars_started=started,
        wars_ended=ended,
        realm_growth=realm_growth(before, after),
        adherence=plan_adherence(records or [], before, after),
    )


def compare(
    before_path: str | Path,
    after_path: str | Path,
    records: list[dict] | None = None,
) -> Evaluation:
    """Compare two gamestates (and optionally a logged cycle)."""
    return _evaluate(load_graph(before_path), load_graph(after_path), records)


def compare_arms(
    before_path: str | Path,
    arms: dict[str, str | Path],
    records: list[dict] | None = None,
) -> dict[str, Evaluation]:
    """Score several after-saves against one baseline save.

    ``arms`` maps an arm name (``"vanilla"``, ``"baseline"``, ``"llm"``) to its
    resulting gamestate. Three arms are what let a difference be attributed to
    the LLM rather than the deterministic baseline: the ``baseline`` arm runs the
    fallback plan with no LLM at all (review v4 §7).
    """
    before = load_graph(before_path)
    return {
        name: _evaluate(before, load_graph(after), records)
        for name, after in arms.items()
    }


def _parse_arm(value: str) -> tuple[str, str]:
    name, _, path = value.partition("=")
    if not name or not path:
        raise argparse.ArgumentTypeError("expected name=path")
    return name, path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ck3_strategist.evaluate",
        description="Score an observer-mode A/B run (Milestone 20).",
    )
    parser.add_argument("before", help="gamestate at the start of the window")
    parser.add_argument(
        "after", nargs="?", help="single after-save (else use repeated --arm)"
    )
    parser.add_argument(
        "--arm",
        action="append",
        type=_parse_arm,
        default=[],
        help="an arm as name=path (repeatable: vanilla=, baseline=, llm=)",
    )
    parser.add_argument(
        "--cycle",
        default=None,
        help="JSONL cycle log to score plan adherence against",
    )
    parser.add_argument("--output", default=None, help="write the report as JSON")
    args = parser.parse_args(argv)

    records = load_cycle(args.cycle) if args.cycle else None
    if args.arm:
        reports = {
            name: ev.to_dict()
            for name, ev in compare_arms(args.before, dict(args.arm), records).items()
        }
    else:
        if not args.after:
            parser.error("provide an after-save or at least one --arm")
        reports = {"after": compare(args.before, args.after, records).to_dict()}

    text = json.dumps(reports, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"wrote evaluation to {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
