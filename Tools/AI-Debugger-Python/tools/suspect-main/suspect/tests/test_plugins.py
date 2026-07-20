def test_registry_has_sbfl():
    from suspect.plugins import register_builtin_adapters, list_adapters

    register_builtin_adapters()
    names = list_adapters()
    assert "sbfl" in names
