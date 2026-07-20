from __future__ import annotations

import sys
from pathlib import Path

from suspect import cli
from suspect.cleanup import collect_artifacts, cleanup


def _touch(path: Path, text: str = "art") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_collect_and_cleanup_removes_artifacts(tmp_path: Path) -> None:
    files = [
        ".coverage",
        ".suspect.coverage.json",
        ".suspect.pytest.xml",
        "mbfl.json",
        "matrix.csv",
    ]
    dirs = [
        ".pytest_cache",
        ".suspect.mbfl",
        "package.egg-info",
    ]
    for name in files:
        _touch(tmp_path / name)
    for name in dirs:
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    plan = collect_artifacts(tmp_path)
    assert len(plan.files) == len(files)
    assert len(plan.directories) == len(dirs)

    result = cleanup(tmp_path)
    assert result.total_removed == len(files) + len(dirs)
    for name in files:
        assert not (tmp_path / name).exists()
    for name in dirs:
        assert not (tmp_path / name).exists()


def test_cleanup_preserves_outputs_when_requested(tmp_path: Path) -> None:
    keep = _touch(tmp_path / "matrix.json")
    trash = _touch(tmp_path / ".suspect.mutatest.json")

    cleanup(tmp_path, include_outputs=False)
    assert keep.exists(), "exported matrix should be preserved"
    assert not trash.exists(), "intermediate artifact should be removed"


class _DummyMatrix:
    def __init__(self) -> None:
        self.rows = {"proj.py:func": {"ochiai": 1.0, "ef": 1, "ep": 0}}


class _DummyAdapter:
    name = "dummy"

    def collect(self, ctx):
        return {}


class _DummyExporter:
    def __init__(self, name: str):
        self.name = name

    def write(self, matrix, out_path: str) -> None:
        Path(out_path).write_text(self.name, encoding="utf-8")


class _DummyOrchestrator:
    def __init__(self, *args, **kwargs) -> None:
        self.project_root = kwargs.get("project_root")

    def run(self, adapters):
        return _DummyMatrix()


def test_cli_auto_clean_removes_artifacts(tmp_path: Path, monkeypatch, capsys) -> None:
    # create fake artifacts that auto-clean should remove
    _touch(tmp_path / ".suspect.coveragerc")
    _touch(tmp_path / ".suspect.pytest.xml")
    (tmp_path / ".pytest_cache").mkdir()

    def fake_register_adapters():
        return None

    def fake_get_adapter(name):
        return _DummyAdapter

    def fake_list_adapters():
        return ["dummy"]

    def fake_register_exporters():
        return None

    def fake_get_exporter(name):
        return lambda: _DummyExporter(name)

    def fake_list_exporters():
        return ["csv", "json", "kill_summary"]

    monkeypatch.setattr(cli, "Orchestrator", _DummyOrchestrator)
    monkeypatch.setattr(cli, "register_builtin_adapters", fake_register_adapters)
    monkeypatch.setattr(cli, "get_adapter", fake_get_adapter)
    monkeypatch.setattr(cli, "list_adapters", fake_list_adapters)
    monkeypatch.setattr(cli, "register_builtin_exporters", fake_register_exporters)
    monkeypatch.setattr(cli, "get_exporter", fake_get_exporter)
    monkeypatch.setattr(cli, "list_exporters", fake_list_exporters)

    argv = [
        "suspect",
        "run",
        "--project",
        str(tmp_path),
        "--tests",
        "pytest -q",
        "--print-top",
        "0",
        "--exporters",
        "csv",
        "json",
        "kill_summary",
        "--auto-clean",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()

    captured = capsys.readouterr().out
    assert "Auto-clean" in captured

    # Default outputs should remain
    assert (tmp_path / "matrix.csv").exists()
    assert (tmp_path / "matrix.json").exists()
    assert (tmp_path / "kill_summary.json").exists()

    # Intermediate artifacts should be gone
    assert not (tmp_path / ".suspect.coveragerc").exists()
    assert not (tmp_path / ".suspect.pytest.xml").exists()
    assert not (tmp_path / ".pytest_cache").exists()