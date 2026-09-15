"""R8: honest terminal install, key/TollGate visible, no fake one-click."""

from pathlib import Path

from fastapi.testclient import TestClient

from gnom_hub.api.app import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_install_sh_is_terminal_schnellinstallation():
    text = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
    assert "Terminal-Schnellinstallation" in text
    assert "kein Ein-Klick" in text
    assert "WS-gnom-hub-v1" in text
    assert "Bestehendes .venv bleibt unangetastet" in text


def test_get_sh_points_to_personal_ws_and_desk_verbs():
    text = (ROOT / "scripts/get.sh").read_text(encoding="utf-8")
    assert "WS-gnom-hub-v1/User/Key.txt" in text
    assert "kein Ein-Klick" in text
    assert "Arbeit starten" in text
    assert "Execute" not in text
    assert "Senden" in text


def test_health_exposes_setup():
    client = TestClient(create_app())
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    setup = body["setup"]
    assert setup["install"] == "terminal-schnellinstallation"
    assert "key_ok" in setup
    assert "tollgate_ok" in setup
    assert "personal_ws" in setup


def test_system_modal_shows_setup_line():
    html = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
    js = (ROOT / "src/gnom_hub/ui/static/parts/03-system.js").read_text(encoding="utf-8")
    assert 'id="system-setup"' in html
    assert "system-setup" in js
    assert "Key fehlt" in js
