"""Milestone 22: cycle cadence and save watching.

Plans are stamped with ``ck3llm_plan_start`` (the cycle year). Rather than
re-planning every AI ruler on every cycle, the pipeline only re-plans rulers
whose plan is missing or at least ``interval`` years old, and reuses the stored
plan for the rest. This keeps the LLM cost bounded and the cadence
self-correcting (it is gated on the plan's own start date, not on autosaves).

A save watcher can detect new/modified save files and trigger a cycle; the
generated-mod delivery route still needs a reload to apply.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from .strategist import Intent
from .translation import GuardedAction, Plan

PLAN_INTERVAL_YEARS = 5


def _year(date: str) -> int | None:
    head = str(date).split(".", 1)[0].strip()
    return int(head) if head.isdigit() else None


def plan_start_year(plan_vars: dict) -> int | None:
    value = plan_vars.get("ck3llm_plan_start")
    if isinstance(value, (int, float)):
        return int(value)
    return None


def is_due(
    plan_vars: dict, current_date: str, interval: int = PLAN_INTERVAL_YEARS
) -> bool:
    """True if the ruler has no plan, or its plan is ``interval`` years old."""
    start = plan_start_year(plan_vars)
    now = _year(current_date)
    if start is None or now is None:
        return True
    return (now - start) >= interval


def ruler_ref_of(plan: Plan) -> str:
    """A stable per-ruler key: the title key behind a ``title:...holder`` scope."""
    scope = plan.ruler_scope
    if scope.startswith("title:") and scope.endswith(".holder"):
        return scope[len("title:") : -len(".holder")]
    return scope


def intent_from_plan(plan: Plan) -> Intent:
    """Reconstruct a (narrative-only) Intent for logging a reused plan."""
    return Intent(
        five_year_goal=plan.goal,
        focus=plan.focus or "Diplomacy",
        aggression=plan.aggression,
        aggression_deviation=0,
        secondary_goal=plan.secondary_goal,
        moves=[],
    )


def plan_from_dict(d: dict) -> Plan:
    actions = [
        GuardedAction(
            kind=str(a.get("kind", "")),
            effect=str(a.get("effect", "")),
            target_ref=str(a.get("target_ref", "")),
            target_scope=str(a.get("target_scope", "")),
            guards=list(a.get("guards") or []),
            params=dict(a.get("params") or {}),
            unary=bool(a.get("unary", False)),
        )
        for a in (d.get("actions") or [])
    ]
    return Plan(
        ruler_scope=str(d.get("ruler_scope", "")),
        plan_id=int(d.get("plan_id", 0)),
        aggression=int(d.get("aggression", 0)),
        modifier=str(d.get("modifier", "")),
        modifier_years=int(d.get("modifier_years", 0)),
        plan_date=str(d.get("plan_date", "")),
        goal=str(d.get("goal", "")),
        focus=str(d.get("focus", "")),
        secondary_goal=str(d.get("secondary_goal", "")),
        actions=actions,
        clear_modifiers=list(d.get("clear_modifiers") or []),
    )


class PlanStore:
    """Persisted plans, keyed by ruler ref, for cadence reuse across cycles."""

    def __init__(self, plans: dict[str, Plan] | None = None):
        self._plans: dict[str, Plan] = dict(plans or {})

    @classmethod
    def load(cls, path: str | Path) -> PlanStore:
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        plans = {
            ref: plan_from_dict(d)
            for ref, d in (data.get("plans") or {}).items()
        }
        return cls(plans)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"plans": {ref: asdict(p) for ref, p in self._plans.items()}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return path

    def get(self, ref: str) -> Plan | None:
        return self._plans.get(ref)

    def put(self, plan: Plan) -> None:
        self._plans[ruler_ref_of(plan)] = plan

    def all(self) -> list[Plan]:
        return list(self._plans.values())


def scan_saves(directory: str | Path) -> dict[str, float]:
    """Map each ``*.ck3`` in a directory to its mtime."""
    directory = Path(directory)
    if not directory.is_dir():
        return {}
    return {str(p): p.stat().st_mtime for p in directory.glob("*.ck3")}


def new_saves(
    before: dict[str, float], after: dict[str, float]
) -> list[str]:
    """Paths that are new or whose mtime changed."""
    return sorted(
        path
        for path, mtime in after.items()
        if before.get(path) != mtime
    )


def watch_saves(
    directory: str | Path,
    on_new: Callable[[list[str]], None],
    interval: float = 5.0,
    max_polls: int | None = None,
) -> dict[str, float]:
    """Poll a directory; call ``on_new`` with new/changed saves.

    ``max_polls`` bounds the loop (``None`` = run until interrupted), which
    keeps the watcher testable.
    """
    seen = scan_saves(directory)
    polls = 0
    while max_polls is None or polls < max_polls:
        time.sleep(interval)
        polls += 1
        current = scan_saves(directory)
        changed = new_saves(seen, current)
        if changed:
            on_new(changed)
        seen = current
    return seen
