"""Lizard metrics adapter: LOC (nloc), params (parameter_count), length (lines).

This adapter uses the `lizard` library to compute per-function metrics and maps
results to SUSPECT method keys via MethodIndex.
"""
from __future__ import annotations

import fnmatch
import os
import pathlib
from typing import Dict

from .base import MetricAdapter
from ..mapping import MethodIndex
from ..plugins import register_adapter

try:  # pragma: no cover
    # lizard exposes an API to analyze a source string
    from lizard import analyze_file  # type: ignore
except Exception:  # pragma: no cover
    analyze_file = None  # type: ignore


class LizardAdapter(MetricAdapter):
    name = "lizard"

    def collect(self, ctx: dict) -> Dict[str, Dict[str, float]]:
        if analyze_file is None:
            raise RuntimeError("lizard is required for Lizard metrics; install with 'pip install lizard'")

        project = pathlib.Path(ctx["project_root"]).resolve()
        sample_only = bool(ctx.get("sample_project_only"))
        include = ctx.get("lizard_include") or ctx.get("complexity_include") or []
        exclude = ctx.get("lizard_exclude") or ctx.get("complexity_exclude") or []
        if sample_only and not include:
            include = ["rich_sample_project/**"]

        def _include(rel: str, filename: str) -> bool:
            if include:
                if not any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(filename, pat) for pat in include):
                    return False
            if exclude and any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(filename, pat) for pat in exclude):
                return False
            return True

        skip_dirs = {".git", "__pycache__", ".venv", "venv", "env", "build", "dist"}
        idx = MethodIndex()
        out: Dict[str, Dict[str, float]] = {}

        for root, dirs, files in os.walk(str(project)):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                rel = pathlib.Path(root).joinpath(fn).relative_to(project).as_posix()
                # Skip tests by default
                is_test = (
                    rel.startswith("tests/")
                    or "/tests/" in rel
                    or fn.startswith("test_")
                    or rel.endswith("_test.py")
                )
                if is_test and not (sample_only and rel.startswith("rich_sample_project/")):
                    continue
                if not _include(rel, fn):
                    continue
                abs_path = project / rel
                try:
                    src = abs_path.read_text(encoding="utf-8")
                except Exception:
                    continue
                # Ensure MethodIndex has this file for (rel, lineno) -> method_key mapping
                try:
                    idx.add_file(rel, src)
                except Exception:
                    pass
                try:
                    result = analyze_file.analyze_source_code(rel, src)  # type: ignore[attr-defined]
                except Exception:
                    continue
                for func in getattr(result, "function_list", []):
                    try:
                        start = int(getattr(func, "start_line", 0) or 0)
                        nloc = float(getattr(func, "nloc", 0) or 0)
                        params = float(getattr(func, "parameter_count", 0) or 0)
                        length = float(getattr(func, "length", 0) or 0)
                    except Exception:
                        continue
                    if start <= 0:
                        continue
                    # Map to SUSPECT method key via MethodIndex (fallback to rel:long_name)
                    mkey = idx.index.get((rel, start))
                    if not mkey:
                        long_name = str(getattr(func, "long_name", getattr(func, "name", "")))
                        if long_name:
                            mkey = f"{rel}:{long_name}"
                        else:
                            continue
                    row = out.setdefault(mkey, {})
                    # Use names expected by user: LOC, params, length
                    row["lizard_loc"] = nloc
                    row["lizard_params"] = params
                    row["lizard_length"] = length
        return out


# Register adapter in registry
try:  # pragma: no cover - side effect
    register_adapter("lizard", LizardAdapter)
except Exception:
    pass
