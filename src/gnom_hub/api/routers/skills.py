"""HTTP routes: skills."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from gnom_hub.api.models import SkillEnableBody, SkillInstallBody, SkillLearnBody
from gnom_hub.hub import get_hub

router = APIRouter()


@router.get("/api/skills")
def skills_list() -> dict[str, Any]:
    hub = get_hub()
    skills = getattr(hub, "skills", None)
    catalog_path = hub.root / "docs" / "skills_catalog.json"
    catalog = None
    if catalog_path.is_file():
        try:
            import json

            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            catalog = None
    return {
        "skills": skills.list_dicts() if skills else [],
        "errors": list(getattr(skills, "errors", []) or []),
        "catalog": catalog,
    }


@router.post("/api/skills/reload")
def skills_reload() -> dict[str, Any]:
    hub = get_hub()
    skills = getattr(hub, "skills", None)
    if skills is None:
        return {"ok": False, "error": "skills not available"}
    loaded = skills.discover_and_load()
    hub.skill_list = list(loaded)
    return {"ok": True, "skills": skills.list_dicts(), "errors": list(skills.errors)}


@router.post("/api/skills/{skill_id}/enable")
def skills_enable(skill_id: str, body: SkillEnableBody) -> dict[str, Any]:
    hub = get_hub()
    skills = getattr(hub, "skills", None)
    if skills is None:
        raise HTTPException(status_code=501, detail="skills not available")
    out = skills.set_enabled(skill_id, body.enabled)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail=out.get("error") or "not found")
    return out


@router.post("/api/skills/install")
def skills_install(body: SkillInstallBody) -> dict[str, Any]:
    """Install a local skill folder into data/skills/user/ (text-only packs)."""
    hub = get_hub()
    skills = getattr(hub, "skills", None)
    if skills is None:
        raise HTTPException(status_code=501, detail="skills not available")
    dest = hub.root / "data" / "skills" / "user"
    out = skills.install_from_path(body.path, dest_root=dest)
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out.get("error") or "install failed")
    hub.skill_list = list(skills.skills)
    return out


@router.post("/api/skills/learn")
def skills_learn(body: SkillLearnBody) -> dict[str, Any]:
    """User-confirmed learned skill → data/skills/user/ (markdown only)."""
    hub = get_hub()
    skills = getattr(hub, "skills", None)
    if skills is None or not hasattr(skills, "save_learned"):
        raise HTTPException(status_code=501, detail="skills not available")
    dest = hub.root / "data" / "skills" / "user"
    out = skills.save_learned(
        name=body.name,
        body=body.body,
        dest_root=dest,
        tags=body.tags or ["learned"],
        triggers=body.triggers or [],
        description=body.description or body.name,
        agents=["worker1", "worker2", "worker3", "worker4", "coordinator", "brainstorm"],
    )
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out.get("error") or "learn failed")
    hub.skill_list = list(skills.skills)
    return out


@router.post("/api/skills/learn_from_last")
def skills_learn_from_last() -> dict[str, Any]:
    """Draft+save a learned skill from last Execute (user-triggered)."""
    hub = get_hub()
    skills = getattr(hub, "skills", None)
    if skills is None or not hasattr(skills, "save_learned"):
        raise HTTPException(status_code=501, detail="skills not available")
    st = hub.pipeline.state
    pin = getattr(hub, "_last_execute_export", None) or {}
    reqs = list(st.distilled_requirements or []) or list(pin.get("distilled_requirements") or [])
    quality = (getattr(st, "quality_notes", "") or pin.get("quality_notes") or "").strip()
    mode = getattr(st, "resolved_plan_mode", "") or pin.get("resolved_plan_mode") or ""
    user_text = (st.user_text or pin.get("user_text") or "").strip()
    if not reqs and not quality and not user_text:
        raise HTTPException(status_code=400, detail="no last execute to learn from")
    title = "Learned from execute"
    if mode:
        title = f"Learned ({mode})"
    elif user_text:
        title = f"Learned: {user_text[:48]}"
    lines = ["# Learned playbook", "", "Captured from a confirmed Execute.", ""]
    if user_text:
        lines += ["## User intent", user_text[:800], ""]
    if mode:
        lines += [f"**plan_mode:** `{mode}`", ""]
    if reqs:
        lines += ["## Requirements"] + [f"- {r}" for r in reqs[:16]] + [""]
    if quality:
        lines += ["## Quality notes", quality[:1500], ""]
    lines += [
        "## Binding rules",
        "- Prefer one coherent deliverable over section-split half-pages.",
        "- Respect Flex wishes and prior skills.",
        "- Never invent tool results.",
    ]
    body = "\n".join(lines)
    triggers = [mode] if mode else []
    if any("html" in str(r).lower() or "seite" in str(r).lower() for r in reqs) or "html" in mode:
        triggers = list({*triggers, "html_page", "full_page_html", "landing"})
    dest = hub.root / "data" / "skills" / "user"
    out = skills.save_learned(
        name=title[:100],
        body=body,
        dest_root=dest,
        tags=["learned", "from_execute"],
        triggers=triggers,
        description=f"Auto-draft from execute ({mode or 'default'})",
        agents=["worker1", "worker2", "worker3", "worker4", "coordinator"],
    )
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out.get("error") or "learn failed")
    hub.skill_list = list(skills.skills)
    return out
