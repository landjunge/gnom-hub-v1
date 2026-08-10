"""Format matched skills for system-prompt injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gnom_hub.skills.loader import SkillSpec

_MAX_TOTAL = 3500
_MAX_ONE = 1400


def skills_prompt_block(
    skills: list[SkillSpec], *, header: str = "Active skills (playbooks)"
) -> str:
    if not skills:
        return ""
    parts: list[str] = [f"## {header}", "Follow these playbooks when relevant. They are not tools."]
    used = 0
    for s in skills:
        body = (s.body or "").strip()
        if len(body) > _MAX_ONE:
            body = body[:_MAX_ONE] + "…"
        chunk = f"### Skill: {s.name} (`{s.id}`)\n{body}"
        if used + len(chunk) > _MAX_TOTAL:
            break
        parts.append(chunk)
        used += len(chunk)
    return "\n\n".join(parts)
