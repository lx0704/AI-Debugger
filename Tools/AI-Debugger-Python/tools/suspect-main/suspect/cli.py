# CLI entry point
import argparse
import signal
import time
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import shlex
from dataclasses import dataclass
from pathlib import Path
from .orchestrator import Orchestrator
from .mapping import MethodIndex
from .cleanup import collect_artifacts, cleanup as cleanup_project
from .formulas.mbfl import mbfl_sbi


def register_builtin_adapters():
    from .plugins import register_builtin_adapters as _register_builtin_adapters

    return _register_builtin_adapters()


def get_adapter(name):
    from .plugins import get_adapter as _get_adapter

    return _get_adapter(name)


def list_adapters():
    from .plugins import list_adapters as _list_adapters

    return _list_adapters()


def register_builtin_exporters():
    from .exporters.plugins import register_builtin_exporters as _register_builtin_exporters

    return _register_builtin_exporters()


def get_exporter(name):
    from .exporters.plugins import get_exporter as _get_exporter

    return _get_exporter(name)


def list_exporters():
    from .exporters.plugins import list_exporters as _list_exporters

    return _list_exporters()

def _parse_print_top(value: str) -> int:
    """Parse the --print-top value allowing the special keyword 'all'.

    Returns:
        -1 to indicate show all rows.
        0 to disable output (as before).
        positive int for top N.
    """
    if isinstance(value, str) and value.lower() == "all":
        return -1
    iv = int(value)
    return iv


def main():
    p = argparse.ArgumentParser("suspect", description="SUSPECT CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run selected analyses and export results")
    run.add_argument("--project", default=".", help="Path to project under analysis")
    run.add_argument("--tests", default="pytest -q", help="Command to run tests")
    run.add_argument("--enable", nargs="+", choices=["sbfl", "mbfl", "complexity", "lizard", "similarity"], default=["sbfl"])
    run.add_argument("--output-csv", default="matrix.csv")
    run.add_argument("--output-json", default="matrix.json")
    run.add_argument("--output-kill-summary", default="kill_summary.json",
                     help="Path for the kill-summary exporter output (if enabled)")
    # Observability & caching flags
    run.add_argument("--log-file", default=os.environ.get("SUSPECT_LOG_FILE"), help="Path to JSONL observer log file.")
    run.add_argument("--log-console", action="store_true", help="Echo observer events to console.")
    run.add_argument("--log-console-verbose", action="store_true", help="Verbose console observer (full payload).")
    run.add_argument("--cache-adapters", action="store_true", help="Enable disk caching of adapter outputs (.suspect_cache).")
    run.add_argument("--no-cache", action="store_true", help="Disable caching even if environment enables it.")
    run.add_argument("--artifact-repo-dir", default=None, help="Directory for artifact repository manifest (defaults to consolidated out dir if set).")
    # Centralized output directory controls
    run.add_argument(
        "--out-dir",
        default=os.environ.get("SUSPECT_OUT_DIR"),
        help=(
            "Directory to place all outputs (matrix + diagnostics). "
            "If relative, resolved against the CLI working directory. "
            "If not provided, use --consolidate-output to auto-create a short per-project folder."
        ),
    )
    run.add_argument(
        "--consolidate-output",
        action="store_true",
        help=(
            "Create a single folder at the CLI root named 'sus-<short_project>' and write/copy all outputs there."
        ),
    )
    run.add_argument("--metric", choices=["sbfl_ochiai", "sbfl_tarantula", "sbfl_jaccard", "sbfl_sbi", "mbfl_sbi", "cyclomatic"], default="sbfl_ochiai",
                     help="Metric to rank methods by in console output")
    run.add_argument("--print-top", type=_parse_print_top, default=10,
                     help="Print top N suspicious methods to console (0 to disable, 'all' for every method)")
    run.add_argument("--include-tests", action="store_true",
                     help="Include test functions in console ranking")
    run.add_argument("--method-name-only", action="store_true",
                     help="In Top table, show only the method's qualified name (no file path)")
    run.add_argument("--show-killers", action="store_true",
                     help="Show killer tests (from MBFL per-test attribution) inline in the Top table when available")
    run.add_argument("--fail-on-tool-error", action="store_true",
                     help="Exit with non-zero status if any adapter raises an error.")
    run.add_argument("--print-coverage", action="store_true",
                     help="Print per-file coverage summary to console")
    run.add_argument("--coverage-top", type=int, default=10,
                     help="Show top N lowest-covered files (0 for all) when printing coverage")
    run.add_argument("--quiet-tests", action="store_true",
                     help="Silence test-run stdout/stderr (appends redirection to --tests)")
    run.add_argument("--exclude-glob", action="append", default=[],
                     help="Glob(s) to exclude files from console reports (can be repeated). Matches basename or relative path.")
    run.add_argument("--list-adapters", action="store_true",
                     help="List available adapters and exit")
    run.add_argument("--list-exporters", action="store_true",
                     help="List available exporters and exit")
    run.add_argument("--exporters", nargs="+", default=["csv", "json", "kill_summary"],
                     help="Which exporters to run (names listed by --list-exporters). Default: csv json kill_summary")
    run.add_argument("--auto-clean", action="store_true",
                     help="After run completion, clean up mutation artifacts (keeps recent run outputs).")
    run.add_argument("--show-kill-matrix", action="store_true",
                     help="After normal output, print a test vs element kill matrix (X=killed, ✓=survived) using killers_by_method.")
    run.add_argument("--kill-matrix-top-methods", type=int, default=10,
                     help="Number of methods (ranked by mbfl_sbi) to include in kill matrix (default 10; 0=auto-all with cap).")
    run.add_argument("--kill-matrix-top-tests", type=int, default=5,
                     help="Number of tests (by total kill count) to include as columns in kill matrix (default 5).")
    run.add_argument("--kill-matrix-element-max-len", type=int, default=0,
                     help="If >0, truncate Element labels in the kill matrix to this many characters (with ellipsis). 0=auto full.")
    run.add_argument("--show-mutant-matrix", action="store_true",
                     help="Print a per-mutant matrix (each row = mutant id:file:line:kind) vs tests (X=killed by test, ✓=no kill).")
    run.add_argument("--mutant-matrix-top-mutants", type=int, default=25,
                     help="Max mutants to display in the per-mutant matrix (default 25; -1 for all).")
    run.add_argument("--mutant-matrix-all-tests", action="store_true",
                     help="In per-mutant matrix, include all killer tests across ALL mutants plus baseline failing tests.")
    run.add_argument("--show-element-mutant-matrix", action="store_true",
                     help="Print a grouped Element/Mutant matrix: methods grouped, each mutant row shows test kills (X/✓) and per-mutant Susp score.")
    run.add_argument("--show-mutant-details", action="store_true",
                     help="Print a per-mutant narrative summary (requires MBFL mutatest diagnostics).")
    run.add_argument("--mutant-details-table", action="store_true",
                     help="When showing mutant details, prepend a compact text table before the narrative.")
    run.add_argument("--show-mbfl-table", action="store_true",
                     help="Print an MBFL Element/Mutant vs Test table with per-element suspicious values.")
    run.add_argument("--mbfl-table-top-methods", type=int, default=10,
                     help="Number of methods to include in the MBFL table (default 10; -1 for all).")
    run.add_argument("--mbfl-table-top-tests", type=int, default=5,
                     help="Number of tests to include as columns in the MBFL table (default 5; -1 for all).")
    run.add_argument("--mbfl-include", action="append", default=[], help="Glob(s) of files/dirs to mutate (can repeat).")
    run.add_argument("--mbfl-exclude", action="append", default=[], help="Glob(s) to exclude from mutation (can repeat).")
    run.add_argument("--mbfl-timeout", type=int, default=0,
                     help="Per-test run timeout in seconds for mutation engine (0 = engine default).")
    run.add_argument("--mbfl-sample", type=float, default=0.0,
                     help="Sampling rate 0.0-1.0 to randomly select mutants (engine-dependent).")
    run.add_argument("--mbfl-allow-failing", action="store_true",
                     help="Allow MBFL to run even if the baseline pytest run fails (skips baseline guard).")
    run.add_argument("--mbfl-kf-detection", nargs="?", const="on", choices=["on", "auto"], default=None,
                     help="Experimental: detect fail→pass flips (kf) by rerunning failing tests per mutant.")
    run.add_argument("--mbfl-kf-budget", type=int, default=60,
                     help="Time budget in seconds for kf detection (default: 60).")
    run.add_argument("--mbfl-kf-max-mutants", type=int, default=10,
                     help="Max mutants per file for kf detection (default: 10).")
    run.add_argument("--mbfl-per-test-attribution", nargs="?", const="on", choices=["on", "auto"], default=None,
                     help="Experimental: attribute kills to specific pytest nodeids (adaptive by default).")
    run.add_argument("--mbfl-pta-budget", type=int, default=0, help=argparse.SUPPRESS)
    run.add_argument("--mbfl-pta-sample", type=float, default=0.0, help=argparse.SUPPRESS)
    run.add_argument("--mbfl-process-cleanup", choices=["on", "off"], default="on",
                     help="After MBFL, attempt to terminate stray pytest processes (default on).")
    run.add_argument("--mbfl-survivor-fallback", choices=["on", "off"], default="on",
                     help="Fallback to survivor heuristics when killer data is unavailable (default on).")
    run.add_argument("--complexity-include", action="append", default=[],
                     help="Glob(s) of files/dirs to include for complexity analysis (can repeat).")
    run.add_argument("--complexity-exclude", action="append", default=[],
                     help="Glob(s) to exclude from complexity analysis (can repeat).")
    run.add_argument("--sample-project-only", action="store_true",
                     help="When complexity is enabled, limit analysis (and tests) to rich_sample_project.")

    args = p.parse_args()
    if args.cmd == "run":
        try:
            if any(a.startswith("--mbfl-pta-budget") for a in sys.argv) or any(a.startswith("--mbfl-pta-sample") for a in sys.argv):
                print("[INFO] PTA tuning flags are deprecated; adaptive defaults are used when omitted. "
                      "You can still override via SUSPECT_MBFL_PTA_BUDGET / SUSPECT_MBFL_PTA_SAMPLE.", file=sys.stderr)
        except Exception:
            pass

        enabled_set = set(args.enable)
        if args.metric == "sbfl_ochiai" and enabled_set == {"complexity"}:
            args.metric = "cyclomatic"
        sample_only = bool(getattr(args, "sample_project_only", False))
        if sample_only and "complexity" in enabled_set and args.tests.strip() == "pytest -q":
            args.tests = "pytest -q rich_sample_project"

        proj_in = args.project
        proj_abs = os.path.abspath(proj_in)
        if not os.path.isdir(proj_abs):
            proj_abs = os.getcwd()
        proj_path = Path(proj_abs)

        register_builtin_adapters()
        if args.list_adapters:
            print("Available adapters:")
            for name in list_adapters():
                print(" -", name)
            return

        adapters = []
        for name in args.enable:
            cls = get_adapter(name)
            if cls:
                try:
                    adapters.append(cls())
                    continue
                except Exception:
                    pass
            print(f"[WARN] adapter '{name}' not found in registry; skipping")

        if getattr(args, "quiet_tests", False):
            if ">" not in args.tests and "2>" not in args.tests:
                args.tests = args.tests + " > /dev/null 2>&1"

        # Determine central output directory (optional)
        def _abbr_name(name: str) -> str:
            # Build a short token like 'rsp' for 'rich_sample_project'
            import re
            tokens = [t for t in re.split(r"[^A-Za-z0-9]+", name) if t]
            if len(tokens) >= 2:
                return "".join(t[0].lower() for t in tokens if t)
            base = tokens[0].lower() if tokens else name.lower()
            return base[:8]

        out_dir_path = None
        try:
            if args.out_dir:
                base = Path(os.getcwd())
                out_dir_path = Path(args.out_dir)
                if not out_dir_path.is_absolute():
                    out_dir_path = base / out_dir_path
                out_dir_path.mkdir(parents=True, exist_ok=True)
            elif args.consolidate_output:
                short = _abbr_name(proj_path.name)
                out_dir_path = Path(os.getcwd()) / f"sus-{short}"
                out_dir_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            out_dir_path = None

        extra_ctx = {
            "mbfl_include": args.mbfl_include,
            "mbfl_exclude": args.mbfl_exclude,
            "mbfl_timeout": args.mbfl_timeout,
            "mbfl_sample": args.mbfl_sample,
            "mbfl_allow_failing": bool(args.mbfl_allow_failing or os.environ.get("SUSPECT_MBFL_ALLOW_FAILING")),
            "mbfl_kf_detection": args.mbfl_kf_detection or os.environ.get("SUSPECT_MBFL_KF_DETECTION"),
            "mbfl_kf_budget": int(os.environ.get("SUSPECT_MBFL_KF_BUDGET", args.mbfl_kf_budget)),
            "mbfl_kf_max_mutants": int(os.environ.get("SUSPECT_MBFL_KF_MAX_MUTANTS", args.mbfl_kf_max_mutants)),
            "mbfl_per_test_attribution": args.mbfl_per_test_attribution or os.environ.get("SUSPECT_MBFL_PTA"),
            "mbfl_pta_budget": int(os.environ.get("SUSPECT_MBFL_PTA_BUDGET", args.mbfl_pta_budget)),
            "mbfl_pta_sample": float(os.environ.get("SUSPECT_MBFL_PTA_SAMPLE", args.mbfl_pta_sample)),
            "mbfl_survivor_fallback": (os.environ.get("SUSPECT_MBFL_SURVIVOR_FALLBACK", args.mbfl_survivor_fallback) or "on"),
            "complexity_include": args.complexity_include,
            "complexity_exclude": args.complexity_exclude,
            "sample_project_only": sample_only,
        }
        # Build observers
        from .observability import build_default_observers
        observers = build_default_observers(
            log_file=args.log_file,
            enable_console=args.log_console,
            verbose_console=args.log_console_verbose,
        )
        # Cache manager optional
        cache_mgr = None
        if args.cache_adapters and not args.no_cache:
            try:
                from .cache import CacheManager
                cache_mgr = CacheManager(project_root=proj_abs)
            except Exception:
                cache_mgr = None
        extra_ctx["observers"] = observers
        extra_ctx["cache_manager"] = cache_mgr
        orch = Orchestrator(project_root=proj_abs, test_cmd=args.tests,
                            fail_on_tool_error=args.fail_on_tool_error, extra_ctx=extra_ctx)
        matrix = orch.run(adapters)

        register_builtin_exporters()
        if args.list_exporters:
            print("Available exporters:")
            for name in list_exporters():
                print(" -", name)
            return

        exporters_to_run = []
        for en in args.exporters:
            cls = get_exporter(en)
            if cls:
                try:
                    exporters_to_run.append(cls())
                    continue
                except Exception:
                    pass
            if en == "csv":
                try:
                    from .exporters.csv_exporter import CSVExporter

                    exporters_to_run.append(CSVExporter())
                    continue
                except Exception:
                    pass
            elif en == "json":
                try:
                    from .exporters.json_exporter import JSONExporter

                    exporters_to_run.append(JSONExporter())
                    continue
                except Exception:
                    pass
            print(f"[WARN] unknown exporter '{en}' - skipping")

        written_paths: list[Path] = []
        for ex in exporters_to_run:
            try:
                name = getattr(ex, "name", None)
                if name == "csv":
                    out = args.output_csv
                elif name == "json":
                    out = args.output_json
                elif name == "kill_summary":
                    out = args.output_kill_summary
                else:
                    out = args.output_json
                out_path = Path(out)
                # If a central output folder is configured, write relative outputs into that folder.
                if out_dir_path is not None and not out_path.is_absolute():
                    out_path = out_dir_path / out_path.name
                elif not out_path.is_absolute():
                    out_path = proj_path / out_path
                matrix.enrich_line_numbers(proj_abs)     
                diff_set = parse_diff(project_root=proj_abs)
                matrix.add_diff_labels(diff_set)
                ex.write(matrix, str(out_path), project_root=proj_abs)
                written_paths.append(out_path)
            except Exception:
                print(f"[WARN] exporter {getattr(ex, 'name', str(ex))} failed")
        if written_paths:
            rel_list: list[str] = []
            for path_obj in written_paths:
                try:
                    if out_dir_path and path_obj.is_relative_to(out_dir_path):  # type: ignore[attr-defined]
                        rel_list.append(str(path_obj.relative_to(out_dir_path)))
                    else:
                        rel_list.append(str(path_obj.relative_to(proj_path)))
                except ValueError:
                    rel_list.append(str(path_obj))
            dest_note = f" in {out_dir_path}" if out_dir_path else ""
            print(f"✅ Wrote {', '.join(rel_list)}{dest_note}")

        # Optionally copy standard artifacts into the central output folder (keep originals in project root)
        # Artifact repository registration
        artifact_repo_dir = args.artifact_repo_dir or (out_dir_path if out_dir_path else None)
        artifact_repo = None
        if artifact_repo_dir:
            try:
                from .artifacts import ArtifactRepository
                artifact_repo = ArtifactRepository(str(artifact_repo_dir))
            except Exception:
                artifact_repo = None

        if out_dir_path is not None:
            try:
                from .cleanup import collect_artifacts, OUTPUT_FILE_PATTERNS, DEFAULT_FILE_PATTERNS
                plan = collect_artifacts(proj_path, include_outputs=True, include_venv=False)
                to_copy = list(plan.files)
                # Also include common top-level outputs if they were written outside out_dir_path
                extra_candidates = [
                    proj_path / (args.output_csv or "matrix.csv"),
                    proj_path / (args.output_json or "matrix.json"),
                    proj_path / (args.output_kill_summary or "kill_summary.json"),
                ]
                for c in extra_candidates:
                    try:
                        if c.is_file() and c not in to_copy:
                            to_copy.append(c)
                    except Exception:
                        pass
                copied = 0
                for src in to_copy:
                    try:
                        dest = out_dir_path / src.name
                        if dest.resolve() == src.resolve():
                            continue
                        # Prefer overwrite with latest
                        shutil.copy2(src, dest)
                        copied += 1
                    except Exception:
                        continue
                if copied:
                    print(f"📦 Consolidated {copied} artifact(s) into {out_dir_path}")
                # Register artifacts with repository manifest
                if artifact_repo:
                    try:
                        for src in to_copy:
                            artifact_repo.register_file(str(out_dir_path / src.name if (out_dir_path / src.name).exists() else src), kind="suspect")
                    except Exception:
                        pass
            except Exception as exc:
                print(f"[WARN] Could not consolidate outputs: {exc}")

        if "mbfl" in args.enable and args.mbfl_process_cleanup == "on":
            try:
                _cleanup_pytest_processes(proj_abs, phase="post")
            except Exception:
                print("[WARN] MBFL process cleanup encountered an error.")

        mbfl_only = enabled_set == {"mbfl"}
        if mbfl_only:
            _print_mbfl_report(proj_abs, args)
        else:
            if args.print_coverage:
                _print_coverage(proj_abs, args.coverage_top, exclude_globs=args.exclude_glob, tests_cmd=args.tests)
            if args.print_top != 0:
                _print_top(matrix, args.metric, args.print_top, include_tests=args.include_tests,
                           project_root=proj_abs, exclude_globs=args.exclude_glob,
                           method_name_only=args.method_name_only, show_killers=args.show_killers)

        if args.show_kill_matrix and "mbfl" in args.enable:
            try:
                _print_kill_matrix(proj_abs, args.kill_matrix_top_methods, args.kill_matrix_top_tests, args.kill_matrix_element_max_len)
            except Exception as exc:
                print(f"[WARN] could not render kill matrix: {exc}")
        if getattr(args, "show_mutant_matrix", False) and "mbfl" in args.enable:
            try:
                _print_mutant_matrix(proj_abs, args.mutant_matrix_top_mutants, args.kill_matrix_top_tests, getattr(args, "mutant_matrix_all_tests", False))
            except Exception as exc:
                print(f"[WARN] could not render mutant matrix: {exc}")
        if getattr(args, "show_mutant_details", False) and "mbfl" in args.enable:
            try:
                _print_mutant_details(proj_abs, getattr(args, "mutant_details_table", False))
            except Exception as exc:
                print(f"[WARN] could not render mutant details: {exc}")
        if getattr(args, "show_mbfl_table", False) and "mbfl" in args.enable:
            try:
                _print_mbfl_table(proj_abs, args.mbfl_table_top_methods, args.mbfl_table_top_tests)
            except Exception as exc:
                print(f"[WARN] could not render MBFL table: {exc}")
        if getattr(args, "show_element_mutant_matrix", False) and "mbfl" in args.enable:
            try:
                _print_element_mutant_matrix(proj_abs, args.kill_matrix_top_methods, args.kill_matrix_top_tests, getattr(args, "mutant_matrix_all_tests", False))
            except Exception as exc:
                print(f"[WARN] could not render element-mutant matrix: {exc}")

        if getattr(args, "auto_clean", False):
            outputs_to_keep: list[Path] = []
            for candidate in (args.output_csv, args.output_json, args.output_kill_summary):
                if not candidate:
                    continue
                out_path = Path(candidate)
                if not out_path.is_absolute():
                    out_path = Path(proj_abs) / out_path
                outputs_to_keep.append(out_path.resolve())
            try:
                clean_res = cleanup_project(
                    Path(proj_abs),
                    include_outputs=False,
                    include_venv=False,
                    dry_run=False,
                    exclude=outputs_to_keep,
                )
                if clean_res.total_removed:
                    print(f"🧹 Auto-clean removed {clean_res.total_removed} artifact(s).")
                else:
                    print("🧹 Auto-clean found no artifacts to remove.")
            except Exception as exc:
                print(f"[WARN] auto-clean encountered an error: {exc}")
    else:
        p.error(f"Unsupported command '{args.cmd}'")


