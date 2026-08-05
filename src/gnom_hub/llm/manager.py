"""LLM-Manager: DeepSeek + Ollama, free-only + budget guards."""

from __future__ import annotations

import os
from collections.abc import Callable

from gnom_hub.llm.deepseek import DEFAULT_MODEL, DeepSeekClient, estimate_cost_usd
from gnom_hub.llm.ollama import DEFAULT_MODEL as OLLAMA_DEFAULT
from gnom_hub.llm.ollama import OllamaClient
from gnom_hub.llm.types import (
    BudgetExceededError,
    FreeOnlyError,
    LLMMessage,
    LLMResult,
    MissingKeyError,
)

# Free when free_only: all ollama/* local models
FREE_MODELS: frozenset[str] = frozenset(
    {
        "ollama",
        OLLAMA_DEFAULT,
        "llama3.2",
        "llama3.1",
        "llama3",
        "mistral",
        "qwen2.5",
        "phi3",
        "gemma2",
    }
)

ClientFactory = Callable[[str], DeepSeekClient]


class LLMManager:
    """
    Chat completions via DeepSeek (cloud) and/or Ollama (local).

    Model routing:
    - prefix ``ollama/`` or ``ollama:`` → Ollama
    - env/default DeepSeek when key present
    - if no DeepSeek key but Ollama is up → auto Ollama
    """

    def __init__(
        self,
        keys: dict[str, str] | None = None,
        *,
        free_only: bool | None = None,
        max_budget_usd: float | None = None,
        default_model: str = DEFAULT_MODEL,
        client_factory: ClientFactory | None = None,
        ollama_base: str | None = None,
    ) -> None:
        self._keys = dict(keys or {})
        if free_only is None:
            free_only = os.getenv("GNOM_FREE_ONLY", "0").strip() in ("1", "true", "yes")
        if max_budget_usd is None:
            raw = os.getenv("GNOM_MAX_BUDGET_USD", "").strip()
            max_budget_usd = float(raw) if raw else None

        self.free_only = free_only
        self.max_budget_usd = max_budget_usd
        self.default_model = default_model
        self._spent_usd = 0.0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._by_agent: dict[str, dict[str, float | int]] = {}
        self._client_factory = client_factory or (lambda key: DeepSeekClient(key))
        self._ollama = OllamaClient(base_url=ollama_base)
        self._ollama_ok: bool | None = None

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    @property
    def prompt_tokens(self) -> int:
        return self._prompt_tokens

    @property
    def completion_tokens(self) -> int:
        return self._completion_tokens

    def usage_snapshot(self) -> dict:
        return {
            "spent_usd": self._spent_usd,
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "by_agent": {k: dict(v) for k, v in self._by_agent.items()},
        }

    def deepseek_key(self, override: str | None = None) -> str:
        if override and override.strip():
            return override.strip()
        return self._keys.get("DEEPSEEK_API_KEY", "").strip()

    def ollama_available(self, *, force: bool = False) -> bool:
        if self._ollama_ok is not None and not force:
            return self._ollama_ok
        self._ollama_ok = self._ollama.available()
        return self._ollama_ok

    def has_provider(self, name: str = "deepseek") -> bool:
        if name == "deepseek":
            return bool(self.deepseek_key())
        if name == "ollama":
            return self.ollama_available()
        if name in ("any", "llm"):
            return bool(self.deepseek_key()) or self.ollama_available()
        return False

    def providers_snapshot(self) -> dict:
        models: list[str] = []
        if self.ollama_available():
            try:
                models = self._ollama.list_models()
            except Exception:  # noqa: BLE001
                models = []
        return {
            "deepseek": self.has_provider("deepseek"),
            "ollama": self.ollama_available(),
            "ollama_host": self._ollama.base_url,
            "ollama_models": models,
            "default_model": self.default_model,
        }

    def list_ollama_models(self) -> list[str]:
        if not self.ollama_available(force=True):
            return []
        try:
            return self._ollama.list_models()
        except Exception:  # noqa: BLE001
            return []

    def chat(
        self,
        messages: list[LLMMessage] | list[dict[str, str]],
        *,
        model: str | None = None,
        api_key: str | None = None,
        agent: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        provider: str | None = None,
    ) -> LLMResult:
        model_name = model or self.default_model
        prov, bare_model = self._resolve_route(model_name, provider)
        self._check_free_only(bare_model if prov == "ollama" else model_name, prov)

        msgs = self._normalize_messages(messages)

        if prov == "ollama":
            result = self._ollama.chat(
                msgs,
                model=bare_model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
        else:
            key = self.deepseek_key(api_key)
            if not key:
                if self.ollama_available():
                    # graceful fallback
                    result = self._ollama.chat(
                        msgs,
                        model=os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                    )
                else:
                    raise MissingKeyError(
                        "DEEPSEEK_API_KEY missing and Ollama not reachable. "
                        "Add Key.txt or start Ollama (OLLAMA_HOST)."
                    )
            else:
                if self.max_budget_usd is not None:
                    rough = estimate_cost_usd(bare_model, 1000, 1000)
                    if self._spent_usd + rough > self.max_budget_usd and self._spent_usd > 0:
                        raise BudgetExceededError(
                            f"Budget exceeded: spent ${self._spent_usd:.4f} / "
                            f"max ${self.max_budget_usd:.4f}"
                        )
                client = self._client_factory(key)
                result = client.chat(
                    msgs,
                    model=bare_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                )

        self._spent_usd += result.cost_usd
        self._prompt_tokens += result.prompt_tokens
        self._completion_tokens += result.completion_tokens
        agent_key = (agent or "system").strip() or "system"
        bucket = self._by_agent.setdefault(
            agent_key,
            {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "calls": 0},
        )
        bucket["prompt_tokens"] = int(bucket["prompt_tokens"]) + result.prompt_tokens
        bucket["completion_tokens"] = int(bucket["completion_tokens"]) + result.completion_tokens
        bucket["cost_usd"] = float(bucket["cost_usd"]) + result.cost_usd
        bucket["calls"] = int(bucket["calls"]) + 1

        return result

    def _resolve_route(self, model: str, provider: str | None) -> tuple[str, str]:
        m = (model or self.default_model).strip()
        p = (provider or "").strip().lower()
        if p == "ollama" or m.lower().startswith("ollama/") or m.lower().startswith("ollama:"):
            bare = m.split("/", 1)[-1]
            if bare.lower().startswith("ollama:"):
                bare = bare.split(":", 1)[-1]
            if bare.lower().startswith("ollama/"):
                bare = bare.split("/", 1)[-1]
            return "ollama", bare or OLLAMA_DEFAULT
        if p == "deepseek":
            return "deepseek", m
        # Auto: no DeepSeek key → Ollama if available
        if not self.deepseek_key() and self.ollama_available():
            if m.startswith("deepseek"):
                return "ollama", os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT)
            return "ollama", m if m else OLLAMA_DEFAULT
        return "deepseek", m

    def _check_free_only(self, model: str, provider: str) -> None:
        if not self.free_only:
            return
        if provider == "ollama":
            return  # local always free
        bare = model.split("/")[-1]
        if model not in FREE_MODELS and bare not in FREE_MODELS:
            raise FreeOnlyError(
                f"Model '{model}' is not free and free_only is enabled. "
                "Use ollama/* or set GNOM_FREE_ONLY=0."
            )

    @staticmethod
    def _normalize_messages(
        messages: list[LLMMessage] | list[dict[str, str]],
    ) -> list[LLMMessage]:
        out: list[LLMMessage] = []
        for m in messages:
            if isinstance(m, LLMMessage):
                out.append(m)
            else:
                out.append(LLMMessage(role=m["role"], content=m["content"]))
        return out
