"""R5.3: desk JS lives in domain parts; app.js is generated."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "src/gnom_hub/ui/static/parts"
APP = (ROOT / "src/gnom_hub/ui/static/app.js").read_text(encoding="utf-8")
EXPECTED = [
    "00-core.js",
    "01-core-api.js",
    "02-speech.js",
    "03-system.js",
    "04-tools.js",
    "05-system-ops.js",
    "06-workspace.js",
    "07-system-skills.js",
    "08-chat-jobs.js",
    "09-boxes.js",
    "10-core-init.js",
]


def test_domain_parts_exist_in_cascade_order():
    names = [p.name for p in sorted(PARTS.glob("*.js"))]
    assert names == EXPECTED


def test_app_js_is_generated_concat_of_parts():
    body = "".join((PARTS / name).read_text(encoding="utf-8") for name in EXPECTED)
    assert APP == body
    assert "edit parts, run scripts/build_ui_js.py" in APP.splitlines()[0]


def test_build_ui_js_check_matches_app_js():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_ui_js.py"), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_domain_file_ownership():
    assert "function toast(" in (PARTS / "00-core.js").read_text(encoding="utf-8")
    assert "async function api(" in (PARTS / "01-core-api.js").read_text(encoding="utf-8")
    assert "function stripForSpeech(" in (PARTS / "02-speech.js").read_text(encoding="utf-8")
    assert "async function openSystemModal(" in (PARTS / "03-system.js").read_text(encoding="utf-8")
    assert "async function openToolsModal(" in (PARTS / "04-tools.js").read_text(encoding="utf-8")
    assert "async function openUsageModal(" in (PARTS / "05-system-ops.js").read_text(
        encoding="utf-8"
    )
    assert "async function openWorkspaceModal(" in (PARTS / "06-workspace.js").read_text(
        encoding="utf-8"
    )
    assert "async function openSkillsModal(" in (PARTS / "07-system-skills.js").read_text(
        encoding="utf-8"
    )
    assert "async function sendChat(" in (PARTS / "08-chat-jobs.js").read_text(encoding="utf-8")
    assert "function renderBox2ReplyTabs(" in (PARTS / "09-boxes.js").read_text(encoding="utf-8")
    assert "function init(" in (PARTS / "10-core-init.js").read_text(encoding="utf-8")


def test_old_mixed_part_filenames_are_gone():
    names = {p.name for p in PARTS.glob("*.js")}
    assert "00-preamble.js" not in names
    assert "01-api-snapshot-tts.js" not in names
    assert "02-modals-tools-ws.js" not in names
    assert "03-chat-jobs-ops.js" not in names
    assert "05-init.js" not in names


def test_runtime_keeps_send_and_god_guards():
    chat = (PARTS / "08-chat-jobs.js").read_text(encoding="utf-8")
    core = (PARTS / "00-core.js").read_text(encoding="utf-8")
    assert "async function sendChat(" in chat
    assert "async function runExecute(" in chat
    assert "sendTarget" in core
    assert "async function toggleGodMode(" in chat
