"""Complexity adapter using radon (cyclomatic, MI, Halstead)."""
from __future__ import annotations

import ast
import fnmatch
import os
import pathlib
from typing import Any, Dict, cast

from .base import MetricAdapter
from ..mapping import MethodIndex
from ..plugins import register_adapter

try:  # pragma: no cover - import guard
    from radon.complexity import cc_visit, cc_rank
    from radon.metrics import mi_visit, halstead_visitor_report
    from radon.visitors import HalsteadVisitor
except Exception:  # pragma: no cover
    cc_visit = None  # type: ignore
    cc_rank = None  # type: ignore
    mi_visit = None  # type: ignore
    halstead_visitor_report = None  # type: ignore
    HalsteadVisitor = None  # type: ignore


class ComplexityAdapter(MetricAdapter):
    """Compute per-method cyclomatic complexity via radon."""

    name = "complexity"

    def collect(self, ctx: dict) -> Dict[str, Dict[str, float]]:  # noqa: C901 keep linear for clarity
        if cc_visit is None:  # pragma: no cover - radon missing
            raise RuntimeError("radon is required for complexity metrics")

        project = pathlib.Path(ctx["project_root"]).resolve()
        include = ctx.get("complexity_include") or []
        exclude = ctx.get("complexity_exclude") or []
        sample_only = bool(ctx.get("sample_project_only"))
        if sample_only:
            include = ["rich_sample_project/**"]

        skip_dirs = {".git", "__pycache__", ".venv", "venv", "env", "build", "dist"}
        index = MethodIndex()
        metrics: Dict[str, Dict[str, float]] = {}

        def _include(rel: str, filename: str) -> bool:
            if include:
                if not any(
                    fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(filename, pat)
                    for pat in include
                ):
                    return False
            if exclude and any(
                fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(filename, pat)
                for pat in exclude
            ):
                return False
            return True

        for root, dirs, files in os.walk(str(project)):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
            for fn in files:
                if not fn.endswith('.py'):
                    continue
                rel_path = pathlib.Path(root).joinpath(fn).relative_to(project).as_posix()
                is_test = (
                    rel_path.startswith('tests/')
                    or '/tests/' in rel_path
                    or fn.startswith('test_')
                    or rel_path.endswith('_test.py')
                )
                if is_test:
                    if sample_only and rel_path.startswith('rich_sample_project/'):
                        pass
                    else:
                        continue
                if not _include(rel_path, fn):
                    continue
                abs_path = project / rel_path
                try:
                    source = abs_path.read_text(encoding='utf-8')
                except Exception:
                    continue
                try:
                    tree = ast.parse(source)
                except Exception:
                    continue
                try:
                    index.add_file(rel_path, source)
                except Exception:
                    continue
                try:
                    cc_results = cc_visit(source)
                except Exception:
                    continue
                # Method-level supplemental metrics (MI, Halstead)
                lines = source.splitlines()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_key = index.index.get((rel_path, node.lineno))
                        if not method_key:
                            continue
                        entry = metrics.setdefault(method_key, {})
                        if mi_visit is not None:
                            segment = ast.get_source_segment(source, node)
                            if segment is None:
                                start = max(0, node.lineno - 1)
                                end = max(start, getattr(node, "end_lineno", node.lineno) - 1)
                                segment = "\n".join(lines[start : end + 1])
                            if segment.strip():
                                try:
                                    mi_value = mi_visit(segment, True)
                                except Exception:
                                    mi_value = None
                                if isinstance(mi_value, (int, float)):
                                    entry['maintainability_index'] = float(mi_value)
                        if HalsteadVisitor is not None and halstead_visitor_report is not None:
                            try:
                                visitor = HalsteadVisitor.from_ast(node)
                                report = halstead_visitor_report(visitor)
                            except Exception:
                                report = None
                            if report is not None:
                                entry['halstead_volume'] = float(report.volume)
                                entry['halstead_difficulty'] = float(report.difficulty)
                                entry['halstead_effort'] = float(report.effort)
                                entry['halstead_bugs'] = float(report.bugs)
                for result in cc_results:
                    lineno = getattr(result, 'lineno', None)
                    complexity = getattr(result, 'complexity', None)
                    if not isinstance(lineno, int) or complexity is None:
                        continue
                    method_key = index.index.get((rel_path, lineno))
                    if not method_key:
                        continue
                    entry = metrics.setdefault(method_key, {})
                    # Keep the maximum complexity per method if multiple nodes map back (e.g., nested definitions)
                    prev = entry.get('cyclomatic')
                    try:
                        value = float(complexity)
                    except Exception:
                        continue
                    if prev is not None and value <= prev:
                        continue
                    entry['cyclomatic'] = value
                    # if cc_rank is not None:
                    #     try:
                    #         cast(Dict[str, Any], entry)['cyclomatic_rank'] = str(cc_rank(value))
                    #     except Exception:
                    #         pass
        return metrics


try:  # pragma: no cover - registration side effect
    register_adapter("complexity", ComplexityAdapter)
except Exception:
    pass
