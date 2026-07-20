from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict


class MetricAdapter(ABC):
    """Minimal adapter interface for metric-producing adapters.

    Implementations should be lightweight and side-effect free where possible.
    """

    name: str = "metric_adapter"

    @abstractmethod
    def collect(self, ctx: dict) -> Dict[str, Dict[str, float]]:
        """Collect metrics for the given context.

        Args:
            ctx: dictionary containing at least 'project_root' and 'test_cmd'.

        Returns:
            Mapping from method_key ("path:qualname") to a dict of metric name -> value.
        """
        raise NotImplementedError()
class MetricAdapter:
    name = "base"
    def collect(self, ctx) -> dict[str, dict[str, float]]:
        raise NotImplementedError
