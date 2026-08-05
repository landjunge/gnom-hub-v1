from pathlib import Path

from gnom_hub.memory.workspace import WorkspaceStore


def test_workspace_read_delete_clear(tmp_path: Path):
    from gnom_hub.memory.workspace import WorkspaceStore

    ws = WorkspaceStore(tmp_path)
    ws.write_text("temp", "a.txt", "hello")
    assert ws.read_text("temp", "a.txt") == "hello"
    assert ws.delete("temp", "a.txt") is True
    ws.write_text("temp", "b.txt", "x")
    assert ws.clear_temp() == 1


def test_workspace_write_promote(tmp_path: Path):
    ws = WorkspaceStore(tmp_path)
    ws.write_text("temp", "note.txt", "hello")
    assert any(f["name"] == "note.txt" for f in ws.list_files("temp"))
    ws.promote("note.txt")
    assert any(f["name"] == "note.txt" for f in ws.list_files("perm"))
    n = ws.clear_temp()
    assert n >= 1
    assert ws.list_files("temp") == []
    assert any(f["name"] == "note.txt" for f in ws.list_files("perm"))
