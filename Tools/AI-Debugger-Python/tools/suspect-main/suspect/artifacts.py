"""Artifact repository abstraction.

Collects and persists run artifacts (matrices, diagnostics, coverage) with an index manifest for easy listing.
The repository lives in a target directory (often the consolidated out-dir) and maintains a JSON manifest:
    artifact_manifest.json
Each entry records: name, filename, kind, size, created_ts, tags.

Retention: if max_entries is set (env SUSPECT_ARTIFACT_MAX or constructor arg), older entries beyond that count are pruned (files removed, manifest updated).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import json, os, pathlib, time

MANIFEST_NAME = "artifact_manifest.json"

@dataclass
class Artifact:
    name: str
    filename: str
    kind: str
    size: int
    created_ts: float
    tags: Dict[str, Any]


class ArtifactRepository:
    def __init__(self, directory: str, max_entries: Optional[int] = None):
        self.dir = pathlib.Path(directory).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        if max_entries is None:
            try:
                max_entries = int(os.environ.get("SUSPECT_ARTIFACT_MAX", "0")) or None
            except Exception:
                max_entries = None
        self.max_entries = max_entries
        self._manifest_path = self.dir / MANIFEST_NAME
        self._manifest: List[Artifact] = []
        self._load_manifest()

    def _load_manifest(self) -> None:
        if not self._manifest_path.exists():
            self._manifest = []
            return
        try:
            raw = json.loads(self._manifest_path.read_text())
            self._manifest = [Artifact(**e) for e in raw.get("artifacts", [])]
        except Exception:
            self._manifest = []

    def _save_manifest(self) -> None:
        try:
            data = {"artifacts": [asdict(a) for a in self._manifest]}
            with open(self._manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def register_file(self, path: str, kind: str, name: Optional[str] = None, tags: Optional[Dict[str, Any]] = None) -> None:
        p = pathlib.Path(path)
        if not p.exists() or not p.is_file():
            return
        art = Artifact(
            name=name or p.stem,
            filename=p.name,
            kind=kind,
            size=p.stat().st_size,
            created_ts=time.time(),
            tags=tags or {},
        )
        self._manifest.append(art)
        self._manifest.sort(key=lambda a: a.created_ts, reverse=True)
        self._prune()
        self._save_manifest()

    def save_json(self, name: str, obj: Dict[str, Any], kind: str = "json", tags: Optional[Dict[str, Any]] = None) -> str:
        fname = f"{name}.json"
        path = self.dir / fname
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2)
        except Exception:
            return str(path)
        self.register_file(str(path), kind=kind, name=name, tags=tags)
        return str(path)

    def list(self) -> List[Artifact]:
        return list(self._manifest)

    def _prune(self) -> None:
        if self.max_entries and len(self._manifest) > self.max_entries:
            keep = self._manifest[: self.max_entries]
            remove = self._manifest[self.max_entries :]
            # remove files for pruned entries (best-effort)
            for art in remove:
                try:
                    (self.dir / art.filename).unlink(missing_ok=True)
                except Exception:
                    continue
            self._manifest = keep
