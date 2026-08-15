"""Protect UX: hard fail + human message, no stub mask."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gnom_hub.agents.models import AgentId, AgentState
from gnom_hub.agents.roles import BrainstormAgent
from gnom_hub.agents.roles_helpers import format_protect_user_message, is_protect_error
from gnom_hub.core.event_bus import EventBus
from gnom_hub.llm.types import BudgetExceededError
from gnom_hub.pipeline.pipeline import Pipeline


def test_is_protect_error():
    assert is_protect_error("agent protection: consumer gnom max_tokens_request 100 > 50")
    assert is_protect_error(BudgetExceededError("budget hard"))
    assert not is_protect_error("connection reset by peer")


def test_format_protect_user_message():
    m = format_protect_user_message("agent protection: max_tokens_request 100 > 50")
    assert "Tollgate Protect" in m
    assert "max_tokens_request" in m
    assert "🛑" in m
    # idempotent — orchestrator must not double-wrap Brainstorm message
    m2 = format_protect_user_message(m)
    assert m2 == m
    assert m2.count("Tollgate Protect") == 1


def test_brainstorm_protect_raises_not_stub():
    bus = EventBus()
    llm = MagicMock()
    llm.has_provider = MagicMock(return_value=True)
    llm.chat = MagicMock(
        side_effect=BudgetExceededError(
            "agent protection: consumer gnom max_tokens_request 200 > 50"
        )
    )
    state = AgentState(
        id=AgentId.BRAINSTORM,
        name="Brainstorm",
        role="brainstorm",
        color="red",
        enabled=True,
        toggleable=True,
    )
    agent = BrainstormAgent(state, bus, llm=llm)
    with pytest.raises(BudgetExceededError, match="Tollgate Protect"):
        agent.run("hi there", memory_ctx="")


def test_safe_stage_protect_does_not_stub():
    bus = EventBus()
    llm = MagicMock()
    llm.has_provider = MagicMock(return_value=True)
    pipe = Pipeline(bus, llm_manager=llm)

    def boom():
        raise BudgetExceededError("agent protection: consumer gnom max_tokens_request 99 > 50")

    with pytest.raises(BudgetExceededError, match="Tollgate Protect"):
        pipe._safe_stage("brainstorm", boom, lambda: "STUB_SHOULD_NOT_RUN")


def test_safe_stage_other_error_still_stubs():
    bus = EventBus()
    llm = MagicMock()
    llm.has_provider = MagicMock(return_value=True)
    pipe = Pipeline(bus, llm_manager=llm)

    def boom():
        raise RuntimeError("connection reset by peer")

    out = pipe._safe_stage("brainstorm", boom, lambda: "stub-ok")
    assert out == "stub-ok"
    assert any("used stub" in w for w in pipe.state.warnings)
