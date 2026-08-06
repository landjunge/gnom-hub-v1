"""Combined HOT+WARM+Vector view for the pipeline."""

from __future__ import annotations

from typing import Any

from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.memory.warm import WarmMemory


class MemoryFacade:
    """What the pipeline sees: Flex wishes + durable WARM + session HOT + vector."""

    FLEX_PREFIXES = ("user:", "wish:", "flex-wish:")

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

    def flex_wishes(self, *, limit: int = 40) -> list[str]:
        """Active Flex wishes from WARM (source=flex or User:/Wish: prefix)."""
        from gnom_hub.agents.roles_helpers import _is_garbage_fact

        out: list[str] = []
        seen: set[str] = set()
        # Prefer source=flex when available via all_facts order
        for f in self.warm.all_facts():
            t = " ".join(str(f).split()).strip()
            if not t or _is_garbage_fact(t):
                continue
            low = t.lower()
            is_flex_src = False
            # WarmMemory may only return text; detect by prefix (source=flex writes User:)
            if low.startswith(self.FLEX_PREFIXES):
                is_flex_src = True
            if not is_flex_src:
                continue
            key = low
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
            if len(out) >= limit:
                break
        return out

    def pipeline_context(self, *, max_chars: int = 1100) -> str:
        from gnom_hub.agents.roles_helpers import _is_garbage_fact

        # A: Flex block FIRST — binding user wishes, not truncated away
        wishes = self.flex_wishes()
        flex_block = ""
        if wishes:
            flex_block = "FLEX_WISHES (binding, user source of truth):\n" + "\n".join(
                f"- {w}" for w in wishes
            )

        warm = [
            f
            for f in self.warm.recent_facts(8)
            if not _is_garbage_fact(f) and not str(f).lower().startswith(self.FLEX_PREFIXES)
        ]
        # Reserve room for flex so HOT/vector cannot erase it
        rest_budget = max_chars
        if flex_block:
            rest_budget = max(200, max_chars - len(flex_block) - 4)

        base = self.hot.pipeline_context(
            max_chars=rest_budget,
            warm_facts=warm,
        )
        chunks: list[str] = []
        if flex_block:
            chunks.append(flex_block)
        if base:
            chunks.append(base)
        if self.vectors is not None and self._last_query:
            hits = self.vectors.search(self._last_query, limit=3)
            if hits:
                lines = []
                for h in hits:
                    text = str(h.get("text") or "")[:120]
                    if not text or _is_garbage_fact(text):
                        continue
                    if str(text).lower().startswith(self.FLEX_PREFIXES):
                        continue  # already in flex block
                    score = h.get("score", 0)
                    lines.append(f"- ({score}) {text}")
                if lines:
                    chunks.append("Vector recall:")
                    chunks.extend(lines)

        if flex_block:
            rest = "\n".join(chunks[1:]).strip() if len(chunks) > 1 else ""
            if rest and len(rest) > rest_budget:
                rest = rest[: rest_budget - 1] + "…"
            if rest:
                return (flex_block + "\n\n" + rest).strip()
            return flex_block

        text = "\n".join(chunks).strip()
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text

    def __getattr__(self, name: str) -> Any:
        return getattr(self.hot, name)
