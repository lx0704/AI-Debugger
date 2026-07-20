import csv
from .base import Exporter


class CSVExporter(Exporter):
    name = "csv"

    def write(self, matrix, path: str, project_root: str = None) -> None:
        print(f"Writing CSV to {path} with project root {project_root}")
        rows = matrix.to_rows(project_root=project_root) # Fixed to pass project_root to to_rows
        
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            print(len(rows[0]), rows[0])
            print(len(rows[1]), rows[1])
            w.writerows(rows)
        
        # Verify the written file
        with open(path, "r") as f:
            first_line = f.readline()

        print("Written CSV header:")
        print(first_line)

        


# Backwards-compatible helper
def write_csv(matrix, path, project_root: str = None):
    CSVExporter().write(matrix, path, project_root=project_root)


# Register with exporter plugins registry when imported
try:
    from .plugins import register_exporter
    register_exporter(CSVExporter.name, CSVExporter)
except Exception:
    pass
