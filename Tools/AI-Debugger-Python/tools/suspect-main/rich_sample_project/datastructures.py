from __future__ import annotations

from collections import deque
from typing import Deque, Generic, Iterable, Iterator, Optional, TypeVar

T = TypeVar("T")


class Stack(Generic[T]):
    def __init__(self, items: Optional[Iterable[T]] = None) -> None:
        self._data: list[T] = list(items) if items is not None else []

    def push(self, item: T) -> None:
        self._data.append(item)

    def pop(self) -> T:
        if not self._data:
            raise IndexError("pop from empty stack")
        return self._data.pop()

    def peek(self) -> T:
        if not self._data:
            raise IndexError("peek from empty stack")
        return self._data[-1]

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._data)

    def __iter__(self) -> Iterator[T]:  # pragma: no cover - trivial
        return iter(self._data)


class Queue(Generic[T]):
    def __init__(self, items: Optional[Iterable[T]] = None) -> None:
        self._data: Deque[T] = deque(items or [])

    def enqueue(self, item: T) -> None:
        self._data.append(item)

    def dequeue(self) -> T:
        if not self._data:
            raise IndexError("dequeue from empty queue")
        return self._data.popleft()

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._data)

    def __iter__(self) -> Iterator[T]:  # pragma: no cover - trivial
        return iter(self._data)
