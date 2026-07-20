# SUSPECT (Software Understanding via Spectrum, Program Execution, Complexity, and Testing)

SUSPECT is a Python-based research tool that integrates multiple fault localization and software quality techniques into a single, extensible framework. It utilizes Spectrum-Based Fault Localization (SBFL) through coverage analysis and test outcomes, Mutation-Based Fault Localization (MBFL) by executing program mutants, and code complexity analysis employing metrics such as Cyclomatic complexity, Maintainability Index, and Halstead measures. By combining these approaches, SUSPECT generates a comprehensive, method-level suspiciousness and complexity matrix in CSV and JSON formats. This output facilitates systematic analysis of buggy software, ranking suspicious program elements, and investigating the correlation between structural complexity and fault proneness, all through a unified command-line tool.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Requirements:
- Python 3.9+
## Overview

SUSPECT is a research-grade CLI for analyzing Python projects with Spectrum-Based Fault Localization (SBFL) and Mutation-Based Fault Localization (MBFL). It produces method-level suspiciousness matrices, pretty console tables, optional exporters, and rich diagnostics you can mine for follow-up investigations.

---

## ✨ Highlights

- **SBFL + coverage** in one command (Ochiai, Tarantula, Jaccard, SBI, etc.).
- **MBFL via mutatest** with optional fail→pass repair detection and per-test attribution.
- **Complexity metrics** (cyclomatic, Maintainability Index, Halstead) powered by radon, rendered in the same Top table and matrix exports.
- **Lizard code metrics** (LOC, parameter count, function length) via the Lizard adapter; merged into the same matrix and console table.
- **Centralized outputs, observability, and caching (v0.1.0)**: consolidate all artifacts with `--consolidate-output`/`--out-dir`, emit structured event logs with `--log-file`/`--log-console`, and speed up reruns via `--cache-adapters`.
- **CSV/JSON matrices** that plug into downstream dashboards or notebooks.
- **Plugin architecture** for adapters and exporters.

---

## 🧰 Requirements

- Python 3.9+
- `pip`, `pytest >= 7.4`, `coverage[toml] >= 7.5`
- `radon` (for complexity), `lizard` (for LOC/params/length) — both are declared in `pyproject.toml` and installed with `pip install -e .`.
- macOS/Linux; Windows works but commands below assume a POSIX shell.

---

## 🏗️ Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

# Optional: install mutatest into the same venv (or a dedicated one)

```

> Tip: set `SUSPECT_MUTATEST_VENV=/path/to/venv` if you prefer MBFL to run inside a separate environment.

---

## Cheat Sheet (one-liners)

- SBFL baseline

```bash
suspect run --enable sbfl --project . --tests "pytest -q" --metric ochiai --print-top 10 --print-coverage
```

- MBFL only (suite green recommended)

```bash
suspect run --enable mbfl --project . --tests "pytest -q" --print-top 10
```

- Combine SBFL + MBFL + complexity + Lizard

```bash
suspect run --enable sbfl mbfl complexity lizard --project . --tests "pytest -q" --metric cyclomatic --print-top 10
```

- Combine all and show the full Top table (no truncation)

```bash
suspect run --enable sbfl mbfl complexity lizard --project . --tests "pytest -q" --metric ochiai --print-top all
```

- Visualize killers: Kill matrix (methods × tests)

```bash
suspect run --enable mbfl --project . --tests "pytest -q" --show-kill-matrix --kill-matrix-top-methods 12 --kill-matrix-top-tests 8
```

- Visualize per-mutant matrix (mutants × tests)

```bash
suspect run --enable mbfl --project . --tests "pytest -q" --show-mutant-matrix --mutant-matrix-top-mutants 30
```

- Show all ranked methods (no truncation)

```bash
suspect run --enable sbfl complexity --project . --tests "pytest -q" --metric ochiai --print-top all
```

- Discover available plugins

```bash
suspect run --list-adapters
suspect run --list-exporters
```

- Clean artifacts (keep reports with --keep-outputs)

```bash
python scripts/clean_suspect_artifacts.py --project . --yes
```

### Centralize outputs into one folder

To write and collect all outputs in a single folder at the CLI root (your current working directory):

- Auto-create a short per-project folder (e.g., sus-rsp for rich_sample_project):

```bash
suspect run --project rich_sample_project --consolidate-output
```

- Or choose an explicit directory (relative or absolute):

```bash
suspect run --project rich_sample_project --out-dir ./.suspect_out
```

Tip: set the environment variable `SUSPECT_OUT_DIR` to make `--out-dir` the default.

---

## 🚀 Quick Start Commands

### 1. SBFL baseline

```bash
suspect run --enable sbfl --project . --tests "pytest -q" \
  --metric ochiai --print-top 10 --print-coverage
