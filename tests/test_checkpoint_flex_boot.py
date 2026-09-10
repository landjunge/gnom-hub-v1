"""Hub boot must restore Flex Box 1 from checkpoint.json without an explicit load."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest


def _hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.config import paths
    from gnom_hub.hub import Hub

    monkeypatch.delenv("GNOM_WS", raising=False)
    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    return Hub()


def test_hub_boot_restores_open_flex_questions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import gnom_hub.hub as hub_mod

    hub = _hub(tmp_path, monkeypatch)
    try:
        hub.pipeline.flex_desk.bind_job("job-boot")
        asked = hub.pipeline.flex_desk.ask(
            agent_id="worker1",
            job_id="job-boot",
            task_id="hero",
            text="Soll der Kopfbereich kürzer sein?",
        )
        hub.pipeline._sync_flex_state()
        saved = hub.save_checkpoint()
        assert saved.get("ok") is True
        assert hub._checkpoint_path.is_file()
        question_id = asked["question_id"]
    finally:
        hub_mod._HUB = None

    hub2 = _hub(tmp_path, monkeypatch)
    try:
        qs = hub2.pipeline.flex_desk.open_questions()
        assert len(qs) == 1
        assert qs[0].question_id == question_id
        assert qs[0].job_id == "job-boot"
        assert qs[0].agent_id == "worker1"
        assert "Kopfbereich" in qs[0].text
        box = hub2.snapshot()["flex_box1"]
        assert box["questions"][0]["question_id"] == question_id
        assert hub2.pipeline.state.flex_job_id == "job-boot"
    finally:
        hub_mod._HUB = None


def test_corrupt_checkpoint_does_not_crash_hub_boot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    import gnom_hub.hub as hub_mod

    ckpt = tmp_path / "data" / "hot" / "checkpoint.json"
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    ckpt.write_text("{not-json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        hub = _hub(tmp_path, monkeypatch)
    try:
        assert hub.pipeline.flex_desk.open_questions() == []
        assert any("checkpoint" in rec.message.lower() for rec in caplog.records)
    finally:
        hub_mod._HUB = None
