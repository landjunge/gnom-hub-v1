"""
Forced tool-use scenarios for agents.

When the user asks for a tool drill / agent tool test, we do NOT invent HTML —
we run real tools and report results. Workers must use the same tools via
TOOL_CALL; the orchestrator may short-circuit with run_forced_tool_scenario.

Live target for browser/web tools: Kleinanzeigen (not example.com).
"""

from __future__ import annotations

import re
from typing import Any

# Primary live site for browser/fetch drills (user preference)
LIVE_SITE = "https://www.kleinanzeigen.de"
LIVE_SITE_LABEL = "kleinanzeigen.de"

_DRILL_MARKERS = (
    "tool drill",
    "tools drill",
    "tool test",
    "tools test",
    "tool-szenario",
    "toolszenario",
    "tool szenario",
    "agent tool",
    "agents tools",
    "nutze tools",
    "tools nutzen",
    "tools verwenden",
    "tools einsetzen",
    "use tools",
    "using tools",
    "playwright",
    "playwright test",
    "computer use",
    "computer-use",
    "computer use test",
    "gui test",
    "gui test agent",
    "shell tool",
    "shell tool test",
    "terminal tool",
    "maus und tastatur",
    "mouse and keyboard",
    "screenshot machen",
    "bildschirm lesen",
    "toolpflicht",
    "tool pflicht",
    "force tools",
    "forced tools",
    "workflow tool",
    "pipeline tool test",
    "teste die tools",
    "test die tools",
    "tools testen",
    "agenten tools",
    "agents brauchen tools",
    "wirkliche tools",
    "echte tools",
    "andere tools",
    "alle tools",
    "web fetch",
    "web_fetch",
    "plugin tools",
    "plugins test",
    "file_ops",
    "git_ops",
    "install_tool",
    "shell_safe",
    "pw_goto",
    "screenshot vom bildschirm",
    "bildschirm lesen",
    "was ist auf dem screen",
    "was ist auf dem bildschirm",
    "maus klicken",
    "shell ausführen",
    "terminal befehl",
    "installiere playwright",
    "git status im hub",
    "liste dateien",
)


def is_tool_drill_task(text: str) -> bool:
    low = (text or "").lower()
    if not low.strip():
        return False
    # pure HTML build must not become tool drill
    if any(
        k in low
        for k in (
            "landingpage",
            "landing page",
            "baue eine seite",
            "html seite",
            "website bauen",
        )
    ) and not any(m in low for m in ("tool", "playwright", "shell", "gui", "computer", "fetch")):
        return False
    if any(m in low for m in _DRILL_MARKERS):
        return True
    # explicit scenario ids
    if re.search(r"\bS[1-7]\b", text or "") and (
        "tool" in low
        or "shell" in low
        or "gui" in low
        or "browser" in low
        or "fetch" in low
        or "kleinanzeigen" in low
        or "flow" in low
    ):
        return True
    # Killer flow phrasing without S7 id
    return bool(
        "kleinanzeigen" in low
        and any(k in low for k in ("screenshot", "speichern", "flow", "probe", "durchlauf"))
    )


def detect_scenario_id(text: str) -> str:
    """
    S1 browser · S2 shell · S3 gui · S4 full · S5 web · S6 plugins · S7 killer · default full
    """
    low = (text or "").lower()
    if (
        re.search(r"\bs7\b", low)
        or "killer" in low
        or (
            "kleinanzeigen" in low
            and any(k in low for k in ("screenshot", "speichern", "flow", "probe", "durchlauf"))
        )
    ):
        return "S7_killer"
    if re.search(r"\bs1\b", low) or "nur browser" in low or "playwright only" in low:
        return "S1_browser"
    if re.search(r"\bs2\b", low) or "nur shell" in low or "terminal only" in low:
        return "S2_shell"
    if re.search(r"\bs3\b", low) or "nur gui" in low or "mouse" in low or "screenshot only" in low:
        return "S3_gui"
    if (
        re.search(r"\bs5\b", low)
        or "web fetch" in low
        or "web_fetch" in low
        or "nur fetch" in low
        or "nur web" in low
    ):
        return "S5_web"
    if (
        re.search(r"\bs6\b", low)
        or "plugin tools" in low
        or "plugins test" in low
        or "file_ops" in low
        or "git_ops" in low
        or "install_tool" in low
        or "shell_safe" in low
    ):
        return "S6_plugins"
    if (
        re.search(r"\bs4\b", low)
        or "full" in low
        or "komplett" in low
        or "alle tools" in low
        or "andere tools" in low
    ):
        return "S4_full"
    return "S4_full"


