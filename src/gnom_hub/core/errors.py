"""Central error-handling strategies for Gnom-Hub.

Layers
------
* **LLM** — keys, provider HTTP, budget (see ``config.auth``)
* **Tool** — ToolRetry / ToolFailed / registry validation
* **Pipeline** — cancel, stage failures, honest worker FEHLER
* **API** — map to HTTP without leaking secrets
* **IO** — files, backups, workspace

Rules
-----
1. Never return raw API keys or full Key.txt in messages.
2. Auth / missing-key failures are **terminal** for workers (no stub success).
3. ToolRetry is transient; ToolFailed is terminal after budget.
4. User-facing text: short, actionable; logs may keep more detail.
5. Structured envelope: ``ok``, ``layer``, ``code``, ``message``, ``retryable``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorLayer(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    PIPELINE = "pipeline"
    API = "api"
    VALIDATION = "validation"
    IO = "io"
    AUTH = "auth"
    INTERNAL = "internal"


class ErrorCode(str, Enum):
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"
    VALIDATION = "validation"
    BAD_REQUEST = "bad_request"
    TOOL_FAILED = "tool_failed"
    TOOL_RETRY_EXHAUSTED = "tool_retry_exhausted"
    TOOL_UNKNOWN = "tool_unknown"
    AUTH = "auth"
    MISSING_KEY = "missing_key"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    CANCELLED = "cancelled"
    NOT_FOUND_FILE = "not_found_file"
    INTERNAL = "internal"


# HTTP status by code (API layer)
_HTTP: dict[ErrorCode, int] = {
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.TOOL_UNKNOWN: 404,
    ErrorCode.NOT_FOUND_FILE: 404,
    ErrorCode.VALIDATION: 422,
    ErrorCode.TOOL_FAILED: 422,
    ErrorCode.TOOL_RETRY_EXHAUSTED: 422,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.AUTH: 401,
    ErrorCode.MISSING_KEY: 401,
    ErrorCode.RATE_LIMIT: 429,
    ErrorCode.NETWORK: 502,
    ErrorCode.CANCELLED: 409,
    ErrorCode.INTERNAL: 500,
    ErrorCode.UNKNOWN: 500,
}


def sanitize_message(text: str, *, limit: int = 400) -> str:
    """Strip obvious secret patterns and cap length for API/UI."""
    s = str(text or "").strip()
    # never echo long sk- keys
    if "sk-" in s:
        parts = []
        for tok in s.split():
            if tok.startswith("sk-") and len(tok) > 12:
                parts.append("sk-…")
            else:
                parts.append(tok)
        s = " ".join(parts)
    if len(s) > limit:
        return s[: limit - 1] + "…"
    return s


def error_envelope(
    *,
    message: str,
    code: ErrorCode | str = ErrorCode.UNKNOWN,
    layer: ErrorLayer | str = ErrorLayer.INTERNAL,
    retryable: bool = False,
    detail: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stable JSON shape for tools, API ``detail``, and traces."""
    c = code.value if isinstance(code, ErrorCode) else str(code)
    ly = layer.value if isinstance(layer, ErrorLayer) else str(layer)
    out: dict[str, Any] = {
        "ok": False,
        "layer": ly,
        "code": c,
        "message": sanitize_message(message),
        "retryable": bool(retryable),
    }
    if detail is not None:
        out["detail"] = detail
    if extra:
        for k, v in extra.items():
            if k not in out:
                out[k] = v
    return out


def http_status_for_code(code: ErrorCode | str) -> int:
    if isinstance(code, str):
        try:
            code = ErrorCode(code)
        except ValueError:
            return 500
    return _HTTP.get(code, 500)


