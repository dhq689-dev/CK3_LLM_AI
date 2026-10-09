"""Milestone 18: render translated plans into CK3 script.

The static mod in ``mod/ck3llm_strategist`` holds the hand-written parts
(aggression modifier tiers and the ``on_action`` hook). This module writes only
the per-cycle ``scripted_effect`` the hook calls. Re-running a cycle overwrites
that one file; the static files are never touched, so a save that still
references an old modifier keeps loading (mod stability, risk register #6).

The generated effect stamps ``ck3llm_plan_id``/``ck3llm_plan_start`` on each
ruler (for the feedback loop) and re-applies the plan every yearly pulse. That
is idempotent for the current levers -- tiers are cleared before being added,
and ``add_pressed_claim``/``create_alliance`` no-op when already satisfied. A
plan-id guard that skips re-application errors when the variable is first unset,
so per-pulse idempotence is deferred to the standing-orders design (CG3).

CK3 requires script files to be UTF-8 **with BOM**, so :func:`write_plans`
writes ``utf-8-sig``.
"""

from __future__ import annotations

from pathlib import Path

from .localization import TITLE_KEY, TOAST_TYPE, loc_key
from .translation import Plan

TAB = "\t"
SCRIPT_ROOT = "common/scripted_effects"
EFFECT_FILE = "ck3llm_plans.txt"
DEFAULT_EFFECT_NAME = "ck3llm_apply_plans"
PLAN_VAR = "ck3llm_plan_id"
PLAN_START_VAR = "ck3llm_plan_start"
DEFAULT_MOD_DIR = (
    Path(__file__).resolve().parent.parent / "mod" / "ck3llm_strategist"
)
DEFAULT_EFFECT_PATH = DEFAULT_MOD_DIR / SCRIPT_ROOT / EFFECT_FILE


def _indent(level: int, text: str) -> str:
    return TAB * level + text


def _render_effect(action) -> str:
    if action.unary:
        return f"{action.effect} = {action.target_scope}"
    if not action.params:
        return f"{action.effect} = yes"
    inner = " ".join(f"{k} = {v}" for k, v in action.params.items())
    return f"{action.effect} = {{ {inner} }}"


def _render_action(action, level: int) -> list[str]:
    effect = _render_effect(action)
    if not action.guards:
        return [_indent(level, effect)]
    lines = [_indent(level, "if = {"), _indent(level + 1, "limit = {")]
    lines.extend(_indent(level + 2, guard) for guard in action.guards)
    lines.append(_indent(level + 1, "}"))
    lines.append(_indent(level + 1, effect))
    lines.append(_indent(level, "}"))
    return lines


def _year_of(date: str) -> str | None:
    year = str(date).split(".", 1)[0].strip()
    return year if year.isdigit() else None


def _render_plan(plan: Plan, debug: bool) -> list[str]:
    if not plan.ruler_scope:
        return []  # landless rulers with no scope cannot be targeted yet
    set_var = f"set_variable = {{ name = {PLAN_VAR} value = {plan.plan_id} }}"
    # NOTE: no plan-id guard here. `NOT = { var:ck3llm_plan_id = X }` errors on
    # the first run when the variable is unset, and every current effect is
    # idempotent anyway (tiers are cleared, `add_pressed_claim`/`create_alliance`
    # no-op when already true). Per-pulse idempotence returns with standing
    # orders (CG3). `remove_character_modifier` is unary in CK3.
    lines = [
        _indent(1, f"{plan.ruler_scope} ?= {{"),
        _indent(2, set_var),
    ]
    start_year = _year_of(plan.plan_date)
    if start_year is not None:
        start_var = (
            f"set_variable = {{ name = {PLAN_START_VAR} value = {start_year} }}"
        )
        lines.append(_indent(2, start_var))
    for stale in plan.clear_modifiers:
        lines.append(_indent(2, f"remove_character_modifier = {stale}"))
    lines += [
        _indent(2, "add_character_modifier = {"),
        _indent(3, f"modifier = {plan.modifier}"),
        _indent(3, f"years = {plan.modifier_years}"),
        _indent(2, "}"),
    ]
    for action in plan.actions:
        lines.extend(_render_action(action, level=2))
    if plan.goal or plan.secondary_goal:
        # only reaches the player if they play this character
        lines.append(_indent(2, "send_interface_toast = {"))
        lines.append(_indent(3, f"type = {TOAST_TYPE}"))
        lines.append(_indent(3, f"title = {TITLE_KEY}"))
        lines.append(_indent(3, f"desc = {loc_key(plan.plan_id)}"))
        lines.append(_indent(2, "}"))
    if debug:
        lines.append(_indent(2, f'debug_log = "ck3llm: plan {plan.plan_id} applied"'))
    lines.append(_indent(1, "}"))
    return lines


def render_plans(
    plans: list[Plan],
    effect_name: str = DEFAULT_EFFECT_NAME,
    debug: bool = True,
) -> str:
    """Render plans into the body of a CK3 scripted effect."""
    lines = [f"{effect_name} = {{"]
    for plan in plans:
        lines.extend(_render_plan(plan, debug))
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_plans(
    path: str | Path,
    plans: list[Plan],
    effect_name: str = DEFAULT_EFFECT_NAME,
    debug: bool = True,
) -> Path:
    """Write the rendered effect to ``path`` as UTF-8 with BOM."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_plans(plans, effect_name, debug)
    with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(text)
    return path


def write_mod_effect(
    plans: list[Plan],
    mod_dir: str | Path = DEFAULT_MOD_DIR,
    effect_name: str = DEFAULT_EFFECT_NAME,
    debug: bool = True,
) -> Path:
    """Write the effect into a mod directory (``<mod_dir>/common/...``)."""
    path = Path(mod_dir) / SCRIPT_ROOT / EFFECT_FILE
    return write_plans(path, plans, effect_name, debug)
