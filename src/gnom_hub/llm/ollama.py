"""Ollama local LLM client (native /api/chat, stdlib only)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from gnom_hub.llm.types import LLMError, LLMMessage, LLMResult

DEFAULT_BASE_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        try:
            self.list_models()
            return True
        except Exception:  # noqa: BLE001
            return False

    def list_models(self) -> list[str]:
        """Return installed model names from /api/tags."""
        url = f"{self.base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8") if raw else "{}")
        models = data.get("models") or []
        names: list[str] = []
        for m in models:
            if isinstance(m, dict) and m.get("name"):
                names.append(str(m["name"]))
            elif isinstance(m, str):
                names.append(m)
        return names

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
        _ = frequency_penalty, presence_penalty  # not used by ollama chat
        url = f"{self.base_url}/api/chat"
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if top_p is not None:
            options["top_p"] = top_p
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": options,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                status = resp.getcode()
        except urllib.error.HTTPError as e:
            raw = e.read()
            status = e.code
        except urllib.error.URLError as e:
            raise LLMError(f"Ollama network error: {e.reason}") from e

        try:
            data = json.loads(raw.decode("utf-8") if raw else "{}")
        except json.JSONDecodeError as e:
            raise LLMError(f"Ollama invalid JSON (HTTP {status})") from e

        if status >= 400:
            raise LLMError(f"Ollama HTTP {status}: {data}")

        msg = data.get("message") or {}
        content = str(msg.get("content") or "")
        # ollama may report eval counts
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        return LLMResult(
            content=content,
            model=str(data.get("model") or model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=0.0,
            raw=data if isinstance(data, dict) else {},
        )
