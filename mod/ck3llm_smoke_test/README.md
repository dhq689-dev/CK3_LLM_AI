# CK3 LLM Strategist — Smoke Test Mod

**Milestone 14.** The smallest possible mod that proves the injection levers
work, before we build anything on top of them.

## What it proves

1. A generated/static mod **loads**.
2. An `on_action` **fires** (`on_game_start` and `yearly_global_pulse`).
3. A **character modifier applies** (`diplomacy +5`).
4. The `?=` **safe-scope operator** works (`title:...holder ?= {...}`).
5. A save **reloads cleanly** with the mod active.

It deliberately uses only a plain, definitely-valid stat effect (`diplomacy`),
so a failure means the *mechanism* is wrong, not a modifier name. The real AI
dials (`ai_boldness`, ...) come later, once we have the `script_docs` dump.

## Install

Copy this folder into your CK3 mod directory:

```text
Documents/Paradox Interactive/Crusader Kings III/mod/ck3llm_smoke_test/
```

(Or create a directory junction/symlink from the repo's `mod/ck3llm_smoke_test`
to that location.)

Then, in the CK3 launcher, add **"CK3 LLM Strategist - Smoke Test"** to your
playset and enable it.

## Verify

1. Launch CK3 with **debug mode** on (Steam launch option `-debug_mode`), so
   `debug_log` writes to the log.
2. Load a save and play for a moment (or just load — `on_game_start` fires on
   load).
3. Open:

   ```text
   Documents/Paradox Interactive/Crusader Kings III/logs/error.log
   ```

   and search for `ck3llm smoke test`.
4. Check your ruler's **Diplomacy** stat — it should be **+5**.

## What to report back

- Any `ck3llm smoke test` lines that appear in `error.log`.
- Any **errors** mentioning `ck3llm`, `on_game_start`, `yearly_global_pulse`,
  `?=`, or `ck3llm_test_modifier`.
- Whether the Diplomacy stat actually changed.

## Known uncertainties (what we're testing)

- Does `on_game_start` give a **character scope**? If not, its `debug_log` will
  error but the yearly path still proves the mechanism.
- Does `yearly_playable_pulse` / `yearly_global_pulse` fire as expected?
- Is `?=` valid here, and does `title:k_france.holder` resolve? (Change
  `k_france` to a title your save actually has if needed.)
- Do modifier names like `ai_boldness` exist? (Run `script_docs` in the console
  to dump the authoritative list for your version.)

## Files

```text
descriptor.mod
common/modifiers/ck3llm_test_modifiers.txt     # the modifier definition
common/on_action/ck3llm_test_on_actions.txt    # when it runs
common/scripted_effects/ck3llm_test_effects.txt # what it does
```
