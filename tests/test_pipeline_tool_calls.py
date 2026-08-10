"""URL task must leave tool_calls on pipeline state + bus events."""

from __future__ import annotations

from gnom_hub.core.event_bus import EventBus
from gnom_hub.hub import Hub
from gnom_hub.pipeline import Pipeline
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec


def _mock_web_fetch_registry() -> ToolRegistry:
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="web_fetch",
            description="fetch",
            handler=lambda url, max_chars=2500: {
                "ok": True,
                "url": url,
                "text": "hello from mock fetch",
                "status": 200,
            },
            plugin="core",
        )
    )
    return tools


def test_execute_url_task_records_web_fetch_tool_call():
    bus = EventBus()
    events: list[dict] = []
    bus.on("pipeline.tool_call", lambda d: events.append(d if isinstance(d, dict) else {}))

    tools = _mock_web_fetch_registry()
    pipe = Pipeline(bus)
    pipe.tools = tools
    pipe.brainstorm_turn("Fetch https://example.com/docs and summarize for a landing page.")
    st = pipe.execute()
    assert st.stage.value == "done"
    names = [e.get("name") for e in events]
    assert "web_fetch" in names, names
    assert any(c.get("name") == "web_fetch" for c in (st.tool_calls or [])), st.tool_calls
    assert len(st.tool_calls) >= 1


def test_hub_status_includes_auth_fields():
    h = Hub()
    text = h._status_text()
    assert "auth_sys=" in text
    assert "tool_calls=" in text
    assert "deepseek=" in text


def test_snapshot_exposes_tool_calls_for_ui():
    """UI Tools badge / history reads snapshot.pipeline.tool_calls."""
    h = Hub()
    tools = _mock_web_fetch_registry()
    # Prefetch uses pipeline.tools (and hub tools if wired the same)
    h.pipeline.tools = tools
    if hasattr(h, "tools"):
        h.tools = tools
    h.pipeline.brainstorm_turn("Need https://example.org/x for the page")
    st = h.pipeline.execute()
    assert any(c.get("name") == "web_fetch" for c in (st.tool_calls or [])), st.tool_calls
    snap = h.snapshot()
    pipe = snap.get("pipeline") or {}
    calls = pipe.get("tool_calls") or []
    assert any(c.get("name") == "web_fetch" for c in calls), calls
    assert all("ok" in c for c in calls)
