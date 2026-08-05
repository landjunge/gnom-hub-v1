"""Shared helpers for role agents."""

from __future__ import annotations

import re


def _format_brainstorm_history(history: list[dict]) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for turn in history[-12:]:
        role = str(turn.get("role") or "user")
        text = str(turn.get("text") or "").strip()
        if not text:
            continue
        label = "User" if role == "user" else "Brainstorm"
        lines.append(f"{label}: {text[:800]}")
    return "\n".join(lines)


def _brainstorm_user_payload(user_text: str, hist_block: str) -> str:
    if not hist_block:
        return f"USER MESSAGE:\n{user_text}"
    return f"Earlier brainstorm dialogue:\n{hist_block}\n\nLatest USER MESSAGE:\n{user_text}"


def _stub_brainstorm(user_text: str, history: list[dict]) -> str:
    n = len([t for t in history if t.get("role") == "user"]) + 1
    if n <= 1:
        return (
            f"Ideen zu: {user_text}\n"
            "• Ziel und Nutzerwert in einem Satz schärfen\n"
            "• 3–5 Richtungen skizzieren (MVP vs. später)\n"
            "• Was darf bewusst weglassen werden?\n"
            "• Welches Ergebnis soll am Ende in Box 3 liegen?\n"
            "→ Was soll ich als Nächstes vertiefen?"
        )
    return (
        f"Weitergedacht (Runde {n}) zu: {user_text}\n"
        "• Vorherige Ideen enger zusammenführen\n"
        "• Eine Richtung priorisieren\n"
        "• Offene Frage klären, bevor wir ausführen\n"
        "→ Sag 'Execute' / klick Execute, wenn genug gesammelt ist — "
        "oder schreib weiter zum Feinschliff."
    )


def _with_memory(text: str, memory_ctx: str) -> str:
    ctx = _sanitize_memory_ctx(memory_ctx)
    if not ctx:
        return f"USER TASK (only this matters):\n{text}"
    return (
        f"USER TASK (only this matters):\n{text}\n\n"
        f"Optional background facts (ignore if unrelated or nonsense):\n{ctx[:600]}"
    )


def _sanitize_memory_ctx(memory_ctx: str) -> str:
    """Drop garbage lines from memory context before injecting into prompts."""
    if not memory_ctx:
        return ""
    kept: list[str] = []
    for ln in memory_ctx.splitlines():
        s = ln.strip()
        if not s:
            continue
        # keep section headers from pipeline_context
        if s.endswith(":") and len(s) < 40:
            kept.append(ln)
            continue
        body = s.lstrip("-•* ").strip()
        if body and not _is_garbage_fact(body):
            kept.append(ln)
    return "\n".join(kept).strip()


def _is_garbage_fact(text: str) -> bool:
    """
    True if text must never enter HOT/WARM as a fact.

    Rejects HTML/code dumps, empty meta from the Memory LLM, pipeline chatter,
    and known product-hallucination loops — not a second product layer.
    """
    t = " ".join(str(text or "").split()).strip()
    if not t:
        return True
    if len(t) < 8:
        return True
    # bare markdown / list chrome
    if re.fullmatch(r"#{1,6}\s*[\w\s\-]+", t):
        return True
    if t in ("## Requirements", "Requirements", "HOT facts", "WARM facts"):
        return True

    low = t.lower()

    # empty / meta answers from Memory agent
    meta_exact = (
        "(none)",
        "none",
        "n/a",
        "(no relevant memory)",
        "(no durable facts to store)",
        "no durable facts to store",
        "no personal preferences or long-term commitments stated yet.",
        "no personal preferences or long-term commitments stated yet",
    )
    if low in meta_exact or low.startswith("(no ") or low.startswith("no durable"):
        return True
    if "nothing to store" in low or "no relevant memory" in low:
        return True
    if low.startswith("memory:") and ("store" in low or "durable" in low):
        return True

    # HTML / code dumps
    html_markers = (
        "<!doctype",
        "<html",
        "</html>",
        "<head",
        "<body",
        "<meta ",
        "<div",
        "<script",
        "<style",
        "```html",
        "```css",
        "```js",
        "```javascript",
    )
    if any(m in low for m in html_markers):
        return True
    if t.lstrip().startswith("<") and ">" in t[:80]:
        return True
    if low.count("<") >= 2 and low.count(">") >= 2:
        return True

    # pipeline / worker meta (not user knowledge)
    pipeline_meta = (
        "worker produced",
        "worker built",
        "worker-output",
        "worker output",
        "partial html",
        "incomplete css",
        "truncated",
        "max_tokens",
        "quality check",
        "fehlerschicht",
        "user is testing gnom",
        "basic brainstorm task (b1)",
        "basic tests (b1)",
        "running basic tests",
    )
    if any(m in low for m in pipeline_meta):
        return True

    # known hallucination loop topics from older sessions
    notes_markers = (
        "localstorage",
        "notiz-speicher",
        "notizspeicher",
        "ohne backend",
        "json-array",
        "json in localstorage",
        "responsive liste",
        "notes app",
        "note storage",
        "mini-notiz",
        "notiztext",
    )
    if any(b in low for b in notes_markers):
        return True
    if "gnom-hub" in low and ("ist ein" in low or "is a" in low or "is an" in low):
        return True

    # broken markdown fragments like "Today** – …"
    if re.search(r"\w\*\*\s*[–—-]", t):
        return True

    return False


def _lines(raw: str) -> list[str]:
    out: list[str] = []
    for ln in (raw or "").splitlines():
        s = ln.strip().lstrip("-•*0123456789. \t")
        if len(s) > 3:
            out.append(s)
    return out


def _needs_clarify(text: str) -> bool:
    if "?" in text:
        return True
    return bool(re.search(r"\b(maybe|vielleicht|eventuell)\b", text, flags=re.IGNORECASE))
