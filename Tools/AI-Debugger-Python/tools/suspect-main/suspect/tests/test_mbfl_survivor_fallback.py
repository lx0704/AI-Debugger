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
    p = tmp / "mod2.py"
    p.write_text(src, encoding="utf-8")
    return "mod2.py"


def _fake_mutatest_output(mod_rel: str, include_survivors: bool):
    # Always emit detected lines; optionally omit survivor per-line lines to trigger fallback.
    lines = [f"Result: Detected at {mod_rel}: (2, 1)"]
    if include_survivors:
        lines.append(f"Result: Survived at {mod_rel}: (6, 1)")
    # Add summary with aggregate survivors to exercise fallback
    lines.append("\nSummary of mutation testing session")
    lines.append("DETECTED")
    lines.append(f" - {mod_rel}: (l: 2, c: 1)")
    lines.append("SURVIVED")
    lines.append(f" - {mod_rel}: (l: 6, c: 1)")
    lines.append("Overall mutation trial summary")
    lines.append(" - DETECTED: 1")
    lines.append(" - SURVIVED: 1")
    lines.append(" - TOTAL RUNS: 2")
    return "\n".join(lines)


@pytest.mark.parametrize("fallback_flag, expect_survivor, expect_enabled", [
    ("on", True, True),   # fallback should distribute survivor
    ("off", False, False) # survivor remains unmapped
])
def test_survivor_fallback_distribution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fallback_flag: str, expect_survivor: bool, expect_enabled: bool):
    mod_rel = _write_sample_module(tmp_path)

    # Fake venv
    fake_venv = tmp_path / ".mutatest-venv"
    bin_dir = fake_venv / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / ("mutatest.exe" if os.name == "nt" else "mutatest")).write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("SUSPECT_MUTATEST_VENV", str(fake_venv))

    # Stub MethodIndex mapping line 2->foo, 6->bar
    class _FakeIdx:
        def __init__(self):
            # Only map the detected line; leave the survivor line unmapped so fallback logic triggers.
            self.index = {(mod_rel, 2): f"{mod_rel}:foo"}
        def add_file(self, *a, **k):
            return None

    monkeypatch.setattr("suspect.adapters.mbfl_mutatest.MethodIndex", _FakeIdx)

    # Force method lookup to require exact line matches so the survivor location remains unmapped.
    def _exact_method_for_line(self, mindex, file_rel, line):
        return mindex.index.get((file_rel, line))

    monkeypatch.setattr(MBFLMutatestAdapter, "_method_for_line", _exact_method_for_line, raising=False)

    run_state = {"mutant": 0}

    # Fake subprocess.run: emit baseline and per-mutant junitxml files
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
            junit_path.write_text("""
<testsuite>
  <testcase name="pass1"/>
  <testcase name="fail1"><failure/></testcase>
</testsuite>
""".strip(), encoding="utf-8")
        else:
            idx = run_state["mutant"]
            run_state["mutant"] += 1
            if idx == 0:
                junit_body = """
<testsuite>
  <testcase name="pass1"/>
  <testcase name="fail1"/>
</testsuite>
"""
            else:
                junit_body = """
<testsuite>
  <testcase name="pass1"/>
  <testcase name="fail1"><failure/></testcase>
</testsuite>
"""
            junit_path.write_text(junit_body.strip(), encoding="utf-8")
        return _P("")

    monkeypatch.setattr("subprocess.run", _fake_run)

    adapter = MBFLMutatestAdapter()
    result = adapter.collect({
        "project_root": str(tmp_path),
        "test_cmd": "pytest -q",
        "mbfl_survivor_fallback": fallback_flag,
    })

    foo_key = f"{mod_rel}:foo"
    assert foo_key in result

    foo_surv = result[foo_key].get("mutants_survived", 0.0)
    if expect_survivor:
        assert foo_surv > 0.0
        total_foo = result[foo_key].get("mutants_total")
        assert isinstance(total_foo, (int, float)) and total_foo >= 1.0
    else:
        assert foo_surv == 0.0
        assert result[foo_key].get("mutants_total") == 1.0

    diag_path = tmp_path / ".suspect.mutatest.json"
    assert diag_path.exists()
    import json

    diag_payload = json.loads(diag_path.read_text(encoding="utf-8"))
    fallback_diag = (diag_payload.get("mutatest", {}).
                     get("mbfl", {}).
                     get("survivor_fallback", {}))
    assert fallback_diag.get("enabled") == expect_enabled