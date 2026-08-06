"""Telegram bridge start/stop/inbound (extracted from Hub)."""

from __future__ import annotations

import os
from typing import Any

from gnom_hub.telegram.bot import TelegramBridge


class TelegramLifecycleMixin:
    """Mixin extracted from Hub — pure move."""

    def _init_telegram(self) -> TelegramBridge:
        token = (
            self.keys.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
        ).strip()
        return TelegramBridge(self.bus, token, on_command=self._telegram_command)

    def telegram_start(self) -> dict[str, Any]:
        ok = self.telegram.start()
        return {"ok": ok, "running": self.telegram.running, "configured": self.telegram.enabled}

    def telegram_stop(self) -> dict[str, Any]:
        self.telegram.stop()
        return {"ok": True, "running": False}

    def telegram_inbound(self, text: str, chat_id: int | None = None) -> dict[str, Any]:
        reply = self.telegram.handle_text(text, chat_id)
        return {"reply": reply, "snapshot": self.snapshot()}
