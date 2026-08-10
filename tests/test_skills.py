"""Playbook skills loader + match + install."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.skills.inject import skills_prompt_block
from gnom_hub.skills.loader import SkillLoader


def test_load_bundled_skills():
    root = Path(__file__).resolve().parents[1]
    loader = SkillLoader([root / "skills"])
    skills = loader.discover_and_load()
    ids = {s.id for s in skills}
    assert "html_landing" in ids
    assert "tool_honesty" in ids
    assert "de_desk" in ids
    assert all(s.body for s in skills)


def test_match_html_trigger():
    root = Path(__file__).resolve().parents[1]
    loader = SkillLoader([root / "skills"])
    loader.discover_and_load()
    matched = loader.match(
        agent="worker1",
        plan_mode="full_page_html",
        task_kind="html_page",
        text="Landingpage Gnom-Hub",
        limit=5,
    )
    ids = {s.id for s in matched}
    assert "html_landing" in ids
    block = skills_prompt_block(matched)
    assert "html_landing" in block or "Single-file" in block
    assert "playbooks" in block.lower() or "Skill:" in block


def test_disable_skill():
    root = Path(__file__).resolve().parents[1]
    loader = SkillLoader([root / "skills"])
    loader.discover_and_load()
    out = loader.set_enabled("html_landing", False)
    assert out["ok"] is True
    matched = loader.match(plan_mode="full_page_html", text="landing page", limit=5)
    assert all(s.id != "html_landing" for s in matched)
    loader.set_enabled("html_landing", True)


def test_install_rejects_python(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    loader = SkillLoader([root / "skills", tmp_path / "user"])
    loader.discover_and_load()
    bad = tmp_path / "evil"
    bad.mkdir()
    (bad / "skill.md").write_text("---\nid: evil\nname: Evil\n---\nnope\n", encoding="utf-8")
    (bad / "main.py").write_text("print('x')\n", encoding="utf-8")
    out = loader.install_from_path(bad, dest_root=tmp_path / "user")
    assert out["ok"] is False
    assert "Python" in out["error"]


def test_install_ok(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    user = tmp_path / "user"
    loader = SkillLoader([root / "skills", user])
    loader.discover_and_load()
    pack = tmp_path / "my_skill"
    pack.mkdir()
    (pack / "skill.md").write_text(
        "---\nid: my_skill\nname: My Skill\nenabled: true\n"
        "tags: [demo]\ntriggers: [demo]\n---\n# Hello\n",
        encoding="utf-8",
    )
    out = loader.install_from_path(pack, dest_root=user)
    assert out["ok"] is True
    assert loader.get("my_skill") is not None


def test_api_skills(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import gnom_hub.hub as hub_mod
    from gnom_hub.api.app import create_app

    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    # copy minimal skills into tmp project root
    skills_src = Path(__file__).resolve().parents[1] / "skills"
    dest = tmp_path / "skills"
    if skills_src.is_dir():
        import shutil

        shutil.copytree(skills_src, dest)
    (tmp_path / "docs").mkdir(exist_ok=True)
    cat = Path(__file__).resolve().parents[1] / "docs" / "skills_catalog.json"
    if cat.is_file():
        (tmp_path / "docs" / "skills_catalog.json").write_text(
            cat.read_text(encoding="utf-8"), encoding="utf-8"
        )
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/api/skills")
        assert r.status_code == 200
        body = r.json()
        assert "skills" in body
        # may be empty if hub roots differ — at least shape ok
        r2 = c.post("/api/skills/reload")
        assert r2.status_code == 200
    hub_mod._HUB = None