from typing import Optional


def _print_top(matrix, metric: str, top: int, include_tests: bool, project_root: Optional[str] = None,
               exclude_globs: Optional[list[str]] = None, method_name_only: bool = False,
               show_killers: bool = False):
    # Build list of (line_no, pretty_method, rank_score, ef, ep, metrics_dict)
    # Dynamically decide which metric columns to display. We keep a preferred ordering
    # (the classic SBFL metrics + sbfl sbi + mbfl_sbi) for readability.
    preferred_order = ["sbfl_ochiai", "sbfl_tarantula", "sbfl_jaccard", "sbfl_sbi", "mbfl_sbi", "mbfl_tarantula", "mbfl_ochiai","mbfl_jaccard","similarity_tfidf"]
    # Ensure the ranking metric is displayed even if not part of the preferred list (for backward compat).
    if metric not in preferred_order:
        preferred_order.append(metric)
    # Detect presence
    metric_cols = [name for name in preferred_order if any(name in m for _meth, m in matrix.rows.items())]
    # Bring newer complexity metrics into view automatically
    additional_metrics = [
        "maintainability_index",
        "halstead_volume",
        "halstead_difficulty",
        "halstead_effort",
        "halstead_bugs",
        # Lizard metrics (auto-show if present)
        "loc",
        "params",
        "length",
        "diff_label",
    ]
    for extra in additional_metrics:
        if any(extra in m for _meth, m in matrix.rows.items()):
            metric_cols.append(extra)
    # Detect presence of mutation count metrics for auto display
    include_mut_counts = any(
        any(k in m for k in ("mutants_detected", "mutants_survived", "mutation_score"))
        for _meth, m in matrix.rows.items()
    )
    rows = []
    for method, m in matrix.rows.items():
        rank_score = m.get(metric)
        if rank_score is None:
            continue
        if not include_tests and _looks_like_test_method(method):
            if not method.startswith("rich_sample_project/"):
                continue
        # optional exclude patterns
        try:
            path = method.split(":", 1)[0]
            if _is_excluded(path, exclude_globs):
                continue
        except Exception:
            pass
        ef = m.get("ef", "")
        ep = m.get("ep", "")
        line_no = _method_start_line(method, project_root)
        
        pretty = _method_display(method, project_root, method_name_only)
        rows.append((line_no, pretty, float(rank_score), ef, ep, m))

    rows.sort(key=lambda x: x[2], reverse=True)
    if not rows:
        print("No methods with metric values to display.")
        return

    if top >= 0:
        rows = rows[:top]
    show_ef = any(isinstance(r[3], (int, float)) for r in rows)
    show_ep = any(isinstance(r[4], (int, float)) for r in rows)
    term_w = _term_width(default=120)

    include_mk = False
    try:
        for _ln, _pretty, _score, _ef, _ep, m in rows:
            if ("mkf" in m and isinstance(m.get("mkf"), (int, float))) or ("mkp" in m and isinstance(m.get("mkp"), (int, float))):
                include_mk = True
                break
    except Exception:
        include_mk = False

    killers_by_method: dict[str, list[tuple[str, int]]] = {}
    if show_killers and project_root:
        try:
            diag_path = os.path.join(project_root, ".suspect.mutatest.json")
            with open(diag_path, "r", encoding="utf-8") as f:
                diag_all = json.load(f)
            mbfl_diag = (diag_all or {}).get("mutatest", {}).get("mbfl", {}) or {}
            kb = mbfl_diag.get("killers_by_method") or {}
            if isinstance(kb, dict) and kb:
                for mkey, tests in kb.items():
                    if isinstance(tests, dict):
                        items = list(tests.items())
                    elif isinstance(tests, list):
                        items = list(tests)
                    else:
                        items = []
                    killers_by_method[mkey] = sorted(((str(t), int(c)) for t, c in items), key=lambda x: x[1], reverse=True)
            if not killers_by_method:
                pta = mbfl_diag.get("per_test_attribution") or {}
                kills_by_test = pta.get("kills_by_test") or {}
                files = set()
                for _tid, mapping in (kills_by_test or {}).items():
                    for fl in (mapping or {}).keys():
                        try:
                            fpart = str(fl).rsplit(":", 1)[0]
                            files.add(fpart)
                        except Exception:
                            continue
                idx = MethodIndex()
                for fp in files:
                    abs_fp = os.path.join(project_root, fp)
                    try:
                        src = open(abs_fp, "r", encoding="utf-8").read()
                    except Exception:
                        continue
                    key = fp.replace("\\", "/")
                    try:
                        idx.add_file(key, src)
                    except Exception:
                        continue
                per_method_tests: dict[str, dict[str, int]] = {}
                for testid, mapping in (kills_by_test or {}).items():
                    for fl, cnt in (mapping or {}).items():
                        try:
                            fpart, lpart = str(fl).rsplit(":", 1)
                            ln = int(lpart)
                        except Exception:
                            continue
                        fkey = fpart.replace("\\", "/")
                        mkey = None
                        for b in range(ln, 0, -1):
                            mk = idx.index.get((fkey, b))
                            if mk:
                                mkey = mk
                                break
                        if not mkey:
                            continue
                        d = per_method_tests.setdefault(mkey, {})
                        d[testid] = d.get(testid, 0) + int(cnt)
                for mkey, tests in per_method_tests.items():
                    ordered = sorted(tests.items(), key=lambda x: x[1], reverse=True)
                    killers_by_method[mkey] = ordered
        except Exception:
            killers_by_method = {}
    show_killers_col = bool(show_killers and killers_by_method)

    metric_key_set = set(metric_cols)
    table_rows: list[dict[str, str]] = []

    for idx, (line_no, pretty, _score, ef, ep, m) in enumerate(rows, start=1):
        row_map: dict[str, str] = {}
        row_map["rank"] = str(idx)
        row_map["ln"] = str(int(line_no)) if isinstance(line_no, int) else ""
        row_map["method"] = pretty
        if show_ef:
            row_map["ef"] = str(int(ef)) if isinstance(ef, (int, float)) else ""
        if show_ep:
            row_map["ep"] = str(int(ep)) if isinstance(ep, (int, float)) else ""
        for name in metric_cols:
            v = m.get(name)
            if isinstance(v, (int, float)):
                precision = 2 if name == "cyclomatic" else 4
                row_map[name] = f"{float(v):.{precision}f}"
            else:
                row_map[name] = ""
        if include_mk:
            mkf = m.get("mkf")
            mkp = m.get("mkp")
            row_map["mkf"] = str(int(mkf)) if isinstance(mkf, (int, float)) else ""
            row_map["mkp"] = str(int(mkp)) if isinstance(mkp, (int, float)) else ""
        if include_mut_counts:
            det = m.get("mutants_detected")
            surv = m.get("mutants_survived")
            msc = m.get("mutation_score")
            row_map["det"] = str(int(det)) if isinstance(det, (int, float)) else ""
            row_map["surv"] = str(int(surv)) if isinstance(surv, (int, float)) else ""
            row_map["mut_sc"] = f"{float(msc):.2f}" if isinstance(msc, (int, float)) else ""
        if show_killers_col:
            killer_str = ""
            try:
                candidate_keys = []
                for mkey, mm in matrix.rows.items():
                    if mm is m:
                        candidate_keys = [mkey]
                        break
                if not candidate_keys:
                    mkf_val = m.get("mkf")
                    mkp_val = m.get("mkp")
                    mbfl_val = m.get("mbfl_sbi")
                    for mkey, mm in matrix.rows.items():
                        if mm.get("mkf") == mkf_val and mm.get("mkp") == mkp_val and mm.get("mbfl_sbi") == mbfl_val:
                            candidate_keys.append(mkey)
                if candidate_keys:
                    k0 = candidate_keys[0]
                    killers = killers_by_method.get(k0) or []
                    if killers:
                        parts = []
                        for i, (tid, cnt) in enumerate(killers):
                            parts.append(f"{tid} (x{cnt})")
                            if i >= 1:
                                break
                        killer_str = ", ".join(parts)
            except Exception:
                killer_str = ""
            row_map["killers"] = killer_str
        table_rows.append(row_map)

    columns: list[tuple[str, str, str]] = [
        ("rank", "#", "right"),
        ("ln", "ln", "right"),
        ("method", "method", "left"),
    ]
    if show_ef:
        columns.append(("ef", "ef", "right"))
    if show_ep:
        columns.append(("ep", "ep", "right"))
    for name in metric_cols:
        columns.append((name, name, "right"))
    if include_mk:
        columns.extend([("mkf", "mkf", "right"), ("mkp", "mkp", "right")])
    if include_mut_counts:
        columns.extend([("det", "det", "right"), ("surv", "surv", "right"), ("mut_sc", "mut_sc", "right")])
    if show_killers_col:
        columns.append(("killers", "killers", "left"))

    min_widths: dict[str, int] = {
        "rank": max(1, len(str(len(rows)))),
        "ln": 2,
        "method": 16,
        "ef": 3,
        "ep": 3,
        "mkf": 3,
        "mkp": 3,
        "det": 3,
        "surv": 4,
        "mut_sc": 6,
        "killers": 8,
    }

    col_widths: dict[str, int] = {}
    for key, header_label, _align in columns:
        max_len = len(header_label)
        for row_map in table_rows:
            value = row_map.get(key, "")
            max_len = max(max_len, len(value))
        min_width = min_widths.get(key, 8 if key in metric_key_set else 4)
        if key in metric_key_set:
            min_width = max(min_width, 8)
        max_len = max(max_len, min_width)
        if key == "method":
            max_len = min(max_len, 60)
        col_widths[key] = max_len

    columns_count = len(columns)
    frame_extra = 4 + 3 * (columns_count - 1)
    total_width = sum(col_widths[key] for key, _, _ in columns) + frame_extra
    if "method" in col_widths:
        while total_width > term_w and col_widths["method"] > 16:
            col_widths["method"] -= 1
            total_width -= 1
    if "killers" in col_widths:
        while total_width > term_w and col_widths["killers"] > 12:
            col_widths["killers"] -= 1
            total_width -= 1

    def _format_cell(value: str, width: int, align: str, key: str) -> str:
        if key in {"method", "killers"}:
            value = _truncate(value, width)
        elif len(value) > width:
            value = value[:width]
        if align == "right":
            return value.rjust(width)
        return value.ljust(width)

    header_tokens = [label for key, label, _ in columns if key not in {"rank", "ln", "method"}]
    header_metric_list = ", ".join(header_tokens)
    header = f"Top {len(rows)} (ranked by {metric})"
    if header_metric_list:
        header += f" — {header_metric_list}"
    print("\n" + header)
    print("-" * (len(header)))

    separator = "+" + "+".join("-" * (col_widths[key] + 2) for key, _, _ in columns) + "+"
    print(separator)
    header_cells = [
        _format_cell(label, col_widths[key], align, key)
        for key, label, align in columns
    ]
    print("| " + " | ".join(header_cells) + " |")
    print(separator)
    for row_map in table_rows:
        cells = [
            _format_cell(row_map.get(key, ""), col_widths[key], align, key)
            for key, _label, align in columns
        ]
        print("| " + " | ".join(cells) + " |")
    print(separator)
    if show_ef or show_ep or include_mk or ("mbfl_sbi" in metric_cols):
        print("(fail = mutants killed by failing tests, pass = mutants killed by passing tests; mbfl_sbi = fail/(fail+pass))")


