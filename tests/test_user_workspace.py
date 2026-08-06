"""New-install bootstrap: User/ + Key.txt + user.db."""

from pathlib import Path

from gnom_hub.config.user_workspace import (
    ensure_user_workspace,
    format_user_workspace_report,
    inspect_user_workspace,
)


def test_ensure_creates_user_key_and_db(tmp_path: Path):
    (tmp_path / "Key.txt.example").write_text(
        "DEEPSEEK_MODEL=deepseek-v4-flash\nDEEPSEEK_API_KEY=sk-your-system-deepseek-key\n",
        encoding="utf-8",
    )
    st = ensure_user_workspace(tmp_path)
    assert st.workspace_ok
    assert st.user_dir_ok
    assert (tmp_path / "User").is_dir()
    assert st.key_ok
    assert (tmp_path / "User" / "Key.txt").is_file()
    assert st.db_ok
    assert (tmp_path / "User" / "user.db").is_file()
    assert st.ready
    # example placeholder is not a real key
    assert st.key_has_deepseek is False
    report = format_user_workspace_report(st)
    assert "User/" in report
    assert "sync" in report.lower()
    assert "Key.txt" in report
    assert st.sync_unit == "User/"
    assert st.on_usb is False  # tmp_path is local


def test_inspect_missing_user_dir(tmp_path: Path):
    st = inspect_user_workspace(tmp_path)
    assert st.workspace_ok
    assert not st.user_dir_ok
    assert not st.key_ok
    assert not st.db_ok
    assert not st.ready


def test_ensure_preserves_existing_key_and_db(tmp_path: Path):
    ud = tmp_path / "User"
    ud.mkdir()
    (ud / "Key.txt").write_text("DEEPSEEK_API_KEY=sk-real-abc123\n", encoding="utf-8")
    # first ensure creates db
    st1 = ensure_user_workspace(tmp_path)
    assert st1.key_has_deepseek is True
    assert st1.db_ok
    # second ensure does not wipe key
    st2 = ensure_user_workspace(tmp_path)
    text = (ud / "Key.txt").read_text(encoding="utf-8")
    assert "sk-real-abc123" in text
    assert st2.key_has_deepseek is True
    assert st2.ready


def test_legacy_root_key_seeded_into_user(tmp_path: Path):
    (tmp_path / "Key.txt").write_text("DEEPSEEK_API_KEY=sk-from-root\n", encoding="utf-8")
    st = ensure_user_workspace(tmp_path)
    assert (tmp_path / "User" / "Key.txt").is_file()
    assert "sk-from-root" in (tmp_path / "User" / "Key.txt").read_text(encoding="utf-8")
    assert st.key_has_deepseek is True
