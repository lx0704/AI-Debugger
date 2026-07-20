"""
SBFL via coverage.py per-test contexts
--------------------------------------

High-level workflow used here:
1) Run tests under coverage.py with dynamic per-test contexts enabled
     (dynamic_context = test_function). This causes coverage to label executed
     lines with the pytest nodeid of the test function that executed them.

2) Export coverage to JSON with --show-contexts so the JSON contains, per file:
            {
                "files": {
                    "src.py": {
                        "contexts": {
                            "tests/test_x.py::test_foo[case]": [line1, line2, ...],
                            ...
                        },
                        ...
                    }
                }
            }

3) Run pytest again (fast, no coverage) to produce JUnit XML with pass/fail
     outcomes. This gives us Nf, Np, and the list of failing vs passing test
     function names (we normalize to function tokens, e.g., test_foo).

4) Map executed lines to methods by building an AST-based MethodIndex for each
     file. For every JSON context (test nodeid) and its lines, we look up the
     method key for each line, then tally two sets per method:
            - executed_by_fail[method]: set of failing test contexts that hit it
            - executed_by_pass[method]: set of passing test contexts that hit it

     From these sets we derive ef and ep (counts of distinct failing/passing tests
     that executed the method).

5) Compute SBFL metrics per method using ef/ep and totals Nf/Np.

Fallbacks: if JSON contexts are not present, we fall back to coverage's
contexts_by_lineno API; if that also isn't available, we use executed_lines
from JSON; and finally we use plain executed lines (treated as passing-only).
"""

import os
import json
import subprocess
import pathlib
import xml.etree.ElementTree as ET
import sys

from .base import MetricAdapter
from ..formulas import sbfl as F
from ..mapping import MethodIndex
from ..plugins import register_adapter

try:
    from coverage import Coverage  # type: ignore
except Exception:  # pragma: no cover
    Coverage = None  # type: ignore


