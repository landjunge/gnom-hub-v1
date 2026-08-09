"""API-key / provider auth classification (no secrets in logs or snapshots)."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from gnom_hub.config.keys import is_usable_api_key

# Re-export for call sites that only need auth helpers
__all__ = [
    "KeyStatus",
    "LlmFailureKind",
    "classify_api_key",
    "classify_llm_failure",
    "is_auth_failure",
    "key_fingerprint",
    "keys_auth_snapshot",
    "mask_secret",
    "user_message_for_failure",
]


class KeyStatus(str, Enum):
    MISSING = "missing"
    PLACEHOLDER = "placeholder"
    USABLE = "usable"


class LlmFailureKind(str, Enum):
    MISSING_KEY = "missing_key"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    BUDGET = "budget"
    FREE_ONLY = "free_only"
    OTHER = "other"


_AUTH_RE = re.compile(
    r"(401|403|authentication|unauthorized|invalid.?api.?key|api key.*(invalid|wrong)|"
    r"incorrect api key|permission.?denied)",
    re.IGNORECASE,
)
_RATE_RE = re.compile(r"(429|rate.?limit|too many requests|quota)", re.IGNORECASE)
_NET_RE = re.compile(
    r"(network|timeout|timed out|connection|dns|unreachable|urlerror)", re.IGNORECASE
)


def classify_api_key(value: str | None) -> KeyStatus:
    s = (value or "").strip()
    if not s:
        return KeyStatus.MISSING
    if is_usable_api_key(s):
        return KeyStatus.USABLE
    return KeyStatus.PLACEHOLDER


def key_fingerprint(value: str | None) -> str:
    """Short non-reversible-ish id for session blocklists (not a secret)."""
    s = (value or "").strip()
    if not s:
        return ""
    # last 6 + length — enough to de-dupe blocked keys without full leak
    return f"len{len(s)}:{s[-6:]}"


def mask_secret(value: str | None, *, keep: int = 4) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) <= keep:
        return "*" * len(s)
    return f"…{s[-keep:]}"


def classify_llm_failure(exc: BaseException | str) -> LlmFailureKind:
    if isinstance(exc, BaseException):
        name = type(exc).__name__
        msg = str(exc)
        # typed errors first
        if name == "MissingKeyError":
            return LlmFailureKind.MISSING_KEY
        if name == "AuthError":
            return LlmFailureKind.AUTH
        if name == "RateLimitError":
            return LlmFailureKind.RATE_LIMIT
        if name == "BudgetExceededError":
            return LlmFailureKind.BUDGET
        if name == "FreeOnlyError":
            return LlmFailureKind.FREE_ONLY
    else:
        msg = str(exc)
    if _AUTH_RE.search(msg):
        return LlmFailureKind.AUTH
    if _RATE_RE.search(msg):
        return LlmFailureKind.RATE_LIMIT
    if _NET_RE.search(msg):
        return LlmFailureKind.NETWORK
    if "missing" in msg.lower() and "key" in msg.lower():
        return LlmFailureKind.MISSING_KEY
    return LlmFailureKind.OTHER


def is_auth_failure(exc: BaseException | str) -> bool:
    return classify_llm_failure(exc) == LlmFailureKind.AUTH


def user_message_for_failure(exc: BaseException | str, *, role: str = "worker") -> str:
    kind = classify_llm_failure(exc)
    if kind == LlmFailureKind.AUTH:
        return (
            "Authentifizierung fehlgeschlagen (API-Key ungültig/abgelaufen). "
            "User/Key.txt prüfen — keinen sk-your-… Platzhalter."
        )
    if kind == LlmFailureKind.MISSING_KEY:
        return "Kein nutzbarer LLM-Key (DeepSeek/Ollama). Key.txt: echten DEEPSEEK_API_KEY setzen."
    if kind == LlmFailureKind.RATE_LIMIT:
        return "Rate-Limit / Quota erreicht — später erneut versuchen."
    if kind == LlmFailureKind.NETWORK:
        return f"Netzwerkfehler zum LLM: {str(exc)[:160]}"
    if kind == LlmFailureKind.BUDGET:
        return "Session-Budget überschritten (GNOM_MAX_BUDGET_USD)."
    if kind == LlmFailureKind.FREE_ONLY:
        return "Paid-Model blockiert (GNOM_FREE_ONLY=1)."
    return f"LLM-Fehler ({role}): {str(exc)[:280]}"


def keys_auth_snapshot(keys: dict[str, str] | None) -> dict[str, Any]:
    """Safe status for /api/health and snapshot — never includes raw secrets."""
    k = keys or {}
    sys_raw = (k.get("DEEPSEEK_API_KEY") or "").strip()
    wrk_raw = (k.get("WORKER_API_KEY") or "").strip()
    sys_st = classify_api_key(sys_raw)
    wrk_st = classify_api_key(wrk_raw)
    # effective worker: worker key or fall back to system
    if wrk_st == KeyStatus.USABLE:
        eff_worker = KeyStatus.USABLE
        eff_source = "WORKER_API_KEY"
    elif sys_st == KeyStatus.USABLE:
        eff_worker = KeyStatus.USABLE
        eff_source = "DEEPSEEK_API_KEY"
    elif wrk_st == KeyStatus.PLACEHOLDER or sys_st == KeyStatus.PLACEHOLDER:
        eff_worker = KeyStatus.PLACEHOLDER
        eff_source = "WORKER_API_KEY" if wrk_raw else "DEEPSEEK_API_KEY"
    else:
        eff_worker = KeyStatus.MISSING
        eff_source = ""
    return {
        "system": sys_st.value,
        "worker": wrk_st.value,
        "worker_effective": eff_worker.value,
        "worker_source": eff_source,
        "system_tail": mask_secret(sys_raw) if sys_st == KeyStatus.USABLE else "",
        "ready": sys_st == KeyStatus.USABLE or wrk_st == KeyStatus.USABLE,
        "placeholder_detected": sys_st == KeyStatus.PLACEHOLDER or wrk_st == KeyStatus.PLACEHOLDER,
    }
