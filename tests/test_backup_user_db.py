"""Wave 3: backup zip includes consistent user.db."""

from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app
from gnom_hub.memory.hot import HotMemory


def test_hot_save_uses_replace_session(tmp_path: Path) -> None:
    hot = HotMemory(tmp_path, auto_load=False)
    hot.add_message("user", "hello atomic")
    hot.add_fact("session fact")
    hot.save()
    # Reload from DB
    hot2 = HotMemory(tmp_path, auto_load=True)
    assert any(m.get("content") == "hello atomic" for m in hot2.session["messages"])
    assert "session fact" in hot2.session["facts"]


def test_create_backup_includes_user_db(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    monkeypatch.setenv("GNOM_USER_DB", str(tmp_path / "User" / "user.db"))
    (tmp_path / "User").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)

    app = create_app()
    with TestClient(app) as c:
        c.post("/api/chat?sync=1", json={"text": "only brainstorm for backup"})
        c.post("/api/memory/warm", json={"text": "Warm fact for backup zip"})
        r = c.post("/api/backup")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("user_db") is True or body.get("user_db_bytes", 0) > 0
        zpath = Path(body["path"])
        assert zpath.is_file()
        with zipfile.ZipFile(zpath, "r") as zf:
            names = zf.namelist()
            assert any(n.endswith("user/user.db") or n == "user/user.db" for n in names)
            assert "meta.json" in names or any(n.endswith("meta.json") for n in names)
    hub_mod._HUB = None
