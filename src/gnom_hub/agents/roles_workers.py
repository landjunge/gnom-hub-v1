"""Worker and Memory role agents."""

from __future__ import annotations

from typing import Any

from gnom_hub.agents.base import BaseAgent
from gnom_hub.agents.roles_helpers import (
    _is_flex_meta_requirement,
    _is_garbage_fact,
    _with_memory,
)
from gnom_hub.config.auth import user_message_for_failure
from gnom_hub.core.event_bus import EventBus

# ── Worker prompt layers (see docs/WORKER_PROMPTS.md) ─────────────────
# L0 HUB_IDENTITY is injected by BaseAgent.ask
# L1 Role contract
# L2 Priority / budget
# L3 Domain (HTML) rules
# L4 Flex wishes (absolute)
# L5 Tool protocol (prefetch + optional TOOL_CALL loop)

_WORKER_L1_ROLE = (
    "You are a Worker agent inside Gnom-Hub. "
    "Deliver a concrete useful result for the assigned task "
    "(plan, structure, checklist, draft, or full HTML when the task is a page/UI).\n"
    "Work on the USER task only. Match user language.\n"
    "If you cannot complete the task honestly (missing data, impossible constraint), "
    "start the body with FEHLER and explain — never invent a fake success stub."
)

_WORKER_L2_PRIORITY = (
    "PRIORITY ORDER (mandatory — do not reverse):\n"
    "  1) Complete structure / skeleton (always finish the file)\n"
    "  2) Core interactive behavior (JS/handlers, DOM updates)\n"
    "  3) Error/empty states for those core flows\n"
    "  4) CSS/styling LAST (max ~30% of effort; minimal layout first)\n"
    "Budget: ~70% functions+structure, ~30% styling. If near limit, "
    "CUT CSS — never omit </html> or core interactions."
)

_WORKER_L3_HTML = (
    "If HTML/landing/page/UI:\n"
    "  - ONE complete file: <!DOCTYPE html> ... </html>\n"
    "  - At least one real interaction "
    "(onclick= or addEventListener or form submit handler)\n"
    "  - Prefer working demo over pretty design\n"
    "  - DESIGN TOOLS (when present in Tool prefetch):\n"
    "      * Use color_palette CSS variables (--color-primary, --color-surface, …)\n"
    "      * Prefer html_scaffold structure as starting skeleton if provided\n"
    "      * Run contrast_check mentally: text on surface must stay readable\n"
    "      * Do NOT invent a second palette — reuse the prefetched one\n"
    "  - Without design prefetch: still use CSS variables and a dark-friendly default"
)

_WORKER_L4_WISHES = (
    "STANDING USER WISHES (Flex-wish / User: lines) are ABSOLUTE ORDERS:\n"
    "  - Implement them fully in the deliverable — no debate, no skip,\n"
    "    no 'optional', no 'if space allows'.\n"
    "  - Do not contradict, weaken, or postpone them.\n"
    "  - If a wish conflicts with decoration, drop decoration, keep the wish.\n"
    "  - Dark theme / language / always-rules must be visible in the result."
)

_WORKER_L5_TOOLS = (
    "TOOL PROTOCOL:\n"
    '  - The hub may inject a block "Tool prefetch (auto):" with real tool outputs '
    "(web_fetch, memory_search, install_tool, color_palette, html_scaffold, …).\n"
    "  - Treat that block as ground truth. Cite URLs/facts from it; do not contradict it.\n"
    "  - When tools are wired, you may also emit TOOL_CALL lines "
    "(browser_goto, computer_shell, install_tool, …) and use TOOL_RESULT replies.\n"
    "  - Never invent tool results. Never replace live tools with a fake HTML page.\n"
    "  - When install_tool reports a package installed, you may assume the import exists "
    "in later runtime (do not claim you ran the install)."
)


def worker_system_prompt(*, wants_html: bool = False) -> str:
    """Assemble layered worker system prompt (L1–L5)."""
    parts = [
        _WORKER_L1_ROLE,
        _WORKER_L2_PRIORITY,
        _WORKER_L4_WISHES,
        _WORKER_L5_TOOLS,
    ]
    if wants_html:
        parts.insert(2, _WORKER_L3_HTML)
    return "\n".join(parts)


