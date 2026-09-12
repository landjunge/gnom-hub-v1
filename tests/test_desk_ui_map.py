"""Desk UI map cells must match live index.html ids."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
MAP = (ROOT / "docs/DESK_UI_MAP.md").read_text(encoding="utf-8")
PROMPTS = (ROOT / "docs/AGENTS_PROMPTS.md").read_text(encoding="utf-8")


def test_desk_cells_exist_in_html():
    ids = (
        "box1",
        "box2",
        "box2-stack",
        "chat-mod",
        "box3",
        "agent-cards",
        "flex-ask",
        "flex-review",
        "box1-choice-cards",
        "btn-send",
        "btn-execute",
        "chat-input",
        "god-badge",
    )
    for i in ids:
        assert f'id="{i}"' in HTML
        assert f"#{i}" in MAP


def test_desk_map_has_grid_cells():
    for cell in ("Zelle A", "Zelle B", "Zelle C", "Zelle L", "Zelle M1", "Zelle M2", "Zelle R"):
        assert cell in MAP
    assert "Send" in MAP and "Execute" in MAP
    assert "#btn-send" in MAP
    assert "--c-flex" in MAP
    assert "Lila" in MAP


def test_agents_prompts_cover_eight_slots():
    for name in (
        "Brainstorm",
        "Memory",
        "Flex",
        "Coordinator",
        "Worker",
        "HUB_IDENTITY",
        "FLEX_ASK",
        "start_work",
    ):
        assert name in PROMPTS
    assert "maybe_request_execute" in PROMPTS
    assert "#f0c000" in PROMPTS
    assert "START-C1" in PROMPTS or "Auftrag C1" in PROMPTS
