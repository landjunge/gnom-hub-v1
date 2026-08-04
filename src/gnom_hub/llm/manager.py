"""LLM-Manager: provider facade, free-only + budget guards."""

from __future__ import annotations

import os
from collections.abc import Callable

from gnom_hub.llm.deepseek import DEFAULT_MODEL, DeepSeekClient, estimate_cost_usd
from gnom_hub.llm.types import (
    BudgetExceededError,
    FreeOnlyError,
    LLMError,
    LLMMessage,
    LLMResult,
    MissingKeyError,
)

# Models treated as free when free_only is enabled (empty in v1 step 0.2).
FREE_MODELS: frozenset[str] = frozenset()

ClientFactory = Callable[[str], DeepSeekClient]


class LLMManager:
    """
    Thin manager for chat completions.

    Step 0.2: DeepSeek only. Per-agent model/key overrides via chat() kwargs.
    """

    def __init__(
        self,
        keys: dict[str, str] | None = None,
        *,
        free_only: bool | None = None,
        max_budget_usd: float | None = None,
        default_model: str = DEFAULT_MODEL,
        client_factory: ClientFactory | None = None,
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
        self._client_factory = client_factory or (lambda key: DeepSeekClient(key))

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    def deepseek_key(self, override: str | None = None) -> str:
        if override and override.strip():
            return override.strip()
        return self._keys.get("DEEPSEEK_API_KEY", "").strip()

    def has_provider(self, name: str = "deepseek") -> bool:
        if name == "deepseek":
            return bool(self.deepseek_key())
        return False

    def chat(
        self,
        messages: list[LLMMessage] | list[dict[str, str]],
        *,
        model: str | None = None,
        api_key: str | None = None,
        agent: str | None = None,  # reserved for per-agent routing later
        temperature: float = 0.7,
        max_tokens: int | None = None,
        provider: str = "deepseek",
    ) -> LLMResult:
        _ = agent  # step 0.2: single provider; hook for later
        if provider != "deepseek":
            raise LLMError(f"Unknown provider: {provider}")

        model_name = model or self.default_model
        self._check_free_only(model_name)

        key = self.deepseek_key(api_key)
        if not key:
            raise MissingKeyError(
                "DEEPSEEK_API_KEY missing. Add it to Key.txt or .env (see Key.txt.example)."
            )

        # Pre-check budget with a tiny estimate (1k in / 1k out) so we fail fast
        if self.max_budget_usd is not None:
            rough = estimate_cost_usd(model_name, 1000, 1000)
            if self._spent_usd + rough > self.max_budget_usd and self._spent_usd > 0:
                raise BudgetExceededError(
                    f"Budget exceeded: spent ${self._spent_usd:.4f} / "
                    f"max ${self.max_budget_usd:.4f}"
                )

        msgs = self._normalize_messages(messages)
        client = self._client_factory(key)
        result = client.chat(msgs, model=model_name, temperature=temperature, max_tokens=max_tokens)

        self._spent_usd += result.cost_usd
        if self.max_budget_usd is not None and self._spent_usd > self.max_budget_usd:
            # Call already happened; record spend and flag next call
            pass

        return result

    def _check_free_only(self, model: str) -> None:
        if not self.free_only:
            return
        # Strip provider prefixes if any
        bare = model.split("/")[-1]
        if model not in FREE_MODELS and bare not in FREE_MODELS:
            raise FreeOnlyError(
                f"Model '{model}' is not free and free_only is enabled. "
                "Set GNOM_FREE_ONLY=0 or use an allowed free model."
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
