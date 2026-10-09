# Roadmap

Milestones for all phases. Each has a concrete deliverable and a verification
step. The parser stays LLM-agnostic throughout.

---

# Phase 1 — Parser & planner (DONE)

Milestones 0–9. Built and verified standalone, before any LLM work.

- **0 — Project scaffolding.** Python package, `pyproject.toml`,
  `reference_data/`, hand-written fixture.
- **1 — Lexer + parser.** Byte-safe tokenizer + recursive-descent parser for
  the Paradox grammar (`../parser_implementation.md` §1).
- **2 — Section indexer.** Brace-depth scan recording byte/line offsets for the
  big sections; random access without loading the whole file.
- **3 — Character + Title extractors.** Streaming extractors producing
  `Character`/`Title` dataclasses (plus prestige/piety/gold and raw memory IDs).
- **4 — Reference data loader.** Trait/culture/faith/house tables extracted
  from the save itself.
- **5 — WorldGraph.** `characters`/`titles`/`dynasties`/`wars` maps +
  `get_ruler`, `get_vassals`, `get_liege`, `get_realm_titles`.
- **6 — RealmSnapshot + derived values.** Primary title, rank, vassals, claims,
  wars, succession, strength, bucketing, threats with `power_ratio`.
- **7 — Significant-ruler detection.** Tier 1 (emperors/kings), Tier 2 (top
  dukes).
- **8 — StrategicSummary builder.** The only structure sent to the LLM;
  token-budget truncation.
- **9 — LLM strategist.** Pluggable `callable(prompt) -> str`; intent contract
  with validation + retry.

---

# Phase 2 — Memory & relationships (DONE)

Milestones 10–13.

- **10 — Memory extractor.** Stream `character_memory_manager.database` into
  `Memory` objects; link each to its owner.
- **11 — Relationship graph.** Derive `Relationship` edges from memories +
  `family_data`, driven by a configurable `reference_data/relationships.json`
  mapping; filter expired memories against `meta_date()`.
- **12 — Relationship summary.** A `relationships` block in the summary
  (ruler, id, kind, date), capped and rendered into the prompt.
- **13 — Negotiation intents (sketch).** Extended intent contract with a
  `negotiations` list; ID-validated targets.

---

# Phase 3 — Injecting intent into CK3 (PLANNED)

This turns the LLM's intent into actual CK3 AI behaviour. It is the hardest
part of the project and the riskiest, so it is validated *first* with a thin
vertical slice (Milestone 14) before anything is built on top of it.

## The core constraint

CK3 takes no outside input while running and cannot read files at runtime. A
plan must be **baked into script** and delivered at load time (a generated mod)
or through the console. This makes the loop **turn-based**:
save → parse → plan → write → restart → load.

## Design principles

1. **Prove the levers before building.** Validate modifiers, `on_action`
   pulses, `?=`, and clean save reload with a hand-written smoke test *first*.
2. **Soft steering + hard actions.** Soft modifiers nudge the AI; hard actions
   make specific decisions happen. Neither alone is sufficient.
3. **Key plans on titles, not character IDs.** `title:k_france.holder`
   survives succession; character IDs do not. Character IDs are a fallback for
   landless targets only.
4. **Constrained choices from a menu.** Precompute a per-ruler *candidate*
   menu; the LLM chooses from it (schema-validated). The menu is *plausible*,
   not *legal* — in-game triggers are the final arbiter.
5. **Close the loop through the save.** Injected effects set variables (plan
   ID, start date); the next parse reads them back so the LLM has memory of its
   own plans and their outcomes.
6. **Limit hard actions per ruler per cycle** (one or two), so rulers still
   feel like AI and behaviour cannot run away.
7. **Mod/version/LLM agnostic.** Modifier names come from a `script_docs` dump
   (a data file, like `reference_data/`); the LLM stays a pluggable callable.
8. **Never steer the player.** Plans are for AI rulers; the pipeline reads the
   save's `played_character` and excludes that ruler (no tier, no hard actions,
   no plan). In a true observer save there is no player, so nothing is excluded.

