"""Simple synchronous EventBus. All modules communicate through this."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    def on(self, event: str, handler: Callable[..., Any]) -> None:
        self._subscribers[event].append(handler)

    def off(self, event: str, handler: Callable[..., Any]) -> None:
        handlers = self._subscribers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event: str, data: Any = None) -> None:
        for handler in list(self._subscribers.get(event, [])):
            handler(data)

    def clear(self) -> None:
        self._subscribers.clear()
