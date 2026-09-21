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
