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
from pathlib import Path

from .extract import SaveReader
from .graph import WorldGraph
from .reference import ReferenceData
from .snapshot import build_snapshots, bucket_economic, bucket_strength
from .summary import build_summaries
from .tiers import TIER_1, TIER_2, classify_rulers


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
    gamestate_path: str, tier: int = 1, llm_call=None
) -> tuple[list[dict], list | None]:
    """Run the full pipeline. Returns ``(summaries, intents_or_None)``."""
    reader = SaveReader(gamestate_path)
    graph = WorldGraph.from_save(reader)
    reference = ReferenceData.from_save(reader)

    snapshots = build_snapshots(graph)
    bucket_strength(snapshots)
    bucket_economic(snapshots)

    tiers = classify_rulers(snapshots)
    wanted = {TIER_1} if tier == 1 else {TIER_1, TIER_2}
    selected = [s for s in snapshots if tiers[s.ruler_id] in wanted]

    summaries = build_summaries(graph, selected, reference, reader.meta_date())

    if llm_call is None:
        return summaries, None

    from .strategist import Strategist

    strategist = Strategist(llm_call)
    intents = [strategist.plan(s) for s in summaries]
    return summaries, intents


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
    args = parser.parse_args(argv)

    gamestate_path, is_temp = extract_gamestate(args.save)
    try:
        llm_call = None
        if args.llm == "ollama":
            from .strategist import ollama_call

            llm_call = ollama_call(args.model)
        summaries, intents = run_pipeline(gamestate_path, args.tier, llm_call)
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
                [i.__dict__ for i in intents], f, indent=2, ensure_ascii=False
            )
        print(f"wrote {len(intents)} intents to {intents_file}")
