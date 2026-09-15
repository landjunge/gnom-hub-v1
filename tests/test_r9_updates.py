"""R9: update search is allowed; install only on click; busy blocks; no silent main."""

import urllib.error
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gnom_hub import updates as upd
from gnom_hub.api.app import create_app
from gnom_hub.updates import apply, status

ROOT = Path(__file__).resolve().parents[1]


def _clear_last():
    upd._LAST["checked_at"] = None
    upd._LAST["available"] = None
    upd._LAST["error"] = None


def test_update_status_honest():
    _clear_last()
    st = status()
    assert st["installed"]
    assert st["channel"] == "stable"
    assert "Klick" in st["message"]
    assert st["can_apply"] is False
    assert "Notfall" in st["emergency"]


def test_apply_without_release_refuses():
    _clear_last()
    out = apply(busy=False)
    assert out["ok"] is False
    assert out["error"] == "no_release"


def test_apply_busy_refuses():
    out = apply(busy=True)
    assert out["ok"] is False
    assert out["error"] == "busy"


def test_apply_never_installs_from_main():
    _clear_last()
    upd._LAST["available"] = {
        "tag": "v9.9.9",
        "name": "v9.9.9",
        "html_url": "https://example.invalid",
        "draft": False,
        "prerelease": False,
    }
    try:
        out = apply(busy=False)
        assert out["ok"] is False
        assert out["error"] == "not_published"
        assert "main" in out["message"]
    finally:
        _clear_last()


def test_check_404_is_no_release():
    _clear_last()
    err = urllib.error.HTTPError(upd.RELEASES_URL, 404, "Not Found", hdrs=None, fp=None)
    with patch("urllib.request.urlopen", side_effect=err):
        st = upd.check()
    assert st["available"] is None
    assert st["can_apply"] is False
    assert "kein GitHub-Release" in (st.get("message") or "")


def test_updates_api():
    _clear_last()
    client = TestClient(create_app())
    r = client.get("/api/updates")
    assert r.status_code == 200
    body = r.json()
    assert body["installed"]
    assert "notes" in body
    bad = client.post("/api/updates/apply")
    assert bad.status_code in (400, 409)
    html = client.get("/").text
    assert "sys-update-check" in html
    assert "sys-update-details" in html
    assert "sys-update-apply" in html
    assert "sys-update-restore" in html
    js = (ROOT / "src/gnom_hub/ui/static/parts/03-system.js").read_text(encoding="utf-8")
    assert "checkUpdates" in js
    assert "detailsUpdates" in js
    assert "restoreUpdates" in js
