# MBFL Explained

Understand what Mutation-Based Fault Localization (MBFL) does in SUSPECT, how to run it, and how to interpret every number the CLI prints. This single guide replaces the old “plain-English explainer” and “technical notes” documents.

## TL;DR — What MBFL Tells You

- We make tiny, reversible edits (mutants) to your code and re-run the tests.
- If a mutant makes a failing test behave differently, that line is strongly related to the bug you are chasing.
- SUSPECT aggregates those signals per method/function and ranks them so you know where to look first.

> **Stakeholder-ready summary:** “We virtually poke small parts of the code and watch which edits upset the tests the most. The spots that react get ranked highest, so developers can investigate them first.”

## Key Concepts (Plain Language)

| Term | Meaning | Why it matters |
| --- | --- | --- |
| Mutant | Tiny edit, like flipping `==` to `!=` | Simulates a potential bug nearby |
| Killed | Tests fail after the edit | Tests detected the change; good signal |
| Survived | Tests still pass | Possible blind spot in test suite |
| `kf` | Kills linked to failing tests | “Bug aligned” evidence |
| `kp` | Kills linked to passing-only tests | Broader coverage, sometimes noise |

When every test currently passes, `kf = 0`. That is expected—there is no failing reference point yet. Focus on mutation counts and survivor ratios until you reproduce a failure.

## What the Tool Records per Method

| Metric | Description |
| --- | --- |
| `mbfl_sbi` | Failing weight: $$\mathrm{mbfl\_sbi} = \frac{k_f}{k_f + k_p}$$ if the denominator is non-zero, otherwise `0.0`. Values near `1.0` mean failing tests dominate. |
| `mkf`, `mkp` | Raw kill counts split into fail-aware vs pass-only buckets. |
| `mutants_detected`, `mutants_survived`, `mutants_total` | Totals across all mutants for the method. |
| `mutation_score` | Classic detected / total ratio. |

All values are written to `matrix.json` / `matrix.csv` and reflected in the console Top table. Columns that would be entirely zeros (for example `mkf` in a green suite) are hidden automatically to keep the table narrow.

## How SUSPECT Runs MBFL

1. **Target discovery** — Walks your project (skips tests, venv, build folders) and honours `--mbfl-include` / `--mbfl-exclude` globs.
2. **Baseline pytest run** — Executes your `--tests` command once to capture failing/passing counts (`Nf`, `Np`) and pytest nodeids.
3. **Mutant generation & execution** — Uses `mutatest` to apply one edit at a time, run pytest, and capture which nodeids failed or repaired.
4. **Attribution** — Maps `(file, line)` back to a method via `MethodIndex` and classifies each kill as fail-aware (`kf`) or pass-only (`kp`).
5. **Optional extras** —
  - **Repair detection** (`--mbfl-kf-detection`): Applies smart flips with failing nodeids only to find fail→pass repairs.
  - **Per-Test Attribution (PTA)** (`--mbfl-per-test-attribution`): Runs budgeted per-nodeid mutants to list “killer” tests.
6. **Reporting** — Writes matrices, updates `.suspect.mutatest.json`, and prints the console table plus any optional summaries.

## Quick Start Commands

### Minimal (green suite)

```bash
suspect run --enable mbfl --project rich_sample_project --tests "pytest -q" --print-top 10
```

### Repair detection pass

```bash
suspect run --enable mbfl --project rich_sample_project --tests "pytest -q" \
  --mbfl-allow-failing \
  --mbfl-kf-detection auto --mbfl-kf-budget 45 --mbfl-kf-max-mutants 20 \
  --print-top 10
```

### Per-Test Attribution sampler

```bash
suspect run --enable mbfl --project rich_sample_project --tests "pytest -q" \
  --mbfl-allow-failing \
  --mbfl-per-test-attribution on --mbfl-pta-budget 20 --mbfl-pta-sample 0.5 \
  --print-top 10
```

Or use the Makefile shortcuts at repo root:

```bash
make mbfl
make mbfl-kf KF_BUDGET=45 KF_MAX_MUTANTS=20
make mbfl-pta PTA_BUDGET=30 PTA_SAMPLE=0.3
```

## Reading the Console Output

1. **Top table** — Sorted by `mbfl_sbi` when MBFL is enabled. Focus on the first few rows.
2. **Mutation columns** — `mkf`, `mkp`, `det`, `surv`, `mut_score` show raw behaviour. A `mut_score` near `1.0` with many survivors indicates strong detection.
3. **Omitted test columns** — When we cap the number of test columns, SUSPECT prints a note listing how many were hidden and a couple of examples.

When `mbfl_sbi` is zero everywhere, you either have a fully passing suite or every kill came from passing-only tests. Use mutation counts to assess test strength and consider enabling `--mbfl-kf-detection auto` if you expect fail→pass repairs.

## Diagnostics & Artifacts

- `matrix.json`, `matrix.csv` — Authoritative per-method metrics for tooling or spreadsheets.
- `.suspect.mutatest.json` — Everything the adapter knows: baseline stats, each mutant run, survivor fallback notes, repair detection, PTA summaries, and a `killers_by_method` map when PTA is active.
- `.suspect.mbfl.baseline.xml`, `.suspect.mbfl.mutant.xml` — JUnit files retained only when you ask for them or pause a run mid-flight.

### Survivor fallback

If mutatest reports aggregate survivors but not per-line details, SUSPECT proportionally redistributes survivors across methods that had kills. Diagnostics indicate whether that fallback ran and how many survivors were reassigned.

### Per-Test Attribution (PTA)

Diagnostics include `kills_by_test` and a short console section such as “`foo.py:Widget.run` killed by [`tests/test_widget.py::test_run_smoke`, …]`”. Use it to cross-reference problematic tests quickly.

## Performance Tips

- Restrict the search space with `--mbfl-include` / `--mbfl-exclude` globs when the project is large.
- Start with a modest repair budget (10–30 seconds) and increase only if you need deeper coverage.
- PTA is powerful but expensive; sample down to 20–50% of nodeids for iterative debugging.
- The adapter caps total mutants to 400 per run by default; adjust via `--mbfl-sample` for lighter or heavier passes.

## Troubleshooting Checklist

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `baseline_failed` message | Baseline pytest failed and allow-failing disabled | Re-run with `--mbfl-allow-failing` or fix tests first |
| `mbfl_sbi` stays 0 even with failures | Only pass-only kills observed | Focus on mutation counts, enable `--mbfl-kf-detection auto`, or craft tests that fail in the target area |
| Mutants never survive | Tight guard tests; good coverage | No action—this is positive |
| Run takes too long | Too many targets or high budgets | Narrow with include/exclude, lower budgets, or sample mutants |

## Behind the Scenes (for Engineers)

- Adapter code lives in `suspect/adapters/mbfl_mutatest.py`; formulas come from `suspect/formulas/mbfl.py`.
- Method lookup is resilient: we map by line number and walk upward to find the nearest method definition.
- Mutant generation covers comparison flips, boolean operator swaps, and boolean literal toggles. Repair detection reuses those transformations but confines execution to failing nodeids and respects your time budget.
- PTA builds a `kills_by_test` dictionary which the CLI can surface and exporters can consume.

Armed with this guide, you should be able to run MBFL, understand its scores, and tune it for your project without bouncing across multiple documents.
