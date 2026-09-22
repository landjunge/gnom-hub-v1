"""Structured V4 choices and canonical conversation helpers."""

from __future__ import annotations

import re
from typing import Any

_META_MARKERS = (
    "let me think",
    "as coordinator",
    "i should propose",
    "i'll propose",
    "i will propose",
    "thinking:",
    "reasoning:",
    "chain of thought",
    "internal:",
    "als koordinator",
    "ich sollte vorschlagen",
)

_COMM_PREF = (
    "antwort",
    "knappe",
    "knapp,",
    "freundlich",
    "höflich",
    "hoeflich",
    "tone",
    "tonfall",
    "sprache wie",
    "minimale antwort",
    "erwartet knappe",
)

_TECH = (
    "html",
    "css",
    "theme",
    "dark",
    "datei",
    "file",
    "truncate",
    "kürzen",
    "kuerzen",
    "worker",
    "deliver",
)

_RULE_MARKERS = (
    "immer",
    "always",
    "never",
    "nie ",
    "nie,",
    "muss ",
    "must ",
    "darf nicht",
    "don't",
    "do not",
    "bitte immer",
    "standing",
    "regel",
    "rule",
    "keep",
    "wish:",
    "flex-wish:",
)

_WISH_PREFIXES = ("flex-wish:", "wish:", "user:")


def conversation_history(state: Any) -> list[dict[str, str]]:
    """Canonical chat for Brainstorm: messages first, turns only as fallback."""
    rows: list[dict[str, str]] = []
    for m in list(getattr(state, "messages", None) or []):
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or m.get("reply_agent_id") or "").strip().lower()
        text = str(m.get("visible_text") or m.get("text") or m.get("user_text") or "").strip()
        if not text:
            continue
        if role == "user":
            rows.append({"role": "user", "text": text})
        elif role in ("agent", "brainstorm"):
            rows.append({"role": "brainstorm", "text": text})
    if rows:
        return rows
    out: list[dict[str, str]] = []
    for t in list(getattr(state, "brainstorm_turns", None) or []):
        if not isinstance(t, dict):
            continue
        role = str(t.get("role") or "").strip().lower()
        text = str(t.get("text") or t.get("content") or "").strip()
        if text and role in ("user", "brainstorm"):
            out.append({"role": role, "text": text})
    return out


def is_coordinator_meta(text: str) -> bool:
    low = str(text or "").strip().lower()
    if not low:
        return True
    if any(m in low[:80] for m in _META_MARKERS):
        return True
    if low.startswith(("ok,", "okay,", "sure,", "hmm", "wait,", "note to self")):
        return True
    return False


def clean_requirement_lines(raw: str) -> list[str]:
    out: list[str] = []
    for ln in (raw or "").splitlines():
        s = ln.strip().lstrip("-•*0123456789. \t")
        if len(s) <= 3 or is_coordinator_meta(s):
            continue
        out.append(s)
    return out[:7]


def _wish_body(low: str) -> str:
    body = low
    for prefix in _WISH_PREFIXES:
        if body.startswith(prefix):
            return body[len(prefix) :].strip()
    return body


def is_binding_standing_rule(text: str) -> bool:
    """True only for explicit standing work rules, not communication facts."""
    s = " ".join(str(text or "").split()).strip()
    if not s:
        return False
    low = s.lower()
    if any(c in low for c in _COMM_PREF) and not any(t in low for t in _TECH):
        return False
    body = _wish_body(low)
    if len(body) < 8:
        return False
    # Explicit Wish:/Flex-wish: lines are standing work orders once they have a body.
    if low.startswith(("wish:", "flex-wish:")):
        return True
    return any(m in low for m in _RULE_MARKERS)


def _clean_choice_body(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("**", "")).strip(" -–—:;")


def parse_offered_choices(text: str) -> list[dict[str, str]]:
    """Turn Brainstorm bullets / A-D lines into at most four structured cards."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in str(text or "").splitlines():
        m = re.match(r"^\s*(?:[-*•]\s+|([A-Da-d])[.)]\s+)(.+)$", line)
        if not m:
            continue
        body = _clean_choice_body(m.group(2) or "")
        if len(body) < 8 or len(body) > 260:
            continue
        if re.match(r"^(was|welche|welcher|wie|oder)\b", body, flags=re.IGNORECASE):
            continue
        key = body.lower()
        if key in seen:
            continue
        seen.add(key)
        letter = (m.group(1) or chr(65 + len(out))).upper()
        title = body if len(body) <= 58 else body[:55] + "…"
        cid = f"choice-{letter.lower()}"
        out.append(
            {
                "id": cid,
                "title": title,
                "effect": body,
                "value": body,
            }
        )
        if len(out) >= 4:
            break
    return out


def last_offered_choice(state: Any) -> dict[str, str] | None:
    """Primary card of the current offer (A of the last offered set)."""
    offered = list(getattr(state, "offered_choices", None) or [])
    if offered and isinstance(offered[0], dict):
        return offered[0]
    confirmed = list(getattr(state, "confirmed_choices", None) or [])
    if confirmed and isinstance(confirmed[-1], dict):
        return confirmed[-1]
    return None
