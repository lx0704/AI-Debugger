from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Exporter(ABC):
    """Minimal exporter interface.

    Implementations should provide a write(matrix, path) method.
    """

    name: str = "exporter"

    @abstractmethod
    def write(self, matrix: Any, path: str) -> None:
        raise NotImplementedError()
