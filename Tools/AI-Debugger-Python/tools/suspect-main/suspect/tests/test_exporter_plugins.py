def test_exporter_plugins_listed():
    from suspect.exporters.plugins import register_builtin_exporters, list_exporters

    register_builtin_exporters()
    names = list_exporters()
    assert "csv" in names
    assert "json" in names
