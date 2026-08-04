"""Shared LLM types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class LLMResult:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    raw: dict = field(default_factory=dict, repr=False)


class LLMError(Exception):
    """Base LLM failure."""


class MissingKeyError(LLMError):
    """API key not configured."""


class BudgetExceededError(LLMError):
    """Session budget would be exceeded."""


class FreeOnlyError(LLMError):
    """Paid model blocked because free_only is on."""