def task_wants_html(*blobs: str) -> bool:
    text = "\n".join(blobs).lower()
    return any(
        k in text
        for k in (
            "html",
            "landing",
            "webpage",
            "web page",
            "css",
            "seite",
            "website",
            "frontend",
            "dashboard",
            "ui page",
            "web design",
        )
    )


# Tools workers may call (pipeline_do excluded — recursion risk)
_WORKER_TOOL_NAMES = [
    # core
    "browser_open",
    "browser_goto",
    "browser_screenshot",
    "browser_eval",
    "web_fetch",
    "memory_search",
    "hub_status",
    "computer_inspect",
    "computer_shell",
    "computer_type",
    "computer_click",
    "tool_ensure",
    "tool_ensure_package",
    "tool_scenario_run",
    # plugins (install_tool, playwright_browser, file_ops, git_ops, shell_safe)
    "install_tool",
    "install_tool_check",
    "install_tool_stack",
    "pw_goto",
    "pw_click",
    "pw_fill",
    "pw_screenshot",
    "file_list",
    "file_read",
    "file_write",
    "git_status",
    "git_diff",
    "git_commit",
    "shell_safe",
    "shell_safe_allowlist",
    # pipeline_do intentionally omitted — recursion
]


class WorkerAgent(BaseAgent):
    def __init__(
        self,
        state: Any,
        bus: EventBus,
        llm: Any | None = None,
        tools: Any | None = None,
    ) -> None:
        super().__init__(state, bus, llm)
        self.tools = tools

    def run(
        self,
        task: str,
        user_text: str,
        requirements: list[str],
        memory_ctx: str = "",
    ) -> str:
        if not self.enabled:
            return ""
        self.emit_active(True)
        try:
            if self.has_llm():
                try:
                    body = f"Aufgabe: {task}\nOriginal: {user_text}\nAnforderungen:\n" + "\n".join(
                        f"- {r}" for r in requirements[:5]
                    )
                    from gnom_hub.agents.chat_policy import task_kind
                    from gnom_hub.tools.tool_scenarios import (
                        is_tool_drill_task,
                        tool_drill_worker_prompt,
                    )

                    kind = task_kind(f"{user_text}\n{task}")
                    drill = (
                        kind == "tool_drill"
                        or is_tool_drill_task(user_text)
                        or is_tool_drill_task(task)
                    )
                    wants_html = kind == "html_page" or task_wants_html(
                        task, user_text, "\n".join(requirements[:12])
                    )
                    system = worker_system_prompt(wants_html=wants_html)
                    system = (
                        system
                        + "\nALWAYS finish — never cut mid-file. No max token excuses.\n"
                        + "ROUTING (from desk chat policy):\n"
                        + "  tool_drill → ONLY real tools, report TOOL_RESULT lines, NO HTML.\n"
                        + "  browser_nav → browser_open or browser_goto, report URL/title, NO HTML.\n"
                        + "  html_page → complete single-file HTML (layered rules above).\n"
                        + "  research brief → markdown checklist for implementer, not full HTML.\n"
                        + 'If a tool is missing: TOOL_CALL tool_ensure={"which":"browser"} '
                        + "or tool_ensure_package — never invent install output.\n"
                        + f"Detected task_kind={kind}.\n"
                    )
                    if drill:
                        system = system + "\n\n" + tool_drill_worker_prompt()
                    # Tool-aware path when registry is wired (TOOL_CALL protocol)
                    if self.tools is not None:
                        from gnom_hub.tools.agent_bridge import (
                            is_live_browser_task,
                            run_tool_loop,
                            try_browser_nav_execute,
                        )

                        # Deterministic drill: run scenario tools for real (don't wait on LLM)
                        if drill:
                            from gnom_hub.tools.tool_scenarios import run_forced_tool_scenario

                            forced = run_forced_tool_scenario(
                                self.tools,
                                f"{user_text}\n{task}",
                                bus=self.bus,
                            )
                            return str(forced.get("summary") or forced)

                        # Browser nav: deterministic open (LLM optional follow-up not needed)
                        if (
                            kind == "browser_nav"
                            or is_live_browser_task(user_text)
                            or is_live_browser_task(task)
                        ):
                            nav = try_browser_nav_execute(
                                tools=self.tools,
                                user_text=f"{user_text}\n{task}",
                                bus=self.bus,
                            )
                            if nav is not None:
                                return str(nav.get("summary") or nav)

                        # Free path: still force tools when task text smells like ops
                        blob = f"{user_text}\n{task}".lower()
                        ops_hint = any(
                            k in blob
                            for k in (
                                "tool",
                                "shell",
                                "terminal",
                                "git ",
                                "datei",
                                "file_",
                                "screenshot",
                                "playwright",
                                "install",
                                "inspect",
                                "computer",
                                "browser",
                                "fetch",
                                "pwd",
                                "kleinanzeigen",
                            )
                        )
                        force_tools = (
                            kind in ("tool_drill", "browser_nav")
                            or is_live_browser_task(user_text)
                            or ops_hint
                        )
                        if force_tools and kind not in ("tool_drill", "browser_nav", "html_page"):
                            system = (
                                system + "\n# OPS TASK: Call at least one real tool via TOOL_CALL "
                                "before your final answer. Do not invent tool output.\n"
                            )
                        return run_tool_loop(
                            ask_fn=lambda sys, usr, max_tokens=None, temperature=0.45: self.ask(
                                system=sys,
                                user=usr,
                                max_tokens=max_tokens,
                                temperature=temperature,
                            ),
                            system=system,
                            user=_with_memory(body, memory_ctx),
                            tools=self.tools,
                            tool_names=_WORKER_TOOL_NAMES,
                            max_rounds=4 if force_tools else 2,
                            max_tokens=None,
                            temperature=0.35 if force_tools else 0.45,
                            bus=self.bus,
                            agent_id=self.id,
                        )
                    return self.ask(
                        system=system,
                        user=_with_memory(body, memory_ctx),
                        # Workers: no token limit (BaseAgent omits max_tokens for role=worker)
                        max_tokens=None,
                        temperature=0.45,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": self.id, "error": str(exc)},
                    )
            # Stub path: still try browser_open without LLM when tools available
            if self.tools is not None:
                from gnom_hub.tools.agent_bridge import try_browser_nav_execute

                nav = try_browser_nav_execute(
                    tools=self.tools,
                    user_text=f"{user_text}\n{task}",
                    bus=self.bus,
                )
                if nav is not None:
                    return str(nav.get("summary") or nav)
            task_lines = [ln.strip() for ln in (task or "").splitlines() if ln.strip()]
            task_head = task_lines[0][:140] if task_lines else "(empty task)"
            if not self.has_llm():
                why = user_message_for_failure("DEEPSEEK_API_KEY missing", role=self.id)
                return (
                    f"{self.state.name} FEHLER - kein Deliverable\n"
                    f"Aufgabe: {task_head}\n"
                    f"{why}\n"
                    "Kein Fake-Ergebnis. Worker liefert erst mit gueltigem Provider."
                )
            try:
                body = f"Aufgabe: {task}\nOriginal: {user_text}\nAnforderungen:\n" + "\n".join(
                    f"- {r}" for r in requirements[:12]
                )
                wants_html = task_wants_html(task, user_text, "\n".join(requirements[:12]))
                return self.ask(
                    system=worker_system_prompt(wants_html=wants_html),
                    user=_with_memory(body, memory_ctx),
                    # Workers: no token limit (BaseAgent omits max_tokens for role=worker)
                    max_tokens=None,
                    temperature=0.45,
                )
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                self.bus.emit(
                    "pipeline.warning",
                    {"stage": self.id, "error": err, "kind": "llm"},
                )
                note = getattr(self.llm, "note_auth_failure", None)
                if callable(note) and (
                    "401" in err or "403" in err or type(exc).__name__ == "AuthError"
                ):
                    try:
                        note(getattr(self.state, "api_key", None))
                    except Exception:  # noqa: BLE001
                        pass
                why = user_message_for_failure(exc, role=self.id)
                return (
                    f"{self.state.name} FEHLER - kein Deliverable\n"
                    f"Aufgabe: {task_head}\n"
                    f"{why}\n"
                    "Kein Stub-Ersatz. Key pruefen, Budget pruefen, dann erneut ausfuehren."
                )
        finally:
            self.emit_active(False)


