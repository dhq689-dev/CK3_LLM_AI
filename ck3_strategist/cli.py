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
from .extract import SaveReader
from .graph import WorldGraph
from .inject import DEFAULT_MOD_DIR, write_mod_effect
from .menu import build_menu, extract_relations
from .reference import ReferenceData
from .snapshot import bucket_economic, bucket_strength, build_snapshots
from .summary import build_summaries
from .tiers import TIER_1, TIER_2, classify_rulers
from .translation import translate_all


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
) -> tuple[list[dict], list | None, list | None]:
    """Run the full pipeline.

    Returns ``(summaries, intents_or_None, plans_or_None)``. When ``mod_dir`` is
    given and an LLM ran, the per-cycle ``scripted_effect`` is written into that
    mod (Milestone 18). When ``log_dir`` is given, a JSONL cycle log (prompts,
    raw responses, intents, plans, seed/model) is written for evaluation
    (Milestone 20).
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

    if llm_call is None:
        return summaries, None, None

    from .strategist import Strategist, baseline_intent

    intents = []
    entries: list[dict] = []
    for snap, summary in zip(selected, summaries, strict=False):
        exchanges: list[dict] = []
        strategist = Strategist(llm_call, on_exchange=exchanges.append)
        fallback_error: str | None = None
        try:
            intent = strategist.plan(summary)
        except Exception as e:  # noqa: BLE001 - never leave a ruler planless
            fallback_error = str(e)
            intent = baseline_intent(summary)
        intents.append(intent)
        entries.append(
            {
                "ruler_id": snap.ruler_id,
                "ruler_name": summary.get("ruler_name"),
                "title": summary.get("title"),
                "seed": seed,
                "model": model,
                "fallback": fallback_error is not None,
                "fallback_error": fallback_error,
                "exchanges": exchanges,
                "intent": asdict(intent),
            }
        )

    plans = translate_all(summaries, intents, current_date)
    for entry, plan in zip(entries, plans, strict=False):
        entry["plan"] = asdict(plan)

    if log_dir is not None:
        from .runlog import cycle_filename, write_cycle

        write_cycle(
            Path(log_dir) / cycle_filename(current_date), current_date, entries
        )
    if mod_dir is not None:
        write_mod_effect(plans, mod_dir, debug=debug)
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
        choices=["none", "ollama"],
        default="none",
        help="LLM backend (default: none)",
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
    args = parser.parse_args(argv)

    gamestate_path, is_temp = extract_gamestate(args.save)
    try:
        llm_call = None
        if args.llm == "ollama":
            from .strategist import ollama_call

            llm_call = ollama_call(args.model, seed=args.seed)
        summaries, intents, plans = run_pipeline(
            gamestate_path,
            args.tier,
            llm_call,
            mod_dir=args.mod_dir,
            debug=not args.no_debug,
            log_dir=args.log_dir,
            seed=args.seed,
            model=args.model if args.llm != "none" else None,
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
