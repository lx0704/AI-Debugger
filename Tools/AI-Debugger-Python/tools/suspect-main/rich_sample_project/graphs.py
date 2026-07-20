from __future__ import annotations

from collections import deque
from typing import Dict, List, Set, Tuple


def bfs(adj: Dict[str, List[str]], start: str) -> List[str]:
    visited: Set[str] = set()
    order: List[str] = []
    q: deque[str] = deque([start])
    while q:
        v = q.popleft()
        if v in visited:
            continue
        visited.add(v)
        order.append(v)
        for nxt in adj.get(v, []):
            if nxt not in visited:
                q.append(nxt)
    return order


def dijkstra(adj: Dict[str, List[Tuple[str, int]]], src: str) -> Dict[str, int]:
    import heapq

    dist: Dict[str, int] = {src: 0}
    pq: List[Tuple[int, str]] = [(0, src)]
    seen: Set[str] = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in seen:
            continue
        seen.add(u)
        for v, w in adj.get(u, []):
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist
