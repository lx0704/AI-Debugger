#!/usr/bin/env python3
"""
Clean SUSPECT build/test artifacts from the repo or a target project.

Usage (from repo root):
  python scripts/clean_suspect_artifacts.py              # standard cleanup
  python scripts/clean_suspect_artifacts.py --dry-run    # show what would be removed
  python scripts/clean_suspect_artifacts.py --with-venv  # also remove local virtualenvs
  python scripts/clean_suspect_artifacts.py --project rich_sample_project

Flags:
  --project PATH     Clean inside this path (default: repo root)
  --dry-run          List targets without deleting
  --with-venv        Also delete .venv/ venv/ env/ (not just .mutatest-venv)
    --keep-outputs     Preserve exporter outputs (matrix.csv/json, kill_summary.json)
  --yes              Do not prompt for confirmation

What it removes (by default):
  - pytest caches: .pytest_cache/, __pycache__/
  - coverage: .coverage, .coverage.*, coverage.xml, htmlcov/
  - SUSPECT artifacts: .suspect.* files, .suspect.mbfl/ dir
    - MBFL diagnostics: matrix.csv, matrix.json, kill_summary.json, mbfl.json
  - build: build/, dist/, pip-wheel-metadata/, *.egg-info/
  - mutatest venv: .mutatest-venv/

It will not remove your main .venv/ unless --with-venv is passed.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from suspect.cleanup import collect_artifacts, cleanup


def main() -> int:
    ap = argparse.ArgumentParser(description="Clean SUSPECT artifacts")
    ap.add_argument("--project", default=".", help="Project path to clean (default: .)")
    ap.add_argument("--dry-run", action="store_true", help="List targets without deleting")
    ap.add_argument("--with-venv", action="store_true", help="Also delete .venv/ venv/ env/")
    ap.add_argument("--yes", action="store_true", help="Do not prompt for confirmation")
    ap.add_argument("--keep-outputs", action="store_true", help="Preserve matrix/JSON exporters")
    args = ap.parse_args()

    root = Path(args.project).resolve()
    if not root.exists():
        print(f"Path not found: {root}")
        return 2

    plan = collect_artifacts(
        root,
        include_outputs=not args.keep_outputs,
        include_venv=args.with_venv,
    )

    if not plan.files and not plan.directories:
        print("Nothing to clean.")
        return 0

    print(f"Cleaning target: {root}")
    print(f"Will remove: {len(plan.files)} files, {len(plan.directories)} directories")

    if not args.dry_run and not args.yes:
        ans = input("Proceed? [y/N] ").strip().lower()
        if ans not in {"y", "yes"}:
            print("Aborted.")
            return 1

    prefix = "(dry)" if args.dry_run else "----"
    for file_path in plan.files:
        print(f"FILE  {prefix}  {file_path}")
    for dir_path in plan.directories:
        print(f"DIR   {prefix}  {dir_path}")

    result = cleanup(
        root,
        include_outputs=not args.keep_outputs,
        include_venv=args.with_venv,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print("(dry-run) No changes made.")
        return 0
    print(f"Removed {result.total_removed} items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
