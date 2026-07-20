"""Lightweight observability primitives (event bus + observers).

Provides:
  - Event dataclass capturing phase, name, payload.
  - Observer interface for sinks.
  - JsonlObserver: writes one JSON object per line (stable for tail -f).
  - ConsoleObserver: optional pretty printing (debug/dev only).

Design goals:
  - Zero hard dependency on external logging frameworks.
  - Non-blocking best-effort writes; failures never crash the main run.
  - Structured logs to simplify post-hoc analysis & ingestion.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, Iterable, List
import json, os, threading

ISO = "%Y-%m-%dT%H:%M:%S.%fZ"

@dataclass
class Event:
    phase: str           # e.g. 'run_start', 'adapter_start', 'adapter_success', 'adapter_error', 'run_end'
    name: str            # adapter/exporter name or general tag
    payload: Dict[str, Any]
    timestamp: str       # ISO8601 UTC

    @classmethod
    def create(cls, phase: str, name: str, payload: Optional[Dict[str, Any]] = None) -> "Event":
        return cls(phase=phase, name=name, payload=payload or {}, timestamp=datetime.now(timezone.utc).strftime(ISO))


class Observer(Protocol):
    def on_event(self, event: Event) -> None: ...


class JsonlObserver:
    """Append events as JSON lines to a file (thread-safe, lightweight)."""
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        except Exception:
            pass

    def on_event(self, event: Event) -> None:  # noqa: D401
        line = json.dumps(asdict(event), separators=(",", ":"))
        try:
            with self._lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            # Swallow errors to avoid impacting primary workflow
            pass


class ConsoleObserver:
    """Print concise human-readable event summaries (debug)."""
    def __init__(self, verbose: bool=False):
        self.verbose = verbose

    def on_event(self, event: Event) -> None:
        try:
            phase = event.phase
            name = event.name
            payload = event.payload
            ts = event.timestamp
            if self.verbose:
                print(f"[OBS] {ts} {phase} {name} {json.dumps(payload, sort_keys=True)}")
            else:
                # Compact summary
                core = {k: v for k, v in payload.items() if k in {"methods", "elapsed_ms", "error", "cache"}}
                print(f"[OBS] {phase}:{name} {core}")
        except Exception:
            pass


def publish(observers: Iterable[Observer], phase: str, name: str, payload: Optional[Dict[str, Any]] = None) -> None:
    """Helper to create and broadcast an event to all observers."""
    evt = Event.create(phase, name, payload)
    for ob in observers:
        try:
            ob.on_event(evt)
        except Exception:
            continue


def build_default_observers(log_file: Optional[str], enable_console: bool=False, verbose_console: bool=False) -> List[Observer]:
    obs: List[Observer] = []
    if log_file:
        obs.append(JsonlObserver(log_file))
    if enable_console:
        obs.append(ConsoleObserver(verbose=verbose_console))
    return obs
