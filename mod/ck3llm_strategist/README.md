# CK3 LLM Strategist

**Milestone 18.** The permanent, fixed-name mod that carries LLM intent into
CK3. It has two halves:

- **Static (hand-written, this folder):** the aggression modifier tiers and the
  `on_action` hook. Rarely changes.
- **Generated (written by Python every cycle):**
  `common/scripted_effects/ck3llm_plans.txt`. Overwritten each cycle; never edit
  it by hand.

## How it works

`yearly_global_pulse` fires `ck3llm_yearly_pulse`, which calls the generated
`ck3llm_apply_plans` effect. That effect, for each ruler with a plan:

1. reaches the ruler via a stable scope (`title:k_france.holder ?= {...}`, or
   `character:<id>` for the landless);
2. stamps `ck3llm_plan_id` so the plan is idempotent across pulses;
3. applies an aggression modifier tier for a fixed term;
4. runs up to two guarded hard actions (war / alliance / peace) whose in-game
   triggers make illegal moves silently no-op.

## Install

Copy (or junction/symlink) this folder into your CK3 mod directory:

```text
Documents/Paradox Interactive/Crusader Kings III/mod/ck3llm_strategist/
```

and add **"CK3 LLM Strategist"** to your launcher playset.

## Generate the effect

From the repo:

```bash
python -m ck3_strategist <save> --output output --llm ollama \
    --mod-dir mod/ck3llm_strategist
```

This writes `output/plans.json` and overwrites
`common/scripted_effects/ck3llm_plans.txt` (UTF-8 **with BOM**, as CK3
requires).

## Verify

1. Launch with `-debug_mode`; load a save and let a year pass.
2. In `logs/error.log`, look for `ck3llm: plan <id> applied`.
3. Check a targeted ruler received the tier modifier.

## Files

```text
mod/ck3llm_strategist.mod                         # launcher descriptor
ck3llm_strategist/descriptor.mod                  # in-folder descriptor
ck3llm_strategist/common/modifiers/               # hand-written tiers
ck3llm_strategist/common/on_action/               # the yearly hook
ck3llm_strategist/common/scripted_effects/        # GENERATED (stub committed)
```

## Stability rules

- Keep the mod name fixed; one permanent generated mod in the playset.
- Modifier tiers are additive-only.
- Never delete a modifier a save may still reference — neutralise it instead.
