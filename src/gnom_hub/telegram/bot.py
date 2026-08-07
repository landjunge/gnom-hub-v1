"""Optional Telegram bridge: commands → EventBus / Hub (stdlib HTTP only)."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from gnom_hub.core.event_bus import EventBus

# Commands from PRE_PLAN (subset, KISS)
# /status /bs /exec /hot /tools /fetch /ws /jobs /usage /pack /warm …


def parse_allowed_chat_ids(raw: str | None = None) -> frozenset[int]:
    """
    Parse TELEGRAM_ALLOWED_CHAT_IDS (comma/space separated).
    Empty → no IDs configured (secure default: real chats denied).
    """
    text = (raw if raw is not None else os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")).strip()
    if not text:
        return frozenset()
    out: set[int] = set()
    for part in text.replace(";", ",").replace(" ", ",").split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except ValueError:
            continue
    return frozenset(out)


class TelegramBridge:
    """
    Long-poll getUpdates when enabled + token present.
    Does not start unless start() is called.

    Chat allowlist (C1):
      TELEGRAM_ALLOWED_CHAT_IDS=123,-100456
      - Non-empty: only those chat_ids may run commands.
      - Empty: only messages without chat_id (test/API hook) are allowed;
        real Telegram updates always carry chat_id → denied until configured.
    """

    def __init__(
        self,
        bus: EventBus,
        token: str,
        *,
        on_command: Callable[[str, str, dict[str, Any]], str] | None = None,
        poll_seconds: float = 2.0,
        allowed_chat_ids: frozenset[int] | None = None,
    ) -> None:
        self.bus = bus
        self.token = token.strip()
        self.on_command = on_command
        self.poll_seconds = poll_seconds
        self._offset = 0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_chat_id: int | None = None
        self._last_text: str = ""
        self.enabled = bool(self.token)
        self.allowed_chat_ids: frozenset[int] = (
            allowed_chat_ids if allowed_chat_ids is not None else parse_allowed_chat_ids()
        )

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_chat_allowed(self, chat_id: int | None) -> bool:
        """True if this chat may run commands / free-text pipeline."""
        if not self.allowed_chat_ids:
            # No allowlist configured: permit test hook (no chat_id) only.
            return chat_id is None
        if chat_id is None:
            return False
        return int(chat_id) in self.allowed_chat_ids

    def start(self) -> bool:
        if not self.enabled or self.running:
            return self.running
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="telegram-poll", daemon=True)
        self._thread.start()
        self.bus.emit(
            "telegram.status",
            {
                "running": True,
                "allowlist_size": len(self.allowed_chat_ids),
            },
        )
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        self.bus.emit("telegram.status", {"running": False})

    def handle_text(self, text: str, chat_id: int | None = None) -> str:
        """Process one inbound message; returns reply text."""
        if chat_id is not None:
            self._last_chat_id = chat_id
        raw = (text or "").strip()
        self._last_text = raw
        self.bus.emit("telegram.message", {"text": raw, "chat_id": chat_id})

        if not self.is_chat_allowed(chat_id):
            self.bus.emit(
                "telegram.denied",
                {"chat_id": chat_id, "text": raw[:80]},
            )
            if not self.allowed_chat_ids:
                return (
                    "Unauthorized: set TELEGRAM_ALLOWED_CHAT_IDS to your chat id "
                    f"(got chat_id={chat_id})."
                )
            return f"Unauthorized chat_id={chat_id} (not in TELEGRAM_ALLOWED_CHAT_IDS)."

        if not raw.startswith("/"):
            # free text = brainstorm turn (desktop-aligned); use /do for one-shot
            return self._dispatch("bs", raw, {"chat_id": chat_id})

        parts = raw.split(maxsplit=1)
        cmd = parts[0][1:].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        # aliases
        if cmd in ("start", "help"):
            cmd = "help"
        if cmd in ("reset_temp", "resettemp"):
            cmd = "reset"
        return self._dispatch(cmd, arg, {"chat_id": chat_id})

    def send_message(self, chat_id: int, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            self._api(
                "sendMessage",
                {"chat_id": chat_id, "text": text[:4000]},
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    def _dispatch(self, cmd: str, arg: str, meta: dict[str, Any]) -> str:
        self.bus.emit("telegram.command", {"cmd": cmd, "arg": arg, **meta})
        if self.on_command:
            try:
                return self.on_command(cmd, arg, meta)
            except Exception as exc:  # noqa: BLE001
                return f"Error: {exc}"
        return f"Unknown command /{cmd} (no hub handler)"

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                data = self._api(
                    "getUpdates",
                    {"timeout": 25, "offset": self._offset},
                )
                for upd in data.get("result") or []:
                    self._offset = int(upd["update_id"]) + 1
                    msg = upd.get("message") or upd.get("edited_message") or {}
                    chat = msg.get("chat") or {}
                    chat_id = chat.get("id")
                    text = msg.get("text") or ""
                    if text and chat_id is not None:
                        reply = self.handle_text(text, int(chat_id))
                        if reply:
                            self.send_message(int(chat_id), reply)
            except Exception as exc:  # noqa: BLE001
                self.bus.emit("telegram.error", {"error": str(exc)})
                time.sleep(self.poll_seconds)
            time.sleep(0.2)

    def _api(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        body = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Telegram HTTP {e.code}: {raw[:200]}") from e
        data = json.loads(raw)
        if not data.get("ok", True) and method != "getUpdates":
            raise RuntimeError(str(data))
        return data