def _short(val: Any, n: int = 120) -> str:
    s = str(val if val is not None else "")
    return s if len(s) <= n else s[: n - 1] + "…"


def run_forced_tool_scenario(
    tools: Any,
    user_text: str,
    *,
    bus: Any | None = None,
) -> dict[str, Any]:
    """
    Execute a concrete multi-tool scenario. Returns summary for worker box.
    """
    if tools is None:
        return {"ok": False, "error": "no tools registry", "summary": "Keine ToolRegistry."}

    sid = detect_scenario_id(user_text)
    steps: list[dict[str, Any]] = []
    ok_all = True

    def _cancelled() -> bool:
        try:
            from gnom_hub.tools.agent_bridge import _pipeline_cancel_requested

            return bool(_pipeline_cancel_requested())
        except Exception:  # noqa: BLE001
            return False

    def call(name: str, args: dict | None = None) -> dict[str, Any]:
        nonlocal ok_all
        from gnom_hub.tools.agent_bridge import call_tool, label_tool_result

        if _cancelled():
            res = {
                "ok": False,
                "error": "cancelled",
                "mode": "error",
                "cancelled": True,
            }
            steps.append({"tool": name, "args": args or {}, "result": res, "mode": "error"})
            return res

        res = call_tool(tools, name, args or {})
        if not isinstance(res, dict):
            res = {"ok": True, "result": res, "mode": "live"}
        mode = res.get("mode") or label_tool_result(res)
        res["mode"] = mode
        # Site bot-blocks (403) are not scenario infrastructure failures
        err_s = str(res.get("error") or "")
        if "403" in err_s or "Forbidden" in err_s:
            res["site_blocked"] = True
            res["hint"] = "Site blocks bots — use browser/pw_goto instead of web_fetch"
            mode = "blocked"
            res["mode"] = mode
        elif not res.get("ok", True) and res.get("blocked") is not True:
            if not res.get("dry_run") and not res.get("blocked"):
                ok_all = False
        entry = {"tool": name, "args": args or {}, "result": res, "mode": mode}
        steps.append(entry)
        if bus is not None:
            try:
                bus.emit(
                    "pipeline.tool_call",
                    {
                        "agent": "tool_scenario",
                        "tool": name,
                        "args": args or {},
                        "ok": bool(res.get("ok", True)),
                        "mode": mode,
                        "scenario": sid,
                    },
                )
            except Exception:  # noqa: BLE001
                pass
        return res

    lines = [
        f"=== TOOL SCENARIO {sid} ===",
        "Agents MÜSSEN Tools nutzen — kein HTML-Ersatz.",
        f"Live-Ziel Browser/Web: {LIVE_SITE_LABEL}",
        "",
    ]

    # ── S7 killer: install → Kleinanzeigen → screenshot → file in data/ ─
    if sid == "S7_killer":
        r0 = call("install_tool", {"package": "playwright", "dry_run": True})
        lines.append(
            f"[S7] install_tool dry_run: ok={r0.get('ok')} mode={r0.get('mode')} "
            f"already={r0.get('already')}"
        )
        r1 = call(
            "install_tool",
            {"package": "playwright", "dry_run": False, "install_browsers": True},
        )
        lines.append(
            f"[S7] install_tool live: ok={r1.get('ok')} mode={r1.get('mode')} "
            f"already={r1.get('already')}"
        )
        r2 = call("pw_goto", {"url": LIVE_SITE})
        lines.append(
            f"[S7] pw_goto: ok={r2.get('ok')} mode={r2.get('mode')} "
            f"title={_short(r2.get('title'), 70)!r} status={r2.get('status')}"
        )
        r3 = call("pw_screenshot", {})
        shot = r3.get("path") or ""
        lines.append(f"[S7] pw_screenshot: ok={r3.get('ok')} mode={r3.get('mode')} path={shot}")
        note = (
            f"# Kleinanzeigen probe\n"
            f"- url: {LIVE_SITE}\n"
            f"- title: {r2.get('title')}\n"
            f"- status: {r2.get('status')}\n"
            f"- screenshot: {shot}\n"
            f"- mode_goto: {r2.get('mode')}\n"
        )
        r4 = call(
            "file_write",
            {
                "path": "data/computer_use/kleinanzeigen_probe.md",
                "content": note,
            },
        )
        lines.append(
            f"[S7] file_write(kleinanzeigen_probe.md): ok={r4.get('ok')} "
            f"mode={r4.get('mode')} path={r4.get('path')}"
        )
        r5 = call("file_read", {"path": "data/computer_use/kleinanzeigen_probe.md"})
        lines.append(
            f"[S7] file_read: ok={r5.get('ok')} chars={r5.get('chars')} "
            f"text={_short(r5.get('text'), 60)!r}"
        )
        if not (r2.get("ok") and r4.get("ok")):
            ok_all = False

    # ── S1 / S4: Playwright + browser stack (core + plugin) ─────────
    if sid in ("S1_browser", "S4_full"):
        # Plugin install_tool first (self-heal deps)
        # dry_run first (agents may probe), then real ensure
        r0d = call("install_tool", {"package": "playwright", "dry_run": True})
        lines.append(
            f"[browser] install_tool(playwright, dry_run): ok={r0d.get('ok')} "
            f"already={r0d.get('already')} would={r0d.get('would_install')}"
        )
        r0 = call(
            "install_tool",
            {"package": "playwright", "dry_run": False, "install_browsers": True},
        )
        lines.append(
            f"[browser] install_tool(playwright): ok={r0.get('ok')} already={r0.get('already')}"
        )
        r = call("tool_ensure", {"which": "browser"})
        lines.append(f"[browser] tool_ensure(browser): ok={r.get('ok')}")
        # Prefer plugin pw_* tools (must be used for drill to pass)
        r2 = call("pw_goto", {"url": LIVE_SITE})
        lines.append(
            f"[browser] pw_goto({LIVE_SITE_LABEL}): ok={r2.get('ok')} mode={r2.get('mode')} "
            f"title={_short(r2.get('title'), 80)!r} status={r2.get('status')}"
        )
        r3 = call("pw_screenshot", {})
        lines.append(
            f"[browser] pw_screenshot: ok={r3.get('ok')} mode={r3.get('mode')} "
            f"path={r3.get('path')}"
        )
        r4 = call("browser_eval", {"js": "document.title"})
        lines.append(
            f"[browser] browser_eval(document.title): ok={r4.get('ok')} "
            f"result={_short(r4.get('result'), 80)!r}"
        )
        r5 = call("browser_open", {"url": LIVE_SITE})
        lines.append(
            f"[browser] browser_open({LIVE_SITE_LABEL}): ok={r5.get('ok')} "
            f"method={r5.get('method')}"
        )

    # ── S2 / S4: shell (core + shell_safe plugin) ───────────────────
    if sid in ("S2_shell", "S4_full"):
        r_al = call("shell_safe_allowlist", {})
        lines.append(
            f"[shell] shell_safe_allowlist: god={r_al.get('god_mode')} n={len(r_al.get('allow') or [])}"
        )
        for cmd in ("pwd", "date", "uname", "whoami", "python3 -V"):
            r = call("shell_safe", {"cmd": cmd})
            out = (r.get("stdout") or r.get("detail") or "")[:100]
            lines.append(
                f"[shell] shell_safe({cmd}): ok={r.get('ok')} mode={r.get('mode')} "
                f"dry_run={r.get('dry_run')} out={out!r}"
            )
        r_ls = call("computer_shell", {"cmd": "ls data"})
        lines.append(
            f"[shell] computer_shell(ls data): ok={r_ls.get('ok')} "
            f"dry_run={r_ls.get('dry_run')} "
            f"stdout={_short(r_ls.get('stdout') or r_ls.get('detail'), 100)!r}"
        )
        r_hs = call("hub_status", {})
        lines.append(
            f"[shell] hub_status: "
            f"{_short(r_hs if not isinstance(r_hs, dict) else r_hs.get('result', r_hs), 140)}"
        )

    # ── S3 / S4: GUI / computer-use ─────────────────────────────────
    if sid in ("S3_gui", "S4_full"):
        r = call("tool_ensure", {"which": "gui"})
        lines.append(f"[gui] tool_ensure(gui): ok={r.get('ok')}")
        r2 = call("computer_inspect", {})
        lines.append(
            f"[gui] computer_inspect: ok={r2.get('ok')} blocked={r2.get('blocked')} "
            f"note={_short((r2.get('vision') or {}).get('teaching') or r2.get('error'), 80)!r}"
        )
        r3 = call("computer_click", {"x": 12, "y": 12})
        lines.append(
            f"[gui] computer_click(12,12): ok={r3.get('ok')} dry_run={r3.get('dry_run')} "
            f"detail={r3.get('detail')!r}"
        )
        r4 = call("computer_type", {"text": "gnom"})
        lines.append(
            f"[gui] computer_type('gnom'): ok={r4.get('ok')} dry_run={r4.get('dry_run')} "
            f"detail={r4.get('detail')!r}"
        )

    # ── S5 / S4: web_fetch + memory + status ────────────────────────
    if sid in ("S5_web", "S4_full"):
        r = call("web_fetch", {"url": LIVE_SITE, "max_chars": 1500})
        snippet = ""
        if isinstance(r, dict):
            snippet = _short(r.get("text") or r.get("error") or r, 100)
        lines.append(
            f"[web] web_fetch({LIVE_SITE_LABEL}): ok={r.get('ok') if isinstance(r, dict) else True} "
            f"mode={r.get('mode') if isinstance(r, dict) else '?'} snippet={snippet!r}"
        )
        # Kleinanzeigen often 403 for bots — prove fallback path still uses tools
        if isinstance(r, dict) and (
            not r.get("ok") or r.get("site_blocked") or "403" in str(r.get("error") or "")
        ):
            lines.append("[web] note: Kleinanzeigen blocks web_fetch (403) — fallback browser path")
            r_fb = call("pw_goto", {"url": LIVE_SITE})
            lines.append(
                f"[web] fallback pw_goto: ok={r_fb.get('ok')} mode={r_fb.get('mode')} "
                f"title={_short(r_fb.get('title'), 60)!r}"
            )
            r_fb2 = call("web_fetch", {"url": "https://example.com", "max_chars": 800})
            lines.append(
                f"[web] fallback web_fetch(example.com): ok={r_fb2.get('ok')} "
                f"mode={r_fb2.get('mode')} "
                f"snippet={_short((r_fb2.get('text') if isinstance(r_fb2, dict) else r_fb2), 60)!r}"
            )
        r2 = call("memory_search", {"query": "kleinanzeigen tools", "limit": 3})
        lines.append(f"[web] memory_search: {_short(r2, 120)!r}")
        r3 = call("hub_status", {})
        lines.append(
            f"[web] hub_status: {_short(r3 if not isinstance(r3, dict) else r3.get('result', r3), 120)}"
        )
        r4 = call("install_tool_check", {"package": "playwright"})
        lines.append(
            f"[web] install_tool_check(playwright): ok={r4.get('ok')} "
            f"installed={r4.get('installed')}"
        )
        r5 = call("install_tool", {"package": "beautifulsoup4", "dry_run": True})
        lines.append(
            f"[web] install_tool(bs4, dry_run): ok={r5.get('ok')} "
            f"would={r5.get('would_install')} already={r5.get('already')}"
        )

    # ── S6 / S4: plugin suite (must fail if plugins missing) ────────
    if sid in ("S6_plugins", "S4_full"):
        r_dry = call("install_tool", {"package": "pyautogui", "dry_run": True})
        lines.append(
            f"[plugin] install_tool(pyautogui, dry_run): ok={r_dry.get('ok')} "
            f"already={r_dry.get('already')} would={r_dry.get('would_install')}"
        )
        r = call("install_tool_stack", {"which": "gui", "dry_run": True})
        lines.append(f"[plugin] install_tool_stack(gui, dry_run): ok={r.get('ok')}")
        r = call("install_tool_stack", {"which": "all"})
        lines.append(f"[plugin] install_tool_stack(all): ok={r.get('ok')}")
        r2 = call("file_list", {"path": "data"})
        lines.append(f"[plugin] file_list(data): ok={r2.get('ok')} count={r2.get('count')}")
        r3 = call(
            "file_write",
            {
                "path": "data/computer_use/agent_plugin_probe.txt",
                "content": "gnom plugin probe\n",
            },
        )
        lines.append(f"[plugin] file_write(probe): ok={r3.get('ok')} path={r3.get('path')}")
        r4 = call("file_read", {"path": "data/computer_use/agent_plugin_probe.txt"})
        lines.append(
            f"[plugin] file_read(probe): ok={r4.get('ok')} text={_short(r4.get('text'), 40)!r}"
        )
        r5 = call("git_status", {})
        lines.append(
            f"[plugin] git_status: ok={r5.get('ok')} stdout={_short(r5.get('stdout'), 80)!r}"
        )
        r6 = call("git_diff", {"stat": True})
        lines.append(f"[plugin] git_diff(stat): ok={r6.get('ok')}")
        r7 = call("shell_safe", {"cmd": "pwd"})
        lines.append(f"[plugin] shell_safe(pwd): ok={r7.get('ok')} dry_run={r7.get('dry_run')}")
        # Fail scenario hard if plugin tools unknown (not registered)
        missing = [
            s["tool"]
            for s in steps
            if isinstance(s.get("result"), dict)
            and "unknown tool" in str(s["result"].get("error") or "").lower()
        ]
        if missing:
            ok_all = False
            lines.append(f"[plugin] FAIL missing tools: {missing}")

    lines.append("")
    lines.append(f"=== END {sid} overall_ok={ok_all} steps={len(steps)} ===")
    tools_used = sorted({s["tool"] for s in steps})
    lines.append(f"Tools used ({len(tools_used)}): {', '.join(tools_used)}")
    if not ok_all:
        lines.append(
            "Hinweis: God-Mode aus → Shell/GUI oft dry-run/blocked; "
            "Plugin-Tools müssen registriert sein (Reload plugins)."
        )

    summary = "\n".join(lines)
    return {
        "ok": True,
        "scenario": sid,
        "steps": steps,
        "summary": summary,
        "tool_calls": len(steps),
        "tools_used": tools_used,
        "live_site": LIVE_SITE,
    }


