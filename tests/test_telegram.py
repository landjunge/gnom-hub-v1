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
        if cmd == "bs":
            return f"bs:{arg}"
        if cmd == "pack":
            return f"pack:{arg}"
        if cmd == "warm":
            return f"warm:{arg}"
        if cmd == "cancel":
            return "cancel-ok"
        if cmd == "cold":
            return f"cold:{arg}"
        if cmd in ("vec", "vector", "search"):
            return f"vec:{arg}"
        if cmd == "trace":
            return f"trace:{arg}"
        if cmd == "backup":
            return f"backup:{arg}"
        if cmd in ("jobs", "job"):
            return f"jobs:{arg}"
        if cmd in ("usage", "cost", "spend"):
            return f"usage:{arg}"
        if cmd in ("ws", "workspace", "files"):
            return f"ws:{arg}"
        return f"cmd:{cmd}"

    bot = TelegramBridge(bus, token="", on_command=on_cmd)
    assert bot.handle_text("/help") == "help-ok"
    assert bot.handle_text("/do build it") == "did:build it"
    assert bot.handle_text("plain task") == "bs:plain task"
    assert bot.handle_text("/bs idea") == "bs:idea"
    assert bot.handle_text("/pack list") == "pack:list"
    assert bot.handle_text("/warm add fact") == "warm:add fact"
    assert bot.handle_text("/cancel") == "cancel-ok"
    assert bot.handle_text("/cold list") == "cold:list"
    assert bot.handle_text("/vec search hub") == "vec:search hub"
    assert bot.handle_text("/trace 10") == "trace:10"
    assert bot.handle_text("/backup list") == "backup:list"
    assert bot.handle_text("/jobs") == "jobs:"
    assert bot.handle_text("/usage reset") == "usage:reset"
    assert bot.handle_text("/ws list") == "ws:list"
    assert ("warm", "add fact") in seen
    assert ("cancel", "") in seen
    assert ("cold", "list") in seen
    assert ("vec", "search hub") in seen
    assert ("trace", "10") in seen
    assert ("backup", "list") in seen
    assert ("jobs", "") in seen
    assert ("usage", "reset") in seen
    assert ("ws", "list") in seen
