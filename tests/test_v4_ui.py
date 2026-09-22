from __future__ import annotations

from fastapi.testclient import TestClient

from gnom_hub.api.app import create_app


def test_v4_route_serves_clean_desk():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/v4")
    assert response.status_code == 200
    body = response.text
    assert "Gnom-Hub V4" in body
    assert "Brainstorm" in body
    assert "Coordinator" in body
    assert "W1" in body and "W4" in body
    assert "Arbeit starten" in body
    assert "BOX 1" in body and "BOX 3" in body
    assert "Flex" not in body
    assert "Memory" not in body


def test_v4_static_assets_exist_and_are_separate():
    app = create_app()
    with TestClient(app) as client:
        css = client.get("/static/v4.css")
        js = client.get("/static/v4.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert ".desk-grid" in css.text
    assert "choices.slice(0, 4)" in js.text
    assert 'target: "brainstorm"' in js.text
    assert '"/api/execute"' in js.text
    assert "/api/choice" in js.text
    assert '"/api/workspace/keep"' in js.text


def test_v4_approved_visual_rules():
    app = create_app()
    with TestClient(app) as client:
        css = client.get("/static/v4.css").text
        html = client.get("/v4").text
    assert "grid-template-columns:repeat(6,minmax(0,1fr))" in css
    assert ".agent-worker1{--agent:#4169E1}" in css
    assert "@keyframes agent-glow" in css
    assert "50%{opacity:.15" in css
    assert "height:36px" in css
    assert html.count("Arbeit starten") == 2  # button + explanatory empty-state text
    assert html.count('id="execute"') == 1


def test_v4_tool_module_contract():
    app = create_app()
    with TestClient(app) as client:
        html = client.get("/v4").text
        tools_js = client.get("/static/v4-tools.js").text
        manifest = client.get("/static/v4-tool-manifest.js").text
        tools_css = client.get("/static/v4-tools.css").text
    assert 'id="tools-toggle"' in html
    assert 'id="tool-module"' in html
    assert 'id="tool-frame"' in html
    assert "same" not in html.lower()
    assert "activeKey === tool.key" in tools_js
    assert 'event.key === "Escape"' in tools_js
    assert "typingTarget(event.target)" in tools_js
    for key in ["1", "2", "3", "4", "5"]:
        assert f'key: "{key}"' in manifest
    for name in ["NetzwerkPunkt", "Gnom-Hub-V1", "ThreadDesk", "TollGate", "4AllPass"]:
        assert name in manifest
    assert ".tool-grid" in tools_css
    assert ".tool-frame" in tools_css


def test_v4_keyboard_focus_contract():
    app = create_app()
    with TestClient(app) as client:
        tools_js = client.get("/static/v4-tools.js").text
    assert 'event.code === "Space"' in tools_js
    assert 'document.querySelector("#chat-input")' in tools_js
    assert "input.focus()" in tools_js
    assert "event.target.blur()" in tools_js
    assert 'event.key === "Escape"' in tools_js


def test_v4_tool_targets_resolve_runtime_urls(monkeypatch):
    monkeypatch.setenv("TOLLGATE_URL", "http://127.0.0.1:8787")
    monkeypatch.setenv("THREADDESK_URL", "http://127.0.0.1:18181")
    monkeypatch.delenv("GNOM_ALLPASS_URL", raising=False)
    app = create_app()
    with TestClient(app) as client:
        payload = client.get("/api/tool-targets").json()
    rows = {row["id"]: row for row in payload["tools"]}
    assert rows["gnom-hub"]["connected"] is True
    assert rows["gnom-hub"]["target"] == "/v4"
    assert rows["tollgate"]["target"] == "http://127.0.0.1:8787"
    assert rows["threaddesk"]["target"] == "http://127.0.0.1:18181"
    assert rows["4allpass"]["connected"] is False
    assert rows["4allpass"]["external_url"] == "https://4allpass.netzwerkpunkt.de/"


def test_v4_tool_targets_reject_non_http_runtime_url(monkeypatch):
    monkeypatch.setenv("GNOM_ALLPASS_URL", "file:///tmp/not-a-tool")
    app = create_app()
    with TestClient(app) as client:
        payload = client.get("/api/tool-targets").json()
    rows = {row["id"]: row for row in payload["tools"]}
    assert rows["4allpass"]["connected"] is False
    assert rows["4allpass"]["target"] is None


def test_v4_auto_backup_toggle_contract():
    app = create_app()
    with TestClient(app) as client:
        html = client.get("/v4").text
        js = client.get("/static/v4.js").text
        css = client.get("/static/v4.css").text
    assert 'id="auto-backup-chip"' in html
    assert "Backup aus" in html
    assert 'api("/api/system")' in js
    assert "auto_backup_before_execute" in js
    assert "Auto-Backup an · gilt auch bei God Mode" in js
    assert '"sichert …"' in js
    assert ".chip.backup.on" in css
