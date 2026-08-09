"""Worker tool prefetch: web_fetch + memory_search + pipeline.tool_call events."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.core.event_bus import EventBus
from gnom_hub.memory.facade import MemoryFacade
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.memory.warm import WarmMemory
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.tools.worker_prefetch import prefetch_for_workers, tool_calls_needed


def test_tool_calls_needed_detects_url_and_memory():
    assert "web_fetch" in tool_calls_needed("see https://example.com/x")
    assert "memory_search" in tool_calls_needed("always dark theme please")
    assert tool_calls_needed("plain hello") == []


def test_prefetch_emits_memory_search_tool_call(tmp_path: Path):
    bus = EventBus()
    events: list[dict] = []
    bus.on("pipeline.tool_call", lambda d: events.append(d if isinstance(d, dict) else {}))

    hot = HotMemory(tmp_path, auto_load=False)
    warm = WarmMemory(tmp_path)
    vec = VectorStore(tmp_path)
    vec.add("User: always enable dark theme", meta={"source": "flex_wish"})
    mem = MemoryFacade(hot, warm, vec)

    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="memory_search",
            description="search",
            handler=lambda query, limit=5: vec.search(str(query), limit=int(limit)),
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            plugin="core",
        )
    )

    ctx = prefetch_for_workers(
        "Build landing with always dark theme preference",
        bus=bus,
        tools=tools,
        memory=mem,
    )
    assert "Memory search" in ctx or "dark theme" in ctx.lower()
    names = [e.get("name") for e in events]
    assert "memory_search" in names
    assert any(e.get("ok") for e in events if e.get("name") == "memory_search")


def test_prefetch_web_fetch_via_registry_mock():
    bus = EventBus()
    events: list[dict] = []
    bus.on("pipeline.tool_call", lambda d: events.append(d if isinstance(d, dict) else {}))

    tools = ToolRegistry()

    def fake_fetch(url: str, max_chars: int = 8000):
        return {"ok": True, "url": url, "text": "hello from mock " + url[:40]}

    tools.register(
        ToolSpec(
            name="web_fetch",
            description="fetch",
            handler=fake_fetch,
            input_schema={"type": "object", "properties": {"url": {"type": "string"}}},
            plugin="core",
        )
    )
    ctx = prefetch_for_workers(
        "Read https://example.com/page for copy",
        bus=bus,
        tools=tools,
        memory=None,
    )
    assert "hello from mock" in ctx
    assert any(e.get("name") == "web_fetch" and e.get("ok") for e in events)


def test_prefetch_respects_max_tool_calls(tmp_path: Path):
    bus = EventBus()
    n = {"c": 0}

    def counting_fetch(url: str, max_chars: int = 8000):
        n["c"] += 1
        return {"ok": True, "url": url, "text": "x"}

    tools = ToolRegistry()
    tools.register(
        ToolSpec(name="web_fetch", description="f", handler=counting_fetch, plugin="core")
    )
    blob = " ".join(f"https://example.com/p{i}" for i in range(10))
    prefetch_for_workers(blob, bus=bus, tools=tools, max_tool_calls=2, max_urls=10)
    assert n["c"] == 2
