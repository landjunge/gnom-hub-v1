"""Worker HTML must not be capped at 1024 via TollGate (`None or 1024`)."""

from __future__ import annotations

from gnom_hub.core.event_bus import EventBus
from gnom_hub.llm.manager import (
    DEFAULT_WORKER_MAX_TOKENS,
    LLMManager,
    tollgate_max_tokens,
)
from gnom_hub.llm.types import LLMMessage, LLMResult
from gnom_hub.pipeline import Pipeline, PipelineStage
from gnom_hub.pipeline.dispatch import _dod_must_stop
from gnom_hub.pipeline.dod_gate import format_retry_hint


def test_tollgate_max_tokens_worker_none_not_1024(monkeypatch):
    monkeypatch.delenv("GNOM_WORKER_MAX_TOKENS", raising=False)
    assert tollgate_max_tokens("worker1", None) == DEFAULT_WORKER_MAX_TOKENS
    assert tollgate_max_tokens("worker1", None) != 1024
    assert tollgate_max_tokens("brainstorm", 280) == 280
    assert tollgate_max_tokens("brainstorm", None) is None


def test_tollgate_max_tokens_env(monkeypatch):
    monkeypatch.setenv("GNOM_WORKER_MAX_TOKENS", "20000")
    assert tollgate_max_tokens("worker2", None) == 20000


def test_chat_worker_none_not_coerced_to_1024(monkeypatch):
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "1")
    monkeypatch.delenv("TOLLGATE_URL", raising=False)
    seen: dict = {}
    mgr = LLMManager(keys={"DEEPSEEK_API_KEY": "sk-test"})

    def fake_tg(*_a, **k):
        seen.update(k)
        return LLMResult(content="ok", model="tg")

    mgr._chat_via_tollgate = fake_tg  # type: ignore[method-assign]
    mgr.chat(
        [LLMMessage(role="user", content="full html page")],
        agent="worker1",
        max_tokens=None,
    )
    assert seen.get("max_tokens") != 1024
    assert seen.get("max_tokens") == DEFAULT_WORKER_MAX_TOKENS


def test_chat_explicit_budget_still_passed(monkeypatch):
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "1")
    monkeypatch.delenv("TOLLGATE_URL", raising=False)
    seen: dict = {}
    mgr = LLMManager(keys={"DEEPSEEK_API_KEY": "sk-test"})

    def fake_tg(*_a, **k):
        seen.update(k)
        return LLMResult(content="ok", model="tg")

    mgr._chat_via_tollgate = fake_tg  # type: ignore[method-assign]
    mgr.chat(
        [LLMMessage(role="user", content="hi")],
        agent="brainstorm",
        max_tokens=280,
    )
    assert seen.get("max_tokens") == 280


def test_dod_must_stop_incomplete_html():
    assert _dod_must_stop({"ok": False, "issues": ["incomplete_html", "missing_html_close"]})
    assert not _dod_must_stop({"ok": False, "issues": ["worker_error", "incomplete_html"]})
    assert not _dod_must_stop({"ok": False, "issues": ["worker_error"]})
    assert not _dod_must_stop({"ok": True, "issues": []})
    assert not _dod_must_stop({"ok": False, "issues": ["prefetch_palette_unused"]})


def test_retry_hint_demands_complete_html():
    hint = format_retry_hint(
        {"ok": False, "issues": ["incomplete_html", "missing_html_close"], "hints": []},
        attempt=1,
    )
    assert "</html>" in hint
    assert "DOCTYPE" in hint or "doctype" in hint.lower()


def test_incomplete_html_stops_later_workers(monkeypatch):
    bus = EventBus()
    pipe = Pipeline(bus)
    runs: list[str] = []

    def fake_run(self, *_a, **_k):
        runs.append(getattr(self, "id", "?") or "?")
        return "<html><body>cut mid css"

    monkeypatch.setattr("gnom_hub.agents.roles.WorkerAgent.run", fake_run)
    pipe.brainstorm_turn("Build a complete HTML landing page")
    state = pipe.execute()
    assert state.stage == PipelineStage.error
    assert state.result_status == "FEHLER"
    assert "DoD fail" in (state.error or "")
    assert len(runs) <= 3  # retries on first worker, not a full later-worker fan-out
    assert state.worker_outputs
    assert (state.worker_outputs[0].get("validation") or {}).get("ok") is False


def test_tollgate_max_tokens_explicit_worker_budget_not_clamped():
    assert tollgate_max_tokens("worker1", 8192) == 8192
    assert tollgate_max_tokens("worker1", 500) == 500
    assert tollgate_max_tokens("worker1", 0) == 1
    assert tollgate_max_tokens("worker1", -3) == 1


