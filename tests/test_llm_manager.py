import json

import pytest

from gnom_hub.llm.deepseek import DeepSeekClient
from gnom_hub.llm.manager import LLMManager
from gnom_hub.llm.types import (
    BudgetExceededError,
    FreeOnlyError,
    LLMMessage,
    MissingKeyError,
)


def _fake_http_ok(url, headers, body, timeout):
    payload = {
        "model": "deepseek-chat",
        "choices": [{"message": {"role": "assistant", "content": "pong"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    return 200, json.dumps(payload).encode("utf-8")


def _fake_http_error(url, headers, body, timeout):
    return 401, json.dumps({"error": {"message": "bad key"}}).encode("utf-8")


def test_chat_success_with_mock():
    mgr = LLMManager(
        keys={"DEEPSEEK_API_KEY": "sk-test"},
        client_factory=lambda key: DeepSeekClient(key, http_post=_fake_http_ok),
    )
    result = mgr.chat([LLMMessage(role="user", content="ping")])
    assert result.content == "pong"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.cost_usd > 0
    assert mgr.spent_usd == result.cost_usd


def test_chat_accepts_dict_messages():
    mgr = LLMManager(
        keys={"DEEPSEEK_API_KEY": "sk-test"},
        client_factory=lambda key: DeepSeekClient(key, http_post=_fake_http_ok),
    )
    result = mgr.chat([{"role": "user", "content": "hi"}])
    assert result.content == "pong"


def test_missing_key():
    mgr = LLMManager(keys={})
    mgr._ollama_ok = False  # no local fallback in unit test
    with pytest.raises(MissingKeyError):
        mgr.chat([LLMMessage(role="user", content="x")])


def test_ollama_model_prefix_routes(monkeypatch):
    mgr = LLMManager(keys={})
    mgr._ollama_ok = True
    called: dict = {}

    def fake_chat(messages, **kwargs):
        called.update(kwargs)
        from gnom_hub.llm.types import LLMResult

        return LLMResult(content="local", model=kwargs.get("model", "x"))

    mgr._ollama.chat = fake_chat  # type: ignore[method-assign]
    result = mgr.chat([LLMMessage(role="user", content="hi")], model="ollama/llama3.2")
    assert result.content == "local"
    assert called.get("model") == "llama3.2"


def test_free_only_blocks_paid_model():
    mgr = LLMManager(
        keys={"DEEPSEEK_API_KEY": "sk-test"},
        free_only=True,
        client_factory=lambda key: DeepSeekClient(key, http_post=_fake_http_ok),
    )
    with pytest.raises(FreeOnlyError):
        mgr.chat([LLMMessage(role="user", content="x")])


def test_budget_blocks_second_call():
    mgr = LLMManager(
        keys={"DEEPSEEK_API_KEY": "sk-test"},
        max_budget_usd=0.0000001,  # tiny
        client_factory=lambda key: DeepSeekClient(key, http_post=_fake_http_ok),
    )
    # First call may still go through (pre-check only after spend > 0)
    mgr.chat([LLMMessage(role="user", content="a")])
    with pytest.raises(BudgetExceededError):
        mgr.chat([LLMMessage(role="user", content="b")])


def test_deepseek_http_error():
    client = DeepSeekClient("sk-test", http_post=_fake_http_error)
    with pytest.raises(Exception) as ei:
        client.chat([LLMMessage(role="user", content="x")])
    assert "401" in str(ei.value)


def test_has_provider():
    assert LLMManager(keys={"DEEPSEEK_API_KEY": "sk"}).has_provider("deepseek")
    assert not LLMManager(keys={}).has_provider("deepseek")


def test_usage_by_agent():
    mgr = LLMManager(
        keys={"DEEPSEEK_API_KEY": "sk-test"},
        client_factory=lambda key: DeepSeekClient(key, http_post=_fake_http_ok),
    )
    mgr.chat([LLMMessage(role="user", content="a")], agent="brainstorm")
    snap = mgr.usage_snapshot()
    assert snap["prompt_tokens"] == 10
    assert snap["by_agent"]["brainstorm"]["calls"] == 1
