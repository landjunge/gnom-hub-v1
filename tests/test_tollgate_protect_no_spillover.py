"""F-03: GNOM_TOLLGATE_LLM=1 must never fall through to legacy DeepSeek on Protect deny."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gnom_hub.llm.manager import LLMManager, raise_tollgate_chat_error
from gnom_hub.llm.types import BudgetExceededError, LLMError, LLMMessage


def test_protect_deny_raises_budget_exceeded_no_legacy(monkeypatch):
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "1")
    monkeypatch.setenv("TOLLGATE_URL", "http://127.0.0.1:8787")
    monkeypatch.setenv("TOLLGATE_CONSUMER", "gnom")

    keys = {"DEEPSEEK_API_KEY": "sk-abcdefghijklmnop-realish"}
    m = LLMManager(keys=keys)
    # Ensure key path is considered usable
    monkeypatch.setattr(m, "deepseek_key", lambda override=None: keys["DEEPSEEK_API_KEY"])
    monkeypatch.setattr(m, "ollama_available", lambda force=False: False)

    legacy = MagicMock()
    m._client_factory = lambda key: legacy  # type: ignore[method-assign]

    def boom(*_a, **_k):
        raise BudgetExceededError("agent protection: consumer gnom max_tokens_request 2003 > 50")

    monkeypatch.setattr(m, "_chat_via_tollgate", boom)

    with pytest.raises(BudgetExceededError, match="agent protection"):
        m.chat(
            [LLMMessage(role="user", content="hi")],
            model="deepseek-v4-flash",
            agent="brainstorm",
            max_tokens=2000,
        )
    legacy.chat.assert_not_called()


def test_generic_llm_error_also_hard_fails_when_force_tg(monkeypatch):
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "1")
    keys = {"DEEPSEEK_API_KEY": "sk-abcdefghijklmnop-realish"}
    m = LLMManager(keys=keys)
    monkeypatch.setattr(m, "deepseek_key", lambda override=None: keys["DEEPSEEK_API_KEY"])
    monkeypatch.setattr(m, "ollama_available", lambda force=False: False)
    legacy = MagicMock()
    m._client_factory = lambda key: legacy  # type: ignore[method-assign]
    monkeypatch.setattr(
        m, "_chat_via_tollgate", lambda *a, **k: (_ for _ in ()).throw(LLMError("upstream 503"))
    )
    with pytest.raises(LLMError, match="503"):
        m.chat(
            [LLMMessage(role="user", content="hi")],
            model="deepseek-v4-flash",
            agent="brainstorm",
        )
    legacy.chat.assert_not_called()


def test_optional_tollgate_may_fall_through_when_force_off(monkeypatch):
    """GNOM_TOLLGATE_LLM=0 and via_tg from provider still can use legacy — not force path.

    When force is off and provider is deepseek, via_tg may still be true if TOLLGATE_URL set.
    Clear TOLLGATE_URL and force off so legacy runs.
    """
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "0")
    monkeypatch.delenv("TOLLGATE_URL", raising=False)
    keys = {"DEEPSEEK_API_KEY": "sk-abcdefghijklmnop-realish"}
    m = LLMManager(keys=keys)
    monkeypatch.setattr(m, "deepseek_key", lambda override=None: keys["DEEPSEEK_API_KEY"])
    monkeypatch.setattr(m, "ollama_available", lambda force=False: False)

    class FakeClient:
        def chat(self, *a, **k):
            from gnom_hub.llm.types import LLMResult

            return LLMResult(
                content="legacy-ok", model="deepseek", prompt_tokens=1, completion_tokens=1
            )

    m._client_factory = lambda key: FakeClient()  # type: ignore[method-assign]
    monkeypatch.setattr(m, "_tollgate_admit", lambda *a, **k: None)
    monkeypatch.setattr(m, "_tollgate_record", lambda *a, **k: None)

    r = m.chat(
        [LLMMessage(role="user", content="hi")],
        model="deepseek-v4-flash",
        agent="brainstorm",
    )
    assert r.content == "legacy-ok"


def test_agent_protection_string_maps_to_budget_exceeded():
    out = {
        "ok": False,
        "error": "agent protection: consumer gnom max_tokens_request 2003 > 50",
    }
    with pytest.raises(BudgetExceededError, match="agent protection"):
        raise_tollgate_chat_error(out)
