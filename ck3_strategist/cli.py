"""Command-line entry point: save -> strategic summaries -> optional intents.

Accepts either a plaintext ``gamestate`` file or a ``.ck3`` save (a ZIP
containing ``gamestate``, which is extracted to a temp file).
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path

from .aggression import load_aggression_map
from .cadence import PLAN_INTERVAL_YEARS, PlanStore, intent_from_plan, is_due
from .extract import SaveReader
from .graph import WorldGraph
from .inject import DEFAULT_MOD_DIR, write_mod_effect
from .localization import write_mod_localization
from .menu import build_menu, extract_relations
from .reference import ReferenceData
from .snapshot import bucket_economic, bucket_strength, build_snapshots
from .summary import build_summaries
from .tiers import TIER_1, TIER_2, classify_rulers
from .translation import translate


def extract_gamestate(save_path: str) -> tuple[str, bool]:
    """Return ``(gamestate_path, is_temp)``.

    If ``save_path`` is a ZIP, the ``gamestate`` member is streamed to a temp
    file (``is_temp=True``); otherwise the path is returned unchanged.
    """
    if not zipfile.is_zipfile(save_path):
        return save_path, False

    with zipfile.ZipFile(save_path) as z:
        member = next(
            (n for n in z.namelist() if n == "gamestate" or n.endswith("/gamestate")),
            None,
        )
        if member is None:
            raise ValueError(f"no 'gamestate' member in {save_path}")
        fd, tmp_path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "wb") as out, z.open(member) as src:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
    return tmp_path, True


def run_pipeline(
    gamestate_path: str,
    tier: int = 1,
    llm_call=None,
    mod_dir: str | None = None,
    debug: bool = True,
    log_dir: str | None = None,
    seed: int | None = None,
    model: str | None = None,
    planner=None,
    cadence: bool = False,
    plans_store: str | None = None,
    interval: int = PLAN_INTERVAL_YEARS,
) -> tuple[list[dict], list | None, list | None]:
    """Run the full pipeline.

    Returns ``(summaries, intents_or_None, plans_or_None)``. When ``mod_dir`` is
    given and plans were produced, the per-cycle ``scripted_effect`` is written
    into that mod (Milestone 18). When ``log_dir`` is given, a JSONL cycle log is
    written for evaluation (Milestone 20).

    ``llm_call`` is a ``callable(prompt)->str``. Alternatively ``planner`` is a
    ``callable(summary)->Intent`` used directly (no prompts); this is how the
    deterministic ``baseline`` and ``mock`` backends run.

    With ``cadence`` on, a ruler is only re-planned when their plan is missing or
    ``interval`` years old; the stored plan is reused otherwise (Milestone 22).
    """
    reader = SaveReader(gamestate_path)
    graph = WorldGraph.from_save(reader)
    reference = ReferenceData.from_save(reader)

    snapshots = build_snapshots(graph)
    bucket_strength(snapshots)
    bucket_economic(snapshots)

    tiers = classify_rulers(snapshots)
    wanted = {TIER_1} if tier == 1 else {TIER_1, TIER_2}
    selected = [s for s in snapshots if tiers[s.ruler_id] in wanted]

    # Plans steer the AI; never the player's own ruler.
    player_id = reader.player_character_id()
    if player_id is not None:
        selected = [s for s in selected if s.ruler_id != player_id]

    from .relationships import RelationshipGraph

    current_date = reader.meta_date()
    relationships = RelationshipGraph.from_save(
        graph, reader.memories(), current_date=current_date
    )
    truces, alliances = extract_relations(reader)
    menus = {
        s.ruler_id: build_menu(graph, relationships, s.ruler_id, truces, alliances)
        for s in selected
    }
    summaries = build_summaries(
        graph,
        selected,
        reference,
        current_date,
        relationship_graph=relationships,
        menus=menus,
        aggression_map=load_aggression_map(),
    )

    if llm_call is None and planner is None:
        return summaries, None, None

    from .strategist import Strategist, baseline_intent

    store = PlanStore.load(plans_store) if (cadence and plans_store) else None

    intents = []
    entries: list[dict] = []
    plans = []
    for snap, summary in zip(selected, summaries, strict=False):
        title_ref = str(summary.get("title") or "")
        char = graph.characters.get(snap.ruler_id)
        plan_vars = char.plan_vars if char is not None else {}
        if (
            store is not None
            and not is_due(plan_vars, current_date, interval)
        ):
            reused = store.get(title_ref)
            if reused is not None:
                reused_intent = intent_from_plan(reused)
                intents.append(reused_intent)
                plans.append(reused)
                entries.append(
                    {
                        "ruler_id": snap.ruler_id,
                        "ruler_name": summary.get("ruler_name"),
                        "title": summary.get("title"),
                        "reused": True,
                        "intent": asdict(reused_intent),
                        "plan": asdict(reused),
                    }
                )
                continue

        exchanges: list[dict] = []
        fallback_error: str | None = None
        try:
            if planner is not None:
                intent = planner(summary)
            else:
                strategist = Strategist(llm_call, on_exchange=exchanges.append)
                intent = strategist.plan(summary)
        except Exception as e:  # noqa: BLE001 - never leave a ruler planless
            fallback_error = str(e)
            intent = baseline_intent(summary)
        plan = translate(intent, summary, current_date)
        intents.append(intent)
        plans.append(plan)
        entries.append(
            {
                "ruler_id": snap.ruler_id,
                "ruler_name": summary.get("ruler_name"),
                "title": summary.get("title"),
                "seed": seed,
                "model": model,
                "reused": False,
                "fallback": fallback_error is not None,
                "fallback_error": fallback_error,
                "exchanges": exchanges,
                "intent": asdict(intent),
                "plan": asdict(plan),
            }
        )

    if store is not None and plans_store is not None:
        for plan in plans:
            store.put(plan)
        store.save(plans_store)

    if log_dir is not None:
        from .runlog import cycle_filename, write_cycle

        write_cycle(
            Path(log_dir) / cycle_filename(current_date), current_date, entries
        )
    if mod_dir is not None:
        write_mod_effect(plans, mod_dir, debug=debug)
        write_mod_localization(plans, mod_dir)
    return summaries, intents, plans


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ck3_strategist",
        description="Parse a CK3 save into strategic summaries (and LLM intents).",
    )
    parser.add_argument("save", help="path to a .ck3 save or plaintext gamestate")
    parser.add_argument(
        "--tier",
        type=int,
        default=1,
        choices=[1, 2],
        help="1 = kings/emperors (default); 2 = also top dukes",
    )
    parser.add_argument(
        "--output", default="output", help="output directory (default: output)"
    )
    parser.add_argument(
        "--llm",
        choices=["none", "ollama", "baseline", "mock"],
        default="none",
        help="planner backend: none (parse only), ollama, baseline "
        "(deterministic, no LLM), mock (deterministic, picks menu options)",
    )
    parser.add_argument(
        "--model", default="llama3", help="model name for the LLM backend"
    )
    parser.add_argument(
        "--mod-dir",
        default=str(DEFAULT_MOD_DIR),
        help="mod directory to write the generated script into "
        "(default: mod/ck3llm_strategist)",
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="omit debug_log lines from the generated script",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="write a JSONL cycle log (prompts/responses/plans) for evaluation",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="LLM seed, for a reproducible observer-mode A/B run",
    )
    parser.add_argument(
        "--cadence",
        action="store_true",
        help="re-plan only rulers whose plan is missing or >= interval years old",
    )
    parser.add_argument(
        "--plans-store",
        default=None,
        help="plan store for cadence reuse (default: <output>/plans_store.json)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=PLAN_INTERVAL_YEARS,
        help="re-plan interval in in-game years (default: 5)",
    )
    parser.add_argument(
        "--watch",
        default=None,
        metavar="DIR",
        help="watch a saves directory and run a cycle on each new save",
    )
    args = parser.parse_args(argv)

    plans_store = args.plans_store
    if plans_store is None and args.cadence:
        plans_store = str(Path(args.output) / "plans_store.json")

    llm_call = None
    planner = None
    if args.llm == "ollama":
        from .strategist import ollama_call

        llm_call = ollama_call(args.model, seed=args.seed)
    elif args.llm == "baseline":
        from .strategist import baseline_intent

        planner = baseline_intent
    elif args.llm == "mock":
        from .strategist import mock_intent

        planner = mock_intent

    def run_once(save_path: str) -> None:
        gamestate_path, is_temp = extract_gamestate(save_path)
        try:
            summaries, intents, plans = run_pipeline(
                gamestate_path,
                args.tier,
                llm_call,
                mod_dir=args.mod_dir,
                debug=not args.no_debug,
                log_dir=args.log_dir,
                seed=args.seed,
                model=args.model if args.llm == "ollama" else None,
                planner=planner,
                cadence=args.cadence,
                plans_store=plans_store,
                interval=args.interval,
            )
        finally:
            if is_temp:
                os.unlink(gamestate_path)

        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        summaries_file = out / "summaries.json"
        with open(summaries_file, "w", encoding="utf-8") as f:
            json.dump(summaries, f, indent=2, ensure_ascii=False)
        print(f"wrote {len(summaries)} summaries to {summaries_file}")

        if intents is not None:
            intents_file = out / "intents.json"
            with open(intents_file, "w", encoding="utf-8") as f:
                json.dump(
                    [asdict(i) for i in intents], f, indent=2, ensure_ascii=False
                )
            print(f"wrote {len(intents)} intents to {intents_file}")

        if plans is not None:
            plans_file = out / "plans.json"
            with open(plans_file, "w", encoding="utf-8") as f:
                json.dump(
                    [asdict(p) for p in plans], f, indent=2, ensure_ascii=False
                )
            print(f"wrote {len(plans)} plans to {plans_file}")

    if args.watch:
        from .cadence import watch_saves

        print(f"watching {args.watch} for new saves (Ctrl+C to stop)...")
        watch_saves(args.watch, on_new=lambda paths: run_once(paths[-1]))
    else:
        run_once(args.save)
