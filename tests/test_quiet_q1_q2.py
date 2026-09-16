"""Q1 one Box 1 question. Q2 quiet header: name, version, LLM, God."""

from pathlib import Path

from gnom_hub.core.event_bus import EventBus
from gnom_hub.flex_desk import FlexDesk
from gnom_hub.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
JS_PARTS = "".join(
    (ROOT / "src/gnom_hub/ui/static/parts" / n).read_text(encoding="utf-8")
    for n in ("01-core-api.js", "02-speech.js", "10-core-init.js")
)


def test_header_is_name_llm_god_only():
    head = HTML.split('class="top-meta top-meta-badges"', 1)[1].split("</div>", 1)[0]
    assert 'id="llm-badge"' in head
    assert 'id="god-badge"' in head
    for noisy in (
        "cost-badge",
        "mem-badge",
        "vec-badge",
        "cold-badge",
        "docs-badge",
        "skills-badge",
        "tools-badge",
        "stage-badge",
    ):
        assert noisy not in head
    title = HTML.split('class="app-title"', 1)[1].split("</h1>", 1)[0]
    assert "Gnom-Hub-V1" in title
    system = HTML.split('id="system-modal"', 1)[1]
    assert 'id="cost-badge"' in system
    assert 'id="stage-badge"' in system


def test_desk_js_uses_quiet_llm_and_hides_review():
    assert 'document.title = "Gnom-Hub-V1 v"' in JS_PARTS
    assert "LLM: bereit" in JS_PARTS
    assert "LLM: fehlt" in JS_PARTS
    assert "LLM: key placeholder" not in JS_PARTS
    assert "review.hidden = true" in JS_PARTS
    assert "askVisible" in JS_PARTS


def test_snapshot_shows_only_judgment_when_repairs_exist():
    desk = FlexDesk(job_id="job-a")
    desk.ask(
        agent_id="worker1",
        text="Etwas fehlt: dunkles Erscheinungsbild. Soll ich nachbessern lassen?",
        task_id="nachbesserung",
        component="yes_no",
    )
    desk.ask(
        agent_id="worker2",
        text="Etwas fehlt: Fußzeile. Soll ich nachbessern lassen?",
        task_id="nachbesserung",
        component="yes_no",
    )
    desk.offer_judgment()
    opened = desk.open_questions()
    assert len(opened) == 1
    assert opened[0].component == "judgment"
    assert opened[0].text == "Passt das?"
    assert len(desk.queued_questions()) == 2
    snap = desk.snapshot()
    assert len(snap["questions"]) == 1
    assert snap["questions"][0]["text"] == "Passt das?"
    assert snap["queued_n"] == 2


def test_key_missing_beats_judgment():
    desk = FlexDesk(job_id="job-b")
    desk.offer_judgment()
    desk.ask(
        agent_id="flex",
        task_id="key_missing",
        component="yes_no",
        text="Key fehlt. In System einen echten Schlüssel eintragen, dann Arbeit starten.",
        options=["Verstanden"],
        entry_type="blockiert",
    )
    vis = desk.visible_question()
    assert vis is not None
    assert vis.task_id == "key_missing"
    assert len(desk.open_questions()) == 1
    assert any(q.component == "judgment" for q in desk.queued_questions())


def test_answering_promotes_queued_question():
    desk = FlexDesk(job_id="job-c")
    first = desk.ask(
        agent_id="flex",
        text="Erste Frage?",
        task_id="one",
        component="yes_no",
    )
    desk.ask(
        agent_id="flex",
        text="Zweite Frage?",
        task_id="two",
        component="yes_no",
    )
    assert desk.visible_question().question_id == first["question_id"]
    desk.answer(first["question_id"], "Ja")
    vis = desk.visible_question()
    assert vis is not None
    assert vis.task_id == "two"
    assert vis.status == "open"


def test_execute_without_key_asks_once_not_four_repairs():
    pipe = Pipeline(EventBus())
    pipe.brainstorm_turn("Nur ein Gespräch. Keine Datei.")
    pipe.execute()
    opened = pipe.flex_desk.open_questions()
    assert len(opened) == 1
    vis = opened[0]
    assert vis.task_id == "key_missing" or vis.component == "judgment"
    if vis.task_id == "key_missing":
        assert "Key fehlt" in vis.text
    nach = [q for q in pipe.flex_desk.queued_questions() if q.task_id == "nachbesserung"]
    assert len(nach) <= 1
    snap = pipe.flex_desk.snapshot()
    assert len(snap["questions"]) == 1