class CoverageSBFLAdapter(MetricAdapter):
    name = "coverage_sbfl"

    def collect(self, ctx) -> dict[str, dict[str, float]]:
        project = pathlib.Path(ctx["project_root"]).resolve()
        test_cmd = ctx["test_cmd"]  # e.g. "pytest -q"
        py = sys.executable

        # 1) Run coverage with pytest (per-test contexts via local rcfile)
        #    We write a temporary .suspect.coveragerc that enables per-test contexts
        #    and relative file handling for stable keys.
        subprocess.run(f"{py} -m coverage erase", shell=True, check=False, cwd=str(project))
        rc_path = project / ".suspect.coveragerc"
        try:
            rc_path.write_text(
                """[run]
branch = True
dynamic_context = test_function
relative_files = True
source = .
""",
                encoding="utf-8",
            )
        except Exception:
            pass

        # Run tests under coverage with that rcfile. test_cmd is expected to be
        # a module invocation like "pytest -q"; we use "-m {test_cmd}" so the
        # user's test runner runs as a module.
        subprocess.run(
            f"{py} -m coverage run --rcfile {rc_path} -m {test_cmd} .",
            shell=True,
            check=False,
            cwd=str(project),
        )
        # Export coverage JSON with contexts, which we prefer for true per-test mapping.
        subprocess.run(
            f"{py} -m coverage json --show-contexts -o .suspect.coverage.json",
            shell=True,
            check=False,
            cwd=str(project),
        )
        # Run pytest again without coverage to get JUnit XML with outcomes.
        subprocess.run(
            f"{py} -m {test_cmd} --junitxml=.suspect.pytest.xml .",
            shell=True,
            check=False,
            cwd=str(project),
        )

        # 3) Parse outcomes
        Nf, Np, failing_tests, passing_tests = _parse_pytest_junit(str(project / ".suspect.pytest.xml"))

        # 4) Collect per-line contexts and file list
        # We prefer JSON contexts (step 4b below), but we also gather coverage data
        # contexts_by_lineno here as a fallback for environments/versions where JSON
        # lacks contexts.
        files_contexts: dict[str, dict[int, set[str]]] = {}
        files_list: list[tuple[str, pathlib.Path]] = []  # (key used by coverage, absolute path)
        if Coverage is not None:
            try:
                cov = Coverage(data_file=str(project / ".coverage"))
                cov.load()
                data = cov.get_data()
                for cov_key in data.measured_files():
                    if not cov_key:
                        continue
                    abs_path = pathlib.Path(cov_key)
                    if not abs_path.is_absolute():
                        abs_path = (project / abs_path).resolve()
                    else:
                        abs_path = abs_path.resolve()
                    if not abs_path.exists():
                        continue
                    try:
                        if project not in abs_path.parents and abs_path != project:
                            continue
                    except Exception:
                        continue
                    files_list.append((cov_key, abs_path))
                    try:
                        # coverage>=7: contexts_by_lineno gives {lineno: set(contexts)}
                        by_line = data.contexts_by_lineno(cov_key)  # type: ignore[attr-defined]
                    except Exception:
                        try:
                            lines = data.lines(cov_key) or []
                        except Exception:
                            lines = []
                        by_line = {ln: set() for ln in lines}
                    files_contexts[cov_key] = {ln: set(v) for ln, v in (by_line or {}).items()}
            except Exception:
                pass

        # JSON fallback for file list and executed_lines
        json_files: dict[str, dict] = {}
        try:
            data = json.loads((project / ".suspect.coverage.json").read_text())
            json_files = data.get("files", {})
            # Ensure any JSON-only files are in files_list
            existing_keys = {k for k, _ in files_list}
            for k in json_files.keys():
                if k in existing_keys:
                    continue
                abs_path = pathlib.Path(k)
                if not abs_path.is_absolute():
                    abs_path = (project / abs_path).resolve()
                if abs_path.exists():
                    files_list.append((k, abs_path))
        except Exception:
            pass

        # 4b) Prefer TRUE per-test mapping using JSON contexts (if present)
        # When coverage JSON includes "contexts" for files, we can do a precise
        # mapping from failing/passing test cases to the methods they executed.
        touched: dict[str, tuple[int, int]] = {}
        try:
            has_ctx = any(isinstance(info, dict) and info.get("contexts") for info in json_files.values())
        except Exception:
            has_ctx = False
        if json_files and has_ctx:
            # Build method index from JSON file list, skipping tests
            idx_json = MethodIndex()
            for filename in json_files.keys():
                if _is_test_file(filename):
                    continue
                try:
                    ap = str(pathlib.Path(filename) if os.path.isabs(filename) else (project / filename))
                    if not os.path.exists(ap):
                        continue
                    src = open(ap, "r", encoding="utf-8").read()
                    idx_json.add_file(filename, src)
                except Exception:
                    continue

            fail_set = { _normalize_test_name(n) for n in failing_tests }
            pass_set = { _normalize_test_name(n) for n in passing_tests }

            executed_by_fail: dict[str, set[str]] = {}
            executed_by_pass: dict[str, set[str]] = {}
            for filename, finfo in json_files.items():
                if _is_test_file(filename):
                    continue
                contexts = finfo.get("contexts", {}) or {}
                if not isinstance(contexts, dict):
                    continue
                for test_ctx, lines in contexts.items():
                    if not isinstance(lines, (list, tuple)):
                        continue
                    is_fail = _ctx_matches_any(str(test_ctx), fail_set)
                    is_pass = _ctx_matches_any(str(test_ctx), pass_set)
                    if not (is_fail or is_pass):
                        continue
                    for ln in lines:
                        try:
                            ln_i = int(ln)
                        except Exception:
                            continue
                        mkey = idx_json.index.get((filename, ln_i))
                        if not mkey:
                            continue
                        if is_fail:
                            executed_by_fail.setdefault(mkey, set()).add(str(test_ctx))
                        if is_pass:
                            executed_by_pass.setdefault(mkey, set()).add(str(test_ctx))

            # Build touched from executed_by_* maps
            for mkey in set(list(executed_by_fail.keys()) + list(executed_by_pass.keys())):
                ef = len(executed_by_fail.get(mkey, set()))
                ep = len(executed_by_pass.get(mkey, set()))
                touched[mkey] = (ef, ep)

        # 5) Build method index using the same keys as coverage
        idx = MethodIndex()
        for key, abs_path in files_list:
            try:
                src = abs_path.read_text(encoding="utf-8")
                idx.add_file(key, src)
            except Exception:
                continue

        # 6) Per-test mapping using coverage data contexts_by_lineno (fallback if JSON contexts missing)
        # If JSON contexts are unavailable, use coverage's in-memory data API,
        # which for coverage>=7 can provide contexts_by_lineno.
        if not touched:
            # Build method index using the same keys as coverage data
            idx = MethodIndex()
            for key, abs_path in files_list:
                try:
                    src = abs_path.read_text(encoding="utf-8")
                    idx.add_file(key, src)
                except Exception:
                    continue

            method_contexts: dict[str, set[str]] = {}
            for key, by_line in files_contexts.items():
                for ln, ctxs in by_line.items():
                    mk = idx.index.get((key, ln))
                    if not mk:
                        continue
                    method_contexts.setdefault(mk, set()).update(ctxs or set())

            fail_names = { _normalize_test_name(n) for n in failing_tests }
            pass_names = { _normalize_test_name(n) for n in passing_tests }

            if method_contexts:
                for method, ctxset in method_contexts.items():
                    ef_set, ep_set = set(), set()
                    for c in ctxset:
                        cn = _normalize_context(c)
                        if any(fn in cn for fn in fail_names):
                            ef_set.add(cn)
                        if any(pn in cn for pn in pass_names):
                            ep_set.add(cn)
                    touched[method] = (len(ef_set), len(ep_set))

        if not touched:
            # Fallback: use executed_lines from JSON if no contexts available
            for key, finfo in json_files.items():
                for ln in finfo.get("executed_lines", []) or []:
                    mk = idx.index.get((key, ln))
                    if not mk:
                        continue
                    touched[mk] = (Nf, Np)

        # If still nothing, fallback to plain coverage lines as passing-only
        if not touched and Coverage is not None:
            try:
                cov2 = Coverage(data_file=str(project / ".coverage"))
                cov2.load()
                data2 = cov2.get_data()
                for key, _abs in files_list:
                    lines = data2.lines(key) or []
                    for ln in lines:
                        mk = idx.index.get((key, ln))
                        if not mk:
                            continue
                        touched[mk] = (0, Np)
            except Exception:
                pass

        # 7) Compute metrics
        # ef = number of distinct failing tests that executed the method
        # ep = number of distinct passing tests that executed the method
        # Nf = total number of failing tests; Np = total number of passing tests
        # We compute Ochiai, Tarantula, Jaccard, and SBI via the formulas module.
        out: dict[str, dict[str, float]] = {}
        for method, (ef, ep) in touched.items():
            out[method] = {
                "sbfl_ochiai": F.ochiai(ef, ep, Nf, Np),
                "sbfl_tarantula": F.tarantula(ef, ep, Nf, Np),
                "sbfl_jaccard": F.jaccard(ef, ep, Nf, Np),
                "sbfl_sbi": F.sbi(ef, ep, Nf, Np),
                "sbfl_dstar": F.dstar(ef, ep, Nf, Np),
                "sbfl_op2": F.op2(ef, ep, Nf, Np),
                "sbfl_barinel": F.barinel(ef, ep, Nf, Np),
                "sbfl_naish2": F.naish2(ef, ep, Nf, Np),
            }

        # Ensure all methods from indexed files are present, even if untouched by tests.
        # This lets the console list every method (zeros for ef/ep and metrics), useful
        # when you want a complete method inventory.
        try:
            all_methods = set(idx.index.values())
        except Exception:
            all_methods = set()

        # Also index all project python files (excluding tests and common vendor/hidden dirs)
        try:
            idx_all = MethodIndex()
            skip_dirs = {".venv", "venv", "env", ".git", "__pycache__", "build", "dist"}
            for root, dirs, files in os.walk(str(project)):
                # prune skip dirs in-place
                dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    ap = pathlib.Path(root) / fn
                    rel = ap.relative_to(project).as_posix()
                    if _is_test_file(rel):
                        continue
                    try:
                        src = ap.read_text(encoding="utf-8")
                        idx_all.add_file(rel, src)
                    except Exception:
                        continue
            all_methods |= set(idx_all.index.values())
        except Exception:
            pass
        for mk in all_methods:
            if mk not in out:
                out[mk] = {
                    "sbfl_ochiai": F.ochiai(0, 0, Nf, Np),
                    "sbfl_tarantula": F.tarantula(0, 0, Nf, Np),
                    "sbfl_jaccard": F.jaccard(0, 0, Nf, Np),
                    "sbfl_sbi": F.sbi(0, 0, Nf, Np),
                    "sbfl_dstar": F.dstar(0, 0, Nf, Np),
                    "sbfl_op2": F.op2(0, 0, Nf, Np),
                    "sbfl_barinel": F.barinel(0, 0, Nf, Np),
                    "sbfl_naish2": F.naish2(0, 0, Nf, Np),
                }

        return out


