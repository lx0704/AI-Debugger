# Contributing to SUSPECT

Thanks for your interest in improving SUSPECT! This project aims to be a pragmatic research/engineering tool with clear CLI ergonomics and reproducible outputs.

## Quick checklist

- Run tests and basic style checks
  - `pytest -q`
  - Optional: `ruff check suspect tests` and `mypy suspect`
- Verify the CLI help still renders correctly: `suspect --help` and `suspect run --help`
- If you add or change CLI flags:
  - Update the README sections:
    - "Cheat Sheet" (add a small example if relevant)
    - "Common Flags (CLI)"
    - Any adapter-specific sections you touched (SBFL/MBFL/Complexity/Lizard)
  - For observability/caching/artifacts, ensure these are covered when applicable:
    - `--log-file`, `--log-console`, `--log-console-verbose`
    - `--cache-adapters`, `--no-cache` (+ env: `SUSPECT_CACHE_TTL`, `SUSPECT_CACHE_BYPASS`)
    - `--consolidate-output`, `--out-dir`, `--artifact-repo-dir` (+ env: `SUSPECT_OUT_DIR`, `SUSPECT_ARTIFACT_MAX`)
- Include a tiny before/after snippet or sample output in the PR description.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
```

If you run MBFL locally, ensure `mutatest` is installed in the same venv (or set `SUSPECT_MUTATEST_VENV`).

## Cutting a release (maintainers)

1. Bump `version` in `pyproject.toml` and update README highlights.
2. Build artifacts:
   ```bash
   python -m pip install build twine
   python -m build
   ```
3. Test install locally:
   ```bash
   python -m pip install dist/suspect-<VERSION>-py3-none-any.whl
   suspect --version
   ```
4. Tag and publish:
   ```bash
   git tag v<VERSION>
   git push --tags
   # Optional: twine upload dist/*
   ```

That’s it—thank you for contributing!