```

Outputs: `matrix.csv`, `matrix.json`, console Top table, and coverage summary.

### 2. MBFL only (green suite)

```bash
suspect run --enable mbfl --project . --tests "pytest -q" \
  --print-top 10 --print-coverage 0
```

### 3. MBFL with failing tests & repair detection

```bash
suspect run --enable mbfl --project . --tests "pytest -q" \
  --mbfl-allow-failing \
  --mbfl-kf-detection auto --mbfl-kf-budget 45 --mbfl-kf-max-mutants 15 \
  --print-top 10
```

### 4. Per-test attribution sampler

```bash
suspect run --enable mbfl --project . --tests "pytest -q" \
  --mbfl-allow-failing \
  --mbfl-per-test-attribution on --mbfl-pta-budget 20 --mbfl-pta-sample 0.4 \
  --print-top 10
```

### 5. Complexity snapshot (cyclomatic, MI, Halstead)

```bash
suspect run --enable complexity --project . --tests "pytest -q" \
  --metric cyclomatic --print-top 15 --complexity-include "src/**"
```

Add `--sample-project-only` if you simply want to reproduce the rich sample project demo without touching the rest of your repo. The Top table and matrix will include maintainability index and Halstead metrics automatically when available.

### 6. Lizard metrics (LOC/params/length)

```bash
suspect run --enable lizard --project . --tests "pytest -q" \
  --metric cyclomatic --print-top 12
```

Notes:
- Lizard metrics are added as columns `loc`, `params`, `length` in the Top table and in `matrix.csv/json`.
- Scoping: the current Lizard adapter honors `--complexity-include/--complexity-exclude` globs for file selection.
- You can combine Lizard with any other adapter, e.g.:

```bash
suspect run --enable sbfl mbfl complexity lizard --project . --tests "pytest -q" \
  --metric cyclomatic --print-top 10
```

### 7. MBFL visualizations and detailed tables (optional)

- Kill matrix (methods × tests):

```bash
suspect run --enable mbfl --project . --tests "pytest -q" \
  --show-kill-matrix --kill-matrix-top-methods 12 --kill-matrix-top-tests 8 \
  --print-top 10
```

- Per-mutant matrix (mutants × tests):

```bash
suspect run --enable mbfl --project . --tests "pytest -q" \
  --show-mutant-matrix --mutant-matrix-top-mutants 30 --kill-matrix-top-tests 8
```

- Element/Mutant grouped matrix (methods grouped, mutants listed per method):

```bash
suspect run --enable mbfl --project . --tests "pytest -q" \
  --show-element-mutant-matrix --kill-matrix-top-methods 10 --kill-matrix-top-tests 6
```

- MBFL-focused Top table and optional per-mutant details:

```bash
suspect run --enable mbfl --project . --tests "pytest -q" \
  --print-top 10 --show-mbfl-table --show-mutant-details --mutant-details-table
```

- Inline killer tests inside the Top table (when PTA/diagnostics available):

```bash
suspect run --enable mbfl --project . --tests "pytest -q" \
  --print-top 10 --show-killers
```

---

## 📦 Project Structure Cheat Sheet

```
suspect/
├── adapters/          # Metric adapters (sbfl, mbfl, etc.)
├── exporters/         # CSV/JSON and optional custom exporters
├── formulas/          # Suspiciousness formulas (sbfl/mbfl)
├── cli.py             # CLI entrypoint (python -m suspect)
└── tests/             # Pytest suite covering adapters & CLI

