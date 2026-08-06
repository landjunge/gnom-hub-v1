"""Personal WS = sibling of hub; selected HTML only; DB backup."""

from pathlib import Path

from gnom_hub.config.paths import personal_workspace, selected_dir, user_dir
from gnom_hub.config.user_workspace import (
    copy_selected_html,
    ensure_user_workspace,
    format_user_workspace_report,
    inspect_user_workspace,
)
from gnom_hub.memory.workspace import WorkspaceStore


def test_ensure_creates_user_key_and_db(tmp_path: Path):
    (tmp_path / "Key.txt.example").write_text(
        "DEEPSEEK_MODEL=deepseek-v4-flash\nDEEPSEEK_API_KEY=sk-your-system-deepseek-key\n",
        encoding="utf-8",
    )
    st = ensure_user_workspace(tmp_path)
    assert st.workspace_ok
    assert st.user_dir_ok
    # tmp roots: personal WS == hub root (isolated)
    assert personal_workspace(tmp_path) == tmp_path.resolve()
    assert (tmp_path / "User").is_dir()
    assert st.key_ok
    assert (tmp_path / "User" / "Key.txt").is_file()
    assert st.db_ok
    assert (tmp_path / "User" / "user.db").is_file()
    assert st.ready
    assert st.key_has_deepseek is False
    report = format_user_workspace_report(st)
    assert "selected" in report.lower()
    assert (tmp_path / "selected").is_dir()


def test_inspect_missing_user_dir(tmp_path: Path):
    st = inspect_user_workspace(tmp_path)
    assert not st.user_dir_ok
    assert not st.key_ok
    assert not st.db_ok
    assert not st.ready


def test_ensure_preserves_existing_key_and_db(tmp_path: Path):
    ud = tmp_path / "User"
    ud.mkdir()
    (ud / "Key.txt").write_text("DEEPSEEK_API_KEY=sk-real-abc123\n", encoding="utf-8")
    st1 = ensure_user_workspace(tmp_path)
    assert st1.key_has_deepseek is True
    assert st1.db_ok
    st2 = ensure_user_workspace(tmp_path)
    text = (ud / "Key.txt").read_text(encoding="utf-8")
    assert "sk-real-abc123" in text
    assert st2.key_has_deepseek is True
    assert st2.ready
    # backup mirror exists
    assert (tmp_path / "backups" / "user.db").is_file()


def test_legacy_root_key_seeded_into_user(tmp_path: Path):
    (tmp_path / "Key.txt").write_text("DEEPSEEK_API_KEY=sk-from-root\n", encoding="utf-8")
    st = ensure_user_workspace(tmp_path)
    assert (tmp_path / "User" / "Key.txt").is_file()
    assert "sk-from-root" in (tmp_path / "User" / "Key.txt").read_text(encoding="utf-8")
    assert st.key_has_deepseek is True


def test_only_selected_html_copies(tmp_path: Path):
    ws = WorkspaceStore(tmp_path)
    ws.write_text("temp", "page.html", "<html><body>keep me</body></html>")
    ws.write_text("temp", "noise.txt", "not html")
    dest = ws.copy_to_selected("page.html", zone="temp")
    assert dest.parent == selected_dir(tmp_path)
    assert dest.is_file()
    assert "keep me" in dest.read_text(encoding="utf-8")
    # noise never auto-copied
    assert not (selected_dir(tmp_path) / "noise.txt").exists()
    # second deliberate copy with same name gets stamped, still only HTML
    dest2 = copy_selected_html(tmp_path / "data" / "workspace" / "temp" / "page.html", tmp_path)
    assert dest2.suffix.lower() == ".html"
    assert len(list(selected_dir(tmp_path).glob("*.html"))) >= 1


def test_user_dir_under_personal_ws(tmp_path: Path):
    assert user_dir(tmp_path) == (tmp_path / "User").resolve()


def test_keep_html_content_to_selected(tmp_path: Path):
    ws = WorkspaceStore(tmp_path)
    html = "<!DOCTYPE html><html><body><h1>Mine</h1></body></html>"
    dest = ws.keep_html_content(html, "landing.html")
    assert dest.parent == selected_dir(tmp_path)
    assert "Mine" in dest.read_text(encoding="utf-8")
    # clear hub temp does not remove selected
    ws.write_text("temp", "junk.html", html)
    ws.clear_temp()
    assert dest.is_file()
