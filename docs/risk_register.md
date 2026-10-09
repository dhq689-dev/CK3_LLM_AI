# Risk Register

Live list of assumptions, risks, and open questions. Update as things are
verified. This replaces the older "readiness score" reviews as the working
risk document.

## How to read this

- **Likelihood / Impact**: Low / Medium / High.
- **Status**: `open`, `mitigating`, `verified`, `accepted` (constraint we live
  with), `closed`.

## Risks

| # | Risk / assumption | Likelihood | Impact | Status | Mitigation / how to verify |
|---|---|---|---|---|---|
| 1 | **Injection levers** — mod loading, `on_action` hooks, `yearly_global_pulse`, `?=`, and `add_character_modifier` are **verified working** (Milestone 14 smoke test). | — | — | `verified` | See "Injection findings" below. |
| 2 | **Ironman saves are unparseable** — the parser only handles plaintext. | High | Medium | `accepted` | Confirm directly; document as a hard constraint. If only checksummed, there may be a path. |
| 3 | **No geographic adjacency** — Milestone 15's war-target menu needs province adjacency; "shared de-jure liege" is a weak proxy. | High | Medium | `open` | Add static map data (province adjacency) to `reference_data/`. |
| 4 | **The menu can't be fully legal** — CB validity can't be replicated in Python. | High | Low | `accepted` | Treat the menu as *candidate*; in-game triggers are the final arbiter (guarded hard actions). |
| 5 | **LLMs cluster** — most rulers return "aggression 6–8, unify X". | High | Medium | `mitigating` | Deterministic trait-based aggression baseline; LLM only picks targets and deviations. |
| 6 | **Mod stability** — deleting a modifier a save references causes load errors. | Medium | Medium | `mitigating` | One permanent generated mod (fixed name); additive-only tiers; never delete referenced modifiers. |
| 7 | **`start_war` ignores AI readiness** — a forced war may be suicidal. | Medium | Medium | `open` | Cap actions per ruler per cycle; the invented readiness trigger was removed. Readiness re-checks return with the standing-orders design (CG3). |
| 8 | **`power_ratio` misleads** — currently excludes allies, liege, co-belligerents. | Medium | Low | `mitigating` | Definition now documented in `roadmap.md`; state it wherever shown. |
| 9 | **Save write-back fragility** — patching the gamestate and rezipping can corrupt saves. | Medium | High | `open` | Avoid the edit-and-rezip route unless the mod/console routes fail. |
| 10 | **Modifier/effect names may drift** across versions; not yet smoke-tested in-game. | Medium | Low | `mitigating` | All names live in `reference_data/translation.json` and `mod/ck3llm_strategist/common/` (data, not code); AI dials now sourced from the script_docs-derived modifier list. Verify in-game once. |
| 11 | **No evaluation** — nothing measures whether the LLM helps. | High | Medium | `mitigating` | M20 harness built: `runlog.py` logs prompts/outputs/seeds; `evaluate.py` scores wars, realm growth, and plan adherence between two saves. Actual observer-mode A/B runs still pending. |
| 12 | **Character-ID references break on death.** | Medium | Medium | `mitigating` | Key plans on `title:...holder`; use character IDs only for landless targets. |
| 13 | **Version drift** — save format changes between game versions. | Low | Medium | `mitigating` | Verified against 1.17 and 1.19; drift points documented in `../parser_implementation.md` §0. |
| 14 | **Timing** — the LLM is the bottleneck (~5–15 min/cycle). | High | Low | `accepted` | Fine for a turn-based loop; optimise later (skip unchanged realms, smaller model). |
| 15 | **Console `run <file>`** behaviour unconfirmed. | Medium | Low | `open` | Verify it reads from a user `run/` folder before relying on it for a live loop. |
| 16 | **Hard actions** — names validated (CG1) and executed cleanly in-game. | Low | High | `verified` | `add_pressed_claim` and `create_alliance` (unary forms) run without errors; targets guarded with `is_alive`. See "Soft + hard lever status". |
| 17 | **Modifier tiers stacked across cycles** (distinct keys coexisted and partly cancelled). | — | Medium | `closed` | The generator now clears all five tiers before applying the new one (review v4 §3). |
| 18 | **No-plan fallback was missing** — one bad LLM response aborted the whole cycle. | High | High | `closed` | `baseline_intent` + per-ruler `try/except`; failures logged as `fallback: true` (review v4 §6). |
| 19 | **LLM narrative discarded** — `focus` / goals never reach the game. | Low | Low | `closed` | M21/CG5: `Plan` carries the narrative, `localization.py` renders it, and the player sees their own plan as a toast. |
| 20 | **Evaluation can't attribute causation** — two arms can't separate the LLM from the deterministic dial. | High | Medium | `mitigating` | `compare_arms` three-arm harness (vanilla / baseline / LLM) with seeds; runs pending (review v4 §7). |
| 21 | **Single generated file blast radius** — one bad token breaks the effect for every ruler. | Medium | Medium | `open` | Name validator (CG1) plus the standing-orders data-only file (CG3) shrink it. |