def test_tollgate_max_tokens_env_clamp_and_invalid(monkeypatch):
    monkeypatch.setenv("GNOM_WORKER_MAX_TOKENS", "100")
    assert tollgate_max_tokens("worker1", None) == 4096
    monkeypatch.setenv("GNOM_WORKER_MAX_TOKENS", "4096")
    assert tollgate_max_tokens("worker1", None) == 4096
    monkeypatch.setenv("GNOM_WORKER_MAX_TOKENS", "128000")
    assert tollgate_max_tokens("worker1", None) == 128_000
    monkeypatch.setenv("GNOM_WORKER_MAX_TOKENS", "200000")
    assert tollgate_max_tokens("worker1", None) == 128_000
    monkeypatch.setenv("GNOM_WORKER_MAX_TOKENS", "nope")
    assert tollgate_max_tokens("worker1", None) == DEFAULT_WORKER_MAX_TOKENS
    monkeypatch.setenv("GNOM_WORKER_MAX_TOKENS", "")
    assert tollgate_max_tokens("worker1", None) == DEFAULT_WORKER_MAX_TOKENS
    assert tollgate_max_tokens("", None) is None
    assert tollgate_max_tokens("coordinator", None) is None


def _install_routed_chat(monkeypatch, seen: dict) -> None:
    import sys
    import types

    fake = types.ModuleType("tollgate")

    def routed_chat(*_a, **k):
        seen.clear()
        seen.update(k)
        seen["__keys__"] = set(k)
        return {"ok": True, "content": "ok", "model": "tg"}

    fake.routed_chat = routed_chat
    monkeypatch.setitem(sys.modules, "tollgate", fake)
    monkeypatch.delenv("TOLLGATE_URL", raising=False)


def test_routed_chat_worker_none_is_16k(monkeypatch):
    monkeypatch.delenv("GNOM_WORKER_MAX_TOKENS", raising=False)
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "1")
    seen: dict = {}
    _install_routed_chat(monkeypatch, seen)
    mgr = LLMManager(keys={"DEEPSEEK_API_KEY": "sk-test"})
    mgr.chat(
        [LLMMessage(role="user", content="full html page")],
        agent="worker1",
        max_tokens=None,
    )
    assert seen.get("max_tokens") == DEFAULT_WORKER_MAX_TOKENS
    assert seen.get("max_tokens") != 1024


def test_routed_chat_explicit_worker_budget_passed(monkeypatch):
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "1")
    seen: dict = {}
    _install_routed_chat(monkeypatch, seen)
    mgr = LLMManager(keys={"DEEPSEEK_API_KEY": "sk-test"})
    mgr.chat(
        [LLMMessage(role="user", content="full html page")],
        agent="worker1",
        max_tokens=500,
    )
    assert seen.get("max_tokens") == 500


def test_routed_chat_nonworker_none_omits_max_tokens(monkeypatch):
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "1")
    seen: dict = {}
    _install_routed_chat(monkeypatch, seen)
    mgr = LLMManager(keys={"DEEPSEEK_API_KEY": "sk-test"})
    mgr.chat(
        [LLMMessage(role="user", content="hi")],
        agent="brainstorm",
        max_tokens=None,
    )
    assert "max_tokens" not in seen["__keys__"]


def test_free_only_worker_none_reaches_routed_chat_as_16k(monkeypatch):
    monkeypatch.delenv("GNOM_WORKER_MAX_TOKENS", raising=False)
    monkeypatch.setenv("GNOM_FREE_TOLLGATE", "1")
    seen: dict = {}
    _install_routed_chat(monkeypatch, seen)
    mgr = LLMManager(keys={"DEEPSEEK_API_KEY": "sk-test"}, free_only=True)
    mgr.chat(
        [LLMMessage(role="user", content="full html page")],
        agent="worker1",
        max_tokens=None,
    )
    assert seen.get("max_tokens") == DEFAULT_WORKER_MAX_TOKENS


def test_no_cloud_key_worker_none_reaches_routed_chat_as_16k(monkeypatch):
    monkeypatch.delenv("GNOM_WORKER_MAX_TOKENS", raising=False)
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "0")
    monkeypatch.delenv("TOLLGATE_URL", raising=False)
    seen: dict = {}
    _install_routed_chat(monkeypatch, seen)
    mgr = LLMManager(keys={})
    # No key would otherwise auto-route to a live Ollama and skip this call site.
    monkeypatch.setattr(mgr, "ollama_available", lambda *_a, **_k: False)
    mgr.chat(
        [LLMMessage(role="user", content="full html page")],
        agent="worker1",
        max_tokens=None,
    )
    assert seen.get("max_tokens") == DEFAULT_WORKER_MAX_TOKENS


