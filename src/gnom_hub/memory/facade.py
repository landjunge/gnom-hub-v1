"""Combined HOT+WARM view for the pipeline."""

from __future__ import annotations

from typing import Any

from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.warm import WarmMemory


class MemoryFacade:
    """What the pipeline sees: durable WARM + session HOT."""

    def __init__(self, hot: HotMemory, warm: WarmMemory) -> None:
        self.hot = hot
        self.warm = warm

    def pipeline_context(self, *, max_chars: int = 900) -> str:
        return self.hot.pipeline_context(
            max_chars=max_chars,
            warm_facts=self.warm.recent_facts(8),
        )

    # proxy hot methods used elsewhere if needed
    def __getattr__(self, name: str) -> Any:
        return getattr(self.hot, name)