def _render_top_to_string(matrix, metric: str, top: int) -> str:
    """Internal helper for tests: render _print_top output (mutation columns detection) to a string.

    Prints nothing to stdout; returns the composed table or empty string.
    Limited to a simplified subset: always include tests, no exclusions, default widths.
    """
    from io import StringIO
    import contextlib
    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        _print_top(matrix, metric, top, include_tests=True, project_root=None, exclude_globs=None, method_name_only=False)
    return buf.getvalue()


def _print_mbfl_report(project_root: str, args) -> None:
    """Print MBFL-only report with mutatest diagnostics and MBFL-focused Top table.

    Reads diagnostics from `.suspect.mutatest.json` if present.
    """
    # Load results
    try:
        from .matrix import Matrix
        from .exporters.json_exporter import JSONExporter
        # Note: we already have a matrix in caller, but we need to render MBFL-only columns,
        # so reuse the same matrix object passed via outer scope if available.
    except Exception:
        pass
    # Optionally show matrix here too for MBFL-only mode
    if getattr(args, 'show_kill_matrix', False):
        try:
            _print_kill_matrix(project_root, getattr(args, 'kill_matrix_top_methods', 10), getattr(args, 'kill_matrix_top_tests', 5))
        except Exception as e:
            print(f"[WARN] could not render kill matrix: {e}")

    diag_path = os.path.join(project_root, ".suspect.mutatest.json")
    diag = None
    try:
        with open(diag_path, "r", encoding="utf-8") as f:
            diag = json.load(f)
    except Exception:
        diag = None

    # Print Mutatest diagnostic summary if available
    if isinstance(diag, dict) and "mutatest" in diag:
        md = diag.get("mutatest", {})
        status = md.get("status", "ok")
        if status == "no_targets":
            print()
            print("Mutatest diagnostic summary")
            print("=" * len("Mutatest diagnostic summary"))
            print(" - No MBFL targets found based on include/exclude filters.")
            print(" - Adjust `--mbfl-include/--mbfl-exclude` and re-run.")
            return
        if status == "baseline_failed":
            print()
            print("Mutatest diagnostic summary")
            print("=" * len("Mutatest diagnostic summary"))
            print(" - Baseline pytest run failed; MBFL skipped.")
            print(" - Fix failing tests or use includes to narrow scope.")
            return
        cfg = md.get("config", {})
        runs = md.get("runs", [])
        ag = md.get("aggregate", {})
        # If exactly one src mutated, show it; else show project
        srcs = [str(r.get("src")) for r in runs if isinstance(r, dict) and r.get("src")]
        src_disp = os.path.join(project_root, srcs[0]) if len(srcs) == 1 else project_root
        print()
        print("Mutatest diagnostic summary")
        print("=" * len("Mutatest diagnostic summary"))
        print(f" - Source location: {src_disp}")
        print(f" - Test commands: {cfg.get('pytest_bin') and [cfg.get('pytest_bin'), '-q']}")
        print(f" - Mode: {cfg.get('mode', 's')}")
        print(f" - Excluded files: {cfg.get('excluded_patterns', [])}")
        print(f" - N locations input: {cfg.get('nlocations_input', 0)}")
        print(f" - Random seed: {cfg.get('random_seed')}")

        # Aggregate random sample details across runs
        tot_mut = ag.get("total_locations_mutated", 0)
        tot_ident = ag.get("total_locations_identified", 0)
        cov_pct = None
        try:
            # average coverage percentage if available
            cps = [r.get("random_sample", {}).get("coverage_pct") for r in runs]
            cps = [float(x) for x in cps if isinstance(x, (int, float))]
            cov_pct = sum(cps) / len(cps) if cps else None
        except Exception:
            cov_pct = None

        print("\nRandom sample details")
        print("-" * len("Random sample details"))
        print(f" - Total locations mutated: {tot_mut}")
        print(f" - Total locations identified: {tot_ident}")
        if cov_pct is not None:
            print(f" - Location sample coverage: {cov_pct:.2f} %")

        print("\nRunning time details")
        print("-" * len("Running time details"))
        # Summarize timings across runs
        def _avg(field):
            vals = []
            for r in runs:
                t = (((r or {}).get('timing') or {}).get(field) or {}).get('str')
                if t:
                    vals.append(str(t))
            return vals[0] if vals else None
        ct1 = _avg('clean_trial_1')
        ct2 = _avg('clean_trial_2')
        mtt = _avg('mutation_trials_total')
        if ct1:
            print(f" - Clean trial 1 run time: {ct1}")
        if ct2:
            print(f" - Clean trial 2 run time: {ct2}")
        if mtt:
            print(f" - Mutation trials total run time: {mtt}")

        print("\nOverall mutation trial summary")
        print("=" * len("Overall mutation trial summary"))
        print(f" - DETECTED: {ag.get('detected', 0)}")
        print(f" - SURVIVED: {ag.get('survived', 0)}")
        print(f" - TOTAL RUNS: {ag.get('total_runs', 0)}")
        # Print last run datetime if present
        try:
            last_dt = None
            for r in runs:
                dt = ((r or {}).get('summary') or {}).get('run_datetime')
                if dt:
                    last_dt = dt
            if last_dt:
                print(f" - RUN DATETIME: {last_dt}")
        except Exception:
            pass

    # Build a temporary Matrix with only MBFL columns for Top table
    from .matrix import Matrix
    mbfl_cols = {"mbfl_sbi", "mkf", "mkp"}
    m2 = Matrix()
    # Reconstruct from last written json if needed
    try:
        # The caller already exported json to args.output_json (relative to project_root);
        # load that path (resolve relative -> project_root) to filter columns
        json_path = args.output_json
        try:
            import os as _os
            if not _os.path.isabs(json_path):
                json_path = _os.path.join(project_root or ".", json_path)
        except Exception:
            pass
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for method, metrics in data.items():
            only = {k: v for k, v in metrics.items() if k in mbfl_cols}
            if only:
                m2.rows[method].update(only)
    except Exception:
        # Fallback to empty; Top will say no methods
        pass

    top_methods_for_pta: list[str] = []
    if args.print_top and args.print_top > 0:
        # Force metric to a reasonable default if not MBFL
        metric = "mbfl_sbi"
        # Determine the same top ordering for PTA summary later
        rows_scored: list[tuple[str, float]] = []
        try:
            for method, m in m2.rows.items():
                v = m.get(metric)
                if isinstance(v, (int, float)):
                    rows_scored.append((method, float(v)))
            rows_scored.sort(key=lambda x: x[1], reverse=True)
            top_methods_for_pta = [k for k, _ in rows_scored[: args.print_top]]
        except Exception:
            top_methods_for_pta = []
        _print_top_mbfl(m2, metric, args.print_top, include_tests=args.include_tests,
                        project_root=project_root, exclude_globs=args.exclude_glob,
                        method_name_only=args.method_name_only)

    # If PTA diagnostics exist, print a compact summary of killer tests per top method
    try:
        diag_path = os.path.join(project_root, ".suspect.mutatest.json")
        with open(diag_path, "r", encoding="utf-8") as f:
            diag_all = json.load(f)
        mbfl_diag = (diag_all or {}).get("mutatest", {}).get("mbfl", {})
        pta = (mbfl_diag or {}).get("per_test_attribution") or {}
        if pta and pta.get("enabled"):
            kills_by_test = pta.get("kills_by_test") or {}
            # Build MethodIndex for files observed in PTA
            files = set()
            for _tid, mapping in kills_by_test.items():
                for fl in mapping.keys():
                    try:
                        fpart = str(fl).rsplit(":", 1)[0]
                        files.add(fpart)
                    except Exception:
                        continue
            idx = MethodIndex()
            for fp in files:
                abs_fp = os.path.join(project_root, fp)
                try:
                    src = open(abs_fp, "r", encoding="utf-8").read()
                except Exception:
                    continue
                # Use posix-style key like elsewhere
                key = fp.replace("\\", "/")
                try:
                    idx.add_file(key, src)
                except Exception:
                    continue
            # Build per-method -> {test: count}
            per_method_tests: dict[str, dict[str, int]] = {}
            for testid, mapping in kills_by_test.items():
                for fl, cnt in (mapping or {}).items():
                    try:
                        fpart, lpart = str(fl).rsplit(":", 1)
                        ln = int(lpart)
                    except Exception:
                        continue
                    fkey = fpart.replace("\\", "/")
                    # Map to method key by scanning back lines
                    mkey = None
                    for b in range(ln, 0, -1):
                        mk = idx.index.get((fkey, b))
                        if mk:
                            mkey = mk
                            break
                    if not mkey:
                        continue
                    d = per_method_tests.setdefault(mkey, {})
                    d[testid] = d.get(testid, 0) + int(cnt)

            # Show a compact summary for the top methods (limit tests per method)
            if top_methods_for_pta:
                print("\nPer-Test Attribution (experimental)")
                print("-" * len("Per-Test Attribution (experimental)"))
                print("Shows top killer tests per top MBFL methods. Budgets/sampling may omit some tests.")
                max_tests = 3
                for mkey in top_methods_for_pta:
                    tests = per_method_tests.get(mkey)
                    if not tests:
                        continue
                    # Order tests by count desc
                    ordered = sorted(tests.items(), key=lambda x: x[1], reverse=True)[:max_tests]
                    mdisp = _format_method_with_line(mkey, project_root)
                    left = f" - {mdisp}"
                    right = ", ".join(f"{tid} (x{cnt})" for tid, cnt in ordered)
                    # Truncate right side to fit terminal if needed
                    term_w = _term_width(default=120)
                    max_right = max(20, term_w - len(left) - 3)
                    if len(right) > max_right:
                        right = _truncate(right, max_right)
                    print(f"{left}: {right}")
    except Exception:
        pass


