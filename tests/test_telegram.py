from gnom_hub.core.event_bus import EventBus
from gnom_hub.telegram.bot import TelegramBridge


def test_telegram_commands_via_handler():
    bus = EventBus()
    seen = []

    def on_cmd(cmd, arg, meta):
        seen.append((cmd, arg))
        if cmd == "help":
            return "help-ok"
        if cmd == "do":
            return f"did:{arg}"
        return f"cmd:{cmd}"

    bot = TelegramBridge(bus, token="", on_command=on_cmd)
    # empty token = disabled poll, but handle_text still works
    assert bot.handle_text("/help") == "help-ok"
    assert bot.handle_text("/do build it") == "did:build it"
    assert bot.handle_text("plain task") == "did:plain task"
    assert ("help", "") in seen
    assert ("do", "build it") in seen
