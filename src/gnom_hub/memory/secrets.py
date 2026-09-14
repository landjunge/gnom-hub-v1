"""Never put secrets into HOT/WARM/handoffs."""

from __future__ import annotations

import re

_SECRET_WORDS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "bearer ",
    "authorization:",
    "-----begin",
    "private key",
)
_SK = re.compile(r"\bsk-[A-Za-z0-9]{8,}")
_TOKEN_EQ = re.compile(r"\b(token|key|secret)\s*[:=]\s*\S{8,}", re.IGNORECASE)


def looks_like_secret(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    low = t.lower()
    if any(w in low for w in _SECRET_WORDS):
        return True
    return bool(_SK.search(t) or _TOKEN_EQ.search(t))


def filter_secrets(facts: list[str]) -> list[str]:
    out: list[str] = []
    for raw in facts:
        t = " ".join(str(raw).split()).strip()
        if t and not looks_like_secret(t):
            out.append(t)
    return out