def _print_top_mbfl(matrix, metric: str, top: int, include_tests: bool, project_root: Optional[str] = None,
                    exclude_globs: Optional[list[str]] = None, method_name_only: bool = False):
    # MBFL-only Top table: mbfl_sbi (primary), mkf, mkp
    metric_cols = ["mbfl_sbi"]
    rows = []
    for method, m in matrix.rows.items():
        rank_score = m.get(metric)
        if rank_score is None:
            continue
        if not include_tests and _looks_like_test_method(method):
            continue
        try:
            path = method.split(":", 1)[0]
            if _is_excluded(path, exclude_globs):
                continue
        except Exception:
            pass
        line_no = _method_start_line(method, project_root)
        pretty = _method_display(method, project_root, method_name_only)
        rows.append((line_no, pretty, float(rank_score), m))

    rows.sort(key=lambda x: x[2], reverse=True)
    if not rows:
        print("No methods with MBFL metric values to display.")
        return

    if top >= 0:
        rows = rows[:top]
    term_w = _term_width(default=120)
    line_w = max(2, len("ln"))
    rank_w = max(1, len(str(len(rows))))
    metric_w = 10
    mk_w = 4

    # Load killers: prefer diagnostics killers_by_method, else derive from PTA
    killers_by_method: dict[str, list[tuple[str, int]]] = {}
    try:
        diag_path = os.path.join(project_root or ".", ".suspect.mutatest.json")
        with open(diag_path, "r", encoding="utf-8") as f:
            diag_all = json.load(f)
        mbfl_diag = (diag_all or {}).get("mutatest", {}).get("mbfl", {}) or {}
        # Preferred source
        kb = mbfl_diag.get("killers_by_method") or {}
        if kb:
            try:
                for mkey, tests in kb.items():
                    # tests may be dict or list of pairs; normalize to sorted list of (testid, count)
                    if isinstance(tests, dict):
                        items = list(tests.items())
                    else:
                        items = [(a, b) for a, b in tests]
                    killers_by_method[mkey] = sorted(((str(t), int(c)) for t, c in items), key=lambda x: x[1], reverse=True)
            except Exception:
                killers_by_method = {}
        # Fallback to PTA-derived killers if preferred source absent
        if not killers_by_method:
            pta = mbfl_diag.get("per_test_attribution") or {}
            kills_by_test = pta.get("kills_by_test") or {}
            # Build MethodIndex for involved files
            files = set()
            for _tid, mapping in (kills_by_test or {}).items():
                for fl in (mapping or {}).keys():
                    try:
                        fpart = str(fl).rsplit(":", 1)[0]
                        files.add(fpart)
                    except Exception:
                        continue
            idx = MethodIndex()
            for fp in files:
                abs_fp = os.path.join(project_root or ".", fp)
                try:
                    src = open(abs_fp, "r", encoding="utf-8").read()
                except Exception:
                    continue
                key = fp.replace("\\", "/")
                try:
                    idx.add_file(key, src)
                except Exception:
                    continue
            # Aggregate per method
            per_method_tests: dict[str, dict[str, int]] = {}
            for testid, mapping in (kills_by_test or {}).items():
                for fl, cnt in (mapping or {}).items():
                    try:
                        fpart, lpart = str(fl).rsplit(":", 1)
                        ln = int(lpart)
                    except Exception:
                        continue
                    fkey = fpart.replace("\\", "/")
                    mkey = None
                    for b in range(ln, 0, -1):
                        mk = idx.index.get((fkey, b))
                        if mk:
                            mkey = mk
                            break
                    if not mkey:
                        continue
                    d = per_method_tests.setdefault(mkey, {})
                    d[testid] = d.get(testid, 0) + int(cnt)
            # Order tests by count desc for each method
            for mkey, tests in per_method_tests.items():
                ordered = sorted(tests.items(), key=lambda x: x[1], reverse=True)
                killers_by_method[mkey] = ordered
    except Exception:
        killers_by_method = {}

    # Estimate method column width; add optional killers column if available
    show_killers = bool(killers_by_method)
    killers_w = 28 if show_killers else 0
    non_method_chars = rank_w + line_w + 3 + (metric_w * len(metric_cols)) + (mk_w * 2) + killers_w
    col_count = 2 + 1 + len(metric_cols) + 2 + (1 if show_killers else 0)  # rank, ln, method, metrics, mkf,mkp, killers?
    gap_chars = (col_count - 1) * 2
    method_w_avail = max(20, term_w - (non_method_chars + gap_chars))
    method_w = max(20, min(max(len(r[1]) for r in rows), method_w_avail))

    # Always show mbfl_sbi and mkf even if zero across rows; zeros are informative for absence of failing-kill signal.
    show_mbfl_sbi = True
    show_mkf = True
    metric_cols = ["mbfl_sbi"]

    # Detect mutation count metrics presence
    include_mut_counts = any(
        any(k in m for k in ("mutants_detected", "mutants_survived", "mutation_score"))
        for _meth, m in matrix.rows.items()
    )
    header_cols = metric_cols + (["fail"] if show_mkf else []) + ["pass"]
    if include_mut_counts:
        header_cols += ["det", "surv", "mut_score"]
    if show_killers:
        header_cols = header_cols + ["killers"]
    header = f"Top {len(rows)} (ranked by {metric}) — " + ", ".join(header_cols)
    print("\n" + header)
    print("-" * len(header))
    # (Previously we omitted all-zero columns. We now always display them for transparency.)
    head_cols = ["#".rjust(rank_w), "ln".rjust(line_w), "method".ljust(method_w)]
    head_cols += [name.rjust(metric_w) for name in metric_cols]
    if show_mkf:
        head_cols += ["fail".rjust(mk_w)]
    head_cols += ["pass".rjust(mk_w)]
    if include_mut_counts:
        head_cols += ["det".rjust(6), "surv".rjust(6), "mut_sc".rjust(6)]
    if show_killers:
        head_cols += ["killers".ljust(max(8, killers_w))]
    print("  ".join(head_cols))

    for idx, (line_no, pretty, _score, m) in enumerate(rows, start=1):
        pretty_out = _truncate(pretty, method_w)
        vals = [
            str(idx).rjust(rank_w),
            (str(int(line_no)) if isinstance(line_no, int) else "").rjust(line_w),
            pretty_out.ljust(method_w),
        ]
        for name in metric_cols:
            v = m.get(name)
            vals.append((f"{float(v):.4f}" if isinstance(v, (int, float)) else "").rjust(metric_w))
        mkf = m.get("mkf")
        mkp = m.get("mkp")
        if show_mkf:
            vals.append((str(int(mkf)) if isinstance(mkf, (int, float)) else "").rjust(mk_w))  # fail
        vals.append((str(int(mkp)) if isinstance(mkp, (int, float)) else "").rjust(mk_w))  # pass
        if include_mut_counts:
            det = m.get("mutants_detected")
            surv = m.get("mutants_survived")
            msc = m.get("mutation_score")
            vals.append((str(int(det)) if isinstance(det, (int, float)) else "").rjust(6))
            vals.append((str(int(surv)) if isinstance(surv, (int, float)) else "").rjust(6))
            vals.append((f"{float(msc):.2f}" if isinstance(msc, (int, float)) else "").rjust(6))
        if show_killers:
            # Find killers for the original method key; need to map pretty back to key; instead use matrix row method keys
            # Build a reverse lookup from pretty to method if necessary by scanning candidates
            killer_str = ""
            try:
                # Attempt to recover the exact method key by matching metrics dict identity
                # Fallback: search by mkf/mkp+metrics uniqueness
                target_keys = []
                for mkey, mm in matrix.rows.items():
                    if mm is m:
                        target_keys = [mkey]
                        break
                if not target_keys:
                    signature = (
                        m.get("mbfl_sbi"),
                        m.get("mkf"),
                        m.get("mkp"),
                        m.get("mutants_detected"),
                        m.get("mutants_survived"),
                        m.get("mutation_score"),
                    )
                    for mkey, mm in matrix.rows.items():
                        candidate = (
                            mm.get("mbfl_sbi"),
                            mm.get("mkf"),
                            mm.get("mkp"),
                            mm.get("mutants_detected"),
                            mm.get("mutants_survived"),
                            mm.get("mutation_score"),
                        )
                        if candidate == signature:
                            target_keys.append(mkey)
                if target_keys:
                    mkey0 = target_keys[0]
                    killers = killers_by_method.get(mkey0) or []
                    if killers:
                        parts: list[str] = []
                        for i, (tid, cnt) in enumerate(killers):
                            parts.append(f"{tid} (x{cnt})")
                            if i >= 1:
                                break
                        killer_str = _truncate(", ".join(parts), max(8, killers_w))
            except Exception:
                killer_str = ""
            vals.append(killer_str.ljust(max(8, killers_w)))
        print("  ".join(vals))


def _term_width(default: int = 120) -> int:
    try:
        size = shutil.get_terminal_size(fallback=(default, 20))
        return int(size.columns) if size and size.columns else default
    except Exception:
        return default


