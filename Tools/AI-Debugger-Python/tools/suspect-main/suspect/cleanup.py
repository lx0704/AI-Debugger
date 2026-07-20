"""Utilities to remove SUSPECT-generated artifacts.

This consolidates the clean-up logic used by both the CLI and the
``scripts/clean_suspect_artifacts.py`` helper.  It provides a structured
API so callers can choose whether to keep exported reports (``matrix.csv``
/ ``matrix.json`` / kill summary) or delete them together with coverage and
pytest artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
import shutil
from pathlib import Path
from typing import Iterable, Sequence

__all__ = [
    "CleanupPlan",
    "CleanupResult",
    "collect_artifacts",
    "cleanup",
]

# Files generated during SBFL/MBFL runs.
DEFAULT_FILE_PATTERNS: tuple[str, ...] = (
    ".coverage",
    ".coverage.*",
    "coverage.xml",
    ".suspect.coveragerc",
    ".suspect.coverage.json",
    ".suspect.pytest.xml",
    ".suspect.mbfl.pytest.xml",
    ".suspect.mbfl.pytest.ini",
    ".suspect.kf.pytest.xml",
    ".suspect.mutatest.json",
    "mbfl.json",
)

# Exported matrices (optionally kept depending on caller preference).
OUTPUT_FILE_PATTERNS: tuple[str, ...] = (
    "matrix.csv",
    "matrix.json",
    "kill_summary.json",
)

# Directories we routinely want to remove.
DEFAULT_DIR_NAMES: tuple[str, ...] = (
    ".pytest_cache",
    "__pycache__",
    "htmlcov",
    ".suspect.mbfl",
    "build",
    "dist",
    "pip-wheel-metadata",
    ".mutatest-venv",
)

# Directories representing helper virtualenvs.
DEFAULT_VENV_NAMES: tuple[str, ...] = (
    ".mutatest-venv",
    ".venv",
    "venv",
    "env",
)


@dataclass
class CleanupPlan:
    files: list[Path]
    directories: list[Path]


@dataclass
class CleanupResult:
    removed_files: list[Path]
    removed_directories: list[Path]

    @property
    def total_removed(self) -> int:
        return len(self.removed_files) + len(self.removed_directories)


def _expand_patterns(root: Path, patterns: Iterable[str]) -> list[Path]:
    matches: list[Path] = []
    for pattern in patterns:
        for candidate in root.rglob(pattern):
            matches.append(candidate)
    return matches


def collect_artifacts(
    root: Path,
    *,
    include_outputs: bool = True,
    include_venv: bool = False,
    extra_file_patterns: Sequence[str] | None = None,
    exclude: Sequence[Path] | None = None,
) -> CleanupPlan:
    """Collect artifact candidates under *root*.

    Args:
        root: Base directory to search.
        include_outputs: If False, preserve standard exported reports.
        include_venv: If True, also remove helper virtualenv directories.
        extra_file_patterns: Additional glob patterns to include.
        exclude: Specific absolute paths to skip when collecting.
    """

    exclude_set = {p.resolve() for p in (exclude or [])}
    files: list[Path] = []
    dirs: list[Path] = []

    # Files: coverage + pytest + optional outputs
    file_patterns = list(DEFAULT_FILE_PATTERNS)
    if include_outputs:
        file_patterns.extend(OUTPUT_FILE_PATTERNS)
    if extra_file_patterns:
        file_patterns.extend(extra_file_patterns)

    for match in _expand_patterns(root, file_patterns):
        if match.resolve() in exclude_set:
            continue
        if match.is_file():
            files.append(match.resolve())

    # Directories
    dir_names = list(DEFAULT_DIR_NAMES)
    # *.egg-info directories are always safe to remove
    for match in root.rglob("*.egg-info"):
        if match.resolve() in exclude_set:
            continue
        if match.is_dir():
            dirs.append(match.resolve())

    if include_venv:
        dir_names.extend(DEFAULT_VENV_NAMES)
    for name in dir_names:
        for match in root.rglob(name):
            if match.resolve() in exclude_set:
                continue
            if match.is_dir():
                dirs.append(match.resolve())

    # Deduplicate and sort directories deepest-first for safe removal
    files = sorted({p for p in files})
    dirs = sorted({p for p in dirs}, key=lambda p: len(str(p)), reverse=True)
    return CleanupPlan(files=files, directories=dirs)


def cleanup(
    root: Path,
    *,
    include_outputs: bool = True,
    include_venv: bool = False,
    dry_run: bool = False,
    extra_file_patterns: Sequence[str] | None = None,
    exclude: Sequence[Path] | None = None,
) -> CleanupResult:
    """Delete artifacts under *root*.

    Returns the list of removed files/directories.
    """

    plan = collect_artifacts(
        root,
        include_outputs=include_outputs,
        include_venv=include_venv,
        extra_file_patterns=extra_file_patterns,
        exclude=exclude,
    )

    removed_files: list[Path] = []
    removed_dirs: list[Path] = []

    for file_path in plan.files:
        if dry_run:
            continue
        try:
            file_path.unlink(missing_ok=True)
            removed_files.append(file_path)
        except Exception:
            # best-effort cleanup – ignore failures
            continue

    for dir_path in plan.directories:
        if dry_run:
            continue
        try:
            shutil.rmtree(dir_path, ignore_errors=True)
            removed_dirs.append(dir_path)
        except Exception:
            continue

    return CleanupResult(removed_files=removed_files, removed_directories=removed_dirs)
