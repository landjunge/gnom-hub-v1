"""Automated Definition-of-Done gate (deterministic checks).

Workers produce drafts; this module:
  - builds DoD prompt text
  - validates drafts against stable lint codes (``dod_lint``)
  - decides retry + emits structured results for UI / Flex

Orchestrator keeps thin wrappers for backward-compatible imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gnom_hub.pipeline.dod_lint import (
    DOD_MARK_END,
    DOD_MARK_START,
    hints_for_issues,
    retryable_from_issues,
    rule_by_code,
    score_from_issues,
)

_INTERACT_TASK_HINTS = (
    "interact",
    "click",
    "demo",
    "nav",
    "todo",
    "filter",
    "state",
    "klick",
    "dom",
    "button",
    "form",
)

_STOP = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "for",
        "with",
        "from",
        "this",
        "that",
        "user",
        "wish",
        "flex",
        "always",
        "immer",
        "bitte",
        "please",
    ]
)


# ── HTML helpers (parity with previous orchestrator impl) ─────────────


def wants_html_artifact(user_text: str, task: str = "") -> bool:
    from gnom_hub.agents.plan_fast_path import _wants_one_html_page

    return _wants_one_html_page(f"{user_text or ''} {task or ''}")


def html_complete(body: str) -> bool:
    """
    True when body looks like a finished single-file HTML document.

    M11: a lone ``</html>`` mid-stream (truncated doc) must not pass.
    """
    s = (body or "").strip()
    if not s:
        return False
    if "```" in s:
        m = re.search(r"```(?:html)?\s*([\s\S]*?)```", s, re.IGNORECASE)
        if m:
            s = m.group(1).strip()
    low = s.lower()
    if "<!doctype" not in low and "<html" not in low:
        return False
    close_idx = low.rfind("</html>")
    if close_idx < 0:
        return False
    after = low[close_idx + len("</html>") :].strip()
    if (
        after
        and not re.fullmatch(r"(<!--.*?-->|\s)*", after, flags=re.DOTALL)
        and (len(after) > 40 or "<" in after)
    ):
        return False
    if close_idx < max(40, int(len(low) * 0.35)) and len(low) > 120 and close_idx < len(low) * 0.5:
        return False
    if low.rstrip().endswith(("...", "…", "<!--", "<style", "<script", "{", "(")):
        return False
    if low.count("<script") > low.count("</script>"):
        return False
    if low.count("<style") > low.count("</style>"):
        return False
    open_tags = low.count("<")
    close_tags = low.count(">")
    return not (open_tags > 5 and close_tags < open_tags * 0.85)


def has_interaction(body: str) -> bool:
    low = (body or "").lower()
    keys = (
        "onclick=",
        "onchange=",
        "onsubmit=",
        "addEventListener",
        "addeventlistener",
        "oninput=",
        "ontoggle=",
    )
    return any(k.lower() in low for k in keys)


def css_heavy_without_js(body: str) -> bool:
    low = (body or "").lower()
    style_n = low.count("<style") + low.count("stylesheet")
    css_blocks = low.count("{")
    js = low.count("<script") + low.count("function ") + low.count("=>")
    interact = has_interaction(body)
    return bool(
        style_n + (1 if css_blocks > 15 else 0) >= 1 and css_blocks > 20 and not interact and js < 2
    )


# ── DoD Spec (prompt + gate share the same structural checklist) ──────


@dataclass
class DoDItem:
    """One checklist line for prompt inject and gate parity."""

    id: str
    label: str
    severity: str = "must"  # must | should | info
    kind: str = "check"  # check | req | wish | order


@dataclass
class DoDSpec:
    wants_html: bool
    items: list[DoDItem] = field(default_factory=list)
    user_snippet: str = ""
    req_lines: list[str] = field(default_factory=list)
    wish_lines: list[str] = field(default_factory=list)
    palette: dict[str, str] = field(default_factory=dict)

    def codes(self) -> list[str]:
        return [i.id for i in self.items]


def build_dod_spec(
    user_text: str,
    requirements: list[str] | None = None,
    *,
    task: str = "",
    tool_calls: list[dict] | None = None,
) -> DoDSpec:
    """Build the single source of truth used by prompt + (conceptually) gate."""
    from gnom_hub.agents.roles_helpers import _is_flex_meta_requirement
    from gnom_hub.memory.dedupe import dedupe_texts

    raw = [str(r) for r in (requirements or []) if r and not _is_flex_meta_requirement(str(r))]
    reqs = list(dedupe_texts(raw, strategy="requirement", limit=6))
    wishes = [r for r in reqs if str(r).lower().startswith(("flex-wish:", "user:", "wish:"))]
    wants = wants_html_artifact(user_text, task)
    items: list[DoDItem] = [
        DoDItem(
            "order",
            "ORDER: (1) structure (2) core functions/interactions "
            "(3) error/empty states (4) CSS last (~30% max).",
            severity="info",
            kind="order",
        ),
    ]
    if wants:
        items.extend(
            [
                DoDItem(
                    "incomplete_html",
                    "Single complete document: <!DOCTYPE html> … </html>",
                    "must",
                    "check",
                ),
                DoDItem(
                    "missing_html_close",
                    "No mid-file truncation; close all tags/braces",
                    "must",
                    "check",
                ),
                DoDItem(
                    "no_interaction",
                    "At least one working interaction (onclick / addEventListener / form)",
                    "should",
                    "check",
                ),
                DoDItem(
                    "empty_states",
                    "Empty/error states only AFTER core functions, never instead of them",
                    "should",
                    "check",
                ),
                DoDItem(
                    "css_budget",
                    "Prefer minimal CSS over incomplete JS",
                    "should",
                    "check",
                ),
            ]
        )
    else:
        items.append(
            DoDItem(
                "runnable",
                "If code is required: runnable/readable end-to-end, not stubs-only",
                "must",
                "check",
            )
        )
    items.append(
        DoDItem(
            "budget",
            "If budget is tight: drop decoration, keep structure + functions + </html>",
            "info",
            "order",
        )
    )
    for r in reqs:
        items.append(DoDItem("req", r, "must", "req"))
    for w in wishes:
        items.append(DoDItem("wish_missing", w, "must", "wish"))
    palette = extract_palette_from_tool_calls(tool_calls)
    if palette:
        items.append(
            DoDItem(
                "prefetch_palette_unused",
                f"Reuse prefetched palette (primary {palette.get('primary') or '…'})",
                "should",
                "check",
            )
        )
    return DoDSpec(
        wants_html=wants,
        items=items,
        user_snippet=(user_text or "").strip()[:400],
        req_lines=reqs,
        wish_lines=wishes,
        palette=palette,
    )


def render_dod_prompt(spec: DoDSpec) -> str:
    """Render DoD prompt text from Spec (prompt never invents extra gates)."""
    lines = [
        DOD_MARK_START,
        "DONE means functional complete — not 'draft exists' or 'pretty CSS only'.",
    ]
    for it in spec.items:
        if it.kind == "order" and it.id == "order":
            lines.append(it.label)

    if spec.wants_html:
        lines.append("If HTML/page/landing/UI is required:")
        for it in spec.items:
            if it.kind == "check" and it.id not in ("runnable",):
                lines.append(f"  [ ] {it.label}")
    else:
        for it in spec.items:
            if it.kind == "check" and it.id == "runnable":
                lines.append(it.label + ".")

    for it in spec.items:
        if it.id == "budget":
            lines.append(it.label + ".")

    if spec.req_lines:
        lines.append("Requirements (MUSS):")
        lines.extend(f"  [ ] {r}" for r in spec.req_lines)
    if spec.wish_lines:
        lines.append("STANDING WISHES — ABSOLUTE (no pushback, implement fully):")
        lines.extend(f"  [!] {r}" for r in spec.wish_lines)
    if spec.user_snippet:
        lines.append(f"User task: {spec.user_snippet}")
    lines.append(DOD_MARK_END)
    return "\n".join(lines)


def definition_of_done(
    user_text: str,
    requirements: list[str] | None = None,
    *,
    task: str = "",
    tool_calls: list[dict] | None = None,
) -> str:
    """Prompt inject — always generated from the same DoDSpec as gate concepts."""
    return render_dod_prompt(
        build_dod_spec(user_text, requirements, task=task, tool_calls=tool_calls)
    )


# ── Prefetch / wish extraction ────────────────────────────────────────


def extract_absolute_wishes(requirements: list[str] | None) -> list[str]:
    out: list[str] = []
    for r in requirements or []:
        s = str(r).strip()
        low = s.lower()
        if low.startswith(("flex-wish:", "user:", "wish:")):
            out.append(s)
    return out


def extract_palette_from_tool_calls(tool_calls: list[dict] | None) -> dict[str, str]:
    """primary/accent/surface/text hex from successful color_palette prefetch."""
    colors: dict[str, str] = {}
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            continue
        if str(tc.get("name") or "") != "color_palette":
            continue
        if tc.get("ok") is False:
            continue
        res = tc.get("result") if isinstance(tc.get("result"), dict) else {}
        # also allow top-level keys if full result stored
        src = res or tc
        for k in ("primary", "accent", "surface", "text"):
            v = src.get(k) if isinstance(src, dict) else None
            if v and re.fullmatch(r"#[0-9a-fA-F]{3,8}", str(v).strip()):
                colors[k] = str(v).strip()
        # css_len only in summary — try args seed path: no hex; skip
    return colors


def _wish_tokens(wish: str) -> list[str]:
    s = re.sub(r"(?i)^(flex-wish:|user:|wish:)\s*", "", wish or "")
    toks = [w.lower() for w in re.findall(r"[a-zA-ZäöüÄÖÜß0-9]{4,}", s)]
    return [t for t in toks if t not in _STOP][:8]


def wish_reflected(body: str, wish: str) -> bool:
    """Heuristic: absolute wish present in deliverable."""
    low = (body or "").lower()
    tokens = _wish_tokens(wish)
    if not tokens:
        return True
    hits = sum(1 for t in tokens if t in low)
    if hits >= max(1, (len(tokens) + 1) // 2):
        return True
    # phrase substring without prefix
    phrase = re.sub(r"(?i)^(flex-wish:|user:|wish:)\s*", "", wish or "").strip().lower()
    if len(phrase) >= 6 and phrase in low:
        return True
    # dark theme special
    return bool(
        any(t in tokens for t in ("dark", "dunkel", "theme", "modus", "mode"))
        and any(
            x in low
            for x in (
                "dark",
                "dunkel",
                "#0f",
                "#0d",
                "#11",
                "#12",
                "background:#0",
                "background: #0",
                "--surface",
                "prefers-color-scheme: dark",
            )
        )
    )


def palette_used(body: str, colors: dict[str, str]) -> bool:
    if not colors:
        return True
    low = body or ""
    if "--color-primary" in low or "--color-accent" in low or "var(--color-" in low:
        return True
    for v in colors.values():
        if v and v.lower() in low.lower():
            return True
    return False


# ── Core check ────────────────────────────────────────────────────────


@dataclass
class DoDResult:
    ok: bool
    issues: list[str] = field(default_factory=list)
    chars: int = 0
    html_complete: bool | None = None
    has_interaction: bool | None = None
    score: int = 100
    retryable: bool = False
    hints: list[str] = field(default_factory=list)
    soft_issues: list[str] = field(default_factory=list)
    checklist: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": list(self.issues),
            "chars": self.chars,
            "html_complete": self.html_complete,
            "has_interaction": self.has_interaction,
            "score": self.score,
            "retryable": self.retryable,
            "hints": list(self.hints),
            "soft_issues": list(self.soft_issues),
            "checklist": list(self.checklist),
        }


def validate_worker_draft(
    body: str,
    *,
    user_text: str = "",
    task: str = "",
    requirements: list[str] | None = None,
    tool_calls: list[dict] | None = None,
) -> dict[str, Any]:
    """Automated DoD check — returns dict compatible with legacy validation + extras."""
    return check_worker_draft(
        body,
        user_text=user_text,
        task=task,
        requirements=requirements,
        tool_calls=tool_calls,
    ).as_dict()


def check_worker_draft(
    body: str,
    *,
    user_text: str = "",
    task: str = "",
    requirements: list[str] | None = None,
    tool_calls: list[dict] | None = None,
) -> DoDResult:
    s = (body or "").strip()
    issues: list[str] = []
    soft: list[str] = []
    checklist: list[dict[str, Any]] = []

    def add(code: str, *, hard: bool | None = None, detail: str = "") -> None:
        rule = rule_by_code(code)
        sev = rule.severity if rule else "must"
        is_hard = hard if hard is not None else sev == "must"
        passed = False
        if is_hard:
            if code not in issues:
                issues.append(code)
        else:
            if code not in soft and code not in issues:
                soft.append(code)
        checklist.append(
            {
                "id": code,
                "label": rule.message if rule else code,
                "severity": sev,
                "pass": passed,
                "detail": detail,
            }
        )

    def ok_item(code: str, detail: str = "") -> None:
        rule = rule_by_code(code)
        checklist.append(
            {
                "id": code,
                "label": rule.message if rule else code,
                "severity": rule.severity if rule else "must",
                "pass": True,
                "detail": detail,
            }
        )

    # Honesty
    if len(s) < 40:
        add("too_short")
    else:
        ok_item("too_short", "length ok")

    if "FEHLER" in s and "Deliverable" in s:
        add("worker_error")
    if (s.startswith("Stub") or "Stub —" in s) and "FEHLER" not in s:
        add("stub")

    if s.rstrip().endswith(("...", "…")) and len(s) > 80:
        add("truncated_ellipsis")

    # HTML
    wants = wants_html_artifact(user_text, task)
    hc: bool | None = None
    hi: bool | None = None
    if wants:
        hc = html_complete(s)
        if not hc:
            add("incomplete_html")
        else:
            ok_item("incomplete_html", "html complete")
        if "</html>" not in s.lower():
            add("missing_html_close")
        elif hc:
            ok_item("missing_html_close")
        hi = has_interaction(s)
        if hc and not hi:
            add("no_interaction", hard=False)
            blob = f"{user_text} {task}".lower()
            if any(k in blob for k in _INTERACT_TASK_HINTS):
                add("missing_required_interaction")
        elif hc and hi:
            ok_item("no_interaction", "has handler")
        if css_heavy_without_js(s):
            add("css_before_functions", hard=False)
    else:
        if "<html" in s.lower() or "<!doctype" in s.lower():
            hc = html_complete(s)
            hi = has_interaction(s)

    # Absolute wishes
    wishes = extract_absolute_wishes(requirements)
    for w in wishes:
        if not wish_reflected(s, w):
            add("wish_missing", detail=w[:120])
            break  # one code is enough for gate; detail lists first miss
        ok_item("wish_missing", "wish reflected")

    # Prefetch palette
    colors = extract_palette_from_tool_calls(tool_calls)
    if colors:
        if not palette_used(s, colors):
            add("prefetch_palette_unused", hard=False, detail=str(colors.get("primary") or ""))
        else:
            ok_item("prefetch_palette_unused", "palette present")

    # Merge soft codes into issues list (legacy UI expects them there)
    all_listed: list[str] = list(issues)
    for c in soft:
        if c not in all_listed:
            all_listed.append(c)

    must_codes = []
    for c in issues:
        rule = rule_by_code(c)
        if rule is None or rule.severity == "must":
            must_codes.append(c)
    ok = len(must_codes) == 0
    retryable = retryable_from_issues(must_codes if must_codes else (soft if soft else all_listed))
    # Soft-only: ok stays True; still expose retryable for optional palette retry
    if ok and soft:
        retryable = retryable_from_issues(soft)
    hints = hints_for_issues(must_codes or all_listed, limit=6)

    return DoDResult(
        ok=ok,
        issues=all_listed,
        chars=len(s),
        html_complete=hc,
        has_interaction=hi,
        score=score_from_issues(all_listed),
        retryable=retryable,
        hints=hints,
        soft_issues=soft,
        checklist=checklist,
    )


def should_retry(
    result: dict[str, Any] | DoDResult, *, user_text: str = "", task: str = ""
) -> tuple[bool, str]:
    """Whether automated gate should trigger another worker attempt."""
    d = result.as_dict() if isinstance(result, DoDResult) else dict(result or {})
    issues = list(d.get("issues") or [])
    if "worker_error" in issues or "stub" in issues:
        return False, ""
    if not d.get("retryable", False) and d.get("ok", True):
        # soft-only optional retry for html incomplete already covered
        pass
    if "incomplete_html" in issues or (
        wants_html_artifact(user_text, task) and d.get("html_complete") is False
    ):
        return True, "incomplete_html"
    if "missing_required_interaction" in issues:
        return True, "missing_interaction"
    if "wish_missing" in issues:
        return True, "wish_missing"
    if "prefetch_palette_unused" in issues and d.get("retryable"):
        return True, "prefetch_palette"
    if not d.get("ok", True) and wants_html_artifact(user_text, task) and d.get("retryable", True):
        return True, "gate_fail"
    if not d.get("ok", True) and d.get("retryable"):
        return True, "gate_fail"
    return False, ""


def format_retry_hint(result: dict[str, Any] | DoDResult, *, attempt: int = 1) -> str:
    d = result.as_dict() if isinstance(result, DoDResult) else dict(result or {})
    issues = list(d.get("issues") or [])
    hints = list(d.get("hints") or []) or hints_for_issues(issues)
    if attempt <= 1:
        lines = [
            "RETRY (DoD Gate — automated):",
            "Failed checks:",
        ]
        for h in hints[:5]:
            lines.append(f"- {h}")
        if not hints:
            lines.append(f"- issues: {', '.join(issues) or 'unknown'}")
        lines.append(
            "Deliver ONE complete result. Prefer structure + functions over decoration. "
            "If Tool prefetch has a palette, reuse it."
        )
        return "\n".join(lines)
    return (
        "RETRY 2 — SCOPE REDUCTION (DoD Gate):\n"
        "- Smaller but COMPLETE deliverable\n"
        "- Drop decorative CSS; keep core interactions\n"
        "- MUST satisfy absolute wishes and close HTML if required\n"
        f"Issues: {', '.join(issues)}\n" + "\n".join(f"- {h}" for h in hints[:4])
    )


def emit_dod_event(bus: Any, payload: dict[str, Any]) -> None:
    if bus is not None and hasattr(bus, "emit"):
        try:
            bus.emit("pipeline.dod_gate", payload)
        except Exception:  # noqa: BLE001
            pass


def run_dod_check(
    body: str,
    *,
    user_text: str = "",
    task: str = "",
    requirements: list[str] | None = None,
    tool_calls: list[dict] | None = None,
    bus: Any = None,
    worker: str = "",
) -> dict[str, Any]:
    """One-shot automated check + optional event (for API / pipeline)."""
    result = check_worker_draft(
        body,
        user_text=user_text,
        task=task,
        requirements=requirements,
        tool_calls=tool_calls,
    )
    d = result.as_dict()
    emit_dod_event(
        bus,
        {
            "worker": worker,
            "ok": d["ok"],
            "issues": d["issues"],
            "score": d["score"],
            "retryable": d["retryable"],
            "chars": d["chars"],
        },
    )
    return d
