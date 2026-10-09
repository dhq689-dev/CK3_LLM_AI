"""Milestone 21: render plan narratives into CK3 localization.

Surfaces the LLM's intent -- ``five_year_goal``, ``focus``, ``secondary_goal``
-- as a localization file. The generated effect shows the player's own plan as
a toast, and the file doubles as a plain-English plan catalogue for debugging.

CK3 localization files live under ``localization/<lang>/`` and must be UTF-8
**with BOM**, like script files.
"""

from __future__ import annotations

from pathlib import Path

from .translation import Plan

TITLE_KEY = "ck3llm_plan_title"
TITLE_TEXT = "Your five-year plan"
LANG_DIR = Path("localization") / "english"
LOC_FILE = "ck3llm_l_english.yml"
DEFAULT_MOD_DIR = (
    Path(__file__).resolve().parent.parent / "mod" / "ck3llm_strategist"
)


def loc_key(plan_id: int) -> str:
    return f"ck3llm_plan_{plan_id}"


def _escape(text: str) -> str:
    """Sanitise free text for a double-quoted CK3 loc value."""
    cleaned = str(text).replace('"', "'").replace("\r", " ").replace("\n", " ")
    return " ".join(cleaned.split())


def plan_text(plan: Plan) -> str:
    """The toast body for one plan (``\\n`` separates the lines)."""
    parts: list[str] = []
    if plan.goal:
        parts.append(f"Goal: {_escape(plan.goal)}")
    if plan.focus:
        parts.append(f"Focus: {_escape(plan.focus)}")
    if plan.secondary_goal:
        parts.append(f"Then: {_escape(plan.secondary_goal)}")
    return "\\n".join(parts)


def render_localization(plans: list[Plan]) -> str:
    lines = ["l_english:", f' {TITLE_KEY}:0 "{TITLE_TEXT}"']
    for plan in plans:
        text = plan_text(plan)
        if text:
            lines.append(f' {loc_key(plan.plan_id)}:0 "{text}"')
    return "\n".join(lines) + "\n"


def write_localization(path: str | Path, plans: list[Plan]) -> Path:
    """Write the localization file as UTF-8 with BOM."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(render_localization(plans))
    return path


def write_mod_localization(
    plans: list[Plan], mod_dir: str | Path = DEFAULT_MOD_DIR
) -> Path:
    """Write the localization into a mod directory."""
    path = Path(mod_dir) / LANG_DIR / LOC_FILE
    return write_localization(path, plans)
