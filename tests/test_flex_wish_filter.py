"""Flex-wish must not be stripped as Flex/ meta."""

from gnom_hub.agents import AgentId, AgentManager
from gnom_hub.agents.roles_ext import CoordinatorAgent
from gnom_hub.agents.roles_helpers import _is_flex_meta_requirement
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.orchestrator import _definition_of_done


def test_is_flex_meta_requirement():
    assert _is_flex_meta_requirement("Flex/personal: short briefing") is True
    assert _is_flex_meta_requirement("Flex/security: x") is True
    assert _is_flex_meta_requirement("Flex-wish: User: always dark theme") is False
    assert _is_flex_meta_requirement("User: always dark theme") is False
    assert _is_flex_meta_requirement("MVP mit 3 Features") is False


def test_definition_of_done_keeps_flex_wish():
    dod = _definition_of_done(
        "Build landing",
        [
            "Ziel: landing",
            "Flex/personal: was ich weiß",
            "Flex-wish: User: always enable dark theme",
            "Flex-wish: User: never truncate HTML",
        ],
    )
    assert "always enable dark theme" in dod
    assert "never truncate HTML" in dod
    assert "was ich weiß" not in dod  # meta stripped


def test_plan_clean_keeps_flex_wish_in_html_dod():
    bus = EventBus()
    coord = CoordinatorAgent(AgentManager(bus).get(AgentId.COORDINATOR), bus, llm=None)
    tasks = coord.plan(
        "Build a landing page full HTML",
        [
            "Ziel: Bean Shop",
            "Flex/personal: briefing meta",
            "Flex-wish: User: always enable dark theme",
        ],
        ["worker1", "worker2"],
        plan_mode="full_page_html",
    )
    assert len(tasks) == 1
    assert "always enable dark theme" in tasks[0][1]
    assert "briefing meta" not in tasks[0][1]
