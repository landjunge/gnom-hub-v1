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
    if not memory_ctx:
        return ""
    bad = (
        "localstorage",
        "notiz-speicher",
        "notizspeicher",
        "notes app",
        "ohne backend, der notizen",
        "json-array in localstorage",
        "json in localstorage",
        "responsive liste",
        "mini-notiz",
        "note storage",
        "notebook",
    )
    kept: list[str] = []
    for ln in memory_ctx.splitlines():
        low = ln.lower()
        if any(b in low for b in bad):
            continue
        if "gnom-hub" in low and ("ist ein" in low or "is a" in low or "is an" in low):
            continue
        kept.append(ln)
    return "\n".join(kept).strip()


def _is_garbage_fact(text: str) -> bool:
    low = text.lower()
    markers = (
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
    return any(b in low for b in markers) or (
        "gnom-hub" in low and ("ist ein" in low or "is a" in low or "is an" in low)
    )


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
