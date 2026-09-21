"""Resolved V4 tool targets.

The UI launcher has stable product slots, but actual runtime URLs are environment-
specific. Public product pages are exposed separately as fallbacks and are never
reported as connected tool UIs.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse


_TOOL_SLOTS: tuple[dict[str, str], ...] = (
    {
        "key": "1",
        "id": "netzwerkpunkt",
        "name": "NetzwerkPunkt",
        "env": "GNOM_NETWORKPUNKT_URL",
        "external_url": "https://netzwerkpunkt.de/",
    },
    {
        "key": "2",
        "id": "gnom-hub",
        "name": "Gnom-Hub-V1",
        "internal_url": "/v4",
        "external_url": "https://gnom-hub-v1.netzwerkpunkt.de/",
    },
    {
        "key": "3",
        "id": "threaddesk",
        "name": "ThreadDesk",
        "env": "THREADDESK_URL",
        "external_url": "https://threaddesk.netzwerkpunkt.de/",
    },
    {
        "key": "4",
        "id": "tollgate",
        "name": "TollGate",
        "env": "TOLLGATE_URL",
        "external_url": "https://tollgate.netzwerkpunkt.de/",
    },
    {
        "key": "5",
        "id": "4allpass",
        "name": "4AllPass",
        "env": "GNOM_ALLPASS_URL",
        "external_url": "https://4allpass.netzwerkpunkt.de/",
    },
)


def _http_url(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return raw.rstrip("/")


def tool_targets() -> dict[str, object]:
    """Return non-secret launcher targets for the V4 desk."""

    rows: list[dict[str, object]] = []
    for slot in _TOOL_SLOTS:
        internal = slot.get("internal_url")
        env_name = slot.get("env")
        runtime = _http_url(os.getenv(env_name)) if env_name else None
        target = internal or runtime
        rows.append(
            {
                "key": slot["key"],
                "id": slot["id"],
                "name": slot["name"],
                "connected": bool(target),
                "target": target,
                "mode": "internal" if internal else ("embed" if runtime else "unavailable"),
                "external_url": slot["external_url"],
            }
        )
    return {"tools": rows}
