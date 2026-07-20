import math
import os
from pathlib import Path

import pytest

from suspect.adapters.mbfl_mutatest import MBFLMutatestAdapter


def _write_sample_module(tmp: Path) -> str:
    src = (
        "def foo():\n"
        "    value = True\n"
        "    return 1 if value else 0\n"
        "\n"
        "def bar():\n"
        "    value = True\n"
        "    return 2 if value else 0\n"
    )
    p = tmp / "mod.py"
    p.write_text(src, encoding="utf-8")
    return "mod.py"


def test_mbfl_mutatest_adapter_parsing_and_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Arrange: write a source file to mutate
    mod_rel = _write_sample_module(tmp_path)

    # Create a fake mutatest venv with a dummy binary path that "exists"
    fake_venv = tmp_path / ".mutatest-venv"
    bin_dir = fake_venv / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / ("mutatest.exe" if os.name == "nt" else "mutatest")).write_text("#!/bin/sh\n", encoding="utf-8")
    # Point adapter env var to our fake venv
    monkeypatch.setenv("SUSPECT_MUTATEST_VENV", str(fake_venv))

    # Stub MethodIndex: map line 2 -> foo, line 6 -> bar
    class _FakeIdx:
        def __init__(self):
            self.index = {(mod_rel, 2): f"{mod_rel}:foo", (mod_rel, 6): f"{mod_rel}:bar"}
        def add_file(self, *a, **k):
            return None

    monkeypatch.setattr("suspect.adapters.mbfl_mutatest.MethodIndex", _FakeIdx)

    # Fake subprocess.run for baseline and per-mutant pytest runs with junitxml output
    run_state = {"mutant": 0}

    def _fake_run(cmd, cwd=None, env=None, stdout=None, stderr=None, text=None, check=None, shell=False, timeout=None):
        class _P:
            def __init__(self, out=""):
                self.returncode = 0
                self.stdout = out
                self.stderr = ""

        if not shell or not isinstance(cmd, str):
            return _P("")

        import re

        m = re.search(r"--junitxml=([^\s]+)", cmd)
        if not m:
            return _P("")

        junit_path = Path(m.group(1))
        if junit_path.name.endswith("baseline.xml"):
            junit_path.write_text(
                """
<testsuite>
  <testcase name="pass1"/>
  <testcase name="pass2"/>
  <testcase name="pass3"/>
  <testcase name="fail1"><failure/></testcase>
  <testcase name="fail2"><failure/></testcase>
</testsuite>
""".strip(),
                encoding="utf-8",
            )
        else:
            idx = run_state["mutant"]
            run_state["mutant"] += 1
            if idx == 0:
                junit_body = """
<testsuite>
  <testcase name="pass1"/>
  <testcase name="pass2"/>
  <testcase name="pass3"/>
  <testcase name="fail1"/>
  <testcase name="fail2"><failure/></testcase>
</testsuite>
"""
            elif idx == 1:
                junit_body = """
<testsuite>
  <testcase name="pass1"/>
  <testcase name="pass2"/>
  <testcase name="pass3"/>
  <testcase name="fail1"><failure/></testcase>
  <testcase name="fail2"/>
</testsuite>
"""
            else:
                junit_body = """
<testsuite>
  <testcase name="pass1"/>
  <testcase name="pass2"/>
  <testcase name="pass3"/>
  <testcase name="fail1"><failure/></testcase>
  <testcase name="fail2"><failure/></testcase>
</testsuite>
"""
            junit_path.write_text(junit_body.strip(), encoding="utf-8")
        return _P("")

    monkeypatch.setattr("subprocess.run", _fake_run)

    adapter = MBFLMutatestAdapter()
    out = adapter.collect({"project_root": str(tmp_path), "test_cmd": "pytest -q"})

    # Both methods should have been credited with one kill each
    assert f"{mod_rel}:foo" in out and f"{mod_rel}:bar" in out
    foo = out[f"{mod_rel}:foo"]
    bar = out[f"{mod_rel}:bar"]

    # With Nf=2, Np=3, kp=0 approximation
    # mbfl_sbi = kf / (kf+kp); here kp=0, kf=1 -> 1.0
    assert math.isclose(foo["mbfl_sbi"], 1.0, rel_tol=1e-6, abs_tol=1e-6)
    assert math.isclose(foo["mkf"], 1.0)
    assert math.isclose(foo["mkp"], 0.0)

    assert math.isclose(bar["mbfl_sbi"], 1.0, rel_tol=1e-6, abs_tol=1e-6)
    assert math.isclose(bar["mkf"], 1.0)
    assert math.isclose(bar["mkp"], 0.0)

    # New mutant count metrics: each method has one detected, zero survived -> total=1, score=1.0
    for m in (foo, bar):
        assert m.get("mutants_detected") == 1.0
        assert m.get("mutants_survived") == 0.0
        assert m.get("mutants_total") == 1.0
        assert m.get("mutation_score") == 1.0
