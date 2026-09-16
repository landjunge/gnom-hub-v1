"""Quiet desk Q8–Q10: one result chrome, German leftovers, compact row."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
TOKENS = (ROOT / "src/gnom_hub/ui/static/tokens.css").read_text(encoding="utf-8")
CORE = (ROOT / "src/gnom_hub/ui/static/parts/00-core.js").read_text(encoding="utf-8")
BOX = (ROOT / "src/gnom_hub/ui/static/parts/09-boxes.js").read_text(encoding="utf-8")
CHAT = (ROOT / "src/gnom_hub/ui/static/parts/08-chat-jobs.js").read_text(encoding="utf-8")
CSS_AGENTS = (ROOT / "src/gnom_hub/ui/static/css/01-agents.css").read_text(encoding="utf-8")


def test_q8_box3_tabs_only_when_several():
    fn = BOX.split("function renderBox3WorkerTabs", 1)[1].split("function ", 1)[0]
    assert "box3TabsWanted" in fn
    assert "tabs.hidden = true" in fn
    assert "box3-btn-prev" in BOX
    empty = CORE.split("function buildAgentLayers", 1)[1].split("function getAgentBoxBody", 1)[0]
    assert "Brainstorm dialogue" not in empty
    assert "Noch kein Ergebnis" in HTML


def test_q9_german_card_and_target_labels():
    assert 'label: "Koordinator"' in CORE
    assert 'label: "Arbeiter 1"' in CORE
    assert 'label: "Worker 1"' not in CORE
    assert ">Worker 1<" not in HTML
    assert ">Arbeiter 1<" in HTML
    assert "Worker-Seiten" not in HTML
    assert "sind Worker" not in CHAT
    assert "Arbeit starten = Arbeiter" in HTML
    assert "Arbeit läuft…" in CHAT
    assert "Executing…" not in CHAT
    assert "Vector list failed" not in (
        ROOT / "src/gnom_hub/ui/static/parts/05-system-ops.js"
    ).read_text(encoding="utf-8")
    assert "Pack loaded" not in CHAT
    assert "HOT fact added" not in CHAT
    assert "Brainstorm-Dialog" in CORE or "Gespräch" in CORE
    assert 'textContent = "Brain"' in CHAT or '"Brain"' in CHAT
    assert "Senden an" in CHAT
    assert "Vector store (lite)" not in HTML
    assert "Documentation search" not in HTML


def test_q10_compact_cards_and_no_operator_hint():
    assert "--card-h: clamp(44px" in TOKENS or "--card-h: clamp(40px" in TOKENS
    assert "kbd-hint" not in HTML.split('id="chat-mod"', 1)[1].split('id="box3"', 1)[0]
    assert "gap: 8px" in CSS_AGENTS.split(".agent-cards {", 1)[1].split("}", 1)[0]
