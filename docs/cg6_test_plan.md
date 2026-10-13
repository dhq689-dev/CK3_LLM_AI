# CG6 test plan — dose-response + three-arm A/B

Goal: measure whether the LLM layer changes AI behaviour, and whether it
beats the deterministic baseline.

Everything is **turn-based**: generate an effect, reload CK3, play a fixed
number of years, save, repeat. Keep the player **passive** (observer mode if you
can, otherwise just don't act) so the only variable is the mod.

## Setup (once, in PowerShell)

```powershell
$REPO  = "C:\Users\dhq68\projects\ck3_LLM_AI"
$SAVES = "C:\Users\dhq68\OneDrive\Documents\Paradox Interactive\Crusader Kings III\save games"
```

CK3: launch with `-debug_mode`, and the playset must include
**"CK3 LLM Strategist"**.

Create a clean starting point:

1. Start a **new 1066 game** (any ruler; observer mode if available).
2. Pause immediately and save it as **`cg6_start`**. (Save before the first
   1 January so no plan has applied yet.)

Every arm below loads `cg6_start`, runs to a fixed date **30 years later
(1 January 1096)**, and saves under a new name. Run at max speed, don't act.

---

## Part A — dose-response (soft lever: all kings tier 1 vs tier 5)

No LLM needed; fast.

**Arm A1 (tier 1):**
```powershell
python -m ck3_strategist "$SAVES\cg6_start.ck3" --force-aggression 0 `
  --mod-dir "$REPO\mod\ck3llm_strategist" --output "$REPO\output_t1"
```
Reload CK3 → load `cg6_start` → run to **1096.1.1** → save as **`dose_t1`**.

**Arm A2 (tier 5):**
```powershell
python -m ck3_strategist "$SAVES\cg6_start.ck3" --force-aggression 10 `
  --mod-dir "$REPO\mod\ck3llm_strategist" --output "$REPO\output_t5"
```
Reload CK3 → load `cg6_start` → run to **1096.1.1** → save as **`dose_t5`**.

**Compare:**
```powershell
python -m ck3_strategist.evaluate "$SAVES\cg6_start.ck3" `
  --arm tier1="$SAVES\dose_t1.ck3" --arm tier5="$SAVES\dose_t5.ck3"
```

Read `wars_started` and `realm_growth` per arm. If tier 5 shows materially more
wars/growth, the soft lever works; if not, it's a dud (a valid finding).

---

## Part B — three-arm A/B (vanilla vs baseline vs LLM)

Needs Ollama running (GPU enabled). Same `cg6_start` and same 30-year horizon.

**Arm B1 (vanilla — empty effect, no steering):**
```powershell
python -m ck3_strategist "$SAVES\cg6_start.ck3" --llm baseline --limit 0 `
  --mod-dir "$REPO\mod\ck3llm_strategist" --output "$REPO\output_none"
```
(`--limit 0` plans no rulers, so the written effect is empty = vanilla. A planner
flag is needed so the empty effect is actually written.)
Reload → load `cg6_start` → run to **1096.1.1** → save as **`arm_none`**.

**Arm B2 (baseline — trait tiers, no LLM, no orders):**
```powershell
python -m ck3_strategist "$SAVES\cg6_start.ck3" --llm baseline `
  --mod-dir "$REPO\mod\ck3llm_strategist" --output "$REPO\output_baseline"
```
Reload → load `cg6_start` → run to **1096.1.1** → save as **`arm_baseline`**.

**Arm B3 (LLM):**
```powershell
python -m ck3_strategist "$SAVES\cg6_start.ck3" --llm ollama --model qwen2.5:3b --seed 1234 `
  --mod-dir "$REPO\mod\ck3llm_strategist" --output "$REPO\output_llm2" --log-dir "$REPO\output_llm2\logs"
```
Reload → load `cg6_start` → run to **1096.1.1** → save as **`arm_llm`**.

**Compare (with plan adherence from the LLM cycle log):**
```powershell
python -m ck3_strategist.evaluate "$SAVES\cg6_start.ck3" `
  --arm none="$SAVES\arm_none.ck3" `
  --arm baseline="$SAVES\arm_baseline.ck3" `
  --arm llm="$SAVES\arm_llm.ck3" `
  --cycle "$REPO\output_llm2\logs\cycle_1066-9-15.jsonl"
```
(Replace the `cycle_*.jsonl` name with the actual file in `output_llm2\logs\` —
its date matches `cg6_start`.)

---

## What to report back

- The output of each `evaluate` command (the JSON).
- Anything odd: rulers not steered, load errors, or a save that wouldn't load.

## Notes / fallbacks

- If a full 30-year run is too slow, add `--limit 20` to the generate commands
  and run a shorter horizon (e.g. 20 years) — note it in the report.
- If the `observe`/observer route doesn't work, start as a minor ruler and simply
  don't act; the player's ruler is excluded from planning either way.
- `--force-aggression` and `--limit 0` need no Ollama; only B3 does.
- CK3 is deterministic from a given save in observer mode, so each pair of arms
  differs only by the generated effect.
