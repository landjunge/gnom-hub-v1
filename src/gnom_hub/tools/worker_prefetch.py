"""Prefetch tools for worker stage — planned, budget-aware, KISS.

Pipeline:
  plan_prefetch(blob) → ordered PrefetchStep list
  prefetch_for_workers → execute under call + context budgets
  inject as \"Tool prefetch (auto):\" into worker user message

Workers never call tools mid-turn; this module is the only auto path.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+")
_FILE_RE = re.compile(
    r"(?<![\w/])([\w.-]+\.(?:html?|css|js|ts|tsx|jsx|md|txt|json|py|svg))(?![\w/])",
    re.IGNORECASE,
)

# When to auto memory_search (lexical vector)
_MEMORY_HINTS = (
    "memory",
    "erinner",
    "merke",
    "wish",
    "wunsch",
    "prefer",
    "präfer",
    "dark theme",
    "immer",
    "always",
    "flex",
    "warm",
    "präferenz",
    "preference",
)

# HTML / web-design task signals → color_palette + html_scaffold
_HTML_HINTS = (
    "html",
    "landing",
    "webpage",
    "web page",
    "website",
    "webseite",
    "seite",
    "frontend",
    "dashboard",
    "css",
    "ui page",
    "web design",
    "homepage",
    "startseite",
)

# Soft per-category call caps (within global max_tool_calls)
_CATEGORY_CAPS = {
    "install": 4,  # dry+install × 2 packages
    "design": 4,  # palette + contrast + scaffold + tokens
    "net": 3,
    "memory": 1,
    "workspace": 2,
}

# Research / current-events language → web_search (Tollgate/Brave)
_SEARCH_HINTS = (
    "search",
    "suche",
    "recherch",
    "lookup",
    "nachschlagen",
    "aktuell",
    "current",
    "news",
    "latest",
    "who is",
    "was ist",
    "wie funktioniert",
    "find out",
    "google",
    "web search",
    "im internet",
    "online",
)

# Task keywords → allowlisted install_tool package key
# Keep aligned with plugins/install_tool/main.py _ALLOW
_PACKAGE_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("playwright", ("playwright", "chromium", "browser e2e", "headed browser")),
    ("beautifulsoup4", ("beautifulsoup", "beautifulsoup4", " bs4 ", "bs4.", "html soup")),
    ("lxml", ("lxml",)),
    ("pillow", ("pillow", " PIL", "screenshot png", "image screenshot")),
    ("pytesseract", ("pytesseract", "ocr ", "tesseract")),
    ("pyautogui", ("pyautogui", "mouse click", "gui automation")),
    ("mss", (" mss", "screen capture", "monitor capture")),
    ("pynput", ("pynput", "keyboard control", "mouse control")),
]


@dataclass
class PrefetchStep:
    """One planned tool invocation."""

    name: str
    category: str
    priority: int
    cost: int
    reason: str
    args: dict[str, Any] = field(default_factory=dict)
    optional: bool = False


@dataclass
class PrefetchReport:
    """Execution report (for tests / UI / pipeline.meta)."""

    context: str
    plan: list[dict[str, Any]]
    executed: list[str]
    skipped: list[str]
    calls_used: int
    max_tool_calls: int
    context_chars: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def packages_needed(blob: str) -> list[str]:
    """Allowlisted package keys implied by task text (order preserved)."""
    low = f" {(blob or '').lower()} "
    out: list[str] = []
    seen: set[str] = set()
    for pkg, keys in _PACKAGE_HINTS:
        if pkg not in seen and any(k in low for k in keys):
            seen.add(pkg)
            out.append(pkg)
    return out


def wants_design_tools(blob: str) -> bool:
    """True when task looks like HTML/page/UI work."""
    low = (blob or "").lower()
    return any(h in low for h in _HTML_HINTS)


def extract_urls(blob: str, *, max_urls: int = 3) -> list[str]:
    """Dedupe and rank URLs (docs/github preferred over tracking noise)."""
    raw_list: list[str] = []
    seen: set[str] = set()
    for raw in _URL_RE.findall(blob or ""):
        u = raw.rstrip(".,;:)")
        if u in seen:
            continue
        seen.add(u)
        raw_list.append(u)

    def score(u: str) -> tuple[int, int]:
        try:
            host = (urlparse(u).netloc or "").lower()
            path = (urlparse(u).path or "").lower()
        except Exception:  # noqa: BLE001
            host, path = "", ""
        s = 0
        if any(h in host for h in ("github.com", "docs.", "developer.", "mdn.", "readthedocs")):
            s += 5
        if any(x in path for x in ("/docs", "/api", "/guide", "/readme")):
            s += 3
        if "utm_" in u or "fbclid" in u:
            s -= 2
        return (-s, len(u))  # higher score first, then shorter

    raw_list.sort(key=score)
    return raw_list[: max(0, max_urls)]


def extract_workspace_files(blob: str, *, limit: int = 3) -> list[str]:
    """Basenames mentioned in task that look like workspace files."""
    out: list[str] = []
    seen: set[str] = set()
    for m in _FILE_RE.finditer(blob or ""):
        name = m.group(1)
        key = name.lower()
        if key in seen:
            continue
        # skip bare package-looking noise
        if name.lower() in ("package.json", "tsconfig.json"):
            continue
        seen.add(key)
        out.append(name)
        if len(out) >= limit:
            break
    return out


def _palette_seed(blob: str) -> str:
    """Pick a palette preset from task language (defaults dark)."""
    low = (blob or "").lower()
    if "ocean" in low or "blau" in low or "blue" in low:
        return "ocean"
    if "forest" in low or "grün" in low or "green" in low:
        return "forest"
    if "sunset" in low or "orange" in low:
        return "sunset"
    if "rose" in low or "pink" in low:
        return "rose"
    if "brand" in low or "violet" in low or "purple" in low:
        return "brand"
    if "light" in low or "hell" in low:
        return "light"
    if "slate" in low or "grau" in low or "gray" in low or "grey" in low:
        return "slate"
    return "dark"


def _scaffold_kind(blob: str) -> str:
    low = (blob or "").lower()
    if "dashboard" in low:
        return "dashboard"
    if "form" in low or "kontakt" in low or "contact" in low:
        return "form"
    if "article" in low or "blog" in low or "artikel" in low:
        return "article"
    return "landing"


def _memory_query(blob: str) -> str:
    """Compact query: drop URLs, keep wish-ish words + first clause."""
    text = blob or ""
    text = _URL_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Prefer sentence with memory hints
    low = text.lower()
    for h in _MEMORY_HINTS:
        if h in low:
            idx = low.find(h)
            start = max(0, idx - 40)
            end = min(len(text), idx + 80)
            return text[start:end].strip()[:180]
    return text[:180]


def plan_prefetch(
    blob: str,
    *,
    max_urls: int = 3,
    max_packages: int = 2,
    max_workspace_files: int = 2,
) -> list[PrefetchStep]:
    """
    Pure plan: which tools to run and why (no side effects).

    Priority bands (lower runs first):
      10 install · 20 design · 30 workspace · 40 net · 50 memory
    """
    text = blob or ""
    steps: list[PrefetchStep] = []

    # ── install (priority 10) ─────────────────────────────────────────
    for i, pkg in enumerate(packages_needed(text)[:max_packages]):
        steps.append(
            PrefetchStep(
                name="install_tool",
                category="install",
                priority=10 + i,
                cost=2,  # dry_run + maybe install
                reason=f"package hint: {pkg}",
                args={"package": pkg},
            )
        )

    # ── design (priority 20) ──────────────────────────────────────────
    if wants_design_tools(text):
        seed = _palette_seed(text)
        kind = _scaffold_kind(text)
        steps.append(
            PrefetchStep(
                name="color_palette",
                category="design",
                priority=20,
                cost=1,
                reason=f"HTML/UI task · seed={seed}",
                args={"seed": seed, "count": 5},
            )
        )
        steps.append(
            PrefetchStep(
                name="contrast_check",
                category="design",
                priority=21,
                cost=1,
                reason="AA/AAA text on surface",
                args={},  # filled from palette result at runtime
                optional=True,
            )
        )
        steps.append(
            PrefetchStep(
                name="html_scaffold",
                category="design",
                priority=22,
                cost=1,
                reason=f"skeleton kind={kind}",
                args={
                    "kind": kind,
                    "title": " ".join(text.split())[:60] or "Page",
                    "seed": seed,
                },
            )
        )
        steps.append(
            PrefetchStep(
                name="css_tokens",
                category="design",
                priority=23,
                cost=1,
                reason="spacing/type tokens",
                args={"seed": seed},
                optional=True,
            )
        )

    # ── workspace files (priority 30) ─────────────────────────────────
    for i, fname in enumerate(extract_workspace_files(text, limit=max_workspace_files)):
        steps.append(
            PrefetchStep(
                name="workspace_read",
                category="workspace",
                priority=30 + i,
                cost=1,
                reason=f"mentioned file {fname}",
                args={"name": fname, "zone": "temp", "max_chars": 4000},
            )
        )

    # ── URLs (priority 40) ────────────────────────────────────────────
    for i, url in enumerate(extract_urls(text, max_urls=max_urls)):
        steps.append(
            PrefetchStep(
                name="web_fetch",
                category="net",
                priority=40 + i,
                cost=1,
                reason="URL in task",
                args={"url": url, "max_chars": 2500},
            )
        )

    # ── web_search via Tollgate/Brave (priority 42) ───────────────────
    low = text.lower()
    if any(h in low for h in _SEARCH_HINTS) and not extract_urls(text, max_urls=1):
        # Only when no explicit URL — otherwise web_fetch is enough
        q = " ".join(text.split())[:160]
        steps.append(
            PrefetchStep(
                name="web_search",
                category="net",
                priority=42,
                cost=1,
                reason="research/current-events language",
                args={"query": q, "count": 5, "country": "DE", "search_lang": "de"},
            )
        )

    # ── memory (priority 50) ──────────────────────────────────────────
    if any(h in low for h in _MEMORY_HINTS):
        steps.append(
            PrefetchStep(
                name="memory_search",
                category="memory",
                priority=50,
                cost=1,
                reason="wish/preference language",
                args={"query": _memory_query(text), "limit": 3},
            )
        )

    steps.sort(key=lambda s: (s.priority, s.name))
    return steps


def _emit_tool_call(
    bus: Any,
    name: str,
    args: dict[str, Any],
    result: Any,
    record: list[dict[str, Any]] | None = None,
    *,
    reason: str = "",
    mode: str = "prefetch",
) -> None:
    ok = True
    err = None
    summary: Any
    if isinstance(result, dict):
        ok = bool(result.get("ok", True))
        err = result.get("error")
        keys = (
            "ok",
            "error",
            "url",
            "status",
            "package",
            "installed",
            "already_installed",
            "message",
            "dry_run",
            "primary",
            "accent",
            "kind",
            "seed",
            "grade",
            "ratio",
            "name",
            "zone",
            "truncated",
        )
        summary = {k: result[k] for k in keys if k in result}
        if "text" in result:
            summary["text_len"] = len(str(result.get("text") or ""))
        if "css" in result:
            summary["css_len"] = len(str(result.get("css") or ""))
        if "html" in result:
            summary["html_len"] = len(str(result.get("html") or ""))
        if not summary and result:
            summary = {"keys": list(result.keys())[:8]}
    elif isinstance(result, list):
        summary = {"hits": len(result)}
        ok = True
    else:
        summary = {"type": type(result).__name__}
    payload = {
        "name": name,
        "tool": name,  # alias for job tool_log listener
        "args": {
            k: (str(v)[:120] if not isinstance(v, (int, float, bool)) else v)
            for k, v in (args or {}).items()
        },
        "ok": ok,
        "error": err,
        "result": summary,
        "reason": (reason or "").strip()[:220],
        "mode": (mode or "prefetch").strip()[:40] or "prefetch",
    }
    if bus is not None:
        bus.emit("pipeline.tool_call", payload)
    if record is not None:
        record.append(dict(payload))


def _call_tool(
    tools: Any | None,
    name: str,
    arguments: dict[str, Any],
    *,
    fallback: Any = None,
) -> Any:
    if tools is not None and hasattr(tools, "call"):
        try:
            return tools.call(name, arguments)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "tool": name}
    if callable(fallback):
        try:
            return fallback(**arguments)
        except TypeError:
            return fallback(arguments)  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "tool": name}
    return {"ok": False, "error": f"tool {name!r} unavailable"}


def _registry_has(tools: Any | None, name: str) -> bool:
    if tools is None:
        return False
    if hasattr(tools, "list_tools"):
        try:
            return any(str(t.get("name")) == name for t in (tools.list_tools() or []))
        except Exception:  # noqa: BLE001
            pass
    inner = getattr(tools, "_tools", None)
    return isinstance(inner, dict) and name in inner


def _format_header(report_bits: dict[str, Any]) -> str:
    used = report_bits.get("calls_used", 0)
    mx = report_bits.get("max_tool_calls", 0)
    names = report_bits.get("executed") or []
    skipped = report_bits.get("skipped") or []
    line = f"[prefetch] used {used}/{mx} calls · ran: {', '.join(names) or '(none)'}"
    if skipped:
        line += f" · skipped: {', '.join(skipped[:6])}"
    return line


def prefetch_for_workers(
    blob: str,
    *,
    bus: Any = None,
    tools: Any | None = None,
    memory: Any | None = None,
    max_tool_calls: int | None = None,
    max_urls: int = 3,
    max_context_chars: int = 12_000,
    record: list[dict[str, Any]] | None = None,
    return_report: bool = False,
) -> str | PrefetchReport:
    """
    Plan + execute allowlisted prefetches; return context block for workers.

    Budgets:
      - max_tool_calls (default 8 HTML / 6 otherwise)
      - per-category soft caps
      - max_context_chars for injected text

    Emits pipeline.tool_call per invocation.
    """
    text = blob or ""
    if max_tool_calls is None:
        max_tool_calls = 8 if wants_design_tools(text) else 6

    plan = plan_prefetch(text, max_urls=max_urls)
    chunks: list[str] = []
    calls = 0
    cat_used: dict[str, int] = {}
    executed: list[str] = []
    skipped: list[str] = []
    palette_colors: dict[str, str] = {}
    context_len = 0

    def can_spend(step: PrefetchStep, spend: int) -> bool:
        if calls + spend > max_tool_calls:
            return False
        cap = _CATEGORY_CAPS.get(step.category, 99)
        return cat_used.get(step.category, 0) + spend <= cap

    def add_chunk(s: str) -> bool:
        nonlocal context_len
        s = (s or "").strip()
        if not s:
            return True
        if context_len + len(s) + 5 > max_context_chars:
            # try truncated
            room = max_context_chars - context_len - 20
            if room < 80:
                return False
            s = s[:room] + "\n…(truncated)"
        chunks.append(s)
        context_len += len(s) + 5
        return True

    for step in plan:
        # ── install_tool (special: dry then maybe install) ────────────
        if step.name == "install_tool":
            if not _registry_has(tools, "install_tool"):
                skipped.append("install_tool:no_registry")
                continue
            if not can_spend(step, 1):
                skipped.append(f"install_tool:{step.args.get('package')}:budget")
                continue
            pkg = str(step.args.get("package") or "")
            args_dry = {"package": pkg, "dry_run": True}
            st = _call_tool(tools, "install_tool", args_dry)
            calls += 1
            cat_used["install"] = cat_used.get("install", 0) + 1
            _emit_tool_call(bus, "install_tool", args_dry, st, record=record, reason=step.reason)
            executed.append("install_tool")
            installed = bool(isinstance(st, dict) and st.get("already_installed"))
            if installed:
                add_chunk(f"install_tool: {pkg} already installed")
                continue
            if not can_spend(step, 1):
                add_chunk(f"install_tool: {pkg} missing (budget exhausted, not installed)")
                skipped.append(f"install_tool:{pkg}:install_budget")
                continue
            args_inst = {"package": pkg, "dry_run": False}
            res = _call_tool(tools, "install_tool", args_inst)
            calls += 1
            cat_used["install"] = cat_used.get("install", 0) + 1
            _emit_tool_call(
                bus,
                "install_tool",
                args_inst,
                res,
                record=record,
                reason=step.reason + " · install",
            )
            if isinstance(res, dict) and res.get("ok"):
                add_chunk(f"install_tool: installed {pkg}")
            else:
                err = res.get("error") if isinstance(res, dict) else "install failed"
                add_chunk(f"install_tool: failed {pkg} ({err})")
            continue

        # ── contrast needs palette colors ─────────────────────────────
        if step.name == "contrast_check":
            if not palette_colors.get("text") or not palette_colors.get("surface"):
                skipped.append("contrast_check:no_palette")
                continue
            step.args = {
                "fg": palette_colors["text"],
                "bg": palette_colors["surface"],
            }

        # optional steps drop first under pressure
        spend = 1
        if not can_spend(step, spend):
            tag = f"{step.name}:budget"
            skipped.append(tag)
            continue
        if step.optional and calls >= max_tool_calls - 1 and step.name != "contrast_check":
            # keep 1 slot for higher-priority non-optional if any remain
            remaining_required = [
                s
                for s in plan
                if s.priority > step.priority and not s.optional and s.name not in executed
            ]
            if remaining_required:
                skipped.append(f"{step.name}:reserve")
                continue

        if step.name in ("color_palette", "html_scaffold", "css_tokens", "contrast_check"):
            if not _registry_has(tools, step.name):
                skipped.append(f"{step.name}:no_registry")
                continue
            res = _call_tool(tools, step.name, dict(step.args))
            calls += 1
            cat_used["design"] = cat_used.get("design", 0) + 1
            _emit_tool_call(bus, step.name, dict(step.args), res, record=record, reason=step.reason)
            executed.append(step.name)
            if not (isinstance(res, dict) and res.get("ok")):
                err = res.get("error") if isinstance(res, dict) else "failed"
                add_chunk(f"{step.name}: failed ({err})")
                continue
            if step.name == "color_palette":
                palette_colors = {
                    "text": str(res.get("text") or ""),
                    "surface": str(res.get("surface") or ""),
                    "primary": str(res.get("primary") or ""),
                }
                css = str(res.get("css") or "")[:800]
                add_chunk(
                    "color_palette (auto):\n"
                    f"primary={res.get('primary')} accent={res.get('accent')} "
                    f"surface={res.get('surface')} text={res.get('text')}\n"
                    f"{css}"
                )
            elif step.name == "contrast_check":
                add_chunk(
                    f"contrast_check: ratio={res.get('ratio')} grade={res.get('grade')} "
                    f"aa_normal={res.get('aa_normal')}"
                )
            elif step.name == "html_scaffold":
                html = str(res.get("html") or "")[:3500]
                kind = step.args.get("kind", "landing")
                add_chunk(
                    f"html_scaffold (auto kind={kind}):\n"
                    "Use as starting skeleton — keep structure, replace copy/features.\n"
                    f"{html}"
                )
            elif step.name == "css_tokens":
                css = str(res.get("css") or "")[:1200]
                add_chunk(f"css_tokens (auto):\n{css}")
            continue

        if step.name == "workspace_read":
            if not _registry_has(tools, "workspace_read"):
                skipped.append("workspace_read:no_registry")
                continue
            res = _call_tool(tools, "workspace_read", dict(step.args))
            calls += 1
            cat_used["workspace"] = cat_used.get("workspace", 0) + 1
            _emit_tool_call(
                bus, "workspace_read", dict(step.args), res, record=record, reason=step.reason
            )
            executed.append("workspace_read")
            if isinstance(res, dict) and res.get("ok"):
                body = str(res.get("text") or "")[:4000]
                add_chunk(f"workspace_read ({res.get('zone')}/{res.get('name')}):\n{body}")
            else:
                # try perm zone once if temp miss
                err = res.get("error") if isinstance(res, dict) else "read failed"
                alt_args = dict(step.args)
                alt_args["zone"] = "perm"
                if can_spend(step, 1) and _registry_has(tools, "workspace_read"):
                    res2 = _call_tool(tools, "workspace_read", alt_args)
                    calls += 1
                    cat_used["workspace"] = cat_used.get("workspace", 0) + 1
                    _emit_tool_call(
                        bus,
                        "workspace_read",
                        alt_args,
                        res2,
                        record=record,
                        reason=step.reason + " · perm",
                    )
                    if isinstance(res2, dict) and res2.get("ok"):
                        body = str(res2.get("text") or "")[:4000]
                        add_chunk(
                            f"workspace_read ({res2.get('zone')}/{res2.get('name')}):\n{body}"
                        )
                    else:
                        add_chunk(f"workspace_read: {step.args.get('name')} ({err})")
                else:
                    add_chunk(f"workspace_read: {step.args.get('name')} ({err})")
            continue

        if step.name == "web_fetch":
            from gnom_hub.tools.web_fetch import web_fetch

            args = dict(step.args)
            res = _call_tool(
                tools,
                "web_fetch",
                args,
                fallback=lambda url, max_chars=2500: web_fetch(str(url), max_chars=int(max_chars)),
            )
            calls += 1
            cat_used["net"] = cat_used.get("net", 0) + 1
            _emit_tool_call(bus, "web_fetch", args, res, record=record, reason=step.reason)
            executed.append("web_fetch")
            u = args.get("url", "")
            if isinstance(res, dict) and res.get("ok"):
                add_chunk(f"URL: {res.get('url') or u}\n{str(res.get('text') or '')[:2500]}")
            else:
                err = res.get("error") if isinstance(res, dict) else "fetch failed"
                add_chunk(f"URL: {u}\n(fetch failed: {err})")
            continue

        if step.name == "web_search":
            from gnom_hub.tools.brave_search import brave_web_search

            args = dict(step.args)
            res = _call_tool(
                tools,
                "web_search",
                args,
                fallback=lambda query, count=5, country="DE", search_lang="de": brave_web_search(
                    str(query),
                    count=int(count or 5),
                    country=str(country or "DE"),
                    search_lang=str(search_lang or "de"),
                ),
            )
            calls += 1
            cat_used["net"] = cat_used.get("net", 0) + 1
            _emit_tool_call(bus, "web_search", args, res, record=record, reason=step.reason)
            executed.append("web_search")
            if isinstance(res, dict) and res.get("ok"):
                lines = [f"web_search: {args.get('query', '')}"]
                for hit in (res.get("results") or [])[:5]:
                    if not isinstance(hit, dict):
                        continue
                    lines.append(
                        f"- {hit.get('title') or ''}\n  {hit.get('url') or ''}\n  "
                        f"{str(hit.get('description') or '')[:200]}"
                    )
                add_chunk("\n".join(lines)[:3000])
            else:
                err = res.get("error") if isinstance(res, dict) else "search failed"
                add_chunk(f"web_search failed: {err}")
            continue

        if step.name == "memory_search":
            vectors = getattr(memory, "vectors", None) if memory is not None else None
            if vectors is None and not _registry_has(tools, "memory_search"):
                skipped.append("memory_search:no_vectors")
                continue
            args = dict(step.args)
            if (
                tools is not None
                and hasattr(tools, "call")
                and _registry_has(tools, "memory_search")
            ):
                try:
                    hits = tools.call("memory_search", args)
                except Exception as exc:  # noqa: BLE001
                    hits = {"ok": False, "error": str(exc)}
            elif vectors is not None:
                try:
                    hits = vectors.search(
                        str(args.get("query") or ""), limit=int(args.get("limit") or 3)
                    )
                except Exception as exc:  # noqa: BLE001
                    hits = {"ok": False, "error": str(exc)}
            else:
                hits = {"ok": False, "error": "no memory backend"}
            calls += 1
            cat_used["memory"] = cat_used.get("memory", 0) + 1
            _emit_tool_call(bus, "memory_search", args, hits, record=record, reason=step.reason)
            executed.append("memory_search")
            if isinstance(hits, list) and hits:
                lines = []
                for h in hits[:3]:
                    if isinstance(h, dict):
                        lines.append(f"- ({h.get('score', '?')}) {str(h.get('text') or '')[:160]}")
                if lines:
                    add_chunk("Memory search (auto):\n" + "\n".join(lines))
            elif isinstance(hits, dict) and hits.get("error"):
                add_chunk(f"Memory search failed: {hits.get('error')}")
            continue

        skipped.append(f"{step.name}:unknown")

    header = _format_header(
        {
            "calls_used": calls,
            "max_tool_calls": max_tool_calls,
            "executed": executed,
            "skipped": skipped,
        }
    )
    if chunks:
        body = "\n---\n".join(chunks)
        context = f"{header}\n{body}"
    else:
        context = header if executed or skipped else ""

    report = PrefetchReport(
        context=context,
        plan=[
            {
                "name": s.name,
                "category": s.category,
                "priority": s.priority,
                "cost": s.cost,
                "reason": s.reason,
                "optional": s.optional,
                "args": s.args,
            }
            for s in plan
        ],
        executed=executed,
        skipped=skipped,
        calls_used=calls,
        max_tool_calls=max_tool_calls,
        context_chars=len(context),
    )
    if return_report:
        return report
    return report.context


def tool_calls_needed(blob: str) -> list[str]:
    """Which tools would prefetch attempt (for tests / planning)."""
    out: list[str] = []
    for step in plan_prefetch(blob or ""):
        if step.name == "install_tool":
            pkg = step.args.get("package", "")
            out.append(f"install_tool:{pkg}")
        else:
            if step.name not in out:
                out.append(step.name)
    return out


def default_max_tool_calls(blob: str) -> int:
    """HTML/UI tasks get a slightly higher call budget."""
    return 8 if wants_design_tools(blob or "") else 6