rich_sample_project/   # Demo app used in docs & integration tests
docs/                  # This README + MBFL deep dive guide
```

---

## 🧠 How SUSPECT Works

### SBFL Overview

SUSPECT instruments your test suite to see which methods failing and passing tests execute, then scores each method using standard SBFL formulas (Ochiai, Tarantula, Jaccard, SBI). The results are persisted to `matrix.csv` / `matrix.json` and optionally surfaced in a Top-N console table.

### SBFL Workflow

1. **Coverage run** – Executes the test command under `coverage run` with `dynamic_context=test_function`, producing `.suspect.coverage.json` (per-test execution contexts) alongside `.coverage` data.
2. **Outcome capture** – Re-runs pytest with `--junitxml=.suspect.pytest.xml` to record failing (`Nf`) and passing (`Np`) test nodeids.
3. **Line↔method mapping** – Parses source files with the AST-based `MethodIndex` to map `(file, line)` to qualified method names like `bank.py:BankAccount.deposit`.
4. **Aggregation** – Counts unique failing (`ef`) and passing (`ep`) contexts per method, computes suspiciousness metrics with safe zero-division guards, and merges them into an in-memory matrix.
5. **Export & presentation** – Writes CSV/JSON (or custom exporters), prints the console Top table, and emits diagnostics when requested.

### Architecture Highlights

- **CLI (`suspect/cli.py`)** – Argument parsing, orchestration, console rendering.
- **Orchestrator (`orchestrator.py`)** – Executes selected adapters (SBFL, MBFL, complexity) and merges their outputs.
- **Adapters (`suspect/adapters/…`)** – Implement analysis-specific collection logic (coverage SBFL adapter, MBFL mutatest adapter, etc.).
- **Mapping (`mapping.py`)** – Maintains the AST-driven method index shared across adapters.
- **Matrix (`matrix.py`) & exporters** – Provide a normalized store for metrics and format them for CSV/JSON or plugin exporters.

### SBFL Metrics Cheat Sheet

| Metric | Description |
| --- | --- |
| `ef` | Count of unique failing test contexts that executed the method. |
| `ep` | Count of unique passing test contexts that executed the method. |
| `ochiai`, `tarantula`, `jaccard`, `sbi` | Classic SBFL formulas computed from `ef`, `ep`, `Nf`, and `Np`, with zero-division guards. |

### Cyclomatic Complexity Adapter

The complexity adapter uses `radon` to compute McCabe cyclomatic scores, Maintainability Index, and Halstead metrics for every method discovered by `MethodIndex`.

- Enable it with `--enable complexity` (optionally alongside SBFL/MBFL). The CLI automatically adds `cyclomatic`, `maintainability_index`, and `halstead_*` columns (volume, difficulty, effort, bugs) to the matrix.
- Scope the analysis with `--complexity-include` / `--complexity-exclude` globs. By default the adapter walks every `.py` file outside common build and virtualenv folders.
- Tests are skipped unless you opt in via `--include-tests`; alternatively, `--sample-project-only` limits both the test command and complexity scan to `rich_sample_project/**` for the bundled demo.
- The Top table ranks by `--metric cyclomatic` (or your chosen metric) and shows the auxiliary maintainability and Halstead values alongside the cyclomatic score.

Consider combining SBFL suspiciousness and cyclomatic scores to spot highly complex, failure-prone code.

### Lizard Code Metrics Adapter

The Lizard adapter computes basic function-level size metrics and merges them per-method into the matrix.

- Columns emitted per method:
  - `loc` — Lizard NLOC (non-comment logical lines of code)
  - `params` — function parameter count
  - `length` — function length (in lines)
- Enable with `--enable lizard` (can be used alongside SBFL/MBFL/complexity).
- File selection uses the same include/exclude globs documented for complexity (currently `--complexity-include/--complexity-exclude`).
- The Top table will automatically show these columns when present; no extra flags required.

### Artifacts & Fallbacks

- Coverage artifacts are written inside the target project: `.coverage`, `.suspect.coverage.json`, `.suspect.pytest.xml`.
- Matrices are written under the `--project` path unless you provide absolute `--output-csv/--output-json` paths.
- If coverage contexts are missing, the SBFL adapter falls back to per-line aggregates to keep scores usable (pass-only if necessary).
- Mapping remains conservative—unsupported coverage payloads simply reduce resolution rather than crash the run.

---

## ⚙️ Common Flags (CLI)

- `--enable sbfl mbfl complexity lizard` – choose analyses (default: `sbfl`).
- `--metric ochiai|tarantula|jaccard|sbi|mbfl_sbi|cyclomatic` – ranking signal for Top table.
- `--print-top N|all` – show ranked methods (`0` disables; `all` shows every method).
- `--print-coverage` / `--coverage-top N` – coverage report similar to `coverage report -m`.
- `--exclude-glob GLOB` – omit files from Top table & coverage (repeatable).
- `--exporters csv json ...` – run exporters from the registry.
- `--method-name-only` – trim file names from console output.
- `--show-killers` – show top killer tests inline in the Top table when PTA/diagnostics exist.
- `--list-adapters` / `--list-exporters` – print available adapters/exporters and exit.
- `--fail-on-tool-error` – raise instead of warning on adapter failure.

Output & consolidation:

- `--consolidate-output` – copy key artifacts into a single auto-named folder at the CLI root (e.g., `sus-<short-project>`).
- `--out-dir PATH` – write all exporter outputs and consolidated artifacts into PATH. Env default: `SUSPECT_OUT_DIR`.

Observability:

- `--log-file PATH` – write structured JSONL events to PATH (append mode). Each event includes `phase`, `adapter`, `status`, and timings.
- `--log-console` – echo key events to console; add `--log-console-verbose` for detailed traces.

Caching:

- `--cache-adapters` – enable disk cache for adapter outputs keyed by project snapshot, tests, and adapter.
- `--no-cache` – force bypass cache for this run.
  - Env: `SUSPECT_CACHE_TTL` (seconds, default: no expiry), `SUSPECT_CACHE_BYPASS=1` to skip caches.

Artifact repository:

- `--artifact-repo-dir PATH` – maintain an `artifact_manifest.json` catalog of produced files. Env: `SUSPECT_ARTIFACT_MAX` to prune older entries.

MBFL-specific additions:

- `--mbfl-allow-failing` – continue even if the baseline pytest run fails.
- `--mbfl-kf-detection on|auto` – run the fail→pass harness within a time budget.
- `--mbfl-kf-budget SEC` / `--mbfl-kf-max-mutants N` – tune repair detection cost.
- `--mbfl-per-test-attribution on|auto` – attribute kills to pytest nodeids.
- `--mbfl-include/--mbfl-exclude GLOB` – restrict or skip files.
- `--mbfl-sample RATE` – sample mutants (0 < RATE ≤ 1.0).
- `--show-kill-matrix` / `--kill-matrix-top-methods N` / `--kill-matrix-top-tests N` – render method×test kill matrix.
- `--show-mutant-matrix` / `--mutant-matrix-top-mutants N` / `--mutant-matrix-all-tests` – render per-mutant matrix.
- `--show-element-mutant-matrix` – grouped Element/Mutant matrix view.
- `--show-mbfl-table` – MBFL-focused table with mkf/mkp columns.
- `--show-mutant-details` / `--mutant-details-table` – narrative + compact table of mutants.

Environment helpers:

- `SUSPECT_MUTATEST_VENV` – path to venv containing mutatest & pytest binary.
- `SUSPECT_DIAGNOSTICS_LEVEL` (`min|normal|full`) – trim `.suspect.mutatest.json` payloads.
- `SUSPECT_MBFL_SAFE_MODE=1` – auto-enable conservative PTA defaults.

---

## 🧾 Outputs

| Artifact | Description |
| --- | --- |
| `matrix.csv` | Tabular method metrics (one row per method). Columns include SBFL (`ef`,`ep`,`ochiai`,`tarantula`,`jaccard`,`sbi`), MBFL (`mbfl_sbi`,`mkf`,`mkp`,`mutants_*`), Complexity (`cyclomatic`,`maintainability_index`,`halstead_*`), and Lizard (`loc`,`params`,`length`). |
| `matrix.json` | JSON `{ "module.py:Class.method": { metric: value } }` with the same union of columns. |
| `.suspect.mutatest.json` | MBFL diagnostics, test attribution, survivor fallback notes. |
| `.suspect.mbfl.baseline.xml` | Baseline pytest JUnit (only if MBFL ran). |
| `.suspect.mbfl.mutant.xml` | Last mutant run JUnit (overwritten each run). |

Exporters can emit additional files (e.g., CSV, JSON, custom dashboards) by registering via `suspect.exporters` entry points.

---

### Outputs at a glance

| Artifact | SBFL | MBFL | Complexity | Lizard | Combined | Notes |
| --- | :---: | :---: | :---: | :---: | :---: | --- |
| `matrix.csv` | ✓ | ✓ | ✓ | ✓ | ✓ | Emitted by exporters (default `csv`). Use `--output-csv` to change path. |
| `matrix.json` | ✓ | ✓ | ✓ | ✓ | ✓ | Emitted by exporters (default `json`). Use `--output-json` to change path. |
| `kill_summary.json` | — | ✓* | — | — | ✓* | Requires a `kill_summary` exporter to be installed; otherwise skipped with a warning. |
| `.suspect.coverage.json` | ✓ | — | — | — | ✓ | Per-test coverage contexts (SBFL). |
| `.suspect.pytest.xml` | ✓ | — | — | — | ✓ | Pytest JUnit for SBFL pass/fail outcomes. |
| `.suspect.mutatest.json` | — | ✓ | — | — | ✓ | MBFL diagnostics (runs, killers, optional PTA, survivor notes). |
| `.suspect.mbfl.baseline.xml` | — | ✓ | — | — | ✓ | MBFL baseline JUnit. |
| `.suspect.mbfl.mutant.xml` | — | ✓ | — | — | ✓ | Last mutant run JUnit (overwritten each run). |
| `.coverage` | ✓ | — | — | — | ✓ | Coverage data file; also produced when using `--print-coverage`. |
| `sus-<proj>/artifact_manifest.json` | ✓ | ✓ | ✓ | ✓ | ✓ | Index of consolidated artifacts when `--consolidate-output` or `--artifact-repo-dir` is used. |

---

## 🔭 Observability & caching (v0.1.0)

SUSPECT emits structured events you can pipe to a file or the console. This makes it easier to analyze performance, cache hits, and adapter outcomes over time.

Examples:

```bash
suspect run --enable sbfl complexity --project rich_sample_project \
  --tests "pytest -q -k 'not mbfl_tests'" \
  --consolidate-output \
  --log-file sus-rsp/suspect.events.jsonl \
  --cache-adapters
```

Tips:

- JSONL schema includes: `timestamp`, `phase` (run_start, adapter_start, adapter_end, run_end), `adapter`, `status` (ok, error, cache_hit), `elapsed_ms`, and optional `details`.
- Control cache behavior with `SUSPECT_CACHE_TTL` (seconds), `SUSPECT_CACHE_BYPASS=1`, and the `--no-cache` flag.
- Consolidate artifacts with `--consolidate-output` or direct them with `--out-dir`. Use `--artifact-repo-dir` to maintain a manifest and enable pruning via `SUSPECT_ARTIFACT_MAX`.

What’s new in 0.1.0:

- Centralized output folder and artifact manifest.
- Structured event logging to JSONL and optional console.
- Disk cache for adapters (opt-in) for faster reruns.

Legend: ✓ = produced, — = not produced, ✓* = produced if optional exporter is available.

## 🧩 Built-in adapters and exporters

Adapters (enable with `--enable`):

- `sbfl` — Spectrum-Based Fault Localization via coverage + junit (metrics: `ef`, `ep`, `ochiai`, `tarantula`, `jaccard`, `sbi`).
- `mbfl` — Mutation-Based Fault Localization using mutatest (metrics: `mbfl_sbi`, `mkf`, `mkp`, `mutants_detected`, `mutants_survived`, `mutants_total`, `mutation_score`).
- `complexity` — Radon complexity metrics (metrics: `cyclomatic`, `maintainability_index`, `halstead_volume`, `halstead_difficulty`, `halstead_effort`, `halstead_bugs`).
- `lizard` — Lizard code metrics (metrics: `loc`, `params`, `length`).

Exporters:

- `csv` — Writes the merged matrix to `matrix.csv`.
- `json` — Writes the merged matrix to `matrix.json`.

Notes:

- Some configurations or external plugins may provide additional exporters (for example, a `kill_summary` exporter). If an exporter name is not available, the CLI will print a warning and skip it.
- You can discover what’s available in your environment at runtime:

```bash
suspect run --list-adapters
suspect run --list-exporters
```

---

## 📘 Examples

### Export metrics to a custom path

```bash
suspect run --enable sbfl mbfl --project src --tests "pytest tests -q" \
  --output-csv reports/suspect_matrix.csv \
  --output-json reports/suspect_matrix.json \
  --exporters csv json
```

### Narrow MBFL to a module

```bash
suspect run --enable mbfl --project . --tests "pytest -q" \
  --mbfl-include "service/**/*.py" --mbfl-sample 0.25 --print-top 15
