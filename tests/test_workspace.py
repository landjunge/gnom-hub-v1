from pathlib import Path

from gnom_hub.memory.workspace import WorkspaceStore


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
