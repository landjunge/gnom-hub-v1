"""
Agent ↔ ToolRegistry bridge.

Agents do not have native function-calling from every LLM provider.
We use a simple text protocol:

  TOOL_CALL name={"arg": "value"}
  TOOL_CALL name

Workers (and the orchestrator short-circuit) call tools, get results,
then produce a final answer without TOOL_CALL lines.
"""

from __future__ import annotations

import json
import re
from typing import Any

from gnom_hub.tools.browser_tools import extract_urls, normalize_url

# Max tool rounds per worker turn (keeps pipeline bounded)
MAX_TOOL_ROUNDS = 4

_TOOL_CALL_RE = re.compile(
    r"TOOL_CALL\s+([a-zA-Z0-9_.-]+)\s*(?:(=)\s*)?(\{.*\}|\[.*\]|[^\n]*)?",
    re.IGNORECASE | re.DOTALL,
)

_NAV_VERBS = (
    "navigier",
    "navigate",
    "öffne",
    "oeffne",
    "open ",
    "open\t",
    "goto ",
    "go to ",
    "geh zu",
    "gehe zu",
    "besuch",
    "visit ",
    "browse ",
    "surfe",
    "zeig mir",
    "show me",
    "im browser",
    "in the browser",
    "live browser",
    "browser öffnen",
    "browser oeffnen",
)


def is_live_browser_task(text: str) -> bool:
    """True when the user wants a real browser to open a site (not HTML generation)."""
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()
    # Fetch/research for a page ≠ live browser open
    if any(
        k in low
        for k in (
            "for the page",
            "for a page",
            "for the landing",
            "für die seite",
            "fuer die seite",
            "zusammenfassen",
            "summarize",
            "fetch ",
            "web_fetch",
            "inhalt von",
            "content from",
            "research",
        )
    ) and not any(v in low for v in _NAV_VERBS):
        return False
    # HTML/page build wins over "open" in mixed landing tasks
    if any(
        k in low
        for k in (
            "landing",
            "html",
            "website bauen",
            "webseite bauen",
            "baue eine seite",
            "build a page",
            "create a page",
            "erstelle eine seite",
            "readme",
            " for the page",
            " for a page",
        )
    ):
        # still allow pure "öffne X im browser" if no build language dominates
        if not any(v in low for v in _NAV_VERBS):
            return False
        if any(k in low for k in ("baue", "build", "erstelle", "create", "implement")):
            return False
    # known sites / short URL-only messages (desk UX: no magic verb required)
    if re.fullmatch(r"https?://\S+", t.strip(), re.IGNORECASE):
        return True
    if re.fullmatch(
        r"(?:www\.)?(?:kleinanzeigen\.de|grok\.com|x\.ai|github\.com|google\.com)(?:/\S*)?",
        low.strip(),
    ):
        return True
    if "kleinanzeigen" in low and not any(
        k in low for k in ("baue", "landing", "html", "seite bauen")
    ):
        # "kleinanzeigen", "öffne kleinanzeigen", "geh auf kleinanzeigen"
        return True
    if not any(v in low for v in _NAV_VERBS):
        # bare domain with browser word, or short domain-only line
        if "browser" in low and extract_urls(t):
            return True
        return bool(
            len(t) < 48
            and extract_urls(t)
            and not any(
                k in low
                for k in (
                    "bau",
                    "html",
                    "landing",
                    "schreib",
                    "code",
                    "page",
                    "seite",
                    "summar",
                    "fetch",
                )
            )
        )
    return bool(extract_urls(t) or _guess_domain(t))


def resolve_browser_url(text: str) -> str:
    urls = extract_urls(text or "")
    if urls:
        return urls[0]
    dom = _guess_domain(text or "")
    return normalize_url(dom) if dom else ""


def _guess_domain(text: str) -> str:
    m = re.search(
        r"\b((?:[a-z0-9-]+\.)+(?:com|ai|io|org|net|de|app|dev|xyz))\b",
        (text or "").lower(),
    )
    return m.group(1) if m else ""