```

### Quiet test runs + method-only view

```bash
suspect run --enable sbfl --project . --tests "pytest -q" \
  --quiet-tests --method-name-only --print-top 12
```

### Show all methods (no truncation)

```bash
suspect run --enable sbfl complexity --project . --tests "pytest -q" \
  --metric ochiai --print-top all
```

---

## 🧪 Developer Workflow

Run the full test suite (includes integration MBFL scenarios):

```bash
pytest -q
```

Target individual areas:

```bash
pytest suspect/tests/test_cli_top_mutation_columns.py
pytest tests/test_mbfl_integration_midscore.py
```

Format & lint (project uses `ruff` and `mypy` optionally—install extras if needed):

```bash
ruff check suspect tests
mypy suspect
```

---

## 🧹 Cleaning Artifacts

Quickly purge coverage caches, `.suspect.*` payloads, and exporter outputs:

Use the provided Python helper script (safe and non-destructive by default; supports dry-run):

```bash
python scripts/clean_suspect_artifacts.py --project . --yes
```

Flags you may find useful:

- `--dry-run` to list what would be removed
- `--with-venv` to also remove helper virtualenvs (.mutatest-venv, .venv, etc.)
- `--keep-outputs` to preserve `matrix.csv`, `matrix.json`, and `kill_summary.json`

Prefer Make? The target below still wraps the same helper:

```bash
make mbfl-clean
```

Tip: run analyses with `suspect run ... --auto-clean` to automatically remove intermediate `.suspect.*` files once results are exported (your matrices stay put).

---

## ❓ Troubleshooting

| Symptom | Likely cause | Suggested fix |
| --- | --- | --- |
| `baseline_failed` warning | Baseline pytest run failed | Re-run with `--mbfl-allow-failing` or fix the failing tests first |
| `mbfl_sbi` stays 0 | Only pass-only kills detected | Increase fail coverage, enable `--mbfl-kf-detection auto`, or craft focused failing tests |
| Runs take too long | Too many targets or high budgets | Use include/exclude globs, lower budgets, or set `--mbfl-sample <rate>` |
| `.suspect.mutatest.json` huge | PTA capturing lots of data | Set `SUSPECT_DIAGNOSTICS_LEVEL=min` or `SUSPECT_MBFL_SAFE_MODE=1` |

---

## 🤝 Contributing

1. Fork & clone the repo.
2. Create a feature branch.
3. Run tests / lint.
4. Submit a PR with context, sample output, and any new fixtures.

See `docs/mbfl_explained.md` for an in-depth conceptual guide to MBFL and adapter internals.
Heuristics:
- Combine with SBFL suspiciousness: high suspiciousness + low mutation score = prime candidate for deeper testing.
- A big gap between `mkf` and `mkp` can indicate failing tests concentrate on one aspect; survivors may sit in passing-only paths.
- If nearly every method is 1.0 yet diagnostics show survivors aggregate > 0, your mutatest version may not emit per-line survivor lines; survivors then can’t be mapped and per-method scores inflate.
- Outlier high `mutants_survived` counts highlight code with unasserted side-effects or silent failure modes.

Limitations:
- Equivalent (functionally neutral) mutants remain unfiltered and depress scores unfairly.
- Survivor attribution depends on mutatest output format; absence of per-line survivor lines yields zero `mutants_survived` per method.

## How SBFL is computed (current)

1) Runs coverage with `dynamic_context = test_function` to capture per-test contexts.
2) Exports coverage JSON with `--show-contexts` so each file includes `{context: [lines]}` per test.
3) Runs pytest with `--junitxml` to capture pass/fail outcomes.
4) Maps executed lines to methods via an AST-based index; for each method we count:
  - ef: distinct failing test contexts that executed the method
  - ep: distinct passing test contexts that executed the method
5) Computes Ochiai, Tarantula, Jaccard, and SBI from ef/ep and totals Nf/Np.

### Parametrized tests

Each parametrized test case is treated as a distinct test instance and counts separately toward ef/ep. When coverage is run with per-test contexts (for example `dynamic_context = test_function`) the coverage JSON records which lines each test execution touched. Pytest produces unique nodeids for parameterized instances (for example `test_module.py::test_func[param]`). The adapter joins those two sources: it maps a coverage context -> executed lines -> method keys (via the `MethodIndex` AST index) and uses the junit XML produced by pytest to determine whether that specific instance passed or failed.

That means a failing parameter combination that touches method `A` contributes +1 to `A.ef`, while a passing parameter combination that also touches `A` contributes +1 to `A.ep`. This granularity improves the precision of SBFL rankings because each parametrized input is an independent observation.

Operational notes:
- Normalization: coverage context ids and junit testcase names may differ in format; the adapter normalizes both to pytest-style nodeids where possible (module::function[param]) before joining.
- Retries/flaky runs: decide a policy (common choices are "last outcome wins" or "fail-overrides") and apply it consistently when multiple outcomes exist for the same nodeid; document the chosen policy in your workflow.
- Performance: parametrized suites can create many contexts; cache `MethodIndex` results per file and map line ranges in bulk to keep memory and CPU use reasonable.
- Exclusion: test files are filtered out of the final Top table (via `--exclude-glob` or `--include-tests`) so parameterized test functions themselves are not reported as suspicious production code.

Fallbacks when contexts aren’t available:
- coverage API `contexts_by_lineno` if JSON lacks contexts
- JSON `executed_lines` as last resort (attributes all executed lines to all tests)
- Plain executed lines via coverage DB treated as passing-only

## Sample project

Use the richer sample in `rich_sample_project/`:

```bash
suspect run --enable sbfl --project rich_sample_project --tests "pytest -q" \
  --metric ochiai --print-top 10
