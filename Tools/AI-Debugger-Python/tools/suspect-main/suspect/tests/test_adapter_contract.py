def test_coverage_adapter_is_metric_adapter():
    from suspect.adapters.coverage_sbfl import CoverageSBFLAdapter
    from suspect.adapters.base import MetricAdapter

    # Ensure the adapter implements the base contract (subclassing is sufficient)
    assert issubclass(CoverageSBFLAdapter, MetricAdapter)
