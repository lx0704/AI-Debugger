from .mapping import MethodIndex
from typing import Optional


# Cache of computed method start lines per (project_root, file_key)
_FILE_METHOD_STARTS: dict[tuple[str, str], dict[str, int]] = {}


def _method_start_line(method_key: str, project_root: Optional[str]) -> Optional[int]:
    try:
        path, _qual = method_key.split(":", 1)
    except ValueError:
        return None
    try:
        import os
        file_key = path  # the key used by MethodIndex
        abs_path = path if os.path.isabs(path) else os.path.join(project_root or ".", path)
        cache_key = (os.path.abspath(project_root or "."), file_key)
        if cache_key not in _FILE_METHOD_STARTS:
            try:
                src = open(abs_path, "r", encoding="utf-8").read()
            except Exception:
                return None
            idx = MethodIndex()
            idx.add_file(file_key, src)
            starts: dict[str, int] = {}
            for (k, ln), mk in idx.index.items():
                if k != file_key:
                    continue
                if mk not in starts or ln < starts[mk]:
                    starts[mk] = ln
            _FILE_METHOD_STARTS[cache_key] = starts
        return _FILE_METHOD_STARTS[cache_key].get(method_key)
    except Exception:
        return None