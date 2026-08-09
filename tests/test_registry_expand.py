"""Expanded ToolRegistry + new core tools."""

from __future__ import annotations

import pytest

from gnom_hub.hub import Hub
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.plugins.retry import ToolFailed


def test_registry_has_get_names_len():
    reg = ToolRegistry()
    assert len(reg) == 0
    reg.register(
        ToolSpec(name="a", description="A", handler=lambda: 1, tags=("hub",)),
    )
    assert reg.has("a")
    assert reg.get("a") is not None
    assert reg.names() == ["a"]
    assert len(reg) == 1


def test_registry_list_tools_tag_filter():
    reg = ToolRegistry()
    reg.register(ToolSpec(name="x", description="x", handler=lambda: None, tags=("net",)))
    reg.register(ToolSpec(name="y", description="y", handler=lambda: None, tags=("hub",)))
    assert [t["name"] for t in reg.list_tools(tag="hub")] == ["y"]


def test_registry_unknown_tool_lists_available():
    reg = ToolRegistry()
    reg.register(ToolSpec(name="known", description="k", handler=lambda: 1))
    with pytest.raises(KeyError, match="Available: known"):
        reg.call("nope", {})


def test_registry_required_args():
    reg = ToolRegistry()
    reg.register(
        ToolSpec(
            name="need_q",
            description="q",
            handler=lambda query: query,
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )
    )
    with pytest.raises(ToolFailed, match="missing required"):
        reg.call("need_q", {})
    assert reg.call("need_q", {"query": "hi"}) == "hi"


def test_unregister_core_needs_force():
    reg = ToolRegistry()
    reg.register(ToolSpec(name="c", description="c", handler=lambda: 1, plugin="core"))
    assert reg.unregister("c") is False
    assert reg.has("c")
    assert reg.unregister("c", force=True) is True


def test_hub_core_tools_expanded():
    h = Hub()
    names = set(h.tools.names())
    for n in (
        "hub_status",
        "tools_list",
        "memory_search",
        "pipeline_do",
        "pipeline_info",
        "web_fetch",
        "workspace_list",
        "workspace_read",
        "trace_tail",
    ):
        assert n in names, names
    listed = h.tools.call("tools_list", {})
    assert listed["ok"] is True
    assert listed["count"] >= 8
    info = h.tools.call("pipeline_info", {})
    assert info["ok"] is True
    assert "stage" in info
    wl = h.tools.call("workspace_list", {"zone": "temp"})
    assert wl["ok"] is True
    # write + read
    h.workspace.write_text("temp", "tool_reg_probe.txt", "hello-registry")
    rd = h.tools.call(
        "workspace_read",
        {"name": "tool_reg_probe.txt", "zone": "temp", "max_chars": 100},
    )
    assert rd["ok"] is True
    assert "hello-registry" in rd["text"]
    tail = h.tools.call("trace_tail", {"limit": 5})
    assert tail["ok"] is True
    st = h.tools.call("hub_status", {})
    assert "tools=" in st


def test_tools_list_tag_filter_via_hub():
    h = Hub()
    only = h.tools.call("tools_list", {"tag": "workspace"})
    names = {t["name"] for t in only["tools"]}
    assert "workspace_list" in names
    assert "web_fetch" not in names
