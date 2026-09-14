"""R5.5: pipeline domains as mixins; orchestrator re-exports stay."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "src/gnom_hub/pipeline"
EXPECTED = [
    "brainstorm.py",
    "constants.py",
    "dispatch.py",
    "distill.py",
    "flex.py",
    "helpers.py",
    "persist.py",
    "plan.py",
    "worker.py",
]


def test_domain_files_exist():
    names = {p.name for p in PIPE.glob("*.py")}
    for n in EXPECTED:
        assert n in names, n


def test_orchestrator_reexports_and_send_guard():
    from gnom_hub.pipeline.orchestrator import (
        ALLOWED_SEND_TARGETS,
        Orchestrator,
        Pipeline,
        PipelineCancelled,
        _validate_worker_draft,
    )

    assert Pipeline is Orchestrator
    assert "brainstorm" in ALLOWED_SEND_TARGETS
    assert issubclass(PipelineCancelled, Exception)
    assert "ok" in _validate_worker_draft("<html>x", user_text="html landing", task="t")
    src = (PIPE / "brainstorm.py").read_text(encoding="utf-8")
    assert "Never starts Execute" in src or "never starts Execute" in src
    assert "def chat_turn" in src
    assert "def execute" in (PIPE / "dispatch.py").read_text(encoding="utf-8")


def test_orchestrator_class_is_thin_core():
    text = (PIPE / "orchestrator.py").read_text(encoding="utf-8")
    assert "class Orchestrator(" in text
    assert "BrainstormMixin" in text
    assert "def brainstorm_turn" not in text
    assert "def execute" not in text
    assert "def _finish" not in text
