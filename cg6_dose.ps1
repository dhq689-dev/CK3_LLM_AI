# CG6 dose-response runner.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File .\cg6_dose.ps1
#
# It generates the tier-1 effect, waits while you play the arm in CK3, generates
# the tier-5 effect, waits again, then evaluates. It prints the tier
# distribution after each generation so you can confirm the effect is correct.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

$saves  = "$env:USERPROFILE\OneDrive\Documents\Paradox Interactive\Crusader Kings III\save games"
$start  = Join-Path $saves "cg6_start.ck3"
$mod    = "mod\ck3llm_strategist"
$effect = Join-Path $mod "common\scripted_effects\ck3llm_plans.txt"

function Show-Tiers {
    $tiers = Select-String -Path $effect -Pattern '^\s+modifier = (ck3llm_aggressive_\d+)\s*$' |
        ForEach-Object { $_.Matches[0].Groups[1].Value } | Group-Object
    Write-Host ("    active tiers in effect: " + (($tiers | ForEach-Object { "$($_.Name)=$($_.Count)" }) -join ", "))
}

function Generate([int]$agg) {
    Write-Host ""
    Write-Host "==> Generating effect: --force-aggression $agg" -ForegroundColor Cyan
    python -m ck3_strategist "$start" --force-aggression $agg --mod-dir $mod --output "output_agg$agg" |
        Select-Object -Last 3
    Show-Tiers
}

Write-Host "In CK3, if it is running, close it now (the mod script reloads on launch)."
Read-Host "Press Enter to generate the TIER-1 effect"

Generate 0
Write-Host ""
Write-Host "Now in CK3: launch with -debug_mode, load 'cg6_start', play to your end date, save as 'dose_t1'." -ForegroundColor Yellow
Read-Host "When 'dose_t1' is saved, press Enter"

Generate 10
Write-Host ""
Write-Host "Now in CK3: launch, load 'cg6_start' (the SAME start), play to the SAME end date, save as 'dose_t5'." -ForegroundColor Yellow
Read-Host "When 'dose_t5' is saved, press Enter"

Write-Host ""
Write-Host "==> Evaluating" -ForegroundColor Cyan
python -m ck3_strategist.evaluate "$start" `
    --arm tier1=(Join-Path $saves "dose_t1.ck3") `
    --arm tier5=(Join-Path $saves "dose_t5.ck3")
