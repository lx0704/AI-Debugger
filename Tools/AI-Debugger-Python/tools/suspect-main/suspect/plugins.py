"""Simple plugin registry for adapters.

This module provides a tiny, import-time-free registry and a helper to
import builtin adapter modules so they can register themselves.
"""
from typing import Dict, List, Optional, Iterable, Any, cast

_REGISTRY: Dict[str, type] = {}


def register_adapter(name: str, cls: type) -> None:
    _REGISTRY[name] = cls


def get_adapter(name: str) -> Optional[type]:
    return _REGISTRY.get(name)


def list_adapters() -> List[str]:
    return list(_REGISTRY.keys())


def register_builtin_adapters() -> None:
    """Import builtin adapter modules so they can register themselves.

    This is intentionally forgiving: failures to import a particular
    adapter won't abort the whole process.
    """
    try:
        # Cover builtins here; more can be added later.
        from .adapters import coverage_sbfl  # noqa: F401
    except Exception:
        pass
    try:
        from .adapters import complexity  # noqa: F401
    except Exception:
        pass
    try:
        from .adapters import mbfl_mutatest  # noqa: F401
    except Exception:
        pass
    try:
        from .adapters import lizard_metrics  # noqa: F401
    except Exception:
        pass
    try:
        from .adapters import similarity  # noqa: F401
    except Exception:
        pass
    # Discover adapters provided via entry points named 'suspect.adapters'
    try:
        try:
            from importlib import metadata as _md
        except Exception:
            import importlib_metadata as _md  # type: ignore

        eps = _md.entry_points()
        candidates: Any = []
        # entry_points() shape differs by Python version; try .select first
        try:
            select = getattr(eps, "select", None)
            if callable(select):
                candidates = select(group="suspect.adapters")
            else:
                # older mapping-like interface
                candidates = eps.get("suspect.adapters", [])  # type: ignore[attr-defined]
        except Exception:
            candidates = []

        try:
            iter(candidates)  # type: ignore[arg-type]
            cand_iter = candidates  # type: ignore[assignment]
        except Exception:
            cand_iter = []

        for ep in cand_iter:
            try:
                cls = ep.load()
                register_adapter(ep.name, cls)
            except Exception:
                # ignore problems loading third-party adapters
                continue
    except Exception:
        pass
