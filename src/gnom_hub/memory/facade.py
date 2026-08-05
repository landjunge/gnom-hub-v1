"""Combined HOT+WARM+Vector view for the pipeline."""

from __future__ import annotations

from typing import Any

from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.memory.warm import WarmMemory


class MemoryFacade:
    """What the pipeline sees: durable WARM + session HOT + vector recall."""

    def __init__(
        self,
        hot: HotMemory,
        warm: WarmMemory,
        vectors: VectorStore | None = None,
    ) -> None:
        self.hot = hot
        self.warm = warm
        self.vectors = vectors
        self._last_query: str = ""

    def set_query_hint(self, text: str) -> None:
        """User chat text used for vector recall on next pipeline_context()."""
        self._last_query = (text or "").strip()

    def pipeline_context(self, *, max_chars: int = 1100) -> str:
        base = self.hot.pipeline_context(
            max_chars=max_chars,
            warm_facts=self.warm.recent_facts(8),
        )
        chunks: list[str] = []
        if base:
            chunks.append(base)
        if self.vectors is not None and self._last_query:
            hits = self.vectors.search(self._last_query, limit=3)
            if hits:
                chunks.append("Vector recall:")
                for h in hits:
                    score = h.get("score", 0)
                    text = str(h.get("text") or "")[:120]
                    chunks.append(f"- ({score}) {text}")
        text = "\n".join(chunks).strip()
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text

    def __getattr__(self, name: str) -> Any:
        return getattr(self.hot, name)