def format_tool_catalog(tools: Any, *, names: list[str] | None = None) -> str:
    """Human-readable tool list for system prompts."""
    if tools is None:
        return ""
    try:
        listed = tools.list_tools()
    except Exception:  # noqa: BLE001
        return ""
    lines = [
        "=== TOOLS (you may call these) ===",
        "To call a tool, output ONE line exactly:",
        '  TOOL_CALL tool_name={"arg":"value"}',
        "Or with no args:",
        "  TOOL_CALL tool_name",
        "After a tool result is returned, either call another tool or answer finally.",
        "Never invent tool results. Never wrap final answers in TOOL_CALL.",
        "",
    ]
    allow = set(names) if names else None
    for t in listed:
        name = str(t.get("name") or "")
        if not name:
            continue
        if allow is not None and name not in allow:
            continue
        desc = str(t.get("description") or "").strip()
        schema = t.get("input_schema") or {}
        props = (schema.get("properties") or {}) if isinstance(schema, dict) else {}
        req = (schema.get("required") or []) if isinstance(schema, dict) else []
        arg_bits: list[str] = []
        for k, meta in props.items():
            if not isinstance(meta, dict):
                arg_bits.append(k)
                continue
            typ = meta.get("type") or "any"
            mark = "*" if k in req else ""
            arg_bits.append(f"{k}{mark}:{typ}")
        arg_s = ", ".join(arg_bits) if arg_bits else "(no args)"
        lines.append(f"- {name}: {desc}  args=[{arg_s}]")
    lines.append("=== END TOOLS ===")
    return "\n".join(lines)


def parse_tool_calls(text: str) -> list[tuple[str, dict[str, Any]]]:
    """Extract TOOL_CALL lines from model output."""
    out: list[tuple[str, dict[str, Any]]] = []
    if not text:
        return out
    for m in _TOOL_CALL_RE.finditer(text):
        name = (m.group(1) or "").strip()
        raw = (m.group(3) or "").strip()
        if not name:
            continue
        args: dict[str, Any] = {}
        if raw:
            if raw.startswith(("{", "[")):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        args = parsed
                    elif isinstance(parsed, list) and parsed:
                        # single positional → common keys
                        args = (
                            {"url": str(parsed[0])}
                            if name
                            in (
                                "browser_open",
                                "web_fetch",
                            )
                            else {"value": parsed}
                        )
                except json.JSONDecodeError:
                    # try url=... loose
                    args = _loose_args(raw, name)
            else:
                args = _loose_args(raw, name)
        out.append((name, args))
    return out


def _loose_args(raw: str, tool_name: str) -> dict[str, Any]:
    s = raw.strip().strip('"').strip("'")
    if not s:
        return {}
    if tool_name in ("browser_open", "web_fetch"):
        return {"url": s}
    if tool_name in ("computer_shell",):
        return {"cmd": s}
    if tool_name in ("computer_type",):
        return {"text": s}
    if tool_name in ("memory_search",):
        return {"query": s}
    if tool_name in ("pipeline_do",):
        return {"text": s}
    # key=value pairs
    if "=" in s and not s.startswith("http"):
        d: dict[str, Any] = {}
        for part in re.split(r"[,;\s]+", s):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
        if d:
            return d
    return {"value": s}


def label_tool_result(result: dict[str, Any] | None) -> str:
    """Human mode tag for tool results: live | dry-run | blocked | error."""
    if not isinstance(result, dict):
        return "unknown"
    if result.get("blocked"):
        return "blocked"
    if result.get("dry_run"):
        return "dry-run"
    if result.get("ok") is False:
        return "error"
    return "live"


def _pipeline_cancel_requested() -> bool:
    """True when the active pipeline job asked to cancel (cooperative)."""
    try:
        from gnom_hub.hub import get_hub

        hub = get_hub()
        pipe = getattr(hub, "pipeline", None)
        if pipe is None:
            return False
        # Self-heal sticky cancel_check left by tests / early cancel_job
        if not getattr(hub, "_active_job_id", None):
            if getattr(pipe, "cancel_check", None) is not None:
                pipe.cancel_check = None
            return False
        fn = getattr(pipe, "cancel_check", None)
        if not callable(fn):
            return False
        return bool(fn())
    except Exception:  # noqa: BLE001
        return False


