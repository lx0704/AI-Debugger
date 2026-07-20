import sys
import subprocess
import json
from pathlib import Path


def test_cli_runs_and_writes_outputs(tmp_path: Path):
    """Run the CLI against the sample project and ensure exporters write files."""
    repo_root = Path(__file__).resolve().parents[1]
    csv_out = tmp_path / "out.csv"
    json_out = tmp_path / "out.json"

    cmd = [
        sys.executable,
        "-m",
        "suspect.cli",
        "run",
        "--project",
        "rich_sample_project",
        "--enable",
        "sbfl",
        "--exporters",
        "csv",
        "json",
        "--output-csv",
        str(csv_out),
        "--output-json",
        str(json_out),
        "--print-top",
        "0",
    ]

    # Run CLI in repo root so package imports resolve
    subprocess.run(cmd, check=True, cwd=str(repo_root))

    assert csv_out.exists(), "CSV output was not created"
    assert json_out.exists(), "JSON output was not created"

    # Basic content checks
    jtxt = json.loads(json_out.read_text(encoding="utf-8"))
    assert isinstance(jtxt, dict)

    ctxt = csv_out.read_text(encoding="utf-8").strip().splitlines()
    assert len(ctxt) >= 1
