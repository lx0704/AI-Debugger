def test_csv_exporter_is_exporter():
    from suspect.exporters.csv_exporter import CSVExporter
    from suspect.exporters.base import Exporter

    assert issubclass(CSVExporter, Exporter)

def test_json_exporter_is_exporter():
    from suspect.exporters.json_exporter import JSONExporter
    from suspect.exporters.base import Exporter

    assert issubclass(JSONExporter, Exporter)
