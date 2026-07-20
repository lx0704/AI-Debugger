import json, os, sys, subprocess, shutil, textwrap, pathlib

"""Integration test ensuring an MBFL mid-range suspiciousness (>0 and <1).

Strategy:
 - Copy the rich sample project fixture (contains demo_half.py + test_demo_* tests).
 - Run MBFL adapter isolated to demo_half.py and only the two demo tests.
 - Expect both fail- and pass-bucket kills (mkf>0 and mkp>0) yielding 0 < mbfl_sbi < 1.

We do NOT assert an exact 0.50 because the third mutant (bool flip) may survive or
classify into fail bucket depending on environment nuances, giving mkf/mkp ratios
that produce 0.50 or 0.66 recurring. The invariant we need to prove for a hardened
integration demonstration is simply: both partitions non-zero.
"""


def test_mbfl_mid_score_sample_isolation(tmp_path):
    sample_dir = pathlib.Path(__file__).resolve().parents[1] / "rich_sample_project"
    proj = tmp_path / "proj"
    shutil.copytree(sample_dir, proj)

    # Sanity: ensure demo file & tests exist
    assert (proj / "demo_half.py").exists(), "demo_half.py missing in copied project"
    assert (proj / "test_all.py").exists(), "test_all.py missing in copied project"

    # Invoke CLI: isolate mutation target & test subset (two demo tests)
    args = [
        sys.executable, "-m", "suspect.cli", "run",
        "--enable", "mbfl",
        "--project", str(proj),
        "--tests", 'pytest -q -k "test_demo_"',
        "--mbfl-include", "demo_half.py",
        "--print-top", "0",
    ]
    res = subprocess.run(args, cwd=str(tmp_path), capture_output=True, text=True)
    assert res.returncode == 0, f"CLI failed\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"

    matrix_path = tmp_path / "matrix.json"
    assert matrix_path.exists(), "matrix.json not generated"
    data = json.loads(matrix_path.read_text())

    # Locate demo_flag method key
    key = None
    for k in data.keys():
        if k.endswith("demo_half.py:demo_flag") or k.split(":")[-1] == "demo_flag":
            key = k
            break
    assert key, f"demo_flag method not found in matrix.json keys={list(data.keys())}"

    row = data[key]
    mkf = row.get("mkf", 0)
    mkp = row.get("mkp", 0)
    susp = row.get("mbfl_sbi", -1)

    # Hardened assertions: both buckets contributed and suspiciousness truly mid-range
    assert mkf > 0, f"Expected fail bucket kills >0, got {mkf} (row={row})"
    assert mkp > 0, f"Expected pass bucket kills >0, got {mkp} (row={row})"
    assert 0.0 < susp < 1.0, f"Expected mid-range mbfl_sbi, got {susp} (row={row})"