## Two-layer translation

**Soft steering** (continuous, unreliable alone):

- Character modifiers carrying AI personality dials (`ai_boldness`,
  `ai_energy`, `ai_greed`, `ai_vengefulness`, ...) and war dials
  (`ai_war_chance`, `ai_war_cooldown`, ...). **Verify exact names via
  `script_docs`.**
- Pre-define tiers (`ck3llm_aggressive_1` .. `_5`) in a hand-written static
  mod; Python emits only the tier. Apply with `years = 5` so plans self-expire.

**Hard actions** (discrete, deterministic — the game's own effects):

- `start_war`, `add_opinion` (custom modifier), `add_hook`, `create_alliance`,
  `add_truce`, `set_designated_heir`, `add_pressed_claim`.
- Each guarded by in-game triggers so illegal moves silently no-op. `start_war`
  in particular must be guarded by **truce, existing-war, and strength/readiness
  checks**, not just legality.

## Aggression: baseline + deviation

LLMs cluster (most rulers come back "aggression 6–8"). To avoid this and keep
personality-consistency, **derive a baseline aggression deterministically from
traits** (wrathful/ambitious → high; content/calm → low) and let the LLM choose
*targets* and *deviations* from that baseline. The baseline is computed by the
parser; the LLM only nudges.

## `power_ratio`: precise definition

`power_ratio` is currently **threat realm strength ÷ own realm strength**, where
"realm strength" = the ruler's own `strength` plus the summed `strength` of
their vassals. It **does not** include allies, the liege's levies, or
co-belligerents, and it is computed for any ruler with a primary title. This
definition must be stated wherever it is shown, so the LLM is not misled.

## Mod stability rules

- Keep **one permanent generated mod with a fixed name** in the playset.
- Make the static modifier tiers **additive-only**.
- **Never delete a modifier definition a save still references** — that causes
  load errors. Superseded modifiers are neutralised, not removed.

## Delivery routes

| Route | Restart? | Robustness | Notes |
|---|---|---|---|
| Generated mod file | Yes | High | Cleanest. Static `on_action` calls a Python-written scripted effect. |
| Console `effect`/`run` | No | Medium | Near-live; non-Ironman only; **verify `run <file>` behaviour**. |
| Edit gamestate + rezip | Reload | Low | Format-fragile; avoid unless the others fail. |

Recommended: **generated mod first**, console later if a live loop is wanted.

## Cadence

- Plans are stamped with a **plan ID + start date** as character variables.
- Recompute roughly **every 5 in-game years**, gated on the plan start date
  (not on the autosave interval), so cadence is self-correcting.
- A **save watcher** can trigger on any save (manual or auto). Application
  still needs a reload on the generated-mod route.

## Feedback loop

The injected effect writes `ck3llm_plan_id` and a start date. The next parse
reads them, so the briefing can say "you have been pursuing this plan since
year X" — giving the LLM memory of its own intent and its results.

## No-plan fallback

If the LLM is unavailable or returns invalid output after retries, fall back to
a **deterministic baseline plan** derived from traits (the same baseline used
for aggression). The pipeline must never leave a ruler planless.

## Milestones

- **14 — Injection smoke test (vertical slice). DONE.** Mod loads, the
  `on_action` list-append hook fires, `yearly_global_pulse` fires, `?=`
  resolves a character scope, and `add_character_modifier` applies. See
  "Injection findings" in `risk_register.md` for the four gotchas
  (`supported_version`, UTF-8 BOM, the `effect` override, global
  `on_game_start` scope).
- **15 — Legal-move menu builder. DONE (claim-based).** Per ruler: war targets
  (claims on titles held by others), alliance candidates (positive
  relationships), peace options (active wars), plus truces and existing allies
  from the save's `relations` section. **Adjacency is still missing** — the
  menu is claim-based, not border-based; static map data remains a future
  enhancement.
- **16 — Intent contract revision. DONE.** Intent carries `aggression_deviation`
  (effective aggression = `clamp(trait baseline + deviation)`) and a `moves`
  list constrained to the per-ruler menu; targets are stable refs (a title key,
  or `char:<id>` fallback for the landless). The baseline is computed by the
  parser and carried in the summary; moves referencing a non-menu ref are
  dropped during validation.
- **17 — Translation layer. DONE.** `translation.py` turns an intent into a
  structured `Plan`: an aggression modifier tier (`ck3llm_aggressive_1`..`_5`,
  applied for a fixed term) plus up to two **standing orders** from the intent's
  `moves`, each a target variable (`ck3llm_war_target` / `ck3llm_ally_target`).
  Every plan lists all tiers *and* order variables to clear first (so stale
  state doesn't linger, review v4 §3), and targets are resolved from stable refs
  to CK3 scopes. All CK3 names live in `reference_data/translation.json` and are
  checked by `validate.py` against a `script_docs` dump. Emission is M18.
- **18 — Static mod + generated script. DONE (validated in-game 1.20.0.4).**
  `mod/ck3llm_strategist/` holds the hand-written aggression tiers and the
  `yearly_global_pulse` hook; `inject.py` renders each cycle's `Plan`s into
  `common/scripted_effects/ck3llm_plans.txt` (UTF-8 BOM), clearing stale tiers
  and stamping `ck3llm_plan_id`/`ck3llm_plan_start`. In-game runs confirmed the
  hook, `?=` scope, tier apply/clear/expire, the feedback variables, and the
  hard actions (`add_pressed_claim`, `create_alliance`). See risk register
  "Live smoke-test findings" for the syntax gotchas (`remove_character_modifier`
  is unary; `type=value` vars are fixed-point; `is_allied_to`/`create_alliance`
  are unary; guard dead targets with `is_alive`).
- **19 — Feedback loop. DONE.** The generated effect stamps `ck3llm_plan_id`
  and `ck3llm_plan_start`; the parser reads `ck3llm_*` character variables back
  into `Character.plan_vars`, the summary exposes `previous_plan`
  (`{plan_id, since}`), and the strategist prompt tells the LLM what plan it
  has been pursuing and since when.
- **20 — Evaluation. HARNESS DONE (runs pending).** `runlog.py` writes a JSONL
  cycle log (prompts, raw responses, intents, plans, seed/model); `evaluate.py`
  scores saves (wars started/ended, realm growth) and plan adherence (did a war
  for each chosen target title start?). `compare_arms` supports the required
  **three arms** — vanilla / baseline-only / LLM — so a difference can be
  attributed to the LLM rather than the deterministic dial, and
  `--log-dir`/`--seed` make each arm reproducible. Actual in-game observer runs
  (with several seeds) still pending.
- **21 — Narrative / localization. DONE.** `Plan` carries
  `five_year_goal`/`focus`/`secondary_goal`; `localization.py` writes
  `mod/ck3llm_strategist/localization/english/ck3llm_l_english.yml` (UTF-8 BOM)
  as a plain-English plan catalogue. The first in-game surface was a toast to
  the player, but plans are for **AI rulers only** (design principle 8), so the
  toast was dropped; the `ck3llm_plan_toast` message type + localization
  plumbing is kept for a future "inspect an AI ruler" surface.
- **22 — Cadence & save watcher. DONE.** `cadence.py` gates re-planning on the
  ruler's `ck3llm_plan_start` (`is_due`, default 5 years); a `PlanStore`
  persists plans by ruler ref and `run_pipeline` reuses them for rulers not yet
  due (`--cadence` / `--plans-store` / `--interval`). `scan_saves` /
  `new_saves` / `watch_saves` detect new or changed save files, and `--watch
  DIR` runs a cycle on each new save. Verified on a real save: a second cycle
  reused 79 of 80 plans.

## Correctness gate (from review v4 — do before more Phase-3 features)

The review found that the last mile is unvalidated. These are ordered so
correctness precedes features; **CG1–CG2 block trusting the generated file**.

- **CG1 — Verify CK3 names. DONE (1.20.0.4).** `validate.py` parses the
  `script_docs` logs (`effects.log`/`triggers.log`/`modifiers.log`) and checks
  every effect and guard trigger in `translation.json`:
  `python -m ck3_strategist.validate --logs <logs>` → all names found (2128
  effects, 1935 triggers).
- **CG2 — Fix the hard actions. DONE (validated in-game).** Names corrected and
  executed: alliance guard `is_allied_to` (unary), truce trigger `has_truce`; the
  "war" move uses the CB-free `add_pressed_claim = title:<key>`, and
  `create_alliance = <scope>` (both unary). Dead target titles are guarded with
  `<scope> = { is_alive = yes }`. `end_war` is war-scoped, so the `peace` move
  stays dropped until rewritten in a war scope. For a future forced-war lever
  the verified form is `start_war = { cb = claim_cb target = <holder>
  target_title = title:<key> }`.
- **CG3 — Standing orders (data-only generated file). DONE (in-game test
  pending).** Each hard order becomes a variable (`ck3llm_war_target` =
  claimed title, `ck3llm_ally_target` = character); the generated file only
  sets/clears that data and the tier, then calls the static, hand-tested
  `ck3llm_execute_orders`. That static effect re-checks readiness every yearly
  pulse (`has_claim_on`, `is_alive`, `is_allied_to`) before acting
  (`add_pressed_claim` / `create_alliance`). This keeps a malformed generated
  file from carrying effect logic, keeps the order alive for the plan's term
  instead of firing once, and lets vanilla AI pursue granted claims.
- **CG4 — Robustness.** Deterministic no-plan fallback + per-ruler error
  isolation so one bad response cannot abort the whole cycle (review v4 §6).
  *Fallback + isolation now implemented; keep as a regression guard.*
- **CG5 — Localize goals. DONE (with M21).** `five_year_goal` /
  `secondary_goal` / `focus` are rendered to
  `localization/english/ck3llm_l_english.yml` and shown to the player as a toast,
  so the LLM's narrative is no longer silently dropped.
- **CG6 — Measurement.** Run the three-arm, multi-seed A/B, with a
  counterfactual ("how often did vanilla attack the same target anyway?"), plus
  the cheap dose-response test (50 years, all kings tier 1 vs tier 5) to see if
  the soft lever does anything.
- **CG7 — Menu quality.** Province adjacency from the game install (retires
  risk #3); CB validity where feasible.

## Open items to verify (before building on them)

- **Injection levers** — modifiers move behaviour, `yearly_global_pulse` fires,
  `?=` works, save reloads cleanly with a regenerated mod. (Milestone 14.)
- **Ironman saves** — confirmed unparseable? If only checksummed, there may be
  a path.
- **Modifier names** — run `script_docs` once and target real names.
- **Console `run <file>`** — confirm it reads from a user `run/` folder.
- **Autosave interval options** — whether CK3 can be set to a 5-year autosave.

## Timing (per cycle, measured + estimated)

- Pipeline (unzip, index, graph, reference, relationships, summaries): ~45–50 s.
- LLM for ~105 Tier-1 rulers: ~5–15 min (the bottleneck).
- CK3 load: ~1–2 min.

**Total: ~7–18 minutes**, dominated by the LLM. Fine for a turn-based loop,
not real-time. Optimisations: skip unchanged realms, batch/parallelise LLM
calls, use a smaller model.

## Honest scope statement

This is a **turn-based** integration: the game is paused, a cycle is run, and
the save is reloaded. It does not run live inside a session.

---

# Cross-cutting rules

- Never `read()` the whole 170MB file into memory; stream or mmap.
- Never hardcode a closed set of keys — the save is modded (RICE/EP3) and
  contains unknown keys and title prefixes.
- Use `de_facto_liege` for politics, `de_jure_liege` only for claims/expansion.
- The parser must remain LLM-agnostic; the LLM layer consumes JSON only.
- Keep the injection layer behind a clean interface so "how a plan reaches CK3"
  can change without touching the parser or the LLM.
