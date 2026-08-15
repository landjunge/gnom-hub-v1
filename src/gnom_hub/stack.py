"""Three-layer desk: ThreadDesk prepares, Gnom runs the desk, Tollgate owns providers."""

from __future__ import annotations

import os
from typing import Any


def extract_tollgate_route(out: dict[str, Any] | None) -> dict[str, str]:
    """Read provider/model from a Tollgate chat payload. Gnom does not pick."""
    out = out or {}
    routing = out.get("routing") if isinstance(out.get("routing"), dict) else {}
    pick = routing.get("route") if isinstance(routing.get("route"), dict) else {}
    provider = str(pick.get("provider") or out.get("provider") or "").strip()
    model = str(pick.get("model") or out.get("model") or "").strip()
    return {"provider": provider, "model": model, "via": "tollgate"}


def via_tollgate() -> bool:
    return os.getenv("GNOM_TOLLGATE_LLM", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def stack_snapshot() -> dict[str, Any]:
    """Who does what. Gnom does not own a second cloud-provider stack."""
    from gnom_hub.threaddesk_ops import peek

    td = peek()
    via = via_tollgate()
    return {
        "roles": {
            "threaddesk": "prepare",
            "gnom": "desk",
            "tollgate": "providers",
        },
        "providers_owner": "tollgate" if via else "gnom-legacy",
        "local_only": ["ollama"],
        "via_tollgate": via,
        "threaddesk": {
            "present": bool(td.get("present")),
            "mode": td.get("mode") or "",
            "kind": td.get("kind") or "",
        },
        "instruction": (
            "Cloud providers live in Tollgate. Gnom is a client. ThreadDesk never calls a provider."
        ),
    }