def tool_drill_worker_prompt() -> str:
    return (
        "TOOL DRILL MODE — you MUST use tools via TOOL_CALL lines.\n"
        "Do NOT write HTML. Do NOT invent results.\n"
        f"Live site for browser/web: {LIVE_SITE}\n"
        "Plugins (must exist): install_tool, pw_goto/pw_fill/pw_click/pw_screenshot, "
        "file_list/file_read/file_write, git_status/git_diff, shell_safe.\n"
        "Required tools depending on scenario:\n"
        "  S1: install_tool(playwright) → pw_goto(kleinanzeigen) → pw_screenshot → browser_eval\n"
        "  S2: shell_safe cmds + computer_shell + hub_status\n"
        "  S3: tool_ensure(gui) → computer_inspect → click → type\n"
        "  S5: web_fetch → memory_search → install_tool_check\n"
        "  S6 plugins: install_tool_stack → file_* → git_* → shell_safe\n"
        "  S7 killer: install_tool → pw_goto(kleinanzeigen) → pw_screenshot → "
        "file_write data/computer_use/kleinanzeigen_probe.md → file_read\n"
        "  S4 full: all of the above\n"
        "If a tool is missing: call install_tool first. Without tools the scenario FAILS.\n"
        "Always report mode=live|dry-run|blocked|error for each tool.\n"
    )
