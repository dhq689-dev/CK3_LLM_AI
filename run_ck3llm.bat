@echo off
setlocal
rem --- CK3 LLM Strategist: one-click cycle launcher ---
rem Runs the pipeline on the newest save that uses the CK3 LLM Strategist mod,
rem then relaunch CK3 and load that save to apply it.
rem
rem Edit MODEL and SAVES below to taste. To keep it running in the background
rem instead, replace --saves-dir with --watch (it will fire on every save).

cd /d "%~dp0"

set MODEL=qwen2.5:3b
set SAVES=%USERPROFILE%\OneDrive\Documents\Paradox Interactive\Crusader Kings III\save games

echo Running CK3 LLM Strategist on the newest modded save from:
echo   %SAVES%
echo (model: %MODEL%)
echo.

python -m ck3_strategist --saves-dir "%SAVES%" ^
  --mod-marker ck3llm_strategist ^
  --llm ollama --model %MODEL% --seed 1234 ^
  --cadence --plans-store "output\plans_store.json" ^
  --mod-dir "mod\ck3llm_strategist" --log-dir "output\logs" --output "output"

echo.
echo Done. Relaunch CK3 and load the save to apply the new plan.
pause
