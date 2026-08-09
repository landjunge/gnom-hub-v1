"""Shared fact/requirement deduplication strategies (memory + pipeline inject)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Literal

Strategy = Literal["exact", "core", "requirement"]

# Standing-wish / binding prefixes (order: longest first when stripping)
_PREFIXES = ("flex-wish:", "wish:", "user:")


def normalize_whitespace(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def strip_fact_prefixes(text: str) -> str:
    """
    Peel User: / Wish: / Flex-wish: layers (possibly nested).

    'Flex-wish: User: dark theme' → 'dark theme'
    'User: dark theme' → 'dark theme'
    """
    s = normalize_whitespace(text)
    # Drop leading list chrome once
    s = s.lstrip("-•* \t")
    guard = 0
    while s and guard < 6:
        guard += 1
        low = s.lower()
        matched = False
        for p in _PREFIXES:
            if low.startswith(p):
                s = s[len(p) :].strip().lstrip("-•* \t")
                matched = True
                break
        if not matched:
            break
    return s


def exact_key(text: str) -> str:
    """Case-insensitive full-line key (after whitespace collapse)."""
    return normalize_whitespace(text).lower()


def core_key(text: str) -> str:
    """
    Semantic body key: ignore wish prefixes + trailing sentence punct.

    Used so 'User: always dark' and 'Flex-wish: User: always dark.' match.
    """
    body = strip_fact_prefixes(text)
    body = body.rstrip(" .!。…")
    return body.lower()


def requirement_key(text: str) -> str:
    """
    Key for requirement / DoD lists.

    Same as core_key so inject does not double Flex-wish + User lines.
    Non-wish requirements still dedupe on normalized body.
    """
    return core_key(text)


_KEY_FNS: dict[str, Callable[[str], str]] = {
    "exact": exact_key,
    "core": core_key,
    "requirement": requirement_key,
}


def key_for(text: str, strategy: Strategy = "exact") -> str:
    fn = _KEY_FNS.get(strategy) or exact_key
    return fn(text)


def dedupe_texts(
    items: Iterable[str],
    *,
    strategy: Strategy = "exact",
    limit: int | None = None,
    normalize: bool = True,
) -> list[str]:
    """
    Preserve first occurrence order; drop empties and key-collisions.

    strategy:
      exact       — full line lower (HOT/WARM unique-style)
      core        — wish-prefix-agnostic body (Flex / vector)
      requirement — alias of core for inject/DoD lists
    """
    out: list[str] = []
    seen: set[str] = set()
    fn = _KEY_FNS.get(strategy) or exact_key
    for raw in items:
        t = normalize_whitespace(raw) if normalize else str(raw or "").strip()
        if not t:
            continue
        k = fn(t)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(t)
        if limit is not None and len(out) >= limit:
            break
    return out


def already_covered(
    candidate: str,
    existing: Iterable[str],
    *,
    strategy: Strategy = "requirement",
) -> bool:
    """True if candidate's key already appears in existing."""
    k = key_for(candidate, strategy)
    if not k:
        return True
    for e in existing:
        if key_for(e, strategy) == k:
            return True
    return False


def merge_unique(
    base: list[str] | None,
    extra: list[str] | None,
    *,
    strategy: Strategy = "requirement",
    limit: int | None = None,
) -> list[str]:
    """Append extra onto base with strategy dedupe (order: base then extra)."""
    return dedupe_texts([*(base or []), *(extra or [])], strategy=strategy, limit=limit)


def prefer_canonical_wish(text: str) -> str:
    """
    Store/display form for standing wishes: 'User: <body>'.

    Empty body → empty string.
    """
    body = strip_fact_prefixes(text)
    if not body:
        return ""
    return f"User: {body}"[:200]
