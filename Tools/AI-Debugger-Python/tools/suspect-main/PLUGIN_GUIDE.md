Plugin author guide
===================

This repository supports simple in-process plugin discovery via import-time
registration and optional distribution entry-points. This file shows the
minimum steps to make an adapter or exporter plugin so it can be discovered
by `suspect`.

1) In-process registration
--------------------------

Adapters and exporters can register themselves at import time with the
provided registry helpers. Put this at module import time in your package:

```py
from suspect.plugins import register_adapter

class MyAdapter:
    name = "myadapter"
    def collect(self, ctx):
        # return mapping of method_key -> metrics
        return {}

register_adapter(MyAdapter.name, MyAdapter)
```

For exporters:

```py
from suspect.exporters.plugins import register_exporter

class MyExporter:
    name = "myexport"
    def write(self, matrix, path: str) -> None:
        # write matrix
        pass

register_exporter(MyExporter.name, MyExporter)
```

2) Distribution entry-points (recommended)
-------------------------------------------

To make your plugin installable and auto-discoverable by `suspect`, publish an
entry-point under the appropriate group. Example with pyproject.toml (PEP 621)
using `setuptools` style entry points:

```toml
[project.entry-points]
"suspect.adapters" = { "myadapter" = "my_pkg.adapters:MyAdapter" }
"suspect.exporters" = { "myexport" = "my_pkg.exporters:MyExporter" }
```

For older tooling you might set similar keys under `tool.setuptools.entry-points`
or use `setup.cfg`/`setup.py` entry_points mapping. When installed, `suspect`
will attempt to load entry points from these groups and register the provided
classes.

3) Minimal adapter contract
---------------------------

Adapters are expected to implement a simple contract. The internal `MetricAdapter`
abstract base describes the shape. At minimum implement a `collect(ctx)` method
that returns a mapping of method_key -> metrics dict. `ctx` contains runtime
information (project_root, test_cmd, etc.) depending on the orchestrator.

4) Minimal exporter contract
---------------------------

Exporters must implement `write(matrix, path)` where `matrix` is the project's
Matrix object and `path` is the output filename.

5) Examples and tests
---------------------

- Look at `suspect/exporters/csv_exporter.py` and
  `suspect/exporters/json_exporter.py` for minimal exporter examples.
- Look at `suspect/adapters/coverage_sbfl.py` for an example adapter that
  registers itself at import time.

6) Troubleshooting
------------------

- If your plugin isn't listed by `suspect --list-adapters` or
  `--list-exporters`, confirm your package was installed into the same
  environment and that the entry-point metadata is present.
- You can also import your plugin module directly to force registration at
  runtime.

That's it — small, pluggable components make it easy to extend `suspect`.
