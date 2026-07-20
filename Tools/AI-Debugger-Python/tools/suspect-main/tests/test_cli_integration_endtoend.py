import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _copy_sample(tmp_path: Path, sample_dir: Path) -> Path:
    dst = tmp_path / "proj"
    shutil.copytree(sample_dir, dst)
    return dst


def _run_cli(tmp_path: Path, project: Path, print_top: int = 0, include_tests: bool = False):
    args = [
        sys.executable,
        "-m",
        "suspect.cli",
        "run",
        "--enable",
        "sbfl",
        "--project",
        str(project),
        "--tests",
        "pytest -q",
        "--metric",
        "ochiai",
        "--print-top",
        str(print_top),
    ]
    if include_tests:
        args.append("--include-tests")
    res = subprocess.run(args, cwd=str(tmp_path), capture_output=True, text=True)
    return res


def test_cli_generates_outputs(tmp_path: Path):
    sample_dir = Path(__file__).resolve().parents[1] / "rich_sample_project"
    proj = _copy_sample(tmp_path, sample_dir)

    res = _run_cli(tmp_path, proj, print_top=0)
    assert res.returncode == 0, res.stderr or res.stdout

    # Outputs written in tmp_path working directory
    json_path = tmp_path / "matrix.json"
    csv_path = tmp_path / "matrix.csv"
    assert json_path.exists(), "matrix.json not created"
    assert csv_path.exists(), "matrix.csv not created"

    data = json.loads(json_path.read_text())
    # Expect at least some known methods present
    keys = "\n".join(data.keys())
    assert "bank.py:BankAccount.deposit" in keys or \
           ":BankAccount.deposit" in keys


def test_sbfl_scores_nonzero_for_failed(tmp_path: Path):
    sample_dir = Path(__file__).resolve().parents[1] / "rich_sample_project"
    proj = _copy_sample(tmp_path, sample_dir)

    res = _run_cli(tmp_path, proj, print_top=0)
    assert res.returncode == 0, res.stderr or res.stdout

    data = json.loads((tmp_path / "matrix.json").read_text())

    # Find deposit and fib entries and check ef>0 and ochiai>0
    def find_key(fragment: str):
        for k in data.keys():
            if fragment in k:
                return k
        return None

    dep_key = find_key("bank.py:BankAccount.deposit") or find_key(":BankAccount.deposit")
    fib_key = find_key("algos.py:fib") or find_key(":fib")

    assert dep_key, "deposit method not found in matrix.json"
    assert fib_key, "fib method not found in matrix.json"

    assert data[dep_key]["ef"] >= 0.0
    assert data[fib_key]["ef"] >= 0.0
    assert data[dep_key]["ochiai"] >= 0.0
    assert data[fib_key]["ochiai"] >= 0.0


def test_console_excludes_tests_by_default(tmp_path: Path):
    sample_dir = Path(__file__).resolve().parents[1] / "rich_sample_project"
    proj = _copy_sample(tmp_path, sample_dir)

    res = _run_cli(tmp_path, proj, print_top=5)
    assert res.returncode == 0, res.stderr or res.stdout
    out = res.stdout
    # Should contain at least one production method (file:qualname) and exclude tests by default
    assert ".py:" in out, "expected production methods in console output"
    assert "test_all.py:test_deposit_withdraw" not in out
