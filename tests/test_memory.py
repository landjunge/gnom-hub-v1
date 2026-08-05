from pathlib import Path

from gnom_hub.memory import HotMemory, MermaidCanvas
from gnom_hub.memory.atomic import atomic_write_text
from gnom_hub.memory.offload import is_offload_stub, offload, recall, stub_node_id


def test_atomic_write_text(tmp_path: Path):
    target = tmp_path / "sub" / "file.txt"
    atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"
    atomic_write_text(target, "world\n")
    assert target.read_text(encoding="utf-8") == "world\n"


def test_offload_short_returns_text(tmp_path: Path):
    out = offload("short", "n1", tmp_path / "offload", threshold=100)
    assert out == "short"
    assert not (tmp_path / "offload" / "n1.txt").exists()


def test_offload_long_writes_and_stub(tmp_path: Path):
    body = "x" * 50
    off_dir = tmp_path / "offload"
    stub = offload(body, "n7", off_dir, threshold=10)
    assert is_offload_stub(stub)
    assert stub_node_id(stub) == "n7"
    assert recall("n7", off_dir) == body


def test_mermaid_canvas_add_and_to_mermaid():
    c = MermaidCanvas()
    a = c.add_node("first")
    b = c.add_node("second")
    assert a == "n1"
    assert b == "n2"
    mmd = c.to_mermaid()
    assert "flowchart TD" in mmd
    assert 'n1["first"]' in mmd
    assert 'n2["second"]' in mmd
    assert "n1 --> n2" in mmd


def test_mermaid_canvas_save_load(tmp_path: Path):
    path = tmp_path / "canvas.mmd"
    c = MermaidCanvas()
    c.add_node("alpha")
    c.add_node('quote"y')
    c.save(path)
    assert path.is_file()

    c2 = MermaidCanvas()
    c2.load(path)
    assert len(c2.nodes) == 2
    assert c2.nodes[0]["id"] == "n1"
    assert c2.nodes[0]["label"] == "alpha"
    assert c2.nodes[1]["label"] == 'quote"y'


def test_hot_memory_session_roundtrip(tmp_path: Path):
    mem = HotMemory(tmp_path, auto_load=False)
    mem.add_message("user", "hi")
    mem.add_message("assistant", "hello")
    mem.add_fact("sky is blue")
    mem.save()

    assert mem.session_path.is_file()
    assert mem.canvas_path.is_file()

    mem2 = HotMemory(tmp_path)
    assert len(mem2.session["messages"]) == 2
    assert mem2.session["messages"][0]["content"] == "hi"
    assert mem2.session["facts"] == ["sky is blue"]
    assert "updated_at" in mem2.session


def test_hot_memory_offload_on_long_content(tmp_path: Path):
    mem = HotMemory(tmp_path, offload_threshold=20, auto_load=False)
    long = "L" * 100
    mem.add_message("user", long)
    mem.add_fact("F" * 50)
    mem.save()

    msg = mem.session["messages"][0]["content"]
    fact = mem.session["facts"][0]
    assert is_offload_stub(msg)
    assert is_offload_stub(fact)
    nid = stub_node_id(msg)
    assert nid is not None
    assert mem.recall(nid) == long
    assert (tmp_path / "data" / "offload" / f"{nid}.txt").is_file()
    assert len(mem.canvas.nodes) == 2

    mem2 = HotMemory(tmp_path, offload_threshold=20)
    assert is_offload_stub(mem2.session["messages"][0]["content"])
    assert len(mem2.canvas.nodes) == 2


def test_get_context_summary(tmp_path: Path):
    mem = HotMemory(tmp_path, auto_load=False)
    mem.add_message("user", "a")
    mem.add_message("assistant", "b")
    mem.add_fact("note")
    s = mem.get_context_summary()
    assert s.startswith("HOT:")
    assert "messages=2" in s
    assert "facts=1" in s
    assert "canvas_nodes=0" in s


def test_pipeline_context_includes_facts(tmp_path: Path):
    mem = HotMemory(tmp_path, auto_load=False)
    mem.add_fact("Prefer dark theme")
    mem.add_message("user", "build a site")
    ctx = mem.pipeline_context()
    assert "Prefer dark theme" in ctx
    assert "HOT facts" in ctx
