"""Shared skill matching for agents (soft inject only)."""

from __future__ import annotations


def skill_block_for(
    *,
    agent: str,
    text: str = "",
    plan_mode: str = "",
    task_kind: str = "",
    limit: int = 3,
) -> str:
    try:
        from gnom_hub.hub import get_hub
        from gnom_hub.skills.inject import skills_prompt_block

        hub = get_hub()
        skills = getattr(hub, "skills", None)
        if skills is None:
            return ""
        matched = skills.match(
            agent=agent,
            text=text or "",
            plan_mode=plan_mode or "",
            task_kind=task_kind or "",
            limit=limit,
        )
        return skills_prompt_block(matched)
    except Exception:  # noqa: BLE001
        return ""