def _truncate(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    if width <= 3:
        return s[:width]
    return s[: width - 1] + "…"


def _method_display(method_key: str, project_root: Optional[str], method_name_only: bool) -> str:
    """Return how a method should be shown in the Top table.

    - When method_name_only is True, show only the qualified method/class name.
    - Otherwise, show relative file path and qualified name.
    """
    if method_name_only:
        try:
            
            _path, qual = method_key.split(":", 1)
            return qual
        except ValueError:
            return method_key
    return _shorten_method(method_key, project_root)


def _looks_like_test_method(method_key: str) -> bool:
    # method_key format: "<path-or-name>:<qualname>"
    path = method_key.split(":", 1)[0]
    base = path.split("/")[-1]
    return base.startswith("test_") or "/tests/" in path or path.endswith("_test.py")


def _shorten_method(method_key: str, project_root: Optional[str]) -> str:
    try:
        path, qual = method_key.split(":", 1)
    except ValueError:
        return method_key
    try:
        import os
        if project_root:
            # Resolve path relative to project_root when needed to avoid '../'
            abs_path = path if os.path.isabs(path) else os.path.normpath(os.path.join(project_root, path))
            rel = os.path.relpath(abs_path, start=project_root)
            path = rel
        else:
            path = path.split("/")[-1]
    except Exception:
        path = path.split("/")[-1]
    return f"{path}:{qual}"


# Cache of computed method start lines per (project_root, file_key)
_FILE_METHOD_STARTS: dict[tuple[str, str], dict[str, int]] = {}


def _method_start_line(method_key: str, project_root: Optional[str]) -> Optional[int]:
    try:
        path, _qual = method_key.split(":", 1)
    except ValueError:
        return None
    try:
        import os
        file_key = path  # the key used by MethodIndex
        abs_path = path if os.path.isabs(path) else os.path.join(project_root or ".", path)
        cache_key = (os.path.abspath(project_root or "."), file_key)
        if cache_key not in _FILE_METHOD_STARTS:
            try:
                src = open(abs_path, "r", encoding="utf-8").read()
            except Exception:
                return None
            idx = MethodIndex()
            idx.add_file(file_key, src)
            starts: dict[str, int] = {}
            for (k, ln), mk in idx.index.items():
                if k != file_key:
                    continue
                if mk not in starts or ln < starts[mk]:
                    starts[mk] = ln
            _FILE_METHOD_STARTS[cache_key] = starts
        return _FILE_METHOD_STARTS[cache_key].get(method_key)
    except Exception:
        return None


def _format_method_with_line(method_key: str, project_root: Optional[str]) -> str:
    base = _shorten_method(method_key, project_root)
    ln = _method_start_line(method_key, project_root)
    if isinstance(ln, int):
        return f"{base} (L{ln})"
    return base


def _print_coverage(project_root: str, top: int, exclude_globs: Optional[list[str]] = None, tests_cmd: Optional[str] = None) -> None:
    """Print coverage like `coverage report -m`, by running a fresh coverage pass.

    This avoids any anomalies from the per-test dynamic-context run used for SBFL.
    """
    rows: list[tuple[str, int, int, int, int, float, list[int]]] = []
    # Run a clean coverage session in the project root
    abs_proj = os.path.abspath(project_root)
    py = sys.executable or "python"
    # Discover test files explicitly to avoid pytest rootdir heuristics skipping collection.
    test_args: list[str] = []
    try:
        for root, _dirs, files in os.walk(abs_proj):
            for fn in files:
                if (fn.startswith("test_") and fn.endswith(".py")) or fn.endswith("_test.py"):
                    rel = os.path.relpath(os.path.join(root, fn), start=abs_proj)
                    # Normalize to POSIX-style for pytest
                    test_args.append(rel)
    except Exception:
        test_args = []
    try:
        subprocess.run(f"{py} -m coverage erase", shell=True, check=False, cwd=abs_proj)
        # Determine coverage --source (env override or default '.')
        source_root = os.environ.get("SUSPECT_COVERAGE_SOURCE", ".")
        # Avoid duplicating --source if user already injected it
        def _inject_source(cmd: str) -> str:
            if "--source" in cmd:
                return cmd
            return cmd.replace(" -m coverage run ", f" -m coverage run --source {shlex.quote(source_root)} ")
        if tests_cmd:
            # Use user-supplied tests command verbatim (may include redirection)
            base = f"{py} -m coverage run -m {tests_cmd}"
            cmd = _inject_source(base)
        else:
            if test_args:
                base = f"{py} -m coverage run -m pytest -q " + " ".join(shlex.quote(a) for a in test_args)
            else:
                base = f"{py} -m coverage run -m pytest -q"
            cmd = _inject_source(base)
        subprocess.run(cmd, shell=True, check=False, cwd=abs_proj)
    except Exception as e:
        print(f"[WARN] Could not run coverage: {e}")
        return

    # Load results via Coverage API (ensure cwd is project root when reading .coverage)
    try:
        from coverage import Coverage  # type: ignore
        old_cwd = os.getcwd()
        os.chdir(abs_proj)
        try:
            cov = Coverage(data_file=os.path.join(abs_proj, ".coverage"))
            cov.load()
            data = cov.get_data()
            for fname in data.measured_files() if data else []:
                try:
                    _fn, statements, _excluded, missing, _executed = cov.analysis2(fname)  # type: ignore[attr-defined]
                except Exception:
                    continue
                stmts = len(statements) if isinstance(statements, (list, tuple)) else 0
                miss = len(missing) if isinstance(missing, (list, tuple)) else 0
                branches = 0  # branch support off for now
                brpart = 0
                pct = (100.0 * (stmts - miss) / stmts) if stmts else 100.0
                try:
                    disp = os.path.relpath(fname, start=abs_proj)
                    if disp.startswith(".."):
                        disp = os.path.basename(fname)
                except Exception:
                    disp = os.path.basename(fname)
                disp = disp.replace("\\", "/")
                rows.append((disp, stmts, miss, branches, brpart, float(pct), list(missing)))
        finally:
            os.chdir(old_cwd)
    except Exception as e:
        print(f"[WARN] Could not load coverage data: {e}")
        return

    # Fallback: if API-derived rows empty, attempt coverage json report parsing
    if not rows:
        try:
            import json as _json, tempfile as _temp
            tmp = _temp.NamedTemporaryFile(delete=False, suffix=".json")
            tmp_path = tmp.name
            tmp.close()
            subprocess.run(f"{py} -m coverage json -o {shlex.quote(tmp_path)} --show-contexts", shell=True, check=False, cwd=abs_proj)
            with open(tmp_path, "r", encoding="utf-8") as jf:
                cj = _json.load(jf)
            files_meta = cj.get("files", {}) if isinstance(cj, dict) else {}
            for fpath, meta in files_meta.items():
                try:
                    summary = meta.get("summary", {}) if isinstance(meta, dict) else {}
                    stmts = int(summary.get("num_statements", 0))
                    miss = int(summary.get("missing_lines", 0))
                    branches = int(summary.get("num_branches", 0))
                    brpart = int(summary.get("missing_branches", 0))
                    pct = float(summary.get("percent_covered", 100.0))
                    missing_list = meta.get("missing_lines", []) or []
                    try:
                        disp = os.path.relpath(fpath, start=abs_proj)
                        if disp.startswith(".."):
                            disp = os.path.basename(fpath)
                    except Exception:
                        disp = os.path.basename(fpath)
                    disp = disp.replace("\\", "/")
                    if not os.path.abspath(fpath).startswith(os.path.abspath(abs_proj)):
                        continue
                    base = disp.split("/")[-1]
                    if base.startswith("test_") or base.endswith("_test.py"):
                        continue
                    rows.append((disp, stmts, miss, branches, brpart, pct, missing_list))
                except Exception:
                    continue
        except Exception:
            pass

    # Sort by name to emulate coverage's default
    rows.sort(key=lambda r: r[0])
    # Apply exclude globs if provided
    if exclude_globs:
        rows = [r for r in rows if not _is_excluded(r[0], exclude_globs)]
    display_rows = rows[:top] if top and top > 0 else rows

    # Header like coverage report -m
    name_w = max(12, max((len(r[0]) for r in display_rows), default=12))
    print("\nName".ljust(name_w) + f"  {'Stmts':>5}  {'Miss':>5}  {'Branch':>6} {'BrPart':>6}  {'Cover':>6}  Missing")
    print("-" * (name_w + 2 + 5 + 2 + 5 + 2 + 6 + 1 + 6 + 2 + 6 + 2 + 7))
    for name, stmts, miss, branches, brpart, pct, missing_lines in display_rows:
        missing_s = _format_missing_ranges(missing_lines)
        print(f"{name.ljust(name_w)}  {stmts:>5}  {miss:>5}  {branches:>6} {brpart:>6}  {pct:>5.0f}%  {missing_s}")

    # Totals derived from rows
    t_stmts = sum(r[1] for r in rows)
    t_miss = sum(r[2] for r in rows)
    t_branches = sum(r[3] for r in rows)
    t_brpart = sum(r[4] for r in rows)
    t_pct = (100.0 * (t_stmts - t_miss) / t_stmts) if t_stmts else 100.0
    print("-" * (name_w + 2 + 5 + 2 + 5 + 2 + 6 + 1 + 6 + 2 + 6 + 2 + 7))
    print(f"TOTAL".ljust(name_w) + f"  {t_stmts:>5}  {t_miss:>5}  {t_branches:>6} {t_brpart:>6}  {float(t_pct):>5.0f}%")


def _format_missing_ranges(lines: list[int]) -> str:
    if not lines:
        return ""
    ln = sorted(int(x) for x in lines)
    parts = []
    start = prev = ln[0]
    for x in ln[1:]:
        if x == prev + 1:
            prev = x
            continue
        # close current range
        parts.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = x
    parts.append(str(start) if start == prev else f"{start}-{prev}")
    return ", ".join(parts)


def _is_excluded(path: str, patterns: Optional[list[str]]) -> bool:
    if not patterns:
        return False
    p = str(path).replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    for pat in patterns:
        if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False


def _cleanup_pytest_processes(project_root: str, phase: str = "post") -> None:
    """Best-effort termination of stray pytest processes spawned by mutation runs.

    Criteria:
      - command contains 'pytest'
      - command references the project_root path AND a mutant junitxml pattern '.suspect.mbfl/mutant-'
      - process parent is 1 (orphan) OR phase == 'post' (more aggressive)

    We first try SIGTERM then SIGKILL if still present on next scan.
    """
    try:
        ps_out = subprocess.check_output(["ps", "-axo", "pid,ppid,command"], text=True)
    except Exception:
        return
    lines = ps_out.strip().splitlines()[1:]
    targets: list[tuple[int,int,str]] = []
    for ln in lines:
        try:
            parts = ln.strip().split(None, 2)
            if len(parts) < 3:
                continue
            pid = int(parts[0]); ppid = int(parts[1]); cmd = parts[2]
        except Exception:
            continue
        if 'pytest' not in cmd:
            continue
        if project_root not in cmd:
            continue
        if '.suspect.mbfl/mutant-' not in cmd:
            continue
        if ppid == 1 or phase == 'post':
            targets.append((pid, ppid, cmd))
    if not targets:
        return
    # First pass: SIGTERM
    for pid, _ppid, _cmd in targets:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    time.sleep(0.2)
    # Second pass: SIGKILL survivors
    try:
        live_out = subprocess.check_output(["ps", "-axo", "pid"], text=True)
        live_pids = {int(x) for x in live_out.strip().splitlines()[1:] if x.strip().isdigit()}
    except Exception:
        live_pids = set()
    killed_force = 0
    for pid, _ppid, _cmd in targets:
        if pid in live_pids:
            try:
                os.kill(pid, signal.SIGKILL)
                killed_force += 1
            except Exception:
                pass
    summary = f"[INFO] MBFL {phase} cleanup: terminated {len(targets)} pytest processes"
    if killed_force:
        summary += f" (force-killed {killed_force})"
    print(summary)


def _print_kill_matrix(project_root: str, top_methods: int, top_tests: int, element_max_len: int = 0) -> None:
    """Render a method (Element) × test matrix with consistent Element/Mutant headers."""
    import json, os
    try:
        with open(os.path.join(project_root, '.suspect.mutatest.json'), 'r', encoding='utf-8') as f:
            diag = json.load(f)
    except Exception:
        print("[INFO] Kill matrix unavailable (no diagnostics).")
        return
    mbfl_diag = (diag or {}).get('mutatest', {}).get('mbfl', {}) or {}
    killers_by_method = mbfl_diag.get('killers_by_method') or {}
    if not killers_by_method:
        print("[INFO] Kill matrix unavailable (no killer attribution).")
        return
    # Load metrics
    try:
        with open(os.path.join(project_root, 'matrix.json'), 'r', encoding='utf-8') as f:
            matrix_rows = json.load(f)
    except Exception:
        matrix_rows = {}
    # Reconstruct if needed
    if not matrix_rows:
        matrix_rows = {}
        try:
            runs = (diag or {}).get('mutatest', {}).get('runs', []) or []
            from .mapping import MethodIndex as _MI
            mi = _MI(); added = set(); counts = {}
            for r in runs:
                if not isinstance(r, dict):
                    continue
                mut = r.get('mutant') or {}
                f = mut.get('file'); ln = mut.get('line')
                if not (isinstance(f, str) and isinstance(ln, int)):
                    continue
                rel = f.replace('\\', '/').lstrip('./')
                if rel not in added:
                    try:
                        with open(os.path.join(project_root, rel), 'r', encoding='utf-8') as sf:
                            mi.add_file(rel, sf.read())
                        added.add(rel)
                    except Exception:
                        continue
                # find method
                mkey = None
                for b in range(ln, 0, -1):
                    m = mi.index.get((rel, b))
                    if m:
                        mkey = m; break
                if not mkey:
                    continue
                if r.get('killed'):
                    bucket_val = r.get('bucket')
                    d = counts.setdefault(mkey, {'fail': 0, 'pass': 0})
                    if bucket_val in ('fail', 'mixed'):
                        d['fail'] += 1
                    if bucket_val in ('pass', 'mixed'):
                        d['pass'] += 1
            for mk, cp in counts.items():
                fail_v = cp['fail']; pass_v = cp['pass']; den = fail_v + pass_v
                matrix_rows[mk] = {'fail': fail_v, 'pass': pass_v, 'mbfl_sbi': (fail_v/den) if den else 0.0}
        except Exception:
            pass
    # Build ordered methods
    methods = []
    for mkey, killers in killers_by_method.items():
        mm = matrix_rows.get(mkey, {}) if isinstance(matrix_rows, dict) else {}
        score = mm.get('mbfl_sbi')
        if not isinstance(score, (int, float)):
            # Fallback: compute suspiciousness from available counts rather than raw kill totals.
            fail_v = mm.get('fail') if isinstance(mm, dict) else None
            pass_v = mm.get('pass') if isinstance(mm, dict) else None
            if not isinstance(fail_v, (int, float)) and 'mkf' in mm:
                fail_v = mm.get('mkf')
            if not isinstance(pass_v, (int, float)) and 'mkp' in mm:
                pass_v = mm.get('mkp')
            fail_v = fail_v or 0
            pass_v = pass_v or 0
            denom = fail_v + pass_v
            score = (fail_v / denom) if denom else 0.0
        methods.append((mkey, float(score)))
    methods.sort(key=lambda x: x[1], reverse=True)
    if top_methods > 0:
        methods = methods[:top_methods]
    # Collect tests
    test_counts = {}
    for mkey, _s in methods:
        killers = killers_by_method.get(mkey) or {}
        if isinstance(killers, dict):
            for tid, cnt in killers.items():
                test_counts[tid] = test_counts.get(tid, 0) + int(cnt)
        else:
            for tid, cnt in killers:
                test_counts[tid] = test_counts.get(tid, 0) + int(cnt)
    ranked_tests = sorted(test_counts.items(), key=lambda x: x[1], reverse=True)
    if top_tests > 0:
        ranked_tests = ranked_tests[:top_tests]
    test_ids = [t for t, _c in ranked_tests]
    if not methods or not test_ids:
        print("[INFO] Kill matrix has no methods or tests to display.")
        return
    col_labels = [f"T{i+1}" for i in range(len(test_ids))]

    # Abbreviate method keys to friendlier forms (basename:func) with collision resolution.
    original_keys = [m[0] for m in methods]
    abbrev_map = {}
    # First pass: basename:method
    from pathlib import PurePosixPath as _P
    temp_map = {}
    collisions = {}
    for full in original_keys:
        if ':' in full:
            path_part, meth = full.rsplit(':', 1)
        else:
            path_part, meth = full, ''
        base = _P(path_part).name
        short = f"{base}:{meth}" if meth else base
        if short in temp_map:
            collisions.setdefault(short, set()).add(full)
            collisions[short].add(temp_map[short])
        temp_map.setdefault(short, full)
        abbrev_map[full] = short
    # Resolve collisions by prepending parent directories until unique
    if collisions:
        # Build reverse bucket: full -> components
        for short, fullset in collisions.items():
            # For each colliding full path, walk up directories
            buckets = list(fullset)
            # Determine needed depth per path
            resolved = False
            depth = 1
            while not resolved and depth < 10:  # arbitrary safety bound
                seen = {}
                new_labels = {}
                conflict = False
                for full in buckets:
                    if ':' in full:
                        path_part, meth = full.rsplit(':', 1)
                    else:
                        path_part, meth = full, ''
                    parts = _P(path_part).parts
                    # take last depth segments
                    segs = parts[-depth:] if depth <= len(parts) else parts
                    label = '/'.join(segs) + (f":{meth}" if meth else '')
                    if label in seen:
                        conflict = True
                    seen.setdefault(label, full)
                    new_labels[full] = label
                if not conflict:
                    for full, label in new_labels.items():
                        abbrev_map[full] = label
                    resolved = True
                depth += 1
            if not resolved:
                # Fallback: append hash fragment to force uniqueness
                import hashlib
                for full in buckets:
                    h = hashlib.sha1(full.encode('utf-8')).hexdigest()[:6]
                    abbrev_map[full] = f"{abbrev_map[full]}~{h}"

    # Optionally truncate display labels first (before computing width) while tracking mapping.
    truncated_map = {}
    if element_max_len and element_max_len > 4:  # need room for ellipsis
        for full, short in abbrev_map.items():
            if len(short) > element_max_len:
                truncated = short[:element_max_len-1] + '…'
            else:
                truncated = short
            truncated_map[full] = truncated
    else:
        truncated_map = {k: v for k, v in abbrev_map.items()}

    method_col_w = max(14, min(60, max(len(truncated_map[m[0]]) for m in methods)))
    mutant_col_w = 8; cell_w = max(4, max(len(c) for c in col_labels))
    score_col_w = 7; mk_w = 4
    border = ("+" + ("-"*(method_col_w+2)) + "+" + ("-"*(mutant_col_w+2)) + "+" +
              "+".join(["-"*(cell_w+2) for _ in col_labels]) + "+" +
              ("-"*(score_col_w+2)) + "+" + ("-"*(mk_w+2)) + "+" + ("-"*(mk_w+2)) + "+")
    print("\nKill Matrix (X = killed, ✓ = no kill)")
    print(border)
    header = (f"| {'Element'.ljust(method_col_w)} | {'Mutant'.ljust(mutant_col_w)} | " +
              " | ".join(lbl.center(cell_w) for lbl in col_labels) + " | " +
              "Score".center(score_col_w) + " | " + "mkf".center(mk_w) + " | " + "mkp".center(mk_w) + " |")
    print(header); print(border)
    for mkey, _s in methods:
        row_cells: list[str] = []
        killers = killers_by_method.get(mkey) or {}
        if not isinstance(killers, dict):
            nd = {}
            try:
                for tid, cnt in killers:
                    nd[tid] = nd.get(tid, 0) + int(cnt)
            except Exception:
                nd = {}
            killers = nd
        row_cells = [('X' if (tid in killers and killers[tid] > 0) else '✓').center(cell_w) for tid in test_ids]
        mm = matrix_rows.get(mkey, {}) if isinstance(matrix_rows, dict) else {}
        fail_val = mm.get('fail') if isinstance(mm, dict) else None
        pass_val = mm.get('pass') if isinstance(mm, dict) else None
        if fail_val is None and 'mkf' in mm:
            fail_val = mm.get('mkf', 0)
        if pass_val is None and 'mkp' in mm:
            pass_val = mm.get('mkp', 0)
        fail_val = fail_val or 0
        pass_val = pass_val or 0
        denom = fail_val + pass_val
        susp = (fail_val/denom) if denom else 0.0
        score_txt = f"{susp:.2f}".rjust(score_col_w)
        mkf_num = int(mm.get('mkf', fail_val) or 0)
        mkp_num = int(mm.get('mkp', pass_val) or 0)
        mkf_txt = str(mkf_num).rjust(mk_w)
        mkp_txt = str(mkp_num).rjust(mk_w)
        det_total = int(mm.get('mutants_detected') or (mkf_num + mkp_num))
        det_txt = (str(det_total) if det_total else '-').center(mutant_col_w)
        display_key = truncated_map.get(mkey, mkey)
        print(f"| {display_key.ljust(method_col_w)} | {det_txt} | " + " | ".join(row_cells) + f" | {score_txt} | {mkf_txt} | {mkp_txt} |")
    print(border)
    print("Legend (tests):")
    for idx, (tid, _c) in enumerate(ranked_tests, start=1):
        print(f"  {col_labels[idx-1]} = {tid}")
    print("Score = fail(m)/(fail(m)+pass(m)). Mutant = detected mutants (mkf+mkp). mkf=fail bucket kills, mkp=pass bucket kills.")
    # Abbreviation legend
    show_legend = any(abbrev_map[k] != k for k in abbrev_map) or (element_max_len and element_max_len > 0)
    if show_legend:
        print("Element abbreviations:")
        for full in sorted(original_keys):
            short = truncated_map.get(full, full)
            if short != full:
                print(f"  {short} -> {full}")


def _print_mutant_matrix(project_root: str, top_mutants: int, top_tests: int, all_tests: bool = False) -> None:
    """Render a mutant (id + file:line:kind) x test matrix.

    Uses .suspect.mutatest.json runs entries. Each mutant row shows which tests are its *killing* tests.
    A killing test = any test in the mutant's killers list. Survived/timeouts will have only ✓ entries.
    Columns chosen similarly to kill matrix: tests ranked by total kill frequency across selected mutants.
    """
    import json, os
    diag_path = os.path.join(project_root, '.suspect.mutatest.json')
    try:
        with open(diag_path, 'r', encoding='utf-8') as f:
            diag = json.load(f)
    except Exception:
        print("[INFO] Mutant matrix unavailable (no diagnostics).")
        return
    runs = (diag or {}).get('mutatest', {}).get('runs', []) or []
    # Build list of mutant records with killers
    mutant_rows = []
    for r in runs:
        if not isinstance(r, dict):
            continue
        mut = r.get('mutant') or {}
        mid = r.get('id')
        file = mut.get('file'); line = mut.get('line'); kind = mut.get('kind')
        killers = r.get('killers') or []
        repair_tests = r.get('repair_tests') or []
        regress_tests = r.get('regress_tests') or []
        killed = bool(r.get('killed'))
        bucket = r.get('bucket')
        if not (file and isinstance(line, int) and kind):
            continue
        display = f"{mid}:{file}:{line}:{kind}" if mid is not None else f"{file}:{line}:{kind}"
        mutant_rows.append({
            'id': mid,
            'display': display,
            'file': file,
            'line': line,
            'kind': kind,
            'killers': killers if isinstance(killers, list) else [],
            'repair_tests': repair_tests if isinstance(repair_tests, list) else [],
            'regress_tests': regress_tests if isinstance(regress_tests, list) else [],
            'killed': killed,
            'bucket': bucket,
        })
    if not mutant_rows:
        print("[INFO] Mutant matrix unavailable (no mutant run records).")
        return
    # Limit mutants if requested
    if top_mutants >= 0:
        mutant_rows = mutant_rows[:top_mutants]
    # Count test frequencies (optionally across all mutants, not just displayed subset)
    test_counts = {}
    if all_tests:
        # Re-load full runs for killer aggregation regardless of row truncation
        full_runs = (diag or {}).get('mutatest', {}).get('runs', []) or []
        for r in full_runs:
            if not isinstance(r, dict):
                continue
            killers_union = set(r.get('killers') or [])
            killers_union.update(r.get('repair_tests') or [])
            killers_union.update(r.get('regress_tests') or [])
            for t in killers_union:
                test_counts[t] = test_counts.get(t, 0) + 1
    else:
        for mr in mutant_rows:
            killers_union = set(mr.get('killers') or [])
            killers_union.update(mr.get('repair_tests') or [])
            killers_union.update(mr.get('regress_tests') or [])
            for t in killers_union:
                test_counts[t] = test_counts.get(t, 0) + 1
    ranked_tests = sorted(test_counts.items(), key=lambda x: x[1], reverse=True)
    if not all_tests and top_tests > 0:
        ranked_tests = ranked_tests[:top_tests]
    test_ids = [t for t,_c in ranked_tests]
    if all_tests:
        # Always also include baseline failing tests (may not have killed a mutant yet)
        baseline = (diag or {}).get('mutatest', {}).get('baseline', {}) or {}
        failing_nodeids = baseline.get('failing_nodeids') or []
        for bid in failing_nodeids:
            if bid not in test_ids:
                test_ids.append(bid)
    if not test_ids:
        baseline = (diag or {}).get('mutatest', {}).get('baseline', {}) or {}
        failing_nodeids = baseline.get('failing_nodeids') or []
        test_ids = failing_nodeids[:top_tests] if failing_nodeids else []
    if not test_ids:
        print("[INFO] Mutant matrix has no tests to display.")
        return
    col_labels = [f"T{i+1}" for i in range(len(test_ids))]
    test_label_map = dict(zip(test_ids, col_labels))
    # Layout widths
    mut_col_w = max(18, min(72, max(len(mr['display']) for mr in mutant_rows)))
    cell_w = max(4, max(len(c) for c in col_labels))
    susp_col_w = 6  # 'Susp' plus 1 decimal (or 0.00) comfortably
    top_border = "+" + ("-" * (mut_col_w + 2)) + "+" + "+".join(["-" * (cell_w + 2) for _ in col_labels]) + "+" + ("-" * (susp_col_w + 2)) + "+"
    print("\nPer-Mutant Matrix (X = test killed this mutant, ✓ = no kill)")
    print(top_border)
    header = (
        f"| {'Mutant / Test'.ljust(mut_col_w)} | "
        + " | ".join(lbl.center(cell_w) for lbl in col_labels)
        + " | " + "Susp".center(susp_col_w) + " |"
    )
    print(header)
    print(top_border)
    for mr in mutant_rows:
        row_cells = []
        killers_set = set(mr.get('killers') or [])
        killers_set.update(mr.get('repair_tests') or [])
        killers_set.update(mr.get('regress_tests') or [])
        for tid in test_ids:
            mark = 'X' if tid in killers_set else '✓'
            row_cells.append(mark.center(cell_w))
        repair_set = set(mr.get('repair_tests') or [])
        regress_set = set(mr.get('regress_tests') or [])
        denom = len(repair_set) + len(regress_set)
        if denom:
            susp_val = len(repair_set) / denom
        else:
            # Legacy fallback based on bucket label
            bucket = mr.get('bucket')
            if bucket == 'fail':
                susp_val = 1.0
            elif bucket == 'pass':
                susp_val = 0.0
            elif bucket == 'mixed':
                susp_val = 0.5
            else:
                susp_val = None
        susp_txt = (f"{susp_val:.2f}" if isinstance(susp_val, float) else "").rjust(susp_col_w)
        print(f"| {mr['display'].ljust(mut_col_w)} | " + " | ".join(row_cells) + f" | {susp_txt} |")
    print(top_border)
    print("Legend (tests):")
    for idx,(tid,_c) in enumerate(ranked_tests, start=1):
        print(f"  {col_labels[idx-1]} = {tid}")
    scope_note = "all mutants" if top_mutants < 0 else f"top {len(mutant_rows)} mutants"
    tests_note = "all killer tests (global) + baseline failing" if all_tests else "killer tests among displayed mutants"
    limit_note = "no test column limit" if all_tests else (f"top {len(test_ids)} tests" if top_tests > 0 else "all killer tests (displayed subset)")
    print(f"Note: Susp = 1.00 (fail-kill), 0.00 (pass-kill), blank (survived/timeout). Rows: {scope_note}. Columns: {tests_note}; {limit_note}.")


@dataclass
class MutantRecord:
    label: str
    method_display: str
    mutation_kind: str
    mutation_desc: str
    line_no: int
    status_display: str
    baseline_hit: bool
    susp_value: Optional[float]
    fail_count: int
    pass_count: int
    unique_killers: list[str]
    repair_tests: list[str]
    regress_tests: list[str]
    no_kill_data: bool
    snippet: str


def _print_mutant_details(project_root: str, show_table: bool = False) -> None:
    """Print per-mutant diagnostics as an optional table plus narrative summary."""
    import json
    import os

    diag_path = os.path.join(project_root, '.suspect.mutatest.json')
    try:
        with open(diag_path, 'r', encoding='utf-8') as f:
            diag = json.load(f)
    except Exception:
        print("[INFO] Mutant details unavailable (no diagnostics).")
        return

    mutatest = (diag or {}).get('mutatest') or {}
    runs = mutatest.get('runs') or []
    if not runs:
        print("[INFO] Mutant details unavailable (no mutant runs).")
        return

    baseline = mutatest.get('baseline') or {}
    failing_tests = baseline.get('failing_nodeids') or []
    failing_tests_set = {str(t) for t in failing_tests}
    if failing_tests:
        print("\nBaseline failing tests (MBFL baseline run):")
        for tid in failing_tests:
            print(f"  - {tid}")

    kind_descriptions = {
        'cmp_flip': "Comparison operator flipped (e.g., < ↔ <=, == ↔ !=).",
        'bool_flip': "Boolean literal flipped (True ↔ False).",
        'and_to_or': "Logical operator changed: and → or.",
        'or_to_and': "Logical operator changed: or → and.",
    }

    idx = MethodIndex()
    file_cache: dict[str, str] = {}

    def _normalize_path(p: str) -> str:
        norm = p.replace('\\', '/').strip()
        if norm.startswith('./'):
            norm = norm[2:]
        return norm

    def _ensure_file(rel_path: str) -> None:
        if rel_path in file_cache:
            return
        abs_path = os.path.join(project_root, rel_path)
        try:
            text = Path(abs_path).read_text(encoding='utf-8')
        except Exception:
            text = ""
        file_cache[rel_path] = text
        if text:
            try:
                idx.add_file(rel_path, text)
            except Exception:
                pass

    def _line_snippet(rel_path: str, line_no: int) -> str:
        text = file_cache.get(rel_path)
        if text is None:
            _ensure_file(rel_path)
            text = file_cache.get(rel_path, "")
        if not text:
            return ""
        lines = text.splitlines()
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1].strip()
        return ""

    def _method_for_line(rel_path: str, line_no: int) -> Optional[str]:
        if rel_path not in file_cache:
            _ensure_file(rel_path)
        for back in range(line_no, 0, -1):
            mk = idx.index.get((rel_path, back))
            if mk:
                return mk
        return None

    runs_sorted = sorted(runs, key=lambda r: (r.get('id') is None, r.get('id', 0)))
    records: list[MutantRecord] = []

    for entry in runs_sorted:
        if not isinstance(entry, dict):
            continue
        mut_info = entry.get('mutant') or {}
        file_raw = mut_info.get('file')
        line_no = mut_info.get('line')
        kind = mut_info.get('kind')
        if not (isinstance(file_raw, str) and isinstance(line_no, int) and kind):
            continue
        rel_file = _normalize_path(file_raw)
        _ensure_file(rel_file)
        method_key = _method_for_line(rel_file, line_no)
        method_display = _format_method_with_line(method_key, project_root) if method_key else f"{rel_file}:L{line_no}"
        snippet = _line_snippet(rel_file, line_no)
        mid = entry.get('id')
        status = "killed" if entry.get('killed') else "survived"
        bucket = entry.get('bucket')
        bucket_txt = f" ({bucket})" if bucket else ""
        kind_txt = kind_descriptions.get(kind, str(kind).replace('_', ' '))
        mutant_label = f"Mutant {mid}" if mid is not None else f"Mutant {rel_file}:{line_no}"

        killers_raw = entry.get('killers') or []
        killers_list = [str(t) for t in killers_raw if t is not None]
        repair_tests_list = [str(t) for t in (entry.get('repair_tests') or []) if t is not None]
        regress_tests_list = [str(t) for t in (entry.get('regress_tests') or []) if t is not None]
        unique_killers: list[str] = []
        seen = set()
        for tid in killers_list:
            if tid not in seen:
                unique_killers.append(tid)
                seen.add(tid)
        killers_set = set(unique_killers)

        # regress_tests (pass → fail) represent failing outcomes introduced by the mutant.
        # repair_tests (fail → pass) represent baseline failing tests repaired by the mutant.
        fail_sources: list[str] = list(regress_tests_list)
        pass_sources: list[str] = list(repair_tests_list)
        if not fail_sources and bucket == 'pass':
            fail_sources = list(unique_killers)
        if not pass_sources and bucket == 'fail':
            pass_sources = list(unique_killers)
        if not fail_sources and not pass_sources and bucket == 'mixed':
            half = len(unique_killers) // 2
            fail_sources = list(unique_killers[:half])
            pass_sources = list(unique_killers[half:])

        fail_count = len(fail_sources)
        pass_count = len(pass_sources)
        susp_value: Optional[float]
        if fail_count or pass_count:
            susp_value = mbfl_sbi(float(fail_count), float(pass_count))
        else:
            susp_value = None

        involved_tests = set(fail_sources) | set(pass_sources)
        if not involved_tests:
            involved_tests = killers_set
        baseline_hit = bool(involved_tests & failing_tests_set)
        no_kill_data = not unique_killers and not repair_tests_list and not regress_tests_list

        record = MutantRecord(
            label=mutant_label,
            method_display=method_display,
            mutation_kind=str(kind),
            mutation_desc=kind_txt,
            line_no=line_no,
            status_display=f"{status}{bucket_txt}",
            baseline_hit=baseline_hit,
            susp_value=susp_value,
            fail_count=fail_count,
            pass_count=pass_count,
            unique_killers=unique_killers,
            repair_tests=list(repair_tests_list),
            regress_tests=list(regress_tests_list),
            no_kill_data=no_kill_data,
            snippet=snippet,
        )
        records.append(record)

    if not records:
        print("\nMutant details")
        print("=" * len("Mutant details"))
        print("No mutant diagnostic entries to display.")
        return

    if show_table:
        headers = ["Mutant", "Method", "Mutation", "Status", "Baseline", "Susp", "Fail", "Pass", "Top killers"]
        rows: list[list[str]] = []
        for record in records:
            killers = record.unique_killers
            if killers:
                killers_summary = ", ".join(killers[:2])
                remaining = len(killers) - 2
                if remaining > 0:
                    killers_summary += f", +{remaining} more"
            else:
                killers_summary = "-"
            susp_display = f"{record.susp_value:.2f}" if isinstance(record.susp_value, float) else "-"
            rows.append([
                record.label,
                record.method_display,
                record.mutation_kind,
                record.status_display,
                "yes" if record.baseline_hit else "no",
                susp_display,
                str(record.fail_count),
                str(record.pass_count),
                killers_summary,
            ])
        widths = [len(header) for header in headers]
        for row in rows:
            for col_index, cell in enumerate(row):
                if len(cell) > widths[col_index]:
                    widths[col_index] = len(cell)
        border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

        def _format_row(row: list[str]) -> str:
            return "| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(row))) + " |"

        print("\nMutant summary table")
        print(border)
        print(_format_row(headers))
        print(border)
        for row in rows:
            print(_format_row(row))
        print(border)
        print("Susp = fail/(fail+pass). Baseline = yes if any baseline failing test killed the mutant. Top killers show up to two tests.")

    print("\nMutant details")
    print("=" * len("Mutant details"))
    for record in records:
        print(f"\n{record.label} — {record.method_display}")
        print(f"  Mutation: {record.mutation_kind} — {record.mutation_desc}")
        if record.snippet:
            print(f"  Source line [{record.line_no}]: {record.snippet}")
        print(f"  Status: {record.status_display}")
        print(f"  Baseline failing involved: {'yes' if record.baseline_hit else 'no'}")
        if isinstance(record.susp_value, float):
            print(f"  Suspiciousness: {record.susp_value:.2f} (fail={record.fail_count}, pass={record.pass_count})")

        def _print_test_list(label: str, items: list[str]) -> None:
            if not items:
                return
            print(f"  {label} ({len(items)}):")
            for test_id in items:
                print(f"    - {test_id}")

        _print_test_list("Killer tests", record.unique_killers)
        _print_test_list("Repair tests (fail bucket)", record.repair_tests)
        _print_test_list("Regress tests (pass bucket)", record.regress_tests)

        if record.no_kill_data:
            print("  Killer tests: none recorded (mutant survived or diagnostic data unavailable).")


