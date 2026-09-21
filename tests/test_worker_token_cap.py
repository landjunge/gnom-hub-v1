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
    assert _dod_must_stop({"ok": False, "issues": ["worker_error"]})
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
