"""Registry for exporters.

This mirrors the adapter registry: simple in-memory registration and a
helper to import builtin exporter modules.
"""
from typing import Dict, List, Optional

_REGISTRY: Dict[str, type] = {}


def register_exporter(name: str, cls: type) -> None:
    _REGISTRY[name] = cls


def get_exporter(name: str) -> Optional[type]:
    return _REGISTRY.get(name)


def list_exporters() -> List[str]:
    return list(_REGISTRY.keys())


def register_builtin_exporters() -> None:
    try:
        from . import csv_exporter  # noqa: F401
    except Exception:
        pass
    try:
        from . import json_exporter  # noqa: F401
    except Exception:
        pass
    try:
        from . import kill_summary_exporter  # noqa: F401
    except Exception:
        pass
    # Discover exporters provided via entry points named 'suspect.exporters'
    try:
        try:
            from importlib import metadata as _md
        except Exception:
            import importlib_metadata as _md  # type: ignore

        eps = _md.entry_points()
        candidates = []
        if hasattr(eps, 'select'):
            candidates = eps.select(group='suspect.exporters')
        else:
            candidates = eps.get('suspect.exporters', [])

        for ep in candidates:
            try:
                cls = ep.load()
                register_exporter(ep.name, cls)
            except Exception:
                continue
    except Exception:
        pass
