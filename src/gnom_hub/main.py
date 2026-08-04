"""Gnom-Hub v1 entry point."""

from gnom_hub.config.keys import ensure_env_from_key_txt, has_deepseek_key, load_keys
from gnom_hub.config.paths import project_root
from gnom_hub.core.event_bus import EventBus
from gnom_hub.llm.manager import LLMManager


def main() -> None:
    bus = EventBus()

    def on_hello(data):
        print(f"[EventBus] hello -> {data}")

    bus.on("hello", on_hello)
    bus.emit("hello", {"msg": "Gnom-Hub v1 ready"})

    root = project_root()
    env_path = ensure_env_from_key_txt(root)
    keys = load_keys(root)
    llm = LLMManager(keys=keys)

    key_ok = has_deepseek_key(keys)
    print(f"[Keys] root={root}")
    print(f"[Keys] .env={'yes' if env_path and env_path.is_file() else 'no'}")
    print(f"[LLM] DeepSeek key={'yes' if key_ok else 'no (see Key.txt.example)'}")
    print(
        f"[LLM] free_only={llm.free_only} "
        f"max_budget_usd={llm.max_budget_usd} model={llm.default_model}"
    )
    print("Gnom-Hub v1 - Step 0.2 OK")


if __name__ == "__main__":
    main()