# Register this adapter in the global registry
try:
    register_adapter("sbfl", CoverageSBFLAdapter)
except Exception:
    pass


# --- Helper: Parse JUnit XML for test outcomes ---
def _parse_pytest_junit(xml_path):
    """
    Parse the JUnit XML produced by pytest to obtain test outcomes.
    Returns a tuple of:
        - Nf: number of failing tests
        - Np: number of passing tests
        - failing_tests: list of failing test function names (pytest records name attribute)
        - passing_tests: list of passing test function names
    """
    try:
        tree = ET.parse(xml_path)
    except Exception:
        return 0, 0, [], []
    root = tree.getroot()
    failing_tests = []
    passing_tests = []
    # Pytest uses <testcase> elements, failures/errors are children
    for testcase in root.iter("testcase"):
        name = testcase.attrib.get("name")
        # If testcase has <failure> or <error> child, it's a fail
        if testcase.find("failure") is not None or testcase.find("error") is not None:
            failing_tests.append(name)
        else:
            passing_tests.append(name)
    Nf = len(failing_tests)
    Np = len(passing_tests)
    return Nf, Np, failing_tests, passing_tests


def _normalize_test_name(name: str) -> str:
    """Normalize a pytest testcase name to a function token.

    Pytest may include parameterization in names (e.g., test_foo[param]). For
    matching, we only keep the base function token before "[".
    """
    return str(name).split("[", 1)[0]


def _normalize_context(ctx: str) -> str:
    """Pass-through normalization for coverage contexts.

    Coverage contexts for test_function often look like "test:module.py::test_name"
    or the plain pytest nodeid. We keep them as strings for matching.
    """
    return str(ctx)


def _is_test_file(path: str) -> bool:
    """Return True if path looks like a test module.

    We exclude such files from the set of target program methods.
    """
    p = str(path).replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    return "/tests/" in p  or p.startswith("tests/") or name.startswith("test_") or p.endswith("_test.py")


def _ctx_matches_any(ctx: str, names: set[str]) -> bool:
    """Return True if a coverage context string matches any test name.

    Coverage contexts typically include the pytest nodeid. We extract the
    function token after '::' and strip any '[param]' suffix, then check for
    membership. As an extra safeguard, we also allow suffix matches against
    the full context string.
    """
    ctx_s = str(ctx)
    token = ctx_s
    if "::" in ctx_s:
        token = ctx_s.split("::", 1)[1]
    token = token.split("[", 1)[0]
    return token in names or any(ctx_s.endswith(n) for n in names)