class MemoryAgent(BaseAgent):
    """Always-on Memory agent — holds the red thread."""

    def __init__(
        self,
        state: Any,
        bus: EventBus,
        llm: Any | None = None,
        memory: Any | None = None,
    ) -> None:
        super().__init__(state, bus, llm)
        self.memory = memory
        self.state.enabled = True
        self.state.toggleable = False

    def recall(self, user_text: str = "") -> str:
        self.emit_active(True)
        try:
            raw = ""
            if self.memory is not None:
                set_q = getattr(self.memory, "set_query_hint", None)
                if callable(set_q) and user_text:
                    set_q(user_text)
                fn = getattr(self.memory, "pipeline_context", None)
                if callable(fn):
                    raw = str(fn() or "").strip()
            from gnom_hub.agents.roles_helpers import _sanitize_memory_ctx

            raw = _sanitize_memory_ctx(raw)
            if not raw:
                return ""
            if not self.has_llm() or not user_text.strip():
                return raw[:900]
            try:
                curated = self.ask(
                    system=(
                        "You are the Memory agent. From the stored context, select only "
                        "facts relevant to the CURRENT user task. "
                        "Ignore HTML, code, other projects, pipeline meta, and "
                        "ephemeral tool-drill outputs (pwd/date/screenshot paths). "
                        "Keep durable user prefs and product names. "
                        "Output 2–6 short bullet facts. No preamble. "
                        "If nothing is relevant: (no relevant memory)"
                    ),
                    user=f"Task:\n{user_text}\n\nStored context:\n{raw[:2200]}",
                    max_tokens=280,
                    temperature=0.1,
                )
                cleaned = _sanitize_memory_ctx(curated or "")
                if not cleaned or cleaned.lower().startswith("(no relevant"):
                    return ""
                return cleaned[:900]
            except Exception as exc:  # noqa: BLE001
                self.bus.emit(
                    "pipeline.warning",
                    {"stage": "memory_recall", "error": str(exc)},
                )
                return raw[:900]
        finally:
            self.emit_active(False)

    def store(
        self,
        *,
        user_text: str,
        requirements: list[str],
        brainstorm: str,
        flex_notes: str,
        results: list[str],
    ) -> None:
        self.emit_active(True)
        try:
            clean_reqs = [
                r
                for r in requirements
                if not _is_flex_meta_requirement(r)
                and 8 <= len(r) < 160
                and not _is_garbage_fact(r)
            ][:5]
            self.bus.emit(
                "pipeline.memory_hint",
                {
                    "user_text": user_text,
                    "requirements": clean_reqs,
                    "results": results[:2],
                    "brainstorm_notes": brainstorm,
                    "flex_notes": flex_notes,
                },
            )
            if self.has_llm():
                try:
                    safe_results: list[str] = []
                    for r in results[:2]:
                        snip = (r or "").strip()
                        if not snip or _is_garbage_fact(snip[:200]):
                            continue
                        if "```" in snip:
                            snip = snip.split("```", 1)[0].strip()
                        if snip and len(snip) >= 20:
                            safe_results.append(snip[:280])
                    pack = (
                        f"User task: {user_text}\n"
                        f"Requirements:\n"
                        + "\n".join(f"- {r}" for r in clean_reqs)
                        + f"\nBrainstorm head:\n{(brainstorm or '')[:400]}\n"
                    )
                    if safe_results:
                        pack += "Worker notes (no code):\n" + "\n---\n".join(safe_results)
                    curated = self.ask(
                        system=(
                            "You are the Memory agent. Extract 0–3 DURABLE facts only.\n"
                            "Durable = user preference, brand/product name, standing constraint, "
                            "or a decision that should survive a NEW unrelated session.\n"
                            "NEVER store: HTML/CSS/JS, code, session requirements lists, "
                            "worker drafts, test chatter, empty meta, or pipeline status.\n"
                            "One short fact per line. No numbering. No intro.\n"
                            "If nothing durable: (none)"
                        ),
                        user=pack,
                        max_tokens=180,
                        temperature=0.1,
                    )
                    facts: list[str] = []
                    for ln in (curated or "").splitlines():
                        s = ln.strip().lstrip("-•*0123456789. \t")
                        if not s:
                            continue
                        if _is_garbage_fact(s):
                            continue
                        if 8 <= len(s) <= 200:
                            facts.append(s[:200])
                    seen: set[str] = set()
                    uniq: list[str] = []
                    for f in facts:
                        key = f.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        uniq.append(f)
                    if uniq:
                        self.bus.emit(
                            "pipeline.memory_curated",
                            {"facts": uniq[:3], "user_text": user_text},
                        )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "memory_store", "error": str(exc)},
                    )
        finally:
            self.emit_active(False)
