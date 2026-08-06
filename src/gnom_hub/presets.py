"""Worker/team presets + plan_mode (extracted from Hub — pure move)."""

from __future__ import annotations

import json
from typing import Any

from gnom_hub.agents.models import AgentId
from gnom_hub.memory.atomic import atomic_write_text


class PresetsMixin:
    """Mixin extracted from Hub — pure move."""

    def delete_worker_preset(self, name: str) -> dict[str, Any]:
        presets = [p for p in self.list_worker_presets() if p.get("name") != name]
        self._presets_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self._presets_path,
            json.dumps({"presets": presets}, ensure_ascii=False, indent=2) + "\n",
        )
        return {"ok": True, "presets": presets}

    def list_worker_presets(self) -> list[dict[str, Any]]:
        path = self._presets_path
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(data, list):
            return data
        return list(data.get("presets") or [])

    def save_worker_preset(self, name: str, agent_id: str = "worker1") -> dict[str, Any]:
        """Save current worker tuning as a named preset (plan: reusable workers)."""
        agent = self.agents.get(agent_id)
        presets = self.list_worker_presets()
        entry = {
            "name": name.strip() or f"preset-{agent_id}",
            "source_agent": agent.id.value,
            "system_prompt": agent.system_prompt or "",
            "model": agent.model,
            "temperature": agent.temperature,
            "top_p": agent.top_p,
            "max_tokens": agent.max_tokens,
            "frequency_penalty": agent.frequency_penalty,
            "presence_penalty": agent.presence_penalty,
        }
        presets = [p for p in presets if p.get("name") != entry["name"]]
        presets.append(entry)
        self._presets_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self._presets_path,
            json.dumps({"presets": presets}, ensure_ascii=False, indent=2) + "\n",
        )
        return {"ok": True, "preset": entry, "presets": presets}

    def apply_worker_preset(self, name: str, agent_id: str = "worker1") -> dict[str, Any]:
        presets = self.list_worker_presets()
        match = next((p for p in presets if p.get("name") == name), None)
        if not match:
            raise ValueError(f"Unknown preset: {name!r}")
        return self.set_agent_tune(
            agent_id,
            {
                "system_prompt": match.get("system_prompt"),
                "model": match.get("model"),
                "temperature": match.get("temperature"),
                "top_p": match.get("top_p"),
                "max_tokens": match.get("max_tokens"),
                "frequency_penalty": match.get("frequency_penalty"),
                "presence_penalty": match.get("presence_penalty"),
            },
        )

    # ── team presets (who is on + flex + plan_mode + worker tunes) ──

    PLAN_MODES: tuple[str, ...] = ("default", "full_page_html", "plan_qa", "diagnosis")

    def list_team_presets(self) -> list[dict[str, Any]]:
        path = self._team_presets_path
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict)]
        return [p for p in (data.get("presets") or []) if isinstance(p, dict)]

    def _write_team_presets(self, presets: list[dict[str, Any]]) -> None:
        self._team_presets_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self._team_presets_path,
            json.dumps({"presets": presets}, ensure_ascii=False, indent=2) + "\n",
        )

    def save_team_preset(self, name: str) -> dict[str, Any]:
        """Snapshot current enables, flex, plan_mode, and worker tunes."""
        key = (name or "").strip() or "team"
        enabled: dict[str, bool] = {}
        tunes: dict[str, dict[str, Any]] = {}
        for a in self.agents.list_agents():
            aid = a.id.value
            enabled[aid] = bool(a.enabled)
            if aid.startswith("worker"):
                tunes[aid] = {
                    "system_prompt": a.system_prompt or "",
                    "model": a.model,
                    "temperature": a.temperature,
                    "top_p": a.top_p,
                    "max_tokens": a.max_tokens,
                    "frequency_penalty": a.frequency_penalty,
                    "presence_penalty": a.presence_penalty,
                }
        flex = self.agents.get(AgentId.FLEX)
        entry = {
            "name": key,
            "flex": (flex.preset or "security"),
            "plan_mode": getattr(self, "plan_mode", "default") or "default",
            "enabled": enabled,
            "tunes": tunes,
        }
        presets = [p for p in self.list_team_presets() if p.get("name") != key]
        presets.append(entry)
        self._write_team_presets(presets)
        return {"ok": True, "preset": entry, "presets": presets}

    def apply_team_preset(self, name: str) -> dict[str, Any]:
        key = (name or "").strip()
        match = next((p for p in self.list_team_presets() if p.get("name") == key), None)
        if not match:
            raise ValueError(f"Unknown team preset: {name!r}")

        enabled = match.get("enabled") or {}
        if isinstance(enabled, dict):
            for a in self.agents.list_agents():
                aid = a.id.value
                if not a.toggleable:
                    a.enabled = True
                    continue
                if aid in enabled:
                    a.enabled = bool(enabled[aid])
                self.agents.emit_status(a.id)

        flex_name = str(match.get("flex") or "security")
        try:
            self.agents.set_flex_preset(flex_name)
        except ValueError:
            pass

        mode = str(match.get("plan_mode") or "default").strip().lower()
        if mode not in self.PLAN_MODES:
            mode = "default"
        self.plan_mode = mode
        self.pipeline.plan_mode = mode

        tunes = match.get("tunes") or {}
        if isinstance(tunes, dict):
            for aid, fields in tunes.items():
                if not isinstance(fields, dict) or not str(aid).startswith("worker"):
                    continue
                try:
                    self.set_agent_tune(str(aid), fields)
                except (KeyError, TypeError, ValueError):
                    pass

        self._save_agent_state()
        return {
            "ok": True,
            "name": key,
            "plan_mode": self.plan_mode,
            "agents": [self._agent_dict(a) for a in self.agents.list_agents()],
            "snapshot": self.snapshot(),
        }

    def delete_team_preset(self, name: str) -> dict[str, Any]:
        key = (name or "").strip()
        presets = [p for p in self.list_team_presets() if p.get("name") != key]
        self._write_team_presets(presets)
        return {"ok": True, "presets": presets}

    def set_plan_mode(self, mode: str) -> dict[str, Any]:
        key = (mode or "default").strip().lower()
        if key not in self.PLAN_MODES:
            raise ValueError(f"Unknown plan_mode: {mode!r}. Allowed: {self.PLAN_MODES}")
        self.plan_mode = key
        self.pipeline.plan_mode = key
        return {"ok": True, "plan_mode": key}
