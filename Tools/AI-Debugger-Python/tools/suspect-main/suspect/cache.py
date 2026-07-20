"""Simple adapter output caching.

Strategy:
  - Each adapter's collect(ctx) output is cached to .suspect_cache/<adapter>.json
  - A fingerprint key is computed from:
        * adapter name
        * test command
        * sorted list of project *.py file modification times + sizes (cheap proxy for source change)
  - If the stored fingerprint matches the current one, we reuse the cached metrics.
  - TTL optional via environment SUSPECT_CACHE_TTL (seconds); expired entries ignored.

This intentionally avoids hashing file contents for speed; collision risk (size+mtime unchanged but content changed) is acceptable for iterative workflows. User can force bypass with
  SUSPECT_CACHE_BYPASS=1 or CLI flag (to be wired in).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
import json, os, time, pathlib

DEFAULT_DIR = ".suspect_cache"

@dataclass
class CacheEntry:
    fingerprint: str
    created_ts: float
    data: Dict[str, Dict[str, float]]


class CacheManager:
    def __init__(self, project_root: str, cache_dir: str | None = None):
        base = pathlib.Path(project_root)
        self.root = base.resolve()
        self.cache_dir = pathlib.Path(cache_dir or (self.root / DEFAULT_DIR)).resolve()
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.ttl = 0
        try:
            self.ttl = int(os.environ.get("SUSPECT_CACHE_TTL", "0"))
        except Exception:
            self.ttl = 0
        self.bypass = bool(os.environ.get("SUSPECT_CACHE_BYPASS"))

    def _snapshot(self) -> list[tuple[str, int, int]]:
        snap: list[tuple[str, int, int]] = []
        try:
            for p in self.root.rglob("*.py"):
                # Skip virtualenvs and caches
                parts = {"__pycache__", ".venv", "venv", "env", ".git"}
                if any(seg in parts for seg in p.parts):
                    continue
                st = p.stat()
                rel = p.relative_to(self.root).as_posix()
                snap.append((rel, int(st.st_mtime), int(st.st_size)))
        except Exception:
            pass
        return sorted(snap)

    def _fingerprint(self, adapter_name: str, test_cmd: str) -> str:
        snap = self._snapshot()
        return f"{adapter_name}|{test_cmd}|" + ";".join(f"{rel}:{mt}:{sz}" for rel, mt, sz in snap)

    def load(self, adapter_name: str, test_cmd: str) -> CacheEntry | None:
        if self.bypass:
            return None
        fp = self._fingerprint(adapter_name, test_cmd)
        path = self.cache_dir / f"{adapter_name}.json"
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text())
            entry = CacheEntry(
                fingerprint=str(raw.get("fingerprint", "")),
                created_ts=float(raw.get("created_ts", 0.0)),
                data=raw.get("data", {}) or {},
            )
        except Exception:
            return None
        if entry.fingerprint != fp:
            return None
        if self.ttl and (time.time() - entry.created_ts) > self.ttl:
            return None
        return entry

    def store(self, adapter_name: str, test_cmd: str, data: Dict[str, Dict[str, float]]) -> None:
        fp = self._fingerprint(adapter_name, test_cmd)
        path = self.cache_dir / f"{adapter_name}.json"
        payload = {"fingerprint": fp, "created_ts": time.time(), "data": data}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            pass
