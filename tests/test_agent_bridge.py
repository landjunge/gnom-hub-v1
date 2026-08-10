"""Agent tool bridge: browser heuristic, TOOL_CALL parse, catalog."""

from __future__ import annotations

from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.tools.agent_bridge import (
    format_tool_catalog,
    is_live_browser_task,
    parse_tool_calls,
    resolve_browser_url,
    run_tool_loop,
    strip_tool_calls,
    try_browser_nav_execute,
)


def test_is_live_browser_positive():
    assert is_live_browser_task("kleinanzeigen")
    assert is_live_browser_task("https://example.com")
    assert is_live_browser_task("öffne https://x.ai im browser")


def test_is_live_browser_negative_content_for_page():
    assert not is_live_browser_task("Need https://example.org/x for the page")
    assert not is_live_browser_task(
        "Fetch https://example.com/docs and summarize for a landing page."
    )
    assert not is_live_browser_task("Landingpage Gnom-Hub v1 mit HTML")


def test_resolve_browser_url_known_site():
    assert "kleinanzeigen" in resolve_browser_url("kleinanzeigen")


def test_parse_tool_calls_json():
    calls = parse_tool_calls('Thinking...\nTOOL_CALL web_fetch={"url":"https://example.com"}\nDone')
    assert calls == [("web_fetch", {"url": "https://example.com"})]


def test_strip_tool_calls():
    text = 'TOOL_CALL shell_safe={"cmd":"pwd"}\nresult follows'
    assert "TOOL_CALL" not in strip_tool_calls(text)
    assert "result follows" in strip_tool_calls(text)


def test_format_tool_catalog_and_loop():
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="hub_status",
            description="status",
            handler=lambda: {"ok": True, "status": "up"},
            plugin="core",
        )
    )
    cat = format_tool_catalog(tools, names=["hub_status"])
    assert "hub_status" in cat
    assert "TOOL_CALL" in cat

    asks = {"n": 0}

    def ask_fn(system, user, max_tokens=None, temperature=0.45):
        asks["n"] += 1
        if asks["n"] == 1:
            return "TOOL_CALL hub_status={}"
        return "STATUS_OK final"

    out = run_tool_loop(
        ask_fn=ask_fn,
        system="sys",
        user="user",
        tools=tools,
        tool_names=["hub_status"],
        max_rounds=3,
    )
    assert "STATUS_OK" in out or "final" in out


def test_try_browser_nav_execute_mock():
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="browser_open",
            description="open",
            handler=lambda url="": {"ok": True, "url": url, "title": "mock"},
            plugin="core",
        )
    )
    nav = try_browser_nav_execute(
        tools=tools,
        user_text="navigiere zu https://example.com",
        bus=None,
    )
    assert nav is not None
    assert nav.get("ok") is True or "example.com" in str(nav)
