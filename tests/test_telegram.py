from gnom_hub.core.event_bus import EventBus
from gnom_hub.telegram.bot import TelegramBridge, parse_allowed_chat_ids


def _handler():
    seen = []

    def on_cmd(cmd, arg, meta):
        seen.append((cmd, arg, meta.get("chat_id")))
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
        if cmd in ("tools", "tool"):
            return f"tools:{arg}"
        if cmd in ("fetch", "web"):
            return f"fetch:{arg}"
        if cmd == "hot":
            return f"hot:{arg}"
        return f"cmd:{cmd}"

    return on_cmd, seen


def test_telegram_commands_via_handler():
    bus = EventBus()
    on_cmd, seen = _handler()
    # No chat_id → test/API hook allowed when allowlist empty
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
    assert bot.handle_text("/tools") == "tools:"
    assert bot.handle_text("/fetch https://example.com") == "fetch:https://example.com"
    assert bot.handle_text("/hot list") == "hot:list"
    assert any(s[0] == "warm" and s[1] == "add fact" for s in seen)
    assert any(s[0] == "cancel" for s in seen)
    assert any(s[0] == "hot" and s[1] == "list" for s in seen)


def test_parse_allowed_chat_ids():
    assert parse_allowed_chat_ids("") == frozenset()
    assert parse_allowed_chat_ids("123, 456") == frozenset({123, 456})
    assert parse_allowed_chat_ids("123;-100999") == frozenset({123, -100999})
    assert parse_allowed_chat_ids("nope,42") == frozenset({42})


def test_telegram_allowlist_denies_unknown_chat():
    bus = EventBus()
    on_cmd, seen = _handler()
    bot = TelegramBridge(
        bus,
        token="",
        on_command=on_cmd,
        allowed_chat_ids=frozenset({111}),
    )
    # Unknown chat
    reply = bot.handle_text("/do secret", chat_id=999)
    assert "Unauthorized" in reply
    assert not seen
    # Allowed chat
    assert bot.handle_text("/do ok", chat_id=111) == "did:ok"
    assert ("do", "ok", 111) in seen


def test_telegram_empty_allowlist_denies_real_chat_id():
    """Secure default: real Telegram chat_id blocked until allowlist is set."""
    bus = EventBus()
    on_cmd, seen = _handler()
    bot = TelegramBridge(bus, token="", on_command=on_cmd, allowed_chat_ids=frozenset())
    reply = bot.handle_text("/do evil", chat_id=42)
    assert "Unauthorized" in reply
    assert "TELEGRAM_ALLOWED_CHAT_IDS" in reply
    assert not seen
    # Test hook without chat_id still works
    assert bot.handle_text("/help") == "help-ok"
