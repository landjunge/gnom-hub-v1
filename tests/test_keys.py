from pathlib import Path

from gnom_hub.config.keys import (
    ensure_env_from_key_txt,
    load_keys,
    parse_key_file,
)


def test_parse_key_file_basic():
    text = """
# comment
DEEPSEEK_API_KEY=sk-abc
deepseek = sk-alias
export OPENAI_API_KEY="sk-quoted"
"""
    keys = parse_key_file(text)
    assert keys["DEEPSEEK_API_KEY"] in ("sk-abc", "sk-alias")
    assert keys["OPENAI_API_KEY"] == "sk-quoted"


def test_parse_colon_form():
    keys = parse_key_file("DeepSeek: sk-xyz\n")
    assert keys["DEEPSEEK_API_KEY"] == "sk-xyz"


def test_ensure_env_from_key_txt(tmp_path: Path):
    ud = tmp_path / "User"
    ud.mkdir()
    (ud / "Key.txt").write_text("DEEPSEEK_API_KEY=sk-test-1\n", encoding="utf-8")
    env_path = ensure_env_from_key_txt(tmp_path)
    assert env_path is not None
    assert env_path.is_file()
    assert "sk-test-1" in env_path.read_text(encoding="utf-8")


def test_ensure_env_key_txt_wins_for_hub_keys(tmp_path: Path):
    ud = tmp_path / "User"
    ud.mkdir()
    (ud / "Key.txt").write_text("DEEPSEEK_API_KEY=from-key\n", encoding="utf-8")
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=from-env\n", encoding="utf-8")
    ensure_env_from_key_txt(tmp_path)
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "from-key" in text
    assert "from-env" not in text


def test_ensure_env_merges_missing_keys(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OTHER_API_KEY", raising=False)
    ud = tmp_path / "User"
    ud.mkdir()
    (ud / "Key.txt").write_text(
        "DEEPSEEK_API_KEY=sk-ds\nOTHER_API_KEY=sk-other\n", encoding="utf-8"
    )
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=keep-me\n", encoding="utf-8")
    ensure_env_from_key_txt(tmp_path)
    loaded = load_keys(tmp_path, apply_environ=False)
    assert loaded["DEEPSEEK_API_KEY"] == "sk-ds"
    assert loaded["OTHER_API_KEY"] == "sk-other"


def test_load_keys_from_env_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=sk-file\n", encoding="utf-8")
    keys = load_keys(tmp_path, apply_environ=False)
    assert keys["DEEPSEEK_API_KEY"] == "sk-file"
