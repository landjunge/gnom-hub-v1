"""System settings, usage, help, canvas, god-mode (extracted from Hub)."""

from __future__ import annotations

from typing import Any

from gnom_hub.ui.tooltips import TOOLTIPS


class SystemOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def set_god_mode(self, enabled: bool, reason: str = "api") -> dict[str, Any]:
        if enabled:
            self.god_mode.enable(reason)
        else:
            self.god_mode.disable(reason)
        self.computer.set_god_mode(self.god_mode.enabled)
        return self.god_mode.snapshot()

    # ── commands ────────────────────────────────────────────────────

    def usage_dict(self) -> dict[str, Any]:
        snap = self.llm.usage_snapshot()
        return {
            "spent_usd": snap.get("spent_usd", 0.0),
            "prompt_tokens": snap.get("prompt_tokens", 0),
            "completion_tokens": snap.get("completion_tokens", 0),
            "by_agent": snap.get("by_agent") or {},
            "free_only": self.llm.free_only,
            "max_budget_usd": self.llm.max_budget_usd,
        }

    def reset_usage(self) -> dict[str, Any]:
        data = self.llm.reset_usage()
        self._append_trace("usage.reset", {"ok": True})
        return {"ok": True, **data, **self.usage_dict()}

    def set_system(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Global free_only / budget / UI lang (system panel)."""
        if "free_only" in fields and fields["free_only"] is not None:
            self.llm.free_only = bool(fields["free_only"])
        if "max_budget_usd" in fields:
            raw = fields["max_budget_usd"]
            if raw is None or raw == "":
                self.llm.max_budget_usd = None
            else:
                self.llm.max_budget_usd = float(raw)
        if fields.get("default_model"):
            self.llm.default_model = str(fields["default_model"]).strip()
        if fields.get("ui_lang"):
            lang = str(fields["ui_lang"]).strip().lower()
            if lang in ("en", "de"):
                self.ui_lang = lang
        if "auto_pack_after_execute" in fields and fields["auto_pack_after_execute"] is not None:
            self.auto_pack_after_execute = bool(fields["auto_pack_after_execute"])
        if "pack_max" in fields and fields["pack_max"] is not None:
            try:
                self.pack_max = max(5, min(100, int(fields["pack_max"])))
            except (TypeError, ValueError):
                pass
        return self.system_dict()

    def system_dict(self) -> dict[str, Any]:
        usage = self.llm.usage_snapshot()
        return {
            "deepseek": self.llm.has_provider("deepseek"),
            "ollama": self.llm.has_provider("ollama"),
            "free_only": self.llm.free_only,
            "max_budget_usd": self.llm.max_budget_usd,
            "spent_usd": usage["spent_usd"],
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "default_model": self.llm.default_model,
            "god_mode": self.god_mode.enabled,
            "ui_lang": self.ui_lang,
            "checkpoint_exists": self._checkpoint_path.is_file(),
            "version": "3.7.1",
            "providers": self.llm.providers_snapshot(),
            "backups": self.list_backups()[:8],
            "packs": self.list_session_packs()[:12],
            "auto_pack_after_execute": self.auto_pack_after_execute,
            "pack_max": self.pack_max,
        }

    def help_text(self) -> dict[str, Any]:

        return {
            "title": "Gnom-Hub help",
            "how_to": (
                "1) Send / Enter = brainstorm turn. "
                "2) Execute / Ctrl+Enter = distill + workers. "
                "3) Send+Execute = one shot after typing. "
                "4) Ctrl/⌘+S = save HOT + agents. "
                "5) Esc = close fullscreen or cancel job. "
                "6) Box 3: Copy/DL/Tab/WS/↑perm/fullscreen; toolbar Copy all + Diff + History. "
                "7) Cost badge + Compact density; job timer while busy. "
                "8) Auto-save + Box 3 focus after successful Execute. 9) Session packs (chat/history/workspace/ui_prefs/notes; list filter). 10) History Re-Exec. 11) Telegram: /hot /tools /fetch /ws /jobs /usage /backup …"
            ),
            "example": "Type idea → Execute → Pack ↓ (USB) → History Re-Exec → Diff.",
            "pipeline": "Brainstorm → Execute → Distill → Flex → Workers (1–4) → Quality → Memory",
            "keys": (
                "Keyboard: Enter send · Ctrl/⌘+Enter execute · Ctrl/⌘+S save · Esc cancel/close overlay. "
                "DEEPSEEK_API_KEY or Ollama. TELEGRAM optional."
            ),
        }

    def canvas(self) -> dict[str, Any]:
        return {
            "mermaid": self.hot.canvas.to_mermaid(),
            "nodes": list(self.hot.canvas.nodes),
            "path": str(self.hot.canvas_path),
        }

    def tooltips(self, lang: str = "en") -> dict[str, Any]:
        out: dict[str, Any] = {}
        for tip_id, langs in TOOLTIPS.items():
            block = langs.get(lang) or langs.get("en")
            if block:
                out[tip_id] = dict(block)
        return out
