"""Minimal DeepSeek chat client (OpenAI-compatible HTTP, stdlib only)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from gnom_hub.llm.types import LLMError, LLMMessage, LLMResult

DEFAULT_BASE_URL = "https://api.deepseek.com"
# Official model id (DeepSeek API Docs 2026): deepseek-v4-flash
# https://api-docs.deepseek.com/quick_start/pricing/
DEFAULT_MODEL = "deepseek-v4-flash"

# Approx. USD per 1M tokens (input, output) — budget guard only, not billing
_PRICE_PER_M: dict[str, tuple[float, float]] = {
    # USD per 1M tokens (cache-miss input / output) — api-docs.deepseek.com pricing
    "deepseek-v4-flash": (0.14, 0.28),
    "deepseek-v4-pro": (0.435, 0.87),
    # Legacy aliases (older docs / compatibility)
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
}

HttpPost = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = _PRICE_PER_M.get(model, (1.0, 2.0))  # conservative default
    return (prompt_tokens * pin + completion_tokens * pout) / 1_000_000


def _default_http_post(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise LLMError(f"DeepSeek network error: {e.reason}") from e


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        http_post: HttpPost | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LLMError("DeepSeek API key is empty")
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http_post = http_post or _default_http_post

    def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
    ) -> LLMResult:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if top_p is not None:
            payload["top_p"] = top_p
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty

        # V4 Flash/Pro default to thinking=on; that burns max_tokens and often
        # leaves message.content empty. Hub UX needs stable non-thinking output.
        # Docs: {"thinking": {"type": "enabled"|"disabled"}}
        # Override: DEEPSEEK_THINKING=1 to enable.
        thinking_on = os.getenv("DEEPSEEK_THINKING", "0").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if "deepseek-v4" in model.lower():
            payload["thinking"] = {"type": "enabled" if thinking_on else "disabled"}

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        status, raw = self._http_post(url, headers, body, self.timeout)
        try:
            data = json.loads(raw.decode("utf-8") if raw else "{}")
        except json.JSONDecodeError as e:
            raise LLMError(f"DeepSeek invalid JSON (HTTP {status})") from e

        if status >= 400:
            msg = data.get("error", data) if isinstance(data, dict) else data
            raise LLMError(f"DeepSeek HTTP {status}: {msg}")

        try:
            msg = data["choices"][0]["message"]
            content = msg.get("content")
            # Thinking mode may put text only in reasoning_content
            if content is None or (isinstance(content, str) and not content.strip()):
                reasoning = msg.get("reasoning_content") or msg.get("reasoning")
                if isinstance(reasoning, str) and reasoning.strip():
                    content = reasoning
            if content is None:
                content = ""
            elif not isinstance(content, str):
                content = str(content)
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"DeepSeek unexpected response shape: {data!r}") from e

        if not str(content).strip():
            raise LLMError(
                "DeepSeek empty content (enable DEEPSEEK_THINKING=0 or raise max_tokens)"
            )

        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        used_model = str(data.get("model") or model)

        return LLMResult(
            content=content or "",
            model=used_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=estimate_cost_usd(model, prompt_tokens, completion_tokens),
            raw=data if isinstance(data, dict) else {},
        )