## Injection findings (Milestone 14 — verified on 1.20.0.4)

Confirmed against a real game with a hand-written smoke-test mod:

1. **Mod loads** only if `supported_version` matches the game (`1.20.*` here);
   otherwise the launcher leaves it disabled.
2. **Script files must be UTF-8 BOM** (`utf-8-sig`), or CK3 warns and may
   misparse.
3. **Hook on_actions via the list, never `effect`.** Redefining an on_action's
   `effect` is overridden by the base game. Append to `on_actions = { ... }` /
   `events = { ... }` instead — those lists merge.
4. **`yearly_global_pulse` fires** — the workhorse for the translation layer.
5. **`?=` safe-scope works**: `title:k_france.holder ?= { ... }` reaches a
   character from a global pulse.
6. **`on_game_start` has no character scope** (global) — `add_character_modifier`
   fails there. Iterate (`every_ruler`) or use a title scope to reach characters.

Canonical working pattern:

```text
yearly_global_pulse = {
	on_actions = { ck3llm_yearly_pulse }
}

ck3llm_yearly_pulse = {
	effect = {
		title:k_france.holder ?= {
			add_character_modifier = { modifier = ck3llm_aggressive_4 years = 5 }
		}
	}
}
```

## Live smoke-test findings (M18/M19 — 1.20.0.4)

From running the generated effect in-game for the first time:

1. **`remove_character_modifier` is unary** — `remove_character_modifier =
   ck3llm_aggressive_1`, not `{ modifier = ... }` (the block form is parsed as
   the modifier value `{`, and errors).
2. **`type=value` character variables are fixed-point (×100000).** A variable
   set to `1066` is stored as `identity=106600000`; the parser normalises it.
3. **`NOT = { var:name = X }` errors when the variable is unset** ("Failed to
   fetch variable ... due to not being set"). The generated effect no longer
   uses a plan-id guard; per-pulse idempotence returns with standing orders.
4. **One bad effect aborts the whole generated effect.** The `remove` syntax
   above errored on the first ruler, so only that ruler's variables (set before
   the error) persisted. A name validator (CG1) plus small, guarded effects is
   the mitigation.
5. Confirmed working: the `yearly_global_pulse` hook, `?=` scope,
   `set_variable`, and the effect firing (hard actions below).
6. **`add_pressed_claim` works** as a unary effect: `add_pressed_claim =
   title:<key>` (no errors, applied to 31 rulers).
7. **`is_allied_to` and `create_alliance` are unary too.** `is_allied_to =
   <scope>` and `create_alliance = <scope>` (the shorthand sets the
   allied-through characters). The block forms error: `is_allied_to = { target
   = X }` → "Unknown trigger: target"; `create_alliance = { target = X }` →
   "allied_through_owner: field not set".
8. **Dead-but-existing targets error.** `exists` does not exclude a dead
   character, so an alliance target that died between save and pulse errors
   ("alliance target is dead"). Guard with `<scope> = { is_alive = yes }`.
9. **A toast only shows its body via a message type.** `send_interface_toast`
   with the default type renders the title but not the `desc`; the `desc` is
   shown by a message type whose `desc` uses `event_message_text`
   (`$DESCRIPTION$`). The mod defines `ck3llm_plan_toast` for this.

## Soft + hard lever status (validated in-game, 1.20.0.4)

- Aggression tiers apply, clear, and expire (save shows one
  `ck3llm_aggressive_*` per ruler with a 5-year `expiration_date`).
- `ck3llm_plan_id`/`ck3llm_plan_start` are written and read back
  (`previous_plan`) on the next parse.
- `add_pressed_claim` and `create_alliance` execute cleanly with the guards
  above.

## Open questions

- Do AI-personality modifiers (`ai_boldness`, `ai_war_chance`, ...) actually
  move behaviour, and how strongly? (Milestone 14 proved a *stat* modifier
  applies; the AI dials still need testing.)
- Does granting a pressed claim (`add_pressed_claim`) make vanilla AI pursue
  the target, and how often?
- Can CK3's autosave interval be set to 5 years (and is it scriptable)?
- What is the cleanest way to surface plans in-game (toast vs chronicle)?
- What is the minimal legal-move menu that is still useful?
- Does the console `run <file>` route work for a live loop?

## Recently closed

- **Repeated keys / participants / unknown traits** — fixed with regression
  tests (see git history).
- **Quadratic `primary_title`** — fixed with a holder index (~325× faster).
- **`assert` token budget** — replaced with truncation + logging.
- **Expired memories** — now filtered against `meta_date()`.
