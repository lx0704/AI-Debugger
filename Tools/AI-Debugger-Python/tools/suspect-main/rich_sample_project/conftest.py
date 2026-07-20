"""Pytest configuration for the standalone rich sample project."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the sample project's modules resolve as top-level imports (e.g. `import bank`).
PROJECT_ROOT = Path(__file__).resolve().parent
project_path = str(PROJECT_ROOT)

if project_path not in sys.path:
    sys.path.insert(0, project_path)
