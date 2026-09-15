"""User-update status. Search may run; install only on click. No silent apply."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from gnom_hub import __version__

RELEASES_URL = "https://api.github.com/repos/landjunge/gnom-hub-v1/releases/latest"
CHANNEL = "stable"
_LAST: dict[str, Any] = {
    "checked_at": None,
    "available": None,
    "error": None,
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def status() -> dict[str, Any]:
    avail = _LAST.get("available")
    notes = "Noch kein von Daniel freigegebenes Nutzer-Release."
    msg = (
        "Kein veröffentlichtes Nutzer-Release. "
        "Suche prüft GitHub. Installation nur nach Klick, "
        "nicht während laufender Arbeit. Backup wäre vor dem Wechsel Pflicht."
    )
    if avail:
        notes = str(avail.get("name") or avail.get("tag") or notes)
        msg = f"Verfügbar: {avail.get('tag')} — Installation nur nach Klick."
    elif _LAST.get("error"):
        msg = f"Suche: {_LAST['error']}. Kein stilles Update."
    return {
        "installed": __version__,
        "channel": CHANNEL,
        "last_check": _LAST.get("checked_at"),
        "available": avail,
        "notes": notes,
        "emergency": "Notfall: Backup in System laden. Kein stilles Zurückspielen von main.",
        "message": msg,
        "can_apply": bool(avail),
    }


def check() -> dict[str, Any]:
    _LAST["checked_at"] = _iso_now()
    _LAST["error"] = None
    req = urllib.request.Request(
        RELEASES_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "gnom-hub-v1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            _LAST["available"] = None
            _LAST["error"] = "kein GitHub-Release"
            return status()
        _LAST["available"] = None
        _LAST["error"] = f"GitHub {exc.code}"
        return status()
    except (OSError, json.JSONDecodeError) as exc:
        _LAST["available"] = None
        _LAST["error"] = str(exc)[:120]
        return status()
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        _LAST["available"] = None
        return status()
    _LAST["available"] = {
        "tag": tag,
        "name": str(data.get("name") or tag),
        "html_url": str(data.get("html_url") or ""),
        "draft": bool(data.get("draft")),
        "prerelease": bool(data.get("prerelease")),
    }
    return status()


def apply(*, busy: bool) -> dict[str, Any]:
    if busy:
        return {
            "ok": False,
            "error": "busy",
            "message": "Laufende Arbeit blockiert Update. Zuerst Abbrechen.",
        }
    st = status()
    if not st.get("can_apply"):
        return {
            "ok": False,
            "error": "no_release",
            "message": st.get("message") or "Kein Release zum Installieren.",
        }
    return {
        "ok": False,
        "error": "not_published",
        "message": (
            "Es gibt noch kein von Daniel freigegebenes Nutzer-Release. "
            "Kein stilles Update von main."
        ),
    }
