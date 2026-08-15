"""ThreadDesk packet is read-only. Never chats or executes."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app
from gnom_hub.threaddesk_ops import peek


def test_peek_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    got = peek()
    assert got["ok"] is True
    assert got["present"] is False
    assert got["ran"] is False
    assert got["text"] == ""


def test_peek_gnom_chat(tmp_path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    (tmp_path / "gnom-chat.json").write_text(
        json.dumps({"text": "Modus: Send\n\nKontext halten"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "gnom.json").write_text(
        json.dumps({"kind": "threaddesk.gnom", "mode": "brainstorm", "title": "Desk"}),
        encoding="utf-8",
    )
    got = peek()
    assert got["present"] is True
    assert got["kind"] == "threaddesk.gnom"
    assert got["mode"] == "brainstorm"
    assert got["title"] == "Desk"
    assert got["text"].startswith("Modus: Send")
    assert got["ran"] is False


def test_peek_handoff_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    (tmp_path / "handoff.json").write_text(
        json.dumps(
            {
                "kind": "threaddesk.handoff",
                "title": "Switcher",
                "notes": "nächster Schritt",
            }
        ),
        encoding="utf-8",
    )
    got = peek()
    assert got["present"] is True
    assert "Switcher" in got["text"]
    assert "nächster Schritt" in got["text"]


def test_api_threaddesk_does_not_chat(tmp_path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    (tmp_path / "gnom-chat.json").write_text(
        json.dumps({"text": "nur füllen"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/api/threaddesk")
        assert r.status_code == 200
        body = r.json()
        assert body["present"] is True
        assert body["text"] == "nur füllen"
        assert body["ran"] is False
        js = c.get("/static/app.js").text
        assert "loadThreadDesk" in js
        assert 'api("POST", "/api/threaddesk"' not in js
    hub_mod._HUB = None
