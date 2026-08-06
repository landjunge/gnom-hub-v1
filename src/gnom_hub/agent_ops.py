"""Agent persistence, keys, toggle, LLM/tune (extracted from Hub)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gnom_hub.agents.models import AgentId, AgentState
from gnom_hub.memory.atomic import atomic_write_text


class AgentOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def _apply_keys_from_keyfile(self) -> None:
        """
        Map Key.txt onto agents:
          DEEPSEEK_API_KEY / SYSTEM → brainstorm, memory, flex, coordinator
          WORKER_API_KEY / WORKER → worker1–4
          DEEPSEEK_MODEL → default + every agent model
        """
        system_key = (self.keys.get("DEEPSEEK_API_KEY") or "").strip() or None
        worker_key = (self.keys.get("WORKER_API_KEY") or "").strip() or None
        model = (self.keys.get("DEEPSEEK_MODEL") or "").strip() or None
        if model:
            self.llm.default_model = model
        system_ids = (
            AgentId.BRAINSTORM,
            AgentId.MEMORY,
            AgentId.FLEX,
            AgentId.COORDINATOR,
        )
        worker_ids = (
            AgentId.WORKER1,
            AgentId.WORKER2,
            AgentId.WORKER3,
            AgentId.WORKER4,
        )
        if system_key:
            for aid in system_ids:
                try:
                    self.agents.get(aid).api_key = system_key
                except ValueError:
                    pass
        if worker_key:
            for aid in worker_ids:
                try:
                    self.agents.get(aid).api_key = worker_key
                except ValueError:
                    pass
        if model:
            for a in self.agents.list_agents():
                a.model = model
        if not system_key and not worker_key and not model:
            return
        # Keep agents.json in sync (gitignored)
        try:
            self._save_agent_state()
        except OSError:
            pass

    def _load_agent_state(self) -> None:
        path = self._agent_state_path
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        agents = data.get("agents") if isinstance(data, dict) else None
        if not isinstance(agents, list):
            return
        for item in agents:
            if not isinstance(item, dict):
                continue
            aid = item.get("id")
            if not aid:
                continue
            try:
                agent = self.agents.get(aid)
            except ValueError:
                continue
            if agent.toggleable and "enabled" in item:
                agent.enabled = bool(item["enabled"])
            if agent.id == AgentId.FLEX:
                agent.enabled = True
                agent.preset = "personal"
                # TTS stays on for Flex unless user explicitly saved tts:false below
            if agent.id == AgentId.BRAINSTORM and "tts" not in item:
                agent.tts = True
            if item.get("model"):
                agent.model = str(item["model"])
            if item.get("api_key") is not None:
                k = str(item["api_key"]).strip()
                agent.api_key = k or None
            if "tts" in item:
                agent.tts = bool(item["tts"])
            if item.get("system_prompt") is not None:
                agent.system_prompt = str(item["system_prompt"]) or None
            for key in (
                "temperature",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
            ):
                if item.get(key) is not None:
                    try:
                        setattr(agent, key, float(item[key]))
                    except (TypeError, ValueError):
                        pass
            if item.get("max_tokens") is not None:
                try:
                    agent.max_tokens = int(item["max_tokens"])
                except (TypeError, ValueError):
                    pass

    def _save_agent_state(self) -> Path:
        payload = {
            "agents": [
                {
                    "id": a.id.value,
                    "enabled": a.enabled,
                    "preset": a.preset,
                    "model": a.model,
                    # Per-agent keys stay under data/ (gitignored) — never log them
                    "api_key": a.api_key,
                    "tts": a.tts,
                    "system_prompt": a.system_prompt,
                    "temperature": a.temperature,
                    "top_p": a.top_p,
                    "max_tokens": a.max_tokens,
                    "frequency_penalty": a.frequency_penalty,
                    "presence_penalty": a.presence_penalty,
                }
                for a in self.agents.list_agents()
            ]
        }
        path = self._agent_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return path

    # ── serialization ───────────────────────────────────────────────

    def _agent_dict(self, a: AgentState) -> dict[str, Any]:
        usage = self.llm.usage_snapshot()["by_agent"].get(a.id.value, {})
        tokens = int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0))
        has_llm = (
            bool(a.api_key) or self.llm.has_provider("deepseek") or self.llm.has_provider("ollama")
        )
        online = a.enabled and has_llm
        return {
            "id": a.id.value,
            "name": a.name,
            "role": a.role,
            "color": a.color,
            "enabled": a.enabled,
            "toggleable": a.toggleable,
            "preset": a.preset,
            "model": a.model or self.llm.default_model,
            "has_key": has_llm,
            "online": online,
            "tts": bool(a.tts),
            "system_prompt": a.system_prompt or "",
            "temperature": a.temperature,
            "top_p": a.top_p,
            "max_tokens": a.max_tokens,
            "frequency_penalty": a.frequency_penalty,
            "presence_penalty": a.presence_penalty,
            "tokens": tokens,
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "cost_usd": float(usage.get("cost_usd", 0.0)),
            "calls": int(usage.get("calls", 0)),
        }

    def toggle_agent(self, agent_id: str) -> dict[str, Any]:
        enabled = self.agents.toggle(agent_id)
        return {
            "id": agent_id,
            "enabled": enabled,
            "agents": [self._agent_dict(a) for a in self.agents.list_agents()],
        }

    def set_flex_preset(self, name: str) -> dict[str, Any]:
        """Flex is fixed — always personal; name ignored."""
        self.agents.set_flex_preset(name)
        data = self._agent_dict(self.agents.get(AgentId.FLEX))
        data["locked"] = True
        data["preset"] = "personal"
        return data

    def set_agent_llm(
        self,
        agent_id: str,
        *,
        model: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        agent = self.agents.get(agent_id)
        if model is not None:
            agent.model = model.strip() or None
        if api_key is not None:
            agent.api_key = api_key.strip() or None
        self.agents.emit_status(agent_id)
        self._save_agent_state()
        return self._agent_dict(agent)

    def set_agent_tune(self, agent_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update per-agent prompt, LLM knobs, and TTS flag (plan tuning panel)."""
        agent = self.agents.get(agent_id)
        if "model" in fields and fields["model"] is not None:
            agent.model = str(fields["model"]).strip() or None
        if "api_key" in fields and fields["api_key"] is not None:
            key = str(fields["api_key"]).strip()
            agent.api_key = key or None
        if "system_prompt" in fields:
            sp = fields["system_prompt"]
            agent.system_prompt = (str(sp).strip() if sp is not None else "") or None
        if "tts" in fields and fields["tts"] is not None:
            agent.tts = bool(fields["tts"])
        if "temperature" in fields:
            agent.temperature = (
                None if fields["temperature"] is None else float(fields["temperature"])
            )
        if "top_p" in fields:
            agent.top_p = None if fields["top_p"] is None else float(fields["top_p"])
        if "max_tokens" in fields:
            agent.max_tokens = None if fields["max_tokens"] is None else int(fields["max_tokens"])
        if "frequency_penalty" in fields:
            agent.frequency_penalty = (
                None if fields["frequency_penalty"] is None else float(fields["frequency_penalty"])
            )
        if "presence_penalty" in fields:
            agent.presence_penalty = (
                None if fields["presence_penalty"] is None else float(fields["presence_penalty"])
            )
        self.agents.emit_status(agent_id)
        self._save_agent_state()
        return self._agent_dict(agent)