def envelope_http(env: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Return (status_code, body) for FastAPI HTTPException detail=body."""
    code = env.get("code") or ErrorCode.UNKNOWN.value
    return http_status_for_code(str(code)), env


def classify_tool_exception(exc: BaseException, *, tool_name: str = "tool") -> dict[str, Any]:
    """Map tool-layer exceptions to an error envelope."""
    from gnom_hub.plugins.retry import ToolFailed, ToolRetry

    name = type(exc).__name__
    msg = sanitize_message(str(exc))

    if isinstance(exc, ToolFailed):
        code = getattr(exc, "code", None) or ErrorCode.TOOL_FAILED
        if isinstance(code, str):
            try:
                code = ErrorCode(code)
            except ValueError:
                code = ErrorCode.TOOL_FAILED
        retryable = bool(getattr(exc, "retryable", False))
        if "exceeded retries" in msg.lower():
            code = ErrorCode.TOOL_RETRY_EXHAUSTED
            retryable = False
        return error_envelope(
            message=msg or f"tool {tool_name!r} failed",
            code=code,
            layer=ErrorLayer.TOOL,
            retryable=retryable,
            extra={"tool": tool_name, "exc_type": name},
        )

    if isinstance(exc, ToolRetry):
        return error_envelope(
            message=msg or "retry",
            code=ErrorCode.TOOL_FAILED,
            layer=ErrorLayer.TOOL,
            retryable=True,
            extra={"tool": tool_name, "exc_type": name},
        )

    if isinstance(exc, KeyError):
        return error_envelope(
            message=msg or f"unknown tool {tool_name!r}",
            code=ErrorCode.TOOL_UNKNOWN,
            layer=ErrorLayer.TOOL,
            retryable=False,
            extra={"tool": tool_name, "exc_type": name},
        )

    if isinstance(exc, (ValueError, TypeError)):
        return error_envelope(
            message=msg or "invalid tool arguments",
            code=ErrorCode.VALIDATION,
            layer=ErrorLayer.VALIDATION,
            retryable=False,
            extra={"tool": tool_name, "exc_type": name},
        )

    return error_envelope(
        message=msg or f"internal tool error ({name})",
        code=ErrorCode.INTERNAL,
        layer=ErrorLayer.INTERNAL,
        retryable=False,
        extra={"tool": tool_name, "exc_type": name},
    )


def classify_generic_exception(exc: BaseException) -> dict[str, Any]:
    """Best-effort map for API routes (backup, workspace, etc.)."""
    from gnom_hub.config.auth import LlmFailureKind, classify_llm_failure

    name = type(exc).__name__
    msg = sanitize_message(str(exc))

    if name == "PipelineCancelled" or "cancelled" in msg.lower():
        return error_envelope(
            message=msg or "cancelled",
            code=ErrorCode.CANCELLED,
            layer=ErrorLayer.PIPELINE,
            retryable=False,
            extra={"exc_type": name},
        )
    if isinstance(exc, FileNotFoundError):
        return error_envelope(
            message=msg or "not found",
            code=ErrorCode.NOT_FOUND_FILE,
            layer=ErrorLayer.IO,
            retryable=False,
            extra={"exc_type": name},
        )
    if isinstance(exc, KeyError):
        return error_envelope(
            message=msg or "not found",
            code=ErrorCode.NOT_FOUND,
            layer=ErrorLayer.API,
            retryable=False,
            extra={"exc_type": name},
        )
    if isinstance(exc, (ValueError, TypeError)):
        return error_envelope(
            message=msg or "bad request",
            code=ErrorCode.VALIDATION,
            layer=ErrorLayer.VALIDATION,
            retryable=False,
            extra={"exc_type": name},
        )

    kind = classify_llm_failure(exc)
    if kind == LlmFailureKind.AUTH:
        return error_envelope(
            message=msg, code=ErrorCode.AUTH, layer=ErrorLayer.AUTH, retryable=False
        )
    if kind == LlmFailureKind.MISSING_KEY:
        return error_envelope(
            message=msg,
            code=ErrorCode.MISSING_KEY,
            layer=ErrorLayer.AUTH,
            retryable=False,
        )
    if kind == LlmFailureKind.RATE_LIMIT:
        return error_envelope(
            message=msg,
            code=ErrorCode.RATE_LIMIT,
            layer=ErrorLayer.LLM,
            retryable=True,
        )
    if kind == LlmFailureKind.NETWORK:
        return error_envelope(
            message=msg, code=ErrorCode.NETWORK, layer=ErrorLayer.LLM, retryable=True
        )

    return error_envelope(
        message=msg or name,
        code=ErrorCode.INTERNAL,
        layer=ErrorLayer.INTERNAL,
        retryable=False,
        extra={"exc_type": name},
    )


def is_retryable_envelope(env: dict[str, Any] | None) -> bool:
    return bool(env and env.get("retryable"))


__all__ = [
    "ErrorCode",
    "ErrorLayer",
    "classify_generic_exception",
    "classify_tool_exception",
    "envelope_http",
    "error_envelope",
    "http_status_for_code",
    "is_retryable_envelope",
    "sanitize_message",
]
