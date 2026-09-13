"""R4.8: Mikrofon latch, no auto-send; 20px square; Sprache checkbox."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
CHAT_JS = (ROOT / "src/gnom_hub/ui/static/parts/03-chat-jobs-ops.js").read_text(encoding="utf-8")
PRE_JS = (ROOT / "src/gnom_hub/ui/static/parts/00-preamble.js").read_text(encoding="utf-8")
CSS = (ROOT / "src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")


def test_mic_button_square_white_no_tailwind_round():
    open_tag = HTML.split('id="btn-mic"', 1)[1].split(">", 1)[0]
    assert "rounded-md" not in open_tag
    assert "h-8" not in open_tag
    assert ">Mikrofon<" in HTML
    mic = CSS.split(".btn-mic {", 1)[1].split("}", 1)[0]
    assert "border-radius: 0" in mic
    assert "color: #fff" in mic
    assert "height: var(--btn-h)" in mic


def test_mic_does_not_auto_send():
    body = CHAT_JS.split("function toggleMic", 1)[1].split("async function _cycleFlexPreset", 1)[0]
    assert "recognition.continuous = true" in body
    assert "chatInput.value" in body
    assert "sendChat" not in body
    assert "sendMessage" not in body
    assert "/api/chat" not in body
    assert "/api/execute" not in body


def test_mic_latch_and_german_errors():
    assert "Mikrofon aus" in CHAT_JS
    assert "keine Berechtigung" in CHAT_JS
    assert "kein Mikrofon" in CHAT_JS


def test_card_tts_label_is_sprache():
    assert "/> Sprache</label>" in PRE_JS
    assert "/> TTS</label>" not in PRE_JS
    assert "Sprache an:" in PRE_JS