def test_tollgate_client_omits_none_and_passes_budget(monkeypatch):
    import sys
    import types

    calls: list[dict] = []
    client_mod = types.ModuleType("tollgate.client")

    class TollgateClient:
        def __init__(self, **_k):
            pass

        def chat(self, _payload, **k):
            calls.append(dict(k))
            return {"ok": True, "content": "ok", "model": "m"}

    client_mod.TollgateClient = TollgateClient
    pkg = types.ModuleType("tollgate")
    pkg.__path__ = []  # type: ignore[attr-defined]
    pkg.client = client_mod
    monkeypatch.setitem(sys.modules, "tollgate", pkg)
    monkeypatch.setitem(sys.modules, "tollgate.client", client_mod)
    monkeypatch.setenv("TOLLGATE_URL", "http://127.0.0.1:9")
    mgr = LLMManager(keys={"DEEPSEEK_API_KEY": "sk-test"})
    messages = [LLMMessage(role="user", content="full html page")]
    mgr._chat_via_tollgate(
        messages,
        model="",
        provider="worker",
        agent="worker1",
        temperature=0.2,
        max_tokens=DEFAULT_WORKER_MAX_TOKENS,
        prefer_free=False,
    )
    mgr._chat_via_tollgate(
        messages,
        model="",
        provider=None,
        agent="brainstorm",
        temperature=0.2,
        max_tokens=None,
        prefer_free=True,
    )
    assert calls[0]["max_tokens"] == DEFAULT_WORKER_MAX_TOKENS
    assert "max_tokens" not in calls[1]


def test_dod_must_stop_stub_and_missing_close():
    assert not _dod_must_stop({"ok": False, "issues": ["stub", "incomplete_html"]})
    assert not _dod_must_stop({"ok": False, "issues": ["stub"]})
    assert _dod_must_stop({"ok": False, "issues": ["missing_html_close"]})
    assert not _dod_must_stop({"ok": True, "issues": ["incomplete_html", "missing_html_close"]})
    assert not _dod_must_stop({"ok": False, "issues": []})
    assert not _dod_must_stop({})


def test_retry_hint_html_line_only_on_first_attempt():
    close_only = format_retry_hint(
        {"ok": False, "issues": ["missing_html_close"], "hints": []},
        attempt=1,
    )
    assert "mid-CSS" in close_only
    other = format_retry_hint(
        {"ok": False, "issues": ["prefetch_palette_unused"], "hints": ["reuse palette"]},
        attempt=1,
    )
    assert "mid-CSS" not in other
    second = format_retry_hint(
        {"ok": False, "issues": ["incomplete_html", "missing_html_close"], "hints": []},
        attempt=2,
    )
    assert "mid-CSS" not in second
    assert "RETRY 2" in second


def _execute_two_worker_plan(monkeypatch, body: str):
    """HTML fast-path plans one worker. Force a second task so the DoD abort is visible."""
    bus = EventBus()
    pipe = Pipeline(bus)
    runs: list[str] = []

    def fake_run(self, *_a, **_k):
        runs.append(self.id)
        return body

    def two_tasks(*_a, **_k):
        return [
            ("worker1", "Produce the HTML page"),
            ("worker2", "Produce the second section"),
        ]

    monkeypatch.setattr("gnom_hub.agents.roles.WorkerAgent.run", fake_run)
    monkeypatch.setattr(pipe.coordinator, "plan", two_tasks)
    pipe.brainstorm_turn("Build a complete HTML landing page")
    return pipe.execute(), runs


def test_incomplete_html_skips_later_planned_worker(monkeypatch):
    state, runs = _execute_two_worker_plan(monkeypatch, "<html><body>cut mid css")
    assert state.stage == PipelineStage.error
    assert state.result_status == "FEHLER"
    assert "DoD fail" in (state.error or "")
    assert "not delivered" in (state.error or "")
    assert "worker1" in runs
    assert "worker2" not in runs


def test_missing_key_worker_error_does_not_dod_abort(monkeypatch):
    state, runs = _execute_two_worker_plan(
        monkeypatch,
        "Arbeiter 1 FEHLER - kein Deliverable\n"
        "Aufgabe: landing\n"
        "DEEPSEEK_API_KEY fehlt.\n"
        "Kein Fake-Ergebnis. Worker liefert erst mit gueltigem Provider.",
    )
    assert state.stage == PipelineStage.done
    assert state.error is None
    assert state.result_status == "FEHLER"
    assert runs == ["worker1", "worker2"]


def test_stub_does_not_dod_abort(monkeypatch):
    state, runs = _execute_two_worker_plan(
        monkeypatch,
        "Stub — kein Modell. " + ("placeholder " * 8),
    )
    assert state.stage == PipelineStage.done
    assert state.error is None
    assert state.result_status == "FEHLER"
    assert "worker1" in runs and "worker2" in runs
    assert "DoD fail" not in (state.error or "")
