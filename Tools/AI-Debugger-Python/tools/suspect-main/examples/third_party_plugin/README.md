Example third-party plugin
==========================

This folder contains a minimal example of a third-party plugin that
registers an adapter and an exporter with `suspect` at import time and
also exposes entry-points via `pyproject.toml`.

To test locally:

1. From the repo root, install editable:

   python -m pip install -e examples/third_party_plugin

2. Run `suspect --list-adapters` and `suspect --list-exporters` to see the
   example plugin listed.
