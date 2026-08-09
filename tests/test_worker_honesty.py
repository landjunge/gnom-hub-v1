"""Workers must not pretend success when LLM key is missing/invalid."""

from gnom_hub.agents.models import AgentId, AgentState
from gnom_hub.agents.roles_workers import WorkerAgent
from gnom_hub.config.keys import is_usable_api_key
from gnom_hub.core.event_bus import EventBus
from gnom_hub.llm.manager import LLMManager
from gnom_hub.pipeline.orchestrator import _validate_worker_draft


def _worker_state() -> AgentState:
    return AgentState(
        id=AgentId.WORKER1,
        name="Worker 1",
        role="worker",
        color="cyan",
        enabled=True,
        toggleable=True,
    )


def test_placeholder_keys_not_usable():
    assert not is_usable_api_key("")
    assert not is_usable_api_key("sk-your-system-deepseek-key")
    assert not is_usable_api_key("sk-your-worker-deepseek-key")
    assert not is_usable_api_key("changeme")
    assert is_usable_api_key("sk-" + "a" * 40)


def test_manager_hides_placeholder_provider():
    m = LLMManager(keys={"DEEPSEEK_API_KEY": "sk-your-system-deepseek-key"})
    assert m.deepseek_key() == ""
    assert m.has_provider("deepseek") is False


def test_worker_no_llm_says_error_not_stub():
    bus = EventBus()
    w = WorkerAgent(_worker_state(), bus, llm=None)
    out = w.run("HTML landing page", "Build HTML", ["hero"])
    assert "FEHLER" in out
    assert "(Stub" not in out and "Stub — mit" not in out


def test_worker_llm_auth_failure_honest():
    bus = EventBus()

    class Boom:
        def has_provider(self, name="deepseek"):
            return True

        def chat(self, *a, **k):
            raise RuntimeError("DeepSeek HTTP 401: Authentication Fails")

    w = WorkerAgent(_worker_state(), bus, llm=Boom())
    out = w.run("HTML page", "landing", [])
    assert "FEHLER" in out
    assert "(Stub" not in out and "Stub — mit" not in out
    assert "Authentifizierung" in out
    gate = _validate_worker_draft(out, user_text="landing html", task="page")
    assert gate.get("ok") is False
    assert "worker_error" in (gate.get("issues") or [])
