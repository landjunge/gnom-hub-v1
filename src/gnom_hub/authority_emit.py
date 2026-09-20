"""G2: emit Authority Event Envelope to a JSONL file. Never a ThreadDesk DB."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gnom_hub.config.paths import session_data_root

SOURCE = "gnom-hub-v1"
ALLOWED_TYPES = frozenset(
    {
        "work.started",
        "agent.invoked",
        "delegation.created",
        "tool.intent",
        "tool.result",
        "work.finished",
    }
)


def enabled() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return bool((os.environ.get("GNOM_AUTHORITY_EVENTS") or "").strip())
    raw = (os.environ.get("GNOM_AUTHORITY_EVENTS") or "1").strip().lower()
    return raw not in ("0", "false", "off", "no")


def events_path() -> Path:
    override = (os.environ.get("GNOM_AUTHORITY_EVENTS_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    return session_data_root() / "authority-events.jsonl"


def _iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _workflow_id() -> str:
    try:
        from gnom_hub.threaddesk_ops import existing_handoff

        ho = existing_handoff() or {}
        hid = str(ho.get("handoff_id") or ho.get("task_id") or "").strip()
        if hid:
            return hid
    except Exception:  # noqa: BLE001
        pass
    return (os.environ.get("GNOM_RUN_ID") or "gnom-local").strip() or "gnom-local"


def _canonical(event: dict[str, Any]) -> bytes:
    body = {k: v for k, v in event.items() if k != "event_hash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _hash(event: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(event)).hexdigest()


def _last_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    last = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                last = json.loads(line).get("event_hash")
            except json.JSONDecodeError:
                continue
    return str(last) if last else None


def emit(
    event_type: str, *, actor: str = "", action: str = "", resource: str = "", **extra: Any
) -> dict[str, Any] | None:
    """Append one envelope event. Swallows errors so the pipeline never depends on it."""
    if not enabled() or event_type not in ALLOWED_TYPES:
        return None
    try:
        path = events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        trace = _workflow_id()
        event: dict[str, Any] = {
            "schema_version": "1",
            "event_id": uuid.uuid4().hex[:16],
            "timestamp": _iso(),
            "trace_id": trace,
            "span_id": uuid.uuid4().hex[:8],
            "workflow_id": trace,
            "project_id": "gnom-hub-v1",
            "source_tool": SOURCE,
            "event_type": event_type,
            "previous_event_hash": _last_hash(path),
            "data_labels": ["PUBLIC"],
        }
        if actor:
            event["actor"] = {"agent_id": actor, "role": actor}
        if action:
            event["action"] = action
        if resource:
            event["resource"] = resource
        for key, value in extra.items():
            if value is not None and key not in event:
                event[key] = value
        event["event_hash"] = _hash(event)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=True) + "\n")
        return event
    except Exception:  # noqa: BLE001
        return None
