# AGENTS.md

CK3 LLM Strategist: an LLM-driven strategic planning layer for Crusader Kings
III saves. The parser turns a save into a `StrategicSummary` JSON; an LLM turns
that into *intent* (never raw actions). See `docs/vision.md` for the why.

## Documentation map

- `docs/vision.md` — objective, architecture, data model, design decisions.
- `docs/roadmap.md` — all milestones (Phases 1–3) and the Phase 3 design.
- `docs/risk_register.md` — risks, assumptions, open questions.
- `parser_implementation.md` — authoritative parser spec (grammar, field map,
  version-proofing).
- `docs/ck3_injection_ideas.txt`, `docs/review_notes*.md` — source material.

## Commands

```bash
pip install -e ".[dev]"        # install (pytest, ruff, mypy)
pytest                          # tests
ruff check .                    # lint
mypy                            # type-check
python -m ck3_strategist <save> --output output --tier 1   # run the pipeline
```

`<save>` may be a plaintext `gamestate` or a `.ck3` ZIP (extracted
automatically). `--llm ollama` also runs the strategist.

## Project structure

```text
ck3_strategist/
  lexer.py         byte-safe tokenizer
  parser.py        recursive-descent parser
  indexer.py       top-level section indexer (brace-depth)
  extract.py       character/title/dynasty/war/memory extractors
  reference.py     ID→name tables (from the save)
  graph.py         WorldGraph (liege/vassal hierarchy)
  snapshot.py      RealmSnapshot + derived values
  tiers.py         significant-ruler detection
  summary.py       StrategicSummary builder
  relationships.py relationship graph (from memories)
  menu.py          legal-move menu builder (candidate moves per ruler)
  aggression.py    trait-derived aggression baseline
  strategist.py    LLM strategist (intent contract)
  translation.py   intent -> modifier tier + guarded hard actions
  inject.py        render plans -> CK3 scripted_effect (utf-8-sig)
  localization.py  render plan narrative -> CK3 localization (.yml)
  runlog.py        JSONL cycle logging (prompts/outputs/seeds)
  evaluate.py      observer-mode evaluation metrics (wars/growth/adherence)
  validate.py      script_docs name validation for the translation table
  cli.py           command-line entry point
reference_data/    static tables (relationships.json, aggression_traits.json,
                   translation.json)
mod/               static CK3 mod (ck3llm_strategist) + generated effect
docs/              vision, roadmap, risk register
tests/             unit tests + hand-written fixture
sample_savedata/   real saves (gitignored, large)
```

## Conventions

- Never `read()` the whole 170MB save; stream or mmap.
- Never hardcode a closed set of keys — saves are modded (RICE/EP3).
- Use `de_facto_liege` for politics, `de_jure_liege` only for claims/expansion.
- Keep the parser LLM-agnostic; the LLM layer consumes JSON only.
- Keep the injection layer behind a clean interface (how a plan reaches CK3 can
  change without touching the parser or the LLM).
- New config/mappings go in `reference_data/` as data, not code branches.

## Current state

Phase 1, Phase 2, and Phase 3 milestones 14–21 are complete and tested (176
tests): the injection levers are verified (M14), the legal-move menu builder
exists (M15), the intent contract is menu-constrained with a trait-derived
aggression baseline (M16), the translation layer maps intent → modifier tier +
guarded hard actions and clears stale tiers (M17), the static mod + generated
`scripted_effect` render path exists and is **validated in-game** (M18;
injection hook, tier apply/clear/expire, hard actions, and feedback variables
all confirmed on CK3 1.20.0.4), `ck3llm_*` plan variables are read back into the
briefing as `previous_plan` (M19), the evaluation harness (cycle logging +
three-arm A/B metrics) exists (M20), and plan narrative is written to a
localization catalogue (M21). A deterministic no-plan fallback + per-ruler
error isolation are in place, and the **player's ruler is excluded** from
planning (plans steer AI rulers only).

A third-party review (`docs/review_notes_v4.txt`) is folded into the
**"Correctness gate"** in `docs/roadmap.md` (CG1–CG7) and
`docs/risk_register.md` (#16–#21). **CG1 (name validation), CG2 (hard actions),
and CG5 (localized goals) are done.** Next is **M22 — cadence & save watcher**,
then the three-arm observer A/B (CG6) once an LLM is installed.
