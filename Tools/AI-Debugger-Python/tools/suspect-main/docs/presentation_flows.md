# SUSPECT Presentation Flow Guide

A quick-hit script you can follow when walking through SUSPECT with your professor. Each flow builds on the previous one, highlights a specific capability, and lists the exact commands to run so the terminal output matches what you describe. Run everything from the project root (`/Users/louis/local/suspect`) and make sure the virtual environment is active.

```bash
cd /Users/louis/local/suspect
source .venv/bin/activate  # if not already active
```

---

## Flow 1 — Reset & Explore the Sample Project
1. Ensure the rich sample project is in a known good state.
   ```bash
   python rich_sample_project/toggle_failures.py off
   ```
2. Run the full test suite once to prove everything is green.
   ```bash
   pytest -q rich_sample_project
   ```
3. Show the help so everyone sees the CLI surface area.
   ```bash
   suspect --help
   suspect run --help
   ```

**Talking points:** Explain SBFL vs MBFL at a high level, mention the plugin architecture, and point out the default artifacts (`matrix.csv`, `matrix.json`).

---

## Flow 2 — SBFL Baseline with Ochiai Ranking
1. Introduce intentionally failing tests to create suspicious signals.
   ```bash
   python rich_sample_project/toggle_failures.py on
   pytest -q rich_sample_project  # expect failures
   ```
2. Run SBFL only and review the Top table plus coverage summary.
   ```bash
   suspect run --enable sbfl --project rich_sample_project \
     --tests "pytest -q" --metric ochiai --print-top 12 \
     --print-coverage --coverage-top 8
   ```

**Talking points:** Describe how coverage contexts feed `ef`/`ep`, show how the coverage section pinpoints poorly-covered files, and note that exporters wrote `matrix.csv`/`matrix.json` inside `rich_sample_project/`.

---

## Flow 3 — Combined SBFL + MBFL with Exporters
1. Keep the failures enabled so MBFL sees interesting behavior.
2. Run both adapters, export to a dedicated folder, and surface kill summary output.
   ```bash
   mkdir -p reports
   suspect run --enable sbfl mbfl --project rich_sample_project \
     --tests "pytest -q" --print-top 15 \
     --output-csv reports/suspect_matrix.csv \
     --output-json reports/suspect_matrix.json \
     --output-kill-summary reports/kill_summary.json \
     --exporters csv json kill_summary --print-coverage --coverage-top 5
   ```
3. Preview the CSV to connect console numbers to artifacts.
   ```bash
   head -n 12 reports/suspect_matrix.csv
   ```

**Talking points:** Walk through the combined matrix, point out MBFL columns (e.g., `mutants_killed`, `mbfl_sbi`), and show how exporter plugins swap destinations effortlessly.

---

## Flow 4 — MBFL on a Green Suite (Mutation Baseline)
1. Turn failures off so MBFL focuses on survivor ratios.
   ```bash
   python rich_sample_project/toggle_failures.py off
   pytest -q rich_sample_project
   ```
2. Run MBFL alone with full coverage output for context.
   ```bash
   suspect run --enable mbfl --project rich_sample_project \
     --tests "pytest -q" --print-top 10 \
     --print-coverage --coverage-top 0
   ```
3. Inspect the diagnostics payload for survivor details.
   ```bash
   open .suspect.mutatest.json  # macOS quick-look; use cat/jq elsewhere
   ```

**Talking points:** Emphasize how, even when all tests pass, MBFL highlights weakly asserted code (high survivor counts) and stores rich metadata in `.suspect.mutatest.json`.

---

## Flow 5 — Repair Detection & Fail→Pass Analysis
1. Re-enable the failure to demonstrate repair detection.
   ```bash
   python rich_sample_project/toggle_failures.py on
   pytest -q rich_sample_project
   ```
2. Run MBFL with repair detection budgets and discuss the additional metrics.
   ```bash
   suspect run --enable mbfl --project rich_sample_project \
     --tests "pytest -q" --mbfl-allow-failing \
     --mbfl-kf-detection auto --mbfl-kf-budget 45 --mbfl-kf-max-mutants 15 \
     --print-top 12
   ```
3. Highlight the `mkf` (mutant kill failures) and `mbfl_sbi` shifts in the console table.
4. Show the diagnostics file entries for `repair_events`.
   ```bash
   jq '.repair_events | .[:5]' .suspect.mutatest.json
   ```

**Talking points:** Explain the budget knobs, how fail→pass flips increase confidence, and how SUSPECT guards against timeouts.

---

## Flow 6 — Per-Test Attribution Sampler
1. Keep failures on for richer attribution data.
2. Launch MBFL with per-test attribution enabled.
   ```bash
   suspect run --enable mbfl --project rich_sample_project \
     --tests "pytest -q" --mbfl-allow-failing \
     --mbfl-per-test-attribution on --mbfl-pta-budget 20 \
     --mbfl-pta-sample 0.4 --print-top 10
   ```
3. Explore how killers are shown inline and in diagnostics.
   ```bash
   jq '.killers_by_method | to_entries[:5]' .suspect.mutatest.json
   ```

**Talking points:** Show how per-test attribution links suspicious methods to specific pytest node IDs and how sampling controls runtime.

---

## Flow 7 — Auto-Cleanup & Process Hygiene
1. Demonstrate automatic cleanup right after a run.
   ```bash
   suspect run --enable sbfl --project rich_sample_project \
     --tests "pytest -q" --print-top 5 --auto-clean
   ```
2. Show manual cleanup options, including keeping outputs.
   ```bash
   suspect clean --project rich_sample_project --yes --keep-outputs
   ```
3. (Optional) Include helper virtual environments.
   ```bash
   suspect clean --project rich_sample_project --yes --with-venv
   ```

**Talking points:** Stress how auto-clean keeps the workspace tidy, while manual cleanup offers control over exporters and helper environments.

---

## Flow 8 — Wrap-Up & Next Steps
1. Return the sample project to a safe, green state.
   ```bash
   python rich_sample_project/toggle_failures.py off
   pytest -q rich_sample_project
   ```
2. Summarize key artifacts created during the demo:
   - `reports/suspect_matrix.csv` / `reports/suspect_matrix.json`
   - `.suspect.mutatest.json`
   - `kill_summary.json`
3. Invite follow-up experiments (custom adapters, third-party exporters, alternative metrics).

**Talking points:** Reinforce SUSPECT’s extensibility (plugin system), dual SBFL/MBFL strengths, and how the diagnostics feed deeper research questions.

---

### Tips for a Smooth Presentation
- Clear artifacts between flows with `suspect clean --project rich_sample_project --yes` if you want fresh output each time.
- Use `watch -n 1 ls -1` in another terminal to show files appearing/disappearing live.
- Capture the console with `script --flush demo.log` if you want a transcript afterward.
- If the MBFL runs feel slow, mention sampling (`--mbfl-sample 0.25`) and include/exclude globs.

Good luck with the presentation! Let the professor drive a command or two for extra engagement.
