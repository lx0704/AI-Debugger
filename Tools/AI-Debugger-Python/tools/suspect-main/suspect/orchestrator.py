from .matrix import Matrix
from typing import Optional, Dict
import time
from .observability import publish

class Orchestrator:
    def __init__(self, project_root: str, test_cmd: str, fail_on_tool_error: bool=False, extra_ctx: Optional[Dict] = None):
        self.project_root = project_root
        self.test_cmd = test_cmd
        self.fail_on_tool_error = fail_on_tool_error
        self.extra_ctx = extra_ctx or {}

    def run(self, adapters):
        """Run a list of adapters.

        Adapters may be either instances implementing collect(ctx) or classes
        (callable) that will be instantiated with no args.
        """
        ctx = {
            "project_root": self.project_root,
            "test_cmd": self.test_cmd,
        }
        try:
            ctx.update(self.extra_ctx)
        except Exception:
            pass
        matrix = Matrix()
        observers = self.extra_ctx.get("observers", [])
        cache_mgr = self.extra_ctx.get("cache_manager")
        publish(observers, "run_start", "orchestrator", {"adapters": [getattr(a, 'name', str(a)) for a in adapters]})
        for adapter in adapters:
            inst = adapter
            # If a class/type was passed, instantiate it
            try:
                if isinstance(adapter, type):
                    inst = adapter()
            except Exception:
                inst = adapter
            try:
                a_name = getattr(inst, "name", inst.__class__.__name__)
                publish(observers, "adapter_start", a_name, {})
                # Cache lookup
                data = None
                cache_hit = False
                t0 = time.time()
                if cache_mgr is not None:
                    try:
                        entry = cache_mgr.load(a_name, self.test_cmd)
                        if entry is not None:
                            data = entry.data
                            cache_hit = True
                    except Exception:
                        cache_hit = False
                if data is None:
                    data = inst.collect(ctx)  # {method: {metric: value}}
                    
                    # Store in cache
                    if cache_mgr is not None:
                        try:
                            cache_mgr.store(a_name, self.test_cmd, data)
                        except Exception:
                            pass
                elapsed_ms = int((time.time() - t0) * 1000)
                publish(observers, "adapter_success", a_name, {"methods": len(data or {}), "elapsed_ms": elapsed_ms, "cache": ("hit" if cache_hit else "miss")})
                matrix.merge(data)
            except Exception as e:
                name = getattr(inst, "name", str(inst))
                print(f"[WARN] {name} failed: {e}")
                publish(observers, "adapter_error", name, {"error": str(e)})
                if self.fail_on_tool_error:
                    raise
        publish(observers, "run_end", "orchestrator", {"rows": len(matrix.rows)})
        matrix.fill_missing_mbfl()
        return matrix