def _print_mbfl_table(project_root: str, top_methods: int, top_tests: int) -> None:
    """Render an MBFL Element/Mutant vs Test table with per-element suspicious values."""
    import json, os

    diag_path = os.path.join(project_root, '.suspect.mutatest.json')
    try:
        with open(diag_path, 'r', encoding='utf-8') as f:
            diag = json.load(f)
    except Exception:
        print("[INFO] MBFL table unavailable (no diagnostics).")
        return

    mutatest = (diag or {}).get('mutatest', {}) or {}
    runs = mutatest.get('runs') or []
    if not runs:
        print("[INFO] MBFL table unavailable (no mutant runs).")
        return

    baseline = mutatest.get('baseline') or {}
    failing_tests = set(baseline.get('failing_nodeids') or [])

    matrix_metrics: dict[str, dict] = {}
    matrix_candidates = [os.path.join(project_root, 'matrix.json'), os.path.join(os.getcwd(), 'matrix.json')]
    for candidate in matrix_candidates:
        try:
            with open(candidate, 'r', encoding='utf-8') as mfile:
                data = json.load(mfile) or {}
            if data:
                matrix_metrics = data
                break
        except Exception:
            continue
    if not matrix_metrics:
        matrix_metrics = {}

    idx = MethodIndex()
    added_files: set[str] = set()
    methods: dict[str, dict] = {}
    test_status: dict[str, str] = {}
    status_priority = {'?': 0, 'P': 1, 'F': 2}

    def update_status(test_id: str, label: str) -> None:
        if not label:
            return
        current = test_status.get(test_id)
        if current is None or status_priority.get(label, 0) > status_priority.get(current, 0):
            test_status[test_id] = label

    def format_count_value(val: float) -> str:
        try:
            if abs(val - round(val)) < 1e-9:
                return str(int(round(val)))
            return f"{val:.2f}".rstrip('0').rstrip('.')
        except Exception:
            return str(val)

    for failing_test in failing_tests:
        update_status(failing_test, 'F')

    for entry in runs:
        if not isinstance(entry, dict):
            continue
        mut = entry.get('mutant') or {}
        file_path = mut.get('file')
        line_no = mut.get('line')
        kind = mut.get('kind')
        if not (isinstance(file_path, str) and isinstance(line_no, int)):
            continue
        rel_file = file_path.replace('\\', '/').lstrip('./')
        if rel_file not in added_files:
            abs_file = os.path.join(project_root, rel_file)
            try:
                with open(abs_file, 'r', encoding='utf-8') as src_f:
                    idx.add_file(rel_file, src_f.read())
                added_files.add(rel_file)
            except Exception:
                pass
        method_key = None
        for back in range(line_no, 0, -1):
            mk = idx.index.get((rel_file, back))
            if mk:
                method_key = mk
                break
        if not method_key:
            continue
        info = methods.setdefault(method_key, {
            'mutants': [],
            'fail_tests': set(),
            'pass_tests': set(),
            'raw_fail_mutants': set(),
            'raw_pass_mutants': set(),
        })
        killers_raw = entry.get('killers') or []
        bucket = entry.get('bucket')
        repair_tests = {str(t) for t in (entry.get('repair_tests') or [])}
        regress_tests = {str(t) for t in (entry.get('regress_tests') or [])}
        killers: set[str] = set()
        if repair_tests or regress_tests:
            killers.update(repair_tests)
            killers.update(regress_tests)
        else:
            for t in killers_raw:
                if isinstance(t, str):
                    killers.add(t)
                elif t is not None:
                    killers.add(str(t))
            if not killers and bucket == 'fail' and failing_tests:
                killers.update(failing_tests)
            if bucket == 'fail' and not repair_tests:
                repair_tests = set(killers)
            elif bucket == 'pass' and not regress_tests:
                regress_tests = set(killers)
        mut_id = entry.get('id')
        if mut_id is not None:
            mut_display = f"Mutant {mut_id}"
        else:
            if kind:
                mut_display = f"{rel_file}:{line_no}:{kind}"
            else:
                mut_display = f"{rel_file}:{line_no}"
        mutant_record = {
            'id': mut_id,
            'display': mut_display,
            'killers': sorted(killers),
            'bucket': bucket,
            'repair_tests': sorted(repair_tests),
            'regress_tests': sorted(regress_tests),
        }
        info['mutants'].append(mutant_record)
        if repair_tests:
            for test_id in repair_tests:
                info['fail_tests'].add(test_id)
                update_status(test_id, 'F')
        if regress_tests:
            for test_id in regress_tests:
                info['pass_tests'].add(test_id)
                update_status(test_id, 'P')
        if not repair_tests and not regress_tests:
            label = 'F' if bucket == 'fail' else ('P' if bucket == 'pass' else '?')
            for test_id in killers:
                if label == 'F':
                    info['fail_tests'].add(test_id)
                elif label == 'P':
                    info['pass_tests'].add(test_id)
                update_status(test_id, label)
        mut_fail_tests = set(repair_tests) if repair_tests else {tid for tid in killers if test_status.get(tid) == 'F'}
        mut_pass_tests = set(regress_tests) if regress_tests else {tid for tid in killers if test_status.get(tid) == 'P'}
        if not mut_fail_tests and not mut_pass_tests:
            if bucket == 'fail':
                mut_fail_tests = set(killers)
            elif bucket == 'pass':
                mut_pass_tests = set(killers)
        fail_kill_count = len(mut_fail_tests)
        pass_kill_count = len(mut_pass_tests)
        denom = fail_kill_count + pass_kill_count
        if denom:
            mut_susp_value = fail_kill_count / denom
            mut_susp_expr = f"{fail_kill_count}/({fail_kill_count}+{pass_kill_count})={mut_susp_value:.2f}"
        else:
            mut_susp_value = None
            mut_susp_expr = "0/(0+0)=0.00" if killers else ""
        mutant_record.update({
            'fail_kills': fail_kill_count,
            'pass_kills': pass_kill_count,
            'mut_susp_value': mut_susp_value,
            'mut_susp_expr': mut_susp_expr,
        })
        identifier = mut_id if mut_id is not None else mut_display
        if fail_kill_count > 0:
            info['raw_fail_mutants'].add(identifier)
        if pass_kill_count > 0:
            info['raw_pass_mutants'].add(identifier)
        if fail_kill_count == 0 and pass_kill_count == 0:
            if bucket == 'fail':
                info['raw_fail_mutants'].add(identifier)
            elif bucket == 'pass':
                info['raw_pass_mutants'].add(identifier)
            elif bucket == 'mixed':
                info['raw_fail_mutants'].add(identifier)
                info['raw_pass_mutants'].add(identifier)

    if not methods:
        print("[INFO] MBFL table unavailable (no method mapping).")
        return

    def _sbfl_fallback(metrics_row: dict[str, object]) -> Optional[tuple[str, float]]:
        """Pick a spectrum-based suspiciousness metric when MBFL data is absent."""
        if not isinstance(metrics_row, dict):
            return None
        candidates = [
            "ochiai",
            "tarantula",
            "jaccard",
            "sbi",
            "sbfl_sbi",
        ]
        for name in candidates:
            raw = metrics_row.get(name)
            if isinstance(raw, (int, float)):
                return name, float(raw)
        return None

    method_entries: list[tuple[str, dict]] = []
    for method_key, info in methods.items():
        if not info['mutants']:
            continue
        metrics_row = matrix_metrics.get(method_key) or {}
        fallback_pair = _sbfl_fallback(metrics_row)
        fallback_expr = None
        if fallback_pair:
            fallback_expr = f"SBFL {fallback_pair[0]}={fallback_pair[1]:.4f}"
        mkf = metrics_row.get('mkf')
        mkp = metrics_row.get('mkp')
        if isinstance(mkf, (int, float)):
            fail_count_val = float(mkf)
        else:
            fail_count_val = float(len(info['raw_fail_mutants']))
        if isinstance(mkp, (int, float)):
            pass_count_val = float(mkp)
        else:
            pass_count_val = float(len(info['raw_pass_mutants']))
        denom = fail_count_val + pass_count_val
        susp = (fail_count_val / denom) if denom else 0.0
        info['fail_count'] = fail_count_val
        info['pass_count'] = pass_count_val
        info['suspicious'] = susp
        sbfl_note: Optional[str] = None
        if denom:
            fail_disp = format_count_value(fail_count_val)
            pass_disp = format_count_value(pass_count_val)
            info['susp_summary'] = f"{fail_disp}/({fail_disp}+{pass_disp})={susp:.2f}"
        else:
            info['susp_summary'] = "0/(0+0)=0.00"
            if fallback_expr:
                sbfl_note = fallback_expr
                info['susp_summary'] += f" [{sbfl_note}]"
        info['sbfl_note'] = sbfl_note
        if fallback_expr:
            for mutant in info['mutants']:
                mut_expr = mutant.get('mut_susp_expr')
                if not mut_expr:
                    mutant['mut_susp_expr'] = fallback_expr
        info['display'] = _shorten_method(method_key, project_root)
        info['mutants'].sort(key=lambda m: (m['id'] is None, m['id'], m['display']))
        method_entries.append((method_key, info))

    if not method_entries:
        print("[INFO] MBFL table: no methods to display.")
        return

    method_entries.sort(
        key=lambda item: (
            -item[1]['suspicious'],
            -(item[1]['fail_count'] + item[1]['pass_count']),
            item[0],
        )
    )

    if top_methods > 0:
        method_entries = method_entries[:top_methods]

    if not method_entries:
        print("[INFO] MBFL table: no methods to display.")
        return

    test_counts: dict[str, int] = {}
    must_fail_tests: set[str] = set(failing_tests)
    must_pass_tests: set[str] = set()
    for method_key, info in method_entries:
        must_fail_tests.update(info['fail_tests'])
        must_pass_tests.update(info['pass_tests'])
        for mutant in info['mutants']:
            for test_id in mutant['killers']:
                test_counts[test_id] = test_counts.get(test_id, 0) + 1

    if not test_counts:
        print("[INFO] MBFL table: no killer tests to display.")
        return

    ranked_tests = sorted(
        test_counts.keys(),
        key=lambda tid: (0 if test_status.get(tid) == 'F' else 1, -test_counts[tid], tid),
    )
    if top_tests > 0:
        ranked_tests = ranked_tests[:top_tests]
    test_ids = ranked_tests
    # Ensure failing tests are always represented (baseline failures first)
    for tid in sorted(failing_tests):
        if tid not in test_ids:
            test_ids.append(tid)
    for tid in sorted(must_fail_tests):
        if tid not in test_ids:
            test_ids.append(tid)
    # Append pass tests if room (or limit not enforced)
    for tid in sorted(must_pass_tests):
        if tid not in test_ids:
            test_ids.append(tid)
    if not test_ids:
        print("[INFO] MBFL table: no tests to display.")
        return

    omitted_tests: list[str] = []
    if top_tests > 0 and len(test_ids) > top_tests:
        order_map = {tid: idx for idx, tid in enumerate(test_ids)}
        priority_tuples = []
        for tid in test_ids:
            status = test_status.get(tid)
            # Prefer failing tests, then preserve original order
            priority = 0 if status == 'F' else 1
            priority_tuples.append((priority, order_map.get(tid, 0), tid))
        priority_tuples.sort()
        trimmed: list[str] = []
        for _prio, _order, tid in priority_tuples:
            if len(trimmed) < top_tests:
                trimmed.append(tid)
            else:
                omitted_tests.append(tid)
        test_ids = trimmed

    labels = [f"T{i+1}" for i in range(len(test_ids))]
    status_labels = []
    for tid, base_label in zip(test_ids, labels):
        status = test_status.get(tid)
        if status == 'F':
            status_labels.append(f"{base_label}[F]")
        elif status == 'P':
            status_labels.append(f"{base_label}[P]")
        elif status == '?':
            status_labels.append(f"{base_label}[?]")
        else:
            status_labels.append(base_label)

    element_col_w = max(10, min(45, max(len(info['display']) for _method, info in method_entries)))
    mutant_col_w = max(
        10,
        min(35, max(len(mutant['display']) for _method, info in method_entries for mutant in info['mutants'])),
    )
    cell_w = max(3, max(len(lbl) for lbl in status_labels))
    susp_expr_lengths: list[int] = []
    for _method, info in method_entries:
        for mutant in info['mutants']:
            expr = mutant.get('mut_susp_expr') or ""
            if expr:
                susp_expr_lengths.append(len(expr))
        sbfl_note = info.get('sbfl_note')
        if sbfl_note:
            susp_expr_lengths.append(len(sbfl_note))
    if not susp_expr_lengths:
        susp_expr_lengths.append(len("0/(0+0)=0.00"))
    susp_col_w = max(16, min(32, max(susp_expr_lengths)))

    def border() -> str:
        return (
            "+"
            + ("-" * (element_col_w + 2))
            + "+"
            + ("-" * (mutant_col_w + 2))
            + "+"
            + "+".join(["-" * (cell_w + 2) for _ in status_labels])
            + "+"
            + ("-" * (susp_col_w + 2))
            + "+"
        )

    print("\nMBFL Mutant/Test Table (○ = output change)")
    print(border())
    header = (
        f"| {'Element'.ljust(element_col_w)} | {'Mutant'.ljust(mutant_col_w)} | "
        + " | ".join(lbl.center(cell_w) for lbl in status_labels)
        + " | "
        + "Susp".center(susp_col_w)
        + " |"
    )
    print(header)
    print(border())

    for method_idx, (_method_key, info) in enumerate(method_entries):
        method_label = _truncate(info['display'], element_col_w)
        for idx, mutant in enumerate(info['mutants']):
            method_cell = method_label if idx == 0 else ''.ljust(element_col_w)
            mut_susp_expr = mutant.get('mut_susp_expr') or ""
            if mut_susp_expr:
                susp_cell = _truncate(mut_susp_expr, susp_col_w)
            else:
                susp_cell = ""
            susp_cell = susp_cell.ljust(susp_col_w)
            mutant_label = _truncate(mutant['display'], mutant_col_w)
            killers = mutant['killers']
            cells = [('○' if tid in killers else '').center(cell_w) for tid in test_ids]
            print(
                f"| {method_cell.ljust(element_col_w)} | {mutant_label.ljust(mutant_col_w)} | "
                + " | ".join(cells)
                + f" | {susp_cell} |"
            )
        if method_idx < len(method_entries) - 1:
            print(border())
    print(border())

    status_text = {
        'F': 'baseline failing test',
        'P': 'baseline passing test',
        '?': 'test status unavailable',
    }
    print("Legend: ○ = killer (test output changed). Susp = fail/(fail+pass) per mutant using failing vs passing killer tests (falls back to bucket classification when unavailable). Method-level aggregates appear in the summary below.")
    for label, test_id in zip(status_labels, test_ids):
        status = test_status.get(test_id, '?')
        print(f"  {label} = {test_id} ({status_text.get(status, 'test status unavailable')})")
    if omitted_tests:
        print(f"  … plus {len(omitted_tests)} more test(s) omitted. Increase --mbfl-table-top-tests to include them.")
        preview = ", ".join(omitted_tests[:3])
        if preview:
            suffix = "…" if len(omitted_tests) > 3 else ""
            print(f"    omitted examples: {preview}{suffix}")

    # Detailed method/test summary to expose additional context
    print("\nMBFL Method/Test Summary:")
    total_mutants = 0
    for _method_key, info in method_entries:
        total_mutants += len(info['mutants'])
    print(f"  Methods displayed: {len(method_entries)}")
    print(f"  Mutants displayed: {total_mutants}")
    for _method_key, info in method_entries:
        fail_list = sorted(info['fail_tests'])
        pass_list = sorted(info['pass_tests'])
        print(f"  - {info['display']}")
        print(f"      Suspiciousness: {info['susp_summary']}")
        print(f"      Mutants ({len(info['mutants'])}): " + ", ".join(m['display'] for m in info['mutants']))
        if fail_list:
            print(f"      Failing tests ({len(fail_list)}): " + ", ".join(fail_list))
        else:
            print("      Failing tests (0): -")
        if pass_list:
            print(f"      Passing tests ({len(pass_list)}): " + ", ".join(pass_list))
        else:
            print("      Passing tests (0): -")

    # Surface elements that lack detection signal so users can expand coverage
    survivor_only: list[tuple[str, int]] = []
    try:
        for method_key, metrics in (matrix_metrics or {}).items():
            detected = metrics.get('mutants_detected', 0)
            survived = metrics.get('mutants_survived', 0)
            if isinstance(detected, (int, float)) and isinstance(survived, (int, float)):
                if float(detected) == 0.0 and float(survived) > 0.0:
                    survivor_only.append((method_key, int(round(float(survived)))))
    except Exception:
        survivor_only = []

    no_mutant_methods: list[str] = []
    try:
        full_idx = MethodIndex()
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in {'.git', '.hg', '.svn', '__pycache__', '.pytest_cache', '.mypy_cache', '.venv', 'venv', 'env', 'build', 'dist'}]
            rel_root = os.path.relpath(root, project_root)
            if rel_root == '.':
                rel_root = ''
            if 'tests' in dirs:
                dirs.remove('tests')
            for fn in files:
                if not fn.endswith('.py'):
                    continue
                if fn.startswith('test_') or fn.endswith('_test.py'):
                    continue
                rel_path = os.path.join(rel_root, fn).strip('./')
                if not rel_path:
                    rel_path = fn
                rel_posix = rel_path.replace('\\', '/').lstrip('./')
                abs_path = os.path.join(project_root, rel_posix)
                try:
                    with open(abs_path, 'r', encoding='utf-8') as src_f:
                        full_idx.add_file(rel_posix, src_f.read())
                except Exception:
                    continue
        all_methods = {mk for mk in full_idx.index.values() if isinstance(mk, str)}
        matrix_methods = set((matrix_metrics or {}).keys())
        no_mutant_methods = sorted(all_methods - matrix_methods)
    except Exception:
        no_mutant_methods = []

    print("\nMBFL Coverage Gaps:")
    if survivor_only:
        print("  Elements with mutants that all survived (mutants_detected=0):")
        for method_key, survivors in sorted(survivor_only):
            print(f"    - {method_key} (survivors={survivors})")
    else:
        print("  Elements with mutants that all survived (mutants_detected=0): none")
    if no_mutant_methods:
        print("  Elements with no mutants generated:")
        for method_key in no_mutant_methods:
            print(f"    - {method_key}")
    else:
        print("  Elements with no mutants generated: none")


