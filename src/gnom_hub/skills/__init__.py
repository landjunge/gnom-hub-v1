"""Local playbook skills (prompt inject) — not a workflow engine."""

from gnom_hub.skills.inject import skills_prompt_block
from gnom_hub.skills.loader import SkillLoader, SkillSpec

__all__ = ["SkillLoader", "SkillSpec", "skills_prompt_block"]
