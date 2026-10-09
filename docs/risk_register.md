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
| 7 | **`start_war` ignores AI readiness** — a forced war may be suicidal. | Medium | Medium | `mitigating` | Guard hard actions with truce / existing-war / strength checks; cap actions per ruler per cycle. |
| 8 | **`power_ratio` misleads** — currently excludes allies, liege, co-belligerents. | Medium | Low | `mitigating` | Definition now documented in `roadmap.md`; state it wherever shown. |
| 9 | **Save write-back fragility** — patching the gamestate and rezipping can corrupt saves. | Medium | High | `open` | Avoid the edit-and-rezip route unless the mod/console routes fail. |
| 10 | **Modifier/effect names are provisional** until a `script_docs` dump is captured. | Medium | Low | `mitigating` | All names live in `reference_data/translation.json` (data, not code) and are marked provisional; replace them with the dump for the target version. |
| 11 | **No evaluation** — nothing measures whether the LLM helps. | High | Medium | `open` | Milestone 20: observer-mode A/B (vanilla vs LLM), compare adherence, wars, realm growth; log prompts/outputs/seeds. |
| 12 | **Character-ID references break on death.** | Medium | Medium | `mitigating` | Key plans on `title:...holder`; use character IDs only for landless targets. |
| 13 | **Version drift** — save format changes between game versions. | Low | Medium | `mitigating` | Verified against 1.17 and 1.19; drift points documented in `../parser_implementation.md` §0. |
| 14 | **Timing** — the LLM is the bottleneck (~5–15 min/cycle). | High | Low | `accepted` | Fine for a turn-based loop; optimise later (skip unchanged realms, smaller model). |
| 15 | **Console `run <file>`** behaviour unconfirmed. | Medium | Low | `open` | Verify it reads from a user `run/` folder before relying on it for a live loop. |

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

## Open questions

- Do AI-personality modifiers (`ai_boldness`, `ai_war_chance`, ...) actually
  move behaviour, and how strongly? (Milestone 14 proved a *stat* modifier
  applies; the AI dials still need testing.)
- What are the exact `ai_*` modifier names? (Run `script_docs`.)
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