def _print_element_mutant_matrix(project_root: str, top_methods: int, top_tests: int, all_tests: bool = False) -> None:
    """Grouped Element/Mutant kill matrix.

    Rows are mutants grouped under their parent method (Element).
    Susp (instead of prior "Score") per mutant mirrors the per‑mutant matrix semantics:
      - 1.00 if the mutant produced at least one failing test (bucket == 'fail')
      - 0.00 if the mutant only produced passing tests (bucket == 'pass')
      - blank if the mutant survived / timeout / unknown bucket
    Methods ordered by an mbfl_sbi approximation fail/(fail+pass) (fall back to total kills) and limited by top_methods if >0.
    Tests chosen similar to kill matrix logic: union of killers for selected methods' mutants (or all mutants if all_tests), optionally limited by top_tests unless all_tests.
    """
    import json, os
    diag_path = os.path.join(project_root, '.suspect.mutatest.json')
    try:
        with open(diag_path, 'r', encoding='utf-8') as f:
            diag = json.load(f)
    except Exception:
        print("[INFO] Element/Mutant matrix unavailable (no diagnostics).")
        return
    runs = (diag or {}).get('mutatest', {}).get('runs', []) or []
    if not runs:
        print("[INFO] Element/Mutant matrix unavailable (no mutant runs).")
        return
    from .mapping import MethodIndex as _MI
    mi = _MI()
    added_files = set()
    for r in runs:
        mut = r.get('mutant') if isinstance(r, dict) else None
        if not mut:
            continue
        f = mut.get('file')
        if not isinstance(f, str):
            continue
        rel_file = f.replace('\\', '/').lstrip('./')
        if rel_file in added_files:
            continue
        abs_file = os.path.join(project_root, rel_file)
        try:
            with open(abs_file, 'r', encoding='utf-8') as sf:
                mi.add_file(rel_file, sf.read())
            added_files.add(rel_file)
        except Exception:
            continue
    mutants_by_method: dict[str, list[dict]] = {}
    all_killers_counts: dict[str, int] = {}
    per_method_fail: dict[str, int] = {}
    per_method_pass: dict[str, int] = {}
    for r in runs:
        if not isinstance(r, dict):
            continue
        mut = r.get('mutant') or {}
        file = mut.get('file'); line = mut.get('line'); kind = mut.get('kind')
        if not (file and isinstance(line, int)):
            continue
        rel_file = file.replace('\\','/').lstrip('./')
        method = None
        for b in range(line, 0, -1):
            mk = mi.index.get((rel_file, b))
            if mk:
                method = mk
                break
        if not method:
            continue
        killers = r.get('killers') or []
        bucket = r.get('bucket')
        mid = r.get('id')
        mutant_display = f"Mutant {mid}" if mid is not None else f"{rel_file}:{line}:{kind}"
        mutants_by_method.setdefault(method, []).append({
            'id': mid,
            'display': mutant_display,
            'killers': killers if isinstance(killers, list) else [],
            'bucket': bucket,
        })
        for t in (killers if isinstance(killers, list) else []):
            all_killers_counts[t] = all_killers_counts.get(t, 0) + 1
        if r.get('killed'):
            if bucket == 'fail':
                per_method_fail[method] = per_method_fail.get(method, 0) + 1
            elif bucket == 'pass':
                per_method_pass[method] = per_method_pass.get(method, 0) + 1
    if not mutants_by_method:
        print("[INFO] Element/Mutant matrix unavailable (no method mapping).")
        return
    method_order = []
    for m in mutants_by_method.keys():
        f = per_method_fail.get(m, 0); p = per_method_pass.get(m, 0)
        denom = f + p
        s = (f / denom) if denom else 0.0
        method_order.append((m, s, f + p))
    method_order.sort(key=lambda x: (x[1], x[2]), reverse=True)
    if top_methods > 0:
        method_order = method_order[:top_methods]
    selected_methods = [m for m,_s,_c in method_order]
    if all_tests:
        test_counts = all_killers_counts.copy()
    else:
        test_counts = {}
        for m in selected_methods:
            for mut in mutants_by_method.get(m, []):
                for t in mut['killers']:
                    test_counts[t] = test_counts.get(t, 0) + 1
    ranked_tests = sorted(test_counts.items(), key=lambda x: x[1], reverse=True)
    if (not all_tests) and top_tests > 0:
        ranked_tests = ranked_tests[:top_tests]
    test_ids = [t for t,_c in ranked_tests]
    if all_tests:
        baseline = (diag or {}).get('mutatest', {}).get('baseline', {}) or {}
        for ft in (baseline.get('failing_nodeids') or []):
            if ft not in test_ids:
                test_ids.append(ft)
    if not test_ids:
        print("[INFO] Element/Mutant matrix: no tests to display.")
        return
    col_labels = [f"T{i+1}" for i in range(len(test_ids))]
    element_col_w = max(8, min(40, max(len(m) for m in selected_methods)))
    mutant_col_w = max(6, 12)
    cell_w = max(2, 4)
    susp_col_w = 6
    def border():
        return (
            "+" + ("-" * (element_col_w + 2)) + "+" + ("-" * (mutant_col_w + 2)) + "+" + "+".join(["-" * (cell_w + 2) for _ in col_labels]) + "+" + ("-" * (susp_col_w + 2)) + "+"
        )
    print("\nElement/Mutant Kill Matrix (X = killed, ✓ = no kill)")
    print(border())
    header = (
        f"| {'Element'.ljust(element_col_w)} | {'Mutant'.ljust(mutant_col_w)} | "
        + " | ".join(lbl.center(cell_w) for lbl in col_labels)
        + " | " + "Susp".center(susp_col_w) + " |"
    )
    print(header)
    print(border())
    first_method = True
    for m, _s, _c in method_order:
        if not first_method:
            print(border())
        first_method = False
        mut_list = mutants_by_method.get(m, [])
        mut_list.sort(key=lambda x: (x.get('id') is None, x.get('id')))
        for idx, mut in enumerate(mut_list):
            killers = set(mut.get('killers') or [])
            row_cells = []
            for tid in test_ids:
                mark = 'X' if tid in killers else '✓'
                row_cells.append(mark.center(cell_w))
            bucket = mut.get('bucket')
            if bucket == 'fail':
                susp_val = 1.0
            elif bucket == 'pass':
                susp_val = 0.0
            else:
                susp_val = None
            susp_txt = (f"{susp_val:.2f}" if isinstance(susp_val, float) else "").rjust(susp_col_w)
            elem_txt = m.ljust(element_col_w) if idx == 0 else ''.ljust(element_col_w)
            mut_txt = mut['display'].ljust(mutant_col_w)
            print(f"| {elem_txt} | {mut_txt} | " + " | ".join(row_cells) + f" | {susp_txt} |")
    print(border())
    print("Legend: X = killed (mutation detected), ✓ = survived (not detected)")
    print("Susp = 1.00 (mutant caused a failing test), 0.00 (mutant only caused passing tests), blank (survived/timeout)")


