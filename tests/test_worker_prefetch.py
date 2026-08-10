"""Worker tool prefetch: plan, budgets, design, workspace, web_fetch, memory."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.core.event_bus import EventBus
from gnom_hub.memory.facade import MemoryFacade
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.memory.warm import WarmMemory
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.tools.worker_prefetch import (
    PrefetchReport,
    default_max_tool_calls,
    extract_urls,
    extract_workspace_files,
    plan_prefetch,
    prefetch_for_workers,
    tool_calls_needed,
    wants_design_tools,
)


def test_tool_calls_needed_detects_url_and_memory():
    assert "web_fetch" in tool_calls_needed("see https://example.com/x")
    assert "memory_search" in tool_calls_needed("always dark theme please")
    assert tool_calls_needed("plain hello") == []


def test_plan_prefetch_html_order():
    plan = plan_prefetch("Build HTML landing https://docs.example.com/a always dark")
    names = [s.name for s in plan]
    assert "color_palette" in names
    assert "html_scaffold" in names
    assert "web_fetch" in names
    assert "memory_search" in names
    # design before net before memory by priority
    assert names.index("color_palette") < names.index("web_fetch")
    assert names.index("web_fetch") < names.index("memory_search")


def test_extract_urls_ranks_docs():
    blob = "see https://spam.example.com/x?utm_source=1 and https://docs.example.com/guide"
    urls = extract_urls(blob, max_urls=2)
    assert urls[0].startswith("https://docs.example.com")


def test_extract_workspace_files():
    files = extract_workspace_files("update index.html and styles.css please")
    assert "index.html" in files
    assert "styles.css" in files


def test_default_max_tool_calls():
    assert default_max_tool_calls("plain text task") == 6
    assert default_max_tool_calls("HTML landing page") == 8
    assert wants_design_tools("Startseite mit Formular")


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
    assert "[prefetch]" in ctx
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


def test_packages_needed_playwright():
    from gnom_hub.tools.worker_prefetch import packages_needed, tool_calls_needed

    assert "playwright" in packages_needed("use playwright for browser e2e")
    assert "install_tool:playwright" in tool_calls_needed("need playwright chromium")


def test_prefetch_install_tool_dry_then_install():
    bus = EventBus()
    events: list[dict] = []
    bus.on("pipeline.tool_call", lambda d: events.append(d if isinstance(d, dict) else {}))

    calls: list[dict] = []

    def fake_install(package: str = "", dry_run: bool = False):
        calls.append({"package": package, "dry_run": dry_run})
        if dry_run:
            return {
                "ok": True,
                "package": package,
                "already_installed": False,
                "dry_run": True,
                "message": f"would install {package}",
            }
        return {
            "ok": True,
            "package": package,
            "already_installed": True,
            "dry_run": False,
            "message": f"installed {package}",
        }

    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="install_tool",
            description="install",
            handler=fake_install,
            plugin="core",
        )
    )
    ctx = prefetch_for_workers(
        "Please install playwright for e2e checks",
        bus=bus,
        tools=tools,
        memory=None,
        max_tool_calls=5,
    )
    assert "install_tool" in ctx or "playwright" in ctx
    assert any(c["dry_run"] is True for c in calls)
    assert any(c["dry_run"] is False for c in calls)
    names = [e.get("name") for e in events]
    assert names.count("install_tool") >= 2


def test_prefetch_skips_install_if_already_there():
    bus = EventBus()
    events: list[dict] = []
    bus.on("pipeline.tool_call", lambda d: events.append(d if isinstance(d, dict) else {}))
    installs = {"n": 0}

    def fake_install(package: str = "", dry_run: bool = False):
        if not dry_run:
            installs["n"] += 1
        return {
            "ok": True,
            "package": package,
            "already_installed": True,
            "dry_run": dry_run,
            "message": "already",
        }

    tools = ToolRegistry()
    tools.register(
        ToolSpec(name="install_tool", description="i", handler=fake_install, plugin="core")
    )
    prefetch_for_workers(
        "playwright browser e2e",
        bus=bus,
        tools=tools,
        max_tool_calls=5,
    )
    assert installs["n"] == 0
    assert any(e.get("name") == "install_tool" for e in events)


def test_prefetch_design_and_report():
    bus = EventBus()
    tools = ToolRegistry()

    def palette(seed: str = "dark", count: int = 5):
        return {
            "ok": True,
            "primary": "#5b8def",
            "accent": "#7c3aed",
            "surface": "#0f172a",
            "text": "#e6edf3",
            "css": ":root { --color-primary: #5b8def; }\n",
        }

    def scaffold(kind: str = "landing", title: str = "Page", seed: str = "dark"):
        return {"ok": True, "kind": kind, "html": "<!DOCTYPE html><html></html>"}

    def contrast(fg: str = "", bg: str = ""):
        return {"ok": True, "ratio": 12.0, "grade": "AAA", "aa_normal": True}

    def tokens(seed: str = "dark"):
        return {"ok": True, "css": ":root { --space-4: 1rem; }\n"}

    tools.register(ToolSpec(name="color_palette", description="p", handler=palette, plugin="d"))
    tools.register(ToolSpec(name="html_scaffold", description="s", handler=scaffold, plugin="d"))
    tools.register(ToolSpec(name="contrast_check", description="c", handler=contrast, plugin="d"))
    tools.register(ToolSpec(name="css_tokens", description="t", handler=tokens, plugin="d"))

    rep = prefetch_for_workers(
        "HTML landing page ocean",
        bus=bus,
        tools=tools,
        return_report=True,
    )
    assert isinstance(rep, PrefetchReport)
    assert "color_palette" in rep.executed
    assert "html_scaffold" in rep.executed
    assert "contrast_check" in rep.executed
    assert rep.calls_used >= 3
    assert "[prefetch]" in rep.context
    assert "color_palette" in rep.context


def test_prefetch_workspace_read():
    tools = ToolRegistry()

    def read_ws(name: str = "", zone: str = "temp", max_chars: int = 4000):
        if name == "index.html" and zone == "temp":
            return {"ok": True, "name": name, "zone": zone, "text": "<h1>Existing</h1>"}
        return {"ok": False, "error": "not found"}

    tools.register(ToolSpec(name="workspace_read", description="r", handler=read_ws, plugin="core"))
    ctx = prefetch_for_workers("Please improve index.html layout", tools=tools)
    assert "workspace_read" in ctx
    assert "Existing" in ctx


def test_prefetch_context_char_budget():
    tools = ToolRegistry()

    def big_fetch(url: str, max_chars: int = 8000):
        return {"ok": True, "url": url, "text": "X" * 5000}

    tools.register(ToolSpec(name="web_fetch", description="f", handler=big_fetch, plugin="core"))
    ctx = prefetch_for_workers(
        "https://a.example.com/1 https://b.example.com/2 https://c.example.com/3",
        tools=tools,
        max_tool_calls=3,
        max_urls=3,
        max_context_chars=800,
    )
    assert len(ctx) <= 900  # header + truncated
    assert "truncated" in ctx or len(ctx) < 850
