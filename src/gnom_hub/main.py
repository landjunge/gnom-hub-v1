"""Gnom-Hub v1 entry point – CLI smoke or HTTP server."""

from __future__ import annotations

import argparse
import os


def run_smoke() -> None:
    from gnom_hub.core.event_bus import EventBus
    from gnom_hub.hub import Hub

    bus = EventBus()

    def on_hello(data):
        print(f"[EventBus] hello -> {data}")

    bus.on("hello", on_hello)
    bus.emit("hello", {"msg": "Gnom-Hub v1 ready"})

    hub = Hub()
    snap = hub.snapshot()
    print(f"[Keys] root={hub.root}")
    print(f"[LLM] DeepSeek key={'yes' if snap['llm']['deepseek'] else 'no'}")
    print(f"[Agents] {len(snap['agents'])} active roster")
    print(f"[Memory] {snap['memory_summary']}")

    # Brainstorm turn, then execute (works without API key via stubs)
    out = hub.chat("Smoke: one-line plan for a checklist app")
    stage = out["pipeline"]["stage"]
    print(f"[Brainstorm] stage={stage}")
    assert stage == "brainstorm", f"expected brainstorm, got {stage}"
    out = hub.execute_sync()
    stage = out["pipeline"]["stage"]
    print(f"[Execute] stage={stage}")
    if stage == "clarify":
        out = hub.clarify("Yes")
        stage = out["pipeline"]["stage"]
        print(f"[Pipeline] after clarify stage={stage}")
    assert stage == "done", f"expected done, got {stage}"
    print(f"[Pipeline] workers={len(out['pipeline']['worker_results'])}")
    print(f"[WARM] facts={len(hub.warm.all_facts())}")
    print(
        f"[Workspace] temp={len(hub.workspace.list_files('temp'))} perm={len(hub.workspace.list_files('perm'))}"
    )
    print(f"[Telegram] configured={hub.telegram.enabled}")
    print("Gnom-Hub v1 - Step 2.x OK (smoke)")


def run_server(host: str, port: int) -> None:
    import uvicorn

    from gnom_hub.api.app import app

    print(f"Gnom-Hub v1 UI → http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gnom-Hub v1")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run smoke checks without starting the HTTP server",
    )
    parser.add_argument("--host", default=os.getenv("GNOM_HUB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("GNOM_HUB_PORT", "8080")))
    args = parser.parse_args()

    if args.smoke:
        run_smoke()
    else:
        run_server(args.host, args.port)


if __name__ == "__main__":
    main()
