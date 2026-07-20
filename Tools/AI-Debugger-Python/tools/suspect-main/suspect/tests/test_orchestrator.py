def test_orchestrator_with_mock_adapter():
    from suspect.orchestrator import Orchestrator
    from suspect.matrix import Matrix

    class MockAdapter:
        name = "mock"
        def collect(self, ctx):
            return {"a.py:foo": {"ef": 1.0, "ochiai": 0.5}}

    orch = Orchestrator(project_root=".", test_cmd="pytest -q")
    # pass class
    m1 = orch.run([MockAdapter])
    assert isinstance(m1, Matrix)
    assert "a.py:foo" in m1.rows
    # pass instance
    m2 = orch.run([MockAdapter()])
    assert "a.py:foo" in m2.rows
