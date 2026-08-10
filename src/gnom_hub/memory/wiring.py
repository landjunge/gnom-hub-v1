"""Bus → HOT/WARM/vector memory wiring (extracted from Hub — pure move)."""

from __future__ import annotations

from typing import Any


class MemoryWiringMixin:
    """Mixin: expects Hub bus, hot, warm, vectors, trace helpers."""

    def _wire_memory(self) -> None:
        def on_memory_hint(data: Any) -> None:
            if not isinstance(data, dict):
                return
            from gnom_hub.agents.roles_helpers import _is_flex_meta_requirement, _is_garbage_fact

            user_text = str(data.get("user_text") or "").strip()
            if user_text:
                self.hot.add_message("user", user_text[:500])
            notes = str(data.get("brainstorm_notes") or "").strip()
            if notes:
                self.hot.add_message("brainstorm", notes[:800])
            flex = str(data.get("flex_notes") or "").strip()
            if flex:
                self.hot.add_message("flex", flex[:500])
            # HOT: clean requirements only — never HTML / meta
            for req in (data.get("requirements") or [])[:5]:
                text = str(req).strip()
                if (
                    8 <= len(text) <= 160
                    and not _is_flex_meta_requirement(text)
                    and not _is_garbage_fact(text)
                ):
                    self.hot.add_fact(text)
                    self.vectors.add(text, meta={"source": "requirement"})
            # Goal lines are durable (WARM)
            for req in data.get("requirements") or []:
                text = str(req).strip()
                low = text.lower()
                if low.startswith(("ziel:", "goal:")):
                    if 8 <= len(text) <= 160 and not _is_garbage_fact(text):
                        self.warm.add_fact(text)
                        self.vectors.add(text, meta={"source": "goal"})
                    break
            # Worker outputs: short text notes only — never code/HTML bodies
            for res in (data.get("results") or [])[:2]:
                snippet = str(res).strip()
                if "```" in snippet:
                    snippet = snippet.split("```", 1)[0].strip()
                snippet = snippet[:280]
                if (
                    snippet
                    and len(snippet) >= 20
                    and not _is_garbage_fact(snippet)
                    and not snippet.lstrip().startswith("<")
                ):
                    self.hot.add_message("worker", snippet)
            self.hot.save()

        def on_error(data: Any) -> None:
            if isinstance(data, dict):
                self.last_error = str(data.get("error") or "pipeline error")
            else:
                self.last_error = str(data)

        def on_memory_curated(data: Any) -> None:
            """LLM-extracted durable facts from Memory agent → WARM (+ HOT mirror)."""
            if not isinstance(data, dict):
                return
            from gnom_hub.agents.roles_helpers import _is_garbage_fact

            for fact in data.get("facts") or []:
                text = str(fact).strip()
                if 8 <= len(text) <= 200 and not _is_garbage_fact(text):
                    self.hot.add_fact(text)
                    self.warm.add_fact(text)
                    self.vectors.add(text, meta={"source": "memory_agent"})
            self.hot.save()

        def on_done(_data: Any) -> None:
            # Scrub + compress after each successful pipeline finish
            try:
                self.hot.scrub_facts()
                self.hot.compress_if_needed()
                self.hot.save()
            except Exception as exc:  # noqa: BLE001
                self._append_trace("compress.error", {"error": str(exc)})

        def on_flex_facts(data: Any) -> None:
            """Flex wishes → durable WARM (source=flex), ADD-only, trim-protected."""
            if not isinstance(data, dict):
                return
            from gnom_hub.agents.roles_helpers import _is_garbage_fact
            from gnom_hub.memory.dedupe import prefer_canonical_wish

            for fact in data.get("facts") or []:
                text = " ".join(str(fact).split()).strip()
                if not text:
                    continue
                text = prefer_canonical_wish(text) or text
                if not text.lower().startswith(("user:", "wish:")):
                    text = "User: " + text
                if 12 <= len(text) <= 200 and not _is_garbage_fact(text):
                    # source=flex → warm_trim keeps these until non-flex exhausted
                    # add_fact(source=flex) core-dedupes prefix variants
                    self.warm.add_fact(text, source="flex")
                    self.hot.add_fact(text)
                    self.vectors.add(text, meta={"source": "flex_wish"})
            self.hot.save()

        self.bus.on("pipeline.memory_hint", on_memory_hint)
        self.bus.on("pipeline.memory_curated", on_memory_curated)
        self.bus.on("pipeline.flex_facts", on_flex_facts)
        self.bus.on("pipeline.error", on_error)
        self.bus.on("pipeline.done", on_done)
