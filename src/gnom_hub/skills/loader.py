"""Load playbook skills from skills/ and data/skills/ (markdown + frontmatter).

No code execution. Skills are prompt text only.
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


@dataclass
class SkillSpec:
    id: str
    name: str
    version: str = "0.1.0"
    enabled: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    body: str = ""
    path: str = ""
    source: str = "bundled"  # bundled | user | installed

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "description": self.description,
            "tags": list(self.tags),
            "agents": list(self.agents),
            "triggers": list(self.triggers),
            "path": self.path,
            "source": self.source,
            "body_chars": len(self.body or ""),
        }


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    text = raw.lstrip("\ufeff")
    m = _FM_RE.match(text)
    if not m:
        return {}, text.strip()
    meta_raw, body = m.group(1), m.group(2)
    meta: dict[str, Any] = {}
    for line in meta_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
        elif val.lower() in ("true", "yes", "on", "1"):
            meta[key] = True
        elif val.lower() in ("false", "no", "off", "0"):
            meta[key] = False
        else:
            meta[key] = val
    return meta, body.strip()


class SkillLoader:
    """Discover skill.md files under bundled + user skill roots."""

    def __init__(self, roots: list[Path]) -> None:
        self.roots = [Path(r) for r in roots]
        self.skills: list[SkillSpec] = []
        self.errors: list[dict[str, str]] = []

    def discover_and_load(self) -> list[SkillSpec]:
        self.skills = []
        self.errors = []
        seen: set[str] = set()
        for root in self.roots:
            if not root.is_dir():
                continue
            source = "bundled"
            if (
                "data" in root.parts
                and "skills" in root.parts
                or root.name == "user"
                and "data" in str(root)
            ):
                source = "user"
            for child in sorted(root.iterdir()):
                if not child.is_dir() or child.name.startswith(("_", ".")):
                    continue
                skill_md = child / "skill.md"
                if not skill_md.is_file():
                    # also allow skill.md at root of nested
                    continue
                try:
                    spec = self._load_file(skill_md, folder=child.name, source=source)
                except Exception as exc:  # noqa: BLE001
                    self.errors.append({"path": str(skill_md), "error": str(exc)})
                    logger.warning("Skill load failed %s: %s", skill_md, exc)
                    continue
                if spec.id in seen:
                    # user overrides bundled
                    self.skills = [s for s in self.skills if s.id != spec.id]
                seen.add(spec.id)
                self.skills.append(spec)
        return list(self.skills)

    def _load_file(self, path: Path, *, folder: str, source: str) -> SkillSpec:
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        sid = str(meta.get("id") or folder).strip() or folder
        enabled = meta.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() not in ("0", "false", "no", "off")
        tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
        agents = meta.get("agents") if isinstance(meta.get("agents"), list) else []
        triggers = meta.get("triggers") if isinstance(meta.get("triggers"), list) else []
        return SkillSpec(
            id=sid,
            name=str(meta.get("name") or sid),
            version=str(meta.get("version") or "0.1.0"),
            enabled=bool(enabled),
            description=str(meta.get("description") or "")[:300],
            tags=[str(t) for t in tags],
            agents=[str(a) for a in agents],
            triggers=[str(t) for t in triggers],
            body=body[:12000],
            path=str(path),
            source=source,
        )

    def list_dicts(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.skills]

    def get(self, skill_id: str) -> SkillSpec | None:
        for s in self.skills:
            if s.id == skill_id:
                return s
        return None

    def set_enabled(self, skill_id: str, enabled: bool) -> dict[str, Any]:
        s = self.get(skill_id)
        if not s:
            return {"ok": False, "error": f"unknown skill: {skill_id}"}
        s.enabled = bool(enabled)
        return {"ok": True, "id": s.id, "enabled": s.enabled}

    def match(
        self,
        *,
        agent: str | None = None,
        plan_mode: str | None = None,
        task_kind: str | None = None,
        text: str = "",
        tags: list[str] | None = None,
        limit: int = 4,
    ) -> list[SkillSpec]:
        """Return enabled skills matching soft triggers (not a router)."""
        blob = (text or "").lower()
        mode = (plan_mode or "").lower()
        kind = (task_kind or "").lower()
        want_tags = {t.lower() for t in (tags or [])}
        out: list[SkillSpec] = []
        for s in self.skills:
            if not s.enabled:
                continue
            if s.agents and agent:
                ok_agent = False
                for a in s.agents:
                    al = a.lower()
                    if al == agent.lower():
                        ok_agent = True
                        break
                    if al == "worker" and agent.lower().startswith("worker"):
                        ok_agent = True
                        break
                if not ok_agent:
                    continue
            hit = False
            if not s.triggers and not s.tags:
                hit = True
            for tr in s.triggers:
                trl = tr.lower()
                if trl and (trl == mode or trl == kind or trl in blob):
                    hit = True
                    break
            if want_tags and any(tg.lower() in want_tags for tg in s.tags):
                hit = True
            if not hit and s.tags:
                for tg in s.tags:
                    if tg.lower() in blob:
                        hit = True
                        break
            if hit:
                out.append(s)
            if len(out) >= max(1, limit):
                break
        return out

    def install_from_path(self, src: str | Path, *, dest_root: Path) -> dict[str, Any]:
        """Copy a skill folder into dest_root (user skills). No code exec."""
        src_p = Path(src).expanduser().resolve()
        if not src_p.is_dir():
            return {"ok": False, "error": "source must be a directory"}
        skill_md = src_p / "skill.md"
        if not skill_md.is_file():
            return {"ok": False, "error": "skill.md missing in folder"}
        # refuse if package contains .py (skill packs are text-only)
        for p in src_p.rglob("*.py"):
            return {
                "ok": False,
                "error": f"skill pack must not include Python ({p.name}); use plugins/ for code",
            }
        dest_root = Path(dest_root)
        dest_root.mkdir(parents=True, exist_ok=True)
        name = src_p.name
        dest = dest_root / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src_p, dest)
        self.discover_and_load()
        return {"ok": True, "id": name, "path": str(dest), "skills": self.list_dicts()}

    def save_learned(
        self,
        *,
        name: str,
        body: str,
        dest_root: Path,
        skill_id: str | None = None,
        tags: list[str] | None = None,
        triggers: list[str] | None = None,
        agents: list[str] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """Write a user-confirmed learned skill (markdown only)."""
        import re

        body = (body or "").strip()
        name = (name or "").strip() or "Learned skill"
        if not body:
            return {"ok": False, "error": "body required"}
        if len(body) > 10000:
            body = body[:10000] + "…"
        sid = (skill_id or "").strip()
        if not sid:
            slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:48] or "learned"
            sid = f"learned_{slug}"
        dest_root = Path(dest_root)
        dest_root.mkdir(parents=True, exist_ok=True)
        folder = dest_root / sid
        folder.mkdir(parents=True, exist_ok=True)
        tags_l = tags or ["learned"]
        trig_l = triggers or []
        agents_l = agents or []
        tags_s = ", ".join(tags_l)
        trig_s = ", ".join(trig_l)
        agents_s = ", ".join(agents_l)
        desc = (description or name)[:200]
        md = (
            f"---\n"
            f"id: {sid}\n"
            f"name: {name}\n"
            f"version: 0.1.0\n"
            f"enabled: true\n"
            f"description: {desc}\n"
            f"tags: [{tags_s}]\n"
            f"agents: [{agents_s}]\n"
            f"triggers: [{trig_s}]\n"
            f"---\n\n"
            f"{body.strip()}\n"
        )
        (folder / "skill.md").write_text(md, encoding="utf-8")
        self.discover_and_load()
        return {
            "ok": True,
            "id": sid,
            "path": str(folder / "skill.md"),
            "skills": self.list_dicts(),
        }