# Add label 0 and 1 to different method
import re
import os

def parse_diff(project_root, diff_file="diff_log.txt"):

    diff_path = os.path.join(project_root, diff_file)

    print(f"[INFO] Parsing diff file: {diff_path}")

    if not os.path.exists(diff_path):
        print(f"[WARN] Diff file not found: {diff_path}. Returning empty diff set.")
        return set()

    changed = set()

    orig_line = 0
    new_line = 0
    last_reported_method = None

    current_file = None
    methods = []

    with open(diff_path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip("\n")

            # --- Diff headers ---
            if line.startswith('--- '):
                current_file = line[4:].strip()
                current_file = re.split(r'\s+', current_file)[0]  # remove timestamp
                # Read buggy file for method & class info
                with open(current_file, encoding='utf-8') as bf:
                    file_lines = bf.readlines()

                # Track classes and methods: (line_number, class_name, method_name)
                methods = []
                current_class = None
                for i, file_line in enumerate(file_lines):
                    class_match = re.match(r'\s*class\s+(\w+)\s*[\(:]?', file_line)
                    if class_match:
                        current_class = class_match.group(1)
                    method_match = re.match(r'\s*def\s+(\w+)\s*\(', file_line)
                    if method_match:
                        methods.append((i + 1, current_class, method_match.group(1)))
                continue

            if line.startswith('+++ '):
                continue

            # --- Hunk start ---
            if line.startswith('@@'):
                hunk_match = re.match(r'^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
                if hunk_match:
                    orig_line = int(hunk_match.group(1))
                    new_line = int(hunk_match.group(3))
                continue

            # Ignore empty changes
            if line.startswith('-') and line[1:].strip() == '':
                orig_line += 1
                continue
            if line.startswith('+') and line[1:].strip() == '':
                new_line += 1
                continue

            # --- Changed lines ---
            if line.startswith('-'):
                # Find containing method
                method_name = None
                method_line = None
                class_name = None
                for ln, cls, name in reversed(methods):
                    if ln <= orig_line:
                        method_name = name
                        method_line = ln
                        class_name = cls
                        break

                # Filter repetitive method outputs
                if method_name != last_reported_method:
                    rel_file = os.path.relpath(current_file, project_root)
                    changed.add((rel_file, method_line))
                    if class_name:
                        print(f"{current_file}:{class_name}.{method_name}:{method_line}")
                    else:
                        print(f"{current_file}:{method_name}:{method_line}")
                    last_reported_method = method_name

                orig_line += 1

            elif line.startswith('+'):
                new_line += 1

            else:
                orig_line += 1
                new_line += 1

    return changed





if __name__ == "__main__":
    main()
