import json
from .base import Exporter


class JSONExporter(Exporter):
    name = "json"

    def write(self, matrix, path: str, project_root: str = None) -> None:
        print(f"Writing JSON to {path} with project root {project_root}")
        
        with open(path, "w") as f:
            json.dump(matrix.rows, f, indent=2)


def write_json(matrix, path, project_root=None):
    JSONExporter().write(matrix, path, project_root=project_root)


# Register with exporter plugins registry when imported
try:
    from .plugins import register_exporter
    register_exporter(JSONExporter.name, JSONExporter)
except Exception:
    pass
