from gnom_hub.core.event_bus import EventBus


def test_emit_calls_handler():
    bus = EventBus()
    received = []

    def handler(data):
        received.append(data)

    bus.on("ping", handler)
    bus.emit("ping", {"x": 1})

    assert received == [{"x": 1}]


def test_off_removes_handler():
    bus = EventBus()
    received = []

    def handler(data):
        received.append(data)

    bus.on("ping", handler)
    bus.off("ping", handler)
    bus.emit("ping", {"x": 1})

    assert received == []


def test_clear():
    bus = EventBus()
    received = []

    bus.on("ping", lambda d: received.append(d))
    bus.clear()
    bus.emit("ping", 1)

    assert received == []
