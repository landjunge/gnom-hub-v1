"""Deepened auth: key status, failure kinds, session blocklist, typed HTTP errors."""

from __future__ import annotations

from gnom_hub.config.auth import (
    KeyStatus,
    LlmFailureKind,
    classify_api_key,
    classify_llm_failure,
    is_auth_failure,
    keys_auth_snapshot,
    mask_secret,
    user_message_for_failure,
)
from gnom_hub.llm.deepseek import DeepSeekClient
from gnom_hub.llm.manager import LLMManager
from gnom_hub.llm.types import AuthError, LLMMessage, RateLimitError


def test_classify_api_key_statuses():
    assert classify_api_key("") is KeyStatus.MISSING
    assert classify_api_key("sk-your-system-deepseek-key") is KeyStatus.PLACEHOLDER
    assert classify_api_key("sk-" + "a" * 40) is KeyStatus.USABLE


def test_keys_auth_snapshot_no_secrets():
    snap = keys_auth_snapshot(
        {
            "DEEPSEEK_API_KEY": "sk-your-system-deepseek-key",
            "WORKER_API_KEY": "sk-" + "b" * 40,
        }
    )
    assert snap["system"] == "placeholder"
    assert snap["worker"] == "usable"
    assert snap["worker_effective"] == "usable"
    assert snap["worker_source"] == "WORKER_API_KEY"
    assert "sk-" not in str(snap.get("system_tail", ""))
    assert snap["placeholder_detected"] is True


def test_classify_llm_failure_kinds():
    assert classify_llm_failure("DeepSeek HTTP 401: auth") is LlmFailureKind.AUTH
    assert classify_llm_failure(AuthError("x")) is LlmFailureKind.AUTH
    assert classify_llm_failure("HTTP 429 rate limit") is LlmFailureKind.RATE_LIMIT
    assert classify_llm_failure("connection refused") is LlmFailureKind.NETWORK
    assert is_auth_failure("Authentication Fails")


def test_user_messages_de():
    assert "Authentifizierung" in user_message_for_failure("401 invalid")
    assert "Key" in user_message_for_failure("DEEPSEEK_API_KEY missing")


def test_deepseek_maps_401_to_auth_error():
    def fake_post(url, headers, body, timeout):
        return 401, b'{"error":{"message":"bad key"}}'

    c = DeepSeekClient("sk-" + "c" * 40, http_post=fake_post)
    try:
        c.chat([LLMMessage(role="user", content="hi")])
        raise AssertionError("expected AuthError")
    except AuthError as e:
        assert "401" in str(e)


def test_deepseek_maps_429_to_rate_limit():
    def fake_post(url, headers, body, timeout):
        return 429, b'{"error":{"message":"slow down"}}'

    c = DeepSeekClient("sk-" + "d" * 40, http_post=fake_post)
    try:
        c.chat([LLMMessage(role="user", content="hi")])
        raise AssertionError("expected RateLimitError")
    except RateLimitError:
        pass


def test_manager_session_auth_blocklist():
    key = "sk-" + "e" * 40
    m = LLMManager(keys={"DEEPSEEK_API_KEY": key}, client_factory=lambda k: None)
    assert m.deepseek_key() == key
    m.note_auth_failure(key)
    assert m.deepseek_key() == ""
    assert m.has_provider("deepseek") is False
    snap = m.auth_snapshot()
    assert snap["session_auth_blocked"] is True
    m.clear_auth_blocks()
    assert m.deepseek_key() == key


def test_worker_key_fallback():
    sys_k = "sk-" + "f" * 40
    m = LLMManager(
        keys={"DEEPSEEK_API_KEY": sys_k, "WORKER_API_KEY": "sk-your-worker-deepseek-key"}
    )
    assert m.worker_key() == sys_k  # placeholder worker ignored
    wrk = "sk-" + "g" * 40
    m2 = LLMManager(keys={"DEEPSEEK_API_KEY": sys_k, "WORKER_API_KEY": wrk})
    assert m2.worker_key() == wrk


def test_mask_secret():
    assert mask_secret("sk-abcdefghij") == "…ghij"
