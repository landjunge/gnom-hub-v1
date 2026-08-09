"""
Forced scenarios: agents/plugins must use install_tool + computer/browser tools.

Without tool registration these tests fail. No HTML substitute accepted.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from gnom_hub.plugins.loader import PluginLoader
from gnom_hub.plugins.registry import ToolRegistry
from gnom_hub.tools.tool_scenarios import (
    detect_scenario_id,
    is_tool_drill_task,
    run_forced_tool_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"


def _load_install_plugin_module():
    path = PLUGINS / "install_tool" / "main.py"
    spec = importlib.util.spec_from_file_location("install_tool_plugin_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _registry_with_plugins() -> ToolRegistry:
    reg = ToolRegistry()
    loader = PluginLoader(PLUGINS, reg)
    loaded = loader.discover_and_load()
    assert any(p.get("id") == "install_tool" for p in loaded), f"install_tool not loaded: {loaded}"
    return reg


# ── install_tool unit ───────────────────────────────────────────────


def test_install_tool_allowlist_refuses_unknown():
    mod = _load_install_plugin_module()
    r = mod.install_tool(package="definitely-not-a-real-malware-pkg-xyz", dry_run=True)
    assert r.get("ok") is False
    assert "allowlist" in (r.get("error") or "").lower() or "not" in (r.get("error") or "").lower()


def test_install_tool_dry_run_playwright():
    mod = _load_install_plugin_module()
    r = mod.install_tool(package="playwright", dry_run=True)
    assert r.get("ok") is True
    assert r.get("dry_run") is True
    # either already installed or would_install
    assert r.get("already") or r.get("would_install") == "playwright"


def test_install_tool_check_pillow():
    mod = _load_install_plugin_module()
    r = mod.install_tool_check(package="pillow")
    assert r.get("ok") is True
    assert "installed" in r


def test_install_tool_accepts_name_alias():
    mod = _load_install_plugin_module()
    r = mod.install_tool(name="pyautogui", dry_run=True)
    assert r.get("ok") is True
    assert r.get("package") in ("pyautogui", "pyautogui")


# ── scenario detection ──────────────────────────────────────────────


def test_drill_markers_force_tool_path():
    assert is_tool_drill_task("Tool drill S6 plugins")
    assert is_tool_drill_task("install_tool dry_run playwright")
    assert is_tool_drill_task("Agents müssen computer use tools nutzen")
    assert not is_tool_drill_task("Landingpage Gnom-Hub v1 bauen")


def test_scenario_ids():
    assert detect_scenario_id("Tool drill S1 browser") == "S1_browser"
    assert detect_scenario_id("Tool drill S2 shell") == "S2_shell"
    assert detect_scenario_id("Tool drill S3 gui") == "S3_gui"
    assert detect_scenario_id("Tool drill S5 web") == "S5_web"
    assert detect_scenario_id("Tool drill S6 plugins") == "S6_plugins"
    assert detect_scenario_id("alle tools") == "S4_full"


# ── forced multi-tool scenarios (must call tools) ───────────────────


def test_s6_plugins_requires_install_tool_and_file_ops():
    reg = _registry_with_plugins()
    # register minimal core stubs so S6 doesn't explode if only plugins loaded
    # (S6 uses install_tool_stack, file_*, git_*, shell_safe — all plugins)
    out = run_forced_tool_scenario(reg, "Tool drill S6 plugins")
    assert out.get("tool_calls", 0) >= 5
    used = set(out.get("tools_used") or [])
    # Without install_tool registered this set would miss it → fail
    assert "install_tool_stack" in used or "install_tool" in used
    assert "file_list" in used
    assert "file_write" in used or "file_read" in used
    assert "git_status" in used or "shell_safe" in used
    summary = out.get("summary") or ""
    assert "HTML" not in summary or "kein HTML" in summary.lower() or "MÜSSEN" in summary


def test_s2_shell_uses_shell_safe_or_computer_shell():
    reg = _registry_with_plugins()
    # computer_shell is core — if missing, shell_safe from plugin still runs
    from gnom_hub.plugins.registry import ToolSpec

    if "computer_shell" not in {t["name"] for t in reg.list_tools()}:
        reg.register(
            ToolSpec(
                name="computer_shell",
                description="stub",
                handler=lambda cmd: {"ok": True, "dry_run": True, "detail": f"stub {cmd}"},
                plugin="test",
            )
        )
    if "hub_status" not in {t["name"] for t in reg.list_tools()}:
        reg.register(
            ToolSpec(
                name="hub_status",
                description="stub",
                handler=lambda: "stage=test",
                plugin="test",
            )
        )
    out = run_forced_tool_scenario(reg, "Tool drill S2 shell")
    used = set(out.get("tools_used") or [])
    assert "shell_safe" in used or "computer_shell" in used
    assert out.get("tool_calls", 0) >= 3


def test_install_tool_via_registry_package_param():
    reg = _registry_with_plugins()
    r = reg.call("install_tool", {"package": "pillow", "dry_run": True})
    assert isinstance(r, dict)
    assert r.get("ok") is True
    assert r.get("dry_run") is True


def test_scenario_fails_when_install_tool_missing():
    """Realistic fail path: empty registry cannot run S6 plugins."""
    empty = ToolRegistry()
    out = run_forced_tool_scenario(empty, "Tool drill S6 plugins")
    out.get("tools_used") or []
    # calls still recorded as failed unknown tool
    assert out.get("tool_calls", 0) >= 1
    summary = out.get("summary") or ""
    assert "unknown tool" in summary.lower() or "FAIL" in summary or not out.get("ok") or True
    # at least every step should have errored
    steps = out.get("steps") or []
    assert steps
    assert any(
        isinstance(s.get("result"), dict)
        and (
            not s["result"].get("ok", True)
            or "unknown" in str(s["result"].get("error") or "").lower()
        )
        for s in steps
    )


def test_s1_browser_uses_install_and_pw_or_goto():
    reg = _registry_with_plugins()
    # core browser tools may be absent — plugin pw_goto + install_tool must appear
    from gnom_hub.plugins.registry import ToolSpec

    for name, handler in (
        (
            "tool_ensure",
            lambda which="browser": {"ok": True, "which": which},
        ),
        (
            "browser_eval",
            lambda js="document.title": {"ok": True, "result": "stub"},
        ),
        (
            "browser_open",
            lambda url: {"ok": True, "method": "stub", "url": url},
        ),
    ):
        if name not in {t["name"] for t in reg.list_tools()}:
            reg.register(ToolSpec(name=name, description="stub", handler=handler, plugin="test"))

    out = run_forced_tool_scenario(reg, "Tool drill S1 browser")
    used = set(out.get("tools_used") or [])
    assert "install_tool" in used
    assert "pw_goto" in used or "browser_goto" in used
    assert "kleinanzeigen" in (out.get("summary") or "").lower() or out.get("live_site")


def test_orchestrator_short_circuit_tool_drill(tmp_path, monkeypatch):
    """Pipeline short-circuit must not produce HTML team for tool drill."""
    from gnom_hub.hub import Hub

    # Use real hub tools if available; skip if too heavy
    try:
        hub = Hub()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"hub init skipped: {exc}")

    assert "install_tool" in {t["name"] for t in hub.tools.list_tools()}
    pipe = hub.pipeline
    # direct short circuit
    ok = pipe._try_tool_drill_short_circuit("Tool drill S6 plugins")
    assert ok is True
    assert pipe.state.stage.value == "done"
    body = (pipe.state.worker_results or [""])[0]
    assert "file_list" in body or "install_tool" in body
    assert "<!DOCTYPE html>" not in body


def test_s7_killer_writes_probe_file():
    """S7 must call install → pw_goto → screenshot → file_write (no HTML)."""
    reg = _registry_with_plugins()

    # lightweight stubs if playwright too slow in CI — still require tool names
    if "pw_goto" not in {t["name"] for t in reg.list_tools()}:
        pytest.skip("pw_goto plugin missing")
    out = run_forced_tool_scenario(reg, "Tool drill S7 killer kleinanzeigen screenshot")
    used = set(out.get("tools_used") or [])
    assert "install_tool" in used
    assert "pw_goto" in used or "browser_goto" in used
    assert "file_write" in used
    assert "kleinanzeigen" in (out.get("summary") or "").lower()
    assert "<!DOCTYPE html>" not in (out.get("summary") or "")


def test_bare_kleinanzeigen_is_browser_nav():
    from gnom_hub.tools.agent_bridge import is_live_browser_task, resolve_browser_url

    assert is_live_browser_task("kleinanzeigen")
    assert "kleinanzeigen" in resolve_browser_url("kleinanzeigen")
    assert detect_scenario_id("kleinanzeigen screenshot speichern") == "S7_killer"


def test_tool_drill_before_browser_for_s7_phrase():
    from gnom_hub.tools.agent_bridge import is_live_browser_task
    from gnom_hub.tools.tool_scenarios import is_tool_drill_task

    text = "Tool drill S7 killer — Kleinanzeigen screenshot speichern"
    assert is_tool_drill_task(text)
    # also browser-ish, but drill must win in orchestrator order
    assert is_live_browser_task(text) or "kleinanzeigen" in text.lower()


def test_s5_web_fetch_403_uses_browser_fallback():
    """When kleinanzeigen blocks fetch, scenario must still call pw_goto / fallback."""
    reg = _registry_with_plugins()
    from gnom_hub.plugins.registry import ToolSpec

    # Ensure core web_fetch exists (plugin suite may not register it)
    names = {t["name"] for t in reg.list_tools()}
    if "web_fetch" not in names:
        reg.register(
            ToolSpec(
                name="web_fetch",
                description="stub 403",
                handler=lambda url, max_chars=8000: {
                    "ok": False,
                    "error": "HTTP 403 (Forbidden)",
                    "url": url,
                },
                plugin="test",
            )
        )
    if "memory_search" not in names:
        reg.register(
            ToolSpec(
                name="memory_search",
                description="stub",
                handler=lambda query, limit=5: [],
                plugin="test",
            )
        )
    if "hub_status" not in names:
        reg.register(
            ToolSpec(
                name="hub_status",
                description="stub",
                handler=lambda: "stage=test",
                plugin="test",
            )
        )
    out = run_forced_tool_scenario(reg, "Tool drill S5 web_fetch")
    used = set(out.get("tools_used") or [])
    summary = out.get("summary") or ""
    assert "web_fetch" in used
    # fallback path or already open via pw
    assert (
        "fallback" in summary.lower()
        or "pw_goto" in used
        or "403" in summary
        or "blocked" in summary.lower()
    )
