"""Gnom-Hub v1 entry point."""

from gnom_hub.core.event_bus import EventBus


def main() -> None:
    bus = EventBus()

    def on_hello(data):
        print(f"[EventBus] hello -> {data}")

    bus.on("hello", on_hello)
    bus.emit("hello", {"msg": "Gnom-Hub v1 ready"})
    print("Gnom-Hub v1 - Step 0.1 OK")


if __name__ == "__main__":
    main()