def call_tool(tools: Any, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if tools is None:
        return {"ok": False, "error": "no tools registry", "mode": "error"}
    try:
        result = tools.call(name, arguments or {})
        if isinstance(result, dict):
            out = dict(result)
            if "mode" not in out:
                out["mode"] = label_tool_result(out)
            return out
        return {"ok": True, "result": result, "mode": "live"}
    except KeyError:
        return {"ok": False, "error": f"unknown tool: {name}", "mode": "error"}
    except TypeError as exc:
        return {"ok": False, "error": f"bad args for {name}: {exc}", "mode": "error"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{name} failed: {exc}", "mode": "error"}


def strip_tool_calls(text: str) -> str:
    """Remove TOOL_CALL lines for the final deliverable."""
    if not text:
        return ""
    cleaned = _TOOL_CALL_RE.sub("", text)
    # also drop bare "TOOL_CALL name" leftovers
    cleaned = re.sub(r"(?im)^\s*TOOL_CALL\b.*$", "", cleaned)
    return cleaned.strip()


def run_tool_loop(
    *,
    ask_fn,
    system: str,
    user: str,
    tools: Any,
    tool_names: list[str] | None = None,
    max_rounds: int = MAX_TOOL_ROUNDS,
    max_tokens: int | None = None,
    temperature: float = 0.4,
    bus: Any | None = None,
    agent_id: str = "worker",
    cancel_check: Any | None = None,
) -> str:
    """
    Multi-round: model may emit TOOL_CALL, we execute, append results, re-ask.

    ask_fn(system, user, max_tokens=..., temperature=...) -> str
    cancel_check: optional callable; if omitted, uses pipeline cooperative cancel.
    """

    def _cancelled() -> bool:
        if cancel_check is not None:
            try:
                return bool(cancel_check())
            except Exception:  # noqa: BLE001
                return False
        return _pipeline_cancel_requested()

    catalog = format_tool_catalog(tools, names=tool_names)
    if not catalog:
        return ask_fn(system, user, max_tokens=max_tokens, temperature=temperature)

    sys_full = f"{system.rstrip()}\n\n{catalog}"
    conversation = user
    last = ""
    for round_i in range(max(1, max_rounds)):
        if _cancelled():
            return strip_tool_calls(last) or f"(tool loop cancelled after round {round_i})"
        last = ask_fn(
            sys_full,
            conversation,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        calls = parse_tool_calls(last)
        if not calls:
            return strip_tool_calls(last) or last

        # Execute all calls in this turn (usually one)
        blocks: list[str] = []
        for name, args in calls[:3]:
            if _cancelled():
                blocks.append("TOOL_RESULT cancelled=true")
                break
            if tool_names is not None and name not in tool_names:
                res = {"ok": False, "error": f"tool not allowed: {name}", "mode": "error"}
            else:
                res = call_tool(tools, name, args)
            if bus is not None:
                try:
                    bus.emit(
                        "pipeline.tool_call",
                        {
                            "agent": agent_id,
                            "tool": name,
                            "args": args,
                            "ok": bool(res.get("ok", True)),
                            "mode": res.get("mode") or label_tool_result(res),
                            "round": round_i + 1,
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass
            mode = res.get("mode") or label_tool_result(res)
            blocks.append(
                f"TOOL_RESULT {name} mode={mode}\n"
                f"{json.dumps(res, ensure_ascii=False, default=str)[:4000]}"
            )

        conversation = (
            f"{conversation}\n\n"
            f"Your previous output:\n{last[:2000]}\n\n"
            + "\n\n".join(blocks)
            + "\n\nContinue: call another TOOL_CALL if needed, "
            "or give the FINAL answer for the user (no TOOL_CALL lines)."
        )

    # exhausted rounds — return last stripped
    return strip_tool_calls(last) or last


def try_browser_nav_execute(
    *,
    tools: Any,
    user_text: str,
    bus: Any | None = None,
) -> dict[str, Any] | None:
    """
    If task is pure live-browser navigation, open the URL now.
    Returns a result dict for the orchestrator, or None if not a browser task.
    """
    if not is_live_browser_task(user_text):
        return None
    url = resolve_browser_url(user_text)
    if not url:
        return {
            "ok": False,
            "kind": "browser_nav",
            "error": "browser navigation intent but no URL found",
            "summary": "Konnte keine URL aus dem Auftrag lesen.",
        }
    res = call_tool(tools, "browser_open", {"url": url})
    if bus is not None:
        try:
            bus.emit(
                "pipeline.tool_call",
                {
                    "agent": "orchestrator",
                    "tool": "browser_open",
                    "args": {"url": url},
                    "ok": bool(res.get("ok")),
                    "short_circuit": True,
                },
            )
        except Exception:  # noqa: BLE001
            pass
    ok = bool(res.get("ok"))
    method = res.get("method") or "?"
    if ok:
        summary = (
            f"Browser geöffnet: {url}\n"
            f"Methode: {method}\n"
            f"{res.get('detail') or res.get('title') or 'OK'}\n"
            "Live-Navigation ausgeführt (kein HTML-Artefakt nötig)."
        )
    else:
        summary = (
            f"Browser konnte {url} nicht öffnen.\n"
            f"Fehler: {res.get('error') or res}\n"
            "Prüfe God-Mode / OS-Berechtigungen / Playwright."
        )
    return {
        "ok": ok,
        "kind": "browser_nav",
        "url": url,
        "tool_result": res,
        "summary": summary,
    }
