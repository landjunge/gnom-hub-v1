"""No workshop stub as Brainstorm or worker deliverable."""

from gnom_hub.agents.roles_helpers import _stub_brainstorm
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.pipeline import Pipeline


def test_brainstorm_stub_is_honest_missing_model():
    text = _stub_brainstorm("mach mir eine landing page", [])
    low = text.lower()
    assert "ziel in einem satz" not in low
    assert "kernfunktionen" not in low
    assert "mvp" not in low
    assert "key" in low or "modell" in low


def test_pipeline_without_llm_does_not_deliver_stub_work():
    pipe = Pipeline(EventBus())
    state = pipe.start("Baue eine HTML-Seite")
    blob = " ".join(
        [
            state.error or "",
            state.brainstorm_notes or "",
            " ".join(state.distilled_requirements or []),
            " ".join(state.worker_results or []),
        ]
    )
    assert "Stub-Modus" not in blob
    assert "MVP mit 3" not in blob
    assert "Ziel in einem Satz" not in blob
    assert "Kein Modell" in blob or "FEHLER" in blob or "Key" in blob