```

The sample includes:
- algos.py (fib, is_prime)
- bank.py (BankAccount)
- strings.py (reverse, is_palindrome, word_count)
- math_extra.py (gcd, lcm, mean)
- shopping.py (Item, Cart)

### Simulate failing tests (sequential guide)

To see non-zero SBFL scores, toggle intentional failures in the sample:

1) Check current status

```bash
rich_sample_project/toggle_failures.py status
```

2) Enable failing tests

```bash
rich_sample_project/toggle_failures.py on
pytest -q
```

3) Run SUSPECT and inspect ranked methods

```bash
suspect run --enable sbfl --project rich_sample_project --tests "pytest -q" \
  --metric ochiai --print-top 10
```

4) Disable failing tests (return to green)

```bash
rich_sample_project/toggle_failures.py off
pytest -q
```

## Additional notes

- Coverage contexts require coverage.py >= 7.0 and may vary by environment. The SBFL adapter prefers JSON contexts produced by `coverage json --show-contexts`.
- Method mapping is AST-based and may conservatively attribute lines to enclosing methods/classes, especially for nested functions or complex comprehensions.
- Console output shortens paths and excludes test functions by default; use `--include-tests` if you want them.
- Cyclomatic complexity depends on `radon`; install it in the same environment (already declared in `pyproject.toml`) to avoid runtime errors.
