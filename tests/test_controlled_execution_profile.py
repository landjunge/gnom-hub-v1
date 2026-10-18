"""GH-C03: isolated route guards, no real credentials or provider calls."""

from __future__ import annotations

import builtins
from unittest.mock import Mock

import pytest

from gnom_hub.llm.manager import LLMManager
from gnom_hub.llm.types import LLMError, LLMMessage


@pytest.mark.parametrize("opt_out", ["0", "1"])
@pytest.mark.parametrize("model", ["deepseek-v4-flash", "ollama/llama3.2"])
def test_controlled_profile_refuses_unbound_routes_before_any_dispatch(monkeypatch, opt_out, model):
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", opt_out)
    manager = LLMManager(execution_profile="controlled", keys={})
    cloud, local, direct = Mock(), Mock(), Mock()
    manager._chat_via_tollgate = cloud
    manager._ollama.chat = local
    manager._client_factory = direct
    with pytest.raises(LLMError, match="controlled_execution_unavailable"):
        manager.chat([LLMMessage("user", "synthetic task")], model=model, agent="worker1")
    cloud.assert_not_called()
    local.assert_not_called()
    direct.assert_not_called()


def test_controlled_worker_never_falls_back_to_system_key():
    manager = LLMManager(
        execution_profile="controlled",
        keys={"DEEPSEEK_API_KEY": "sk-synthetic-only-system-key-123456"},
    )
    assert manager.worker_key() == ""


def test_real_missing_package_path_not_mocked_admission_never_reaches_legacy(monkeypatch):
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "1")
    monkeypatch.delenv("TOLLGATE_URL", raising=False)
    original = builtins.__import__
    imports = []

    def without_gate(name, *args, **kwargs):
        if name == "tollgate" or name.startswith("tollgate."):
            imports.append(name)
            raise ModuleNotFoundError("synthetic absent gate", name=name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_gate)
    direct = Mock()
    manager = LLMManager(
        keys={"DEEPSEEK_API_KEY": "sk-synthetic-only-system-key-123456"}, client_factory=direct
    )
    with pytest.raises(LLMError, match="tollgate package not installed"):
        manager.chat([LLMMessage("user", "dummy")], agent="brainstorm")
    assert imports == ["tollgate"]
    direct.assert_not_called()


def test_profile_typo_is_not_silently_standalone():
    with pytest.raises(ValueError, match="GNOM_EXECUTION_PROFILE"):
        LLMManager(execution_profile="controlld")
