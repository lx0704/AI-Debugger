from suspect.plugins import register_adapter
from suspect.exporters.plugins import register_exporter


class ExampleAdapter:
    name = "example"

    def __init__(self):
        pass

    def collect(self, ctx):
        # Minimal adapter: returns empty matrix fragment
        return {}


class ExampleExporter:
    name = "example-json"

    def write(self, matrix, path: str) -> None:
        # Minimal exporter: write empty JSON mapping
        with open(path, "w") as f:
            f.write("{}")


register_adapter(ExampleAdapter.name, ExampleAdapter)
register_exporter(ExampleExporter.name, ExampleExporter)
