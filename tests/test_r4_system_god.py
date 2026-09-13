"""R4.7: System modal German; God only via red badge."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
SYS_JS = (ROOT / "src/gnom_hub/ui/static/parts/02-modals-tools-ws.js").read_text(encoding="utf-8")
CHAT_JS = (ROOT / "src/gnom_hub/ui/static/parts/03-chat-jobs-ops.js").read_text(encoding="utf-8")
SNAP_JS = (ROOT / "src/gnom_hub/ui/static/parts/01-api-snapshot-tts.js").read_text(encoding="utf-8")
CSS = (ROOT / "src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")
INIT_JS = (ROOT / "src/gnom_hub/ui/static/parts/05-init.js").read_text(encoding="utf-8")


def _system_html() -> str:
    return HTML.split('id="system-modal"', 1)[1].split('id="vector-modal"', 1)[0]


def test_system_modal_has_no_god_switch():
    chunk = _system_html()
    assert "god-badge" not in chunk
    assert "/api/god-mode" not in chunk
    assert "God einschalten" not in chunk


def test_god_toggle_only_on_badge():
    assert "toggleGodMode" in INIT_JS
    assert 'els.godBadge.addEventListener("click", toggleGodMode)' in INIT_JS
    assert "/api/god-mode" in CHAT_JS
    assert "/api/god-mode" not in SYS_JS


def test_god_badge_german_and_red_on():
    assert "God: aus" in HTML
    assert "God: an" in SNAP_JS
    assert "God: aus" in SNAP_JS
    assert "God-Mode ON" not in CHAT_JS
    assert "Enable God-Mode" not in CHAT_JS
    on = CSS.split(".god-badge.on {", 1)[1].split("}", 1)[0]
    assert "#c62828" in on or "#3b1111" in on


def test_system_toasts_german():
    assert "System übernommen" in SYS_JS
    assert "System settings applied" not in SYS_JS
    assert "System load failed" not in SYS_JS
    assert "DeepSeek: an" in SYS_JS
    assert "Checkpoint gespeichert" in SYS_JS
    assert "Preset wählen" in SYS_JS
