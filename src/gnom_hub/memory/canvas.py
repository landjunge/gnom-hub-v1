"""Simple Mermaid flowchart canvas (HOT symbolic short-term memory)."""

from __future__ import annotations

import re
from pathlib import Path

from gnom_hub.memory.atomic import atomic_write_text

_NODE_RE = re.compile(r'^(\w+)\["((?:\\.|[^"\\])*)"\]\s*$')


def _escape_label(label: str) -> str:
    return label.replace("\\", "\\\\").replace('"', "#quot;")


def _unescape_label(label: str) -> str:
    return label.replace("#quot;", '"').replace("\\\\", "\\")


class MermaidCanvas:
    """In-memory node list; persists as a simple mermaid flowchart .mmd file."""

    def __init__(self) -> None:
        self.nodes: list[dict[str, str | None]] = []

    def add_node(self, label: str, detail: str | None = None) -> str:
        node_id = f"n{len(self.nodes) + 1}"
        self.nodes.append({"id": node_id, "label": label, "detail": detail})
        return node_id

    def to_mermaid(self) -> str:
        lines = ["flowchart TD"]
        if not self.nodes:
            return "\n".join(lines) + "\n"
        for node in self.nodes:
            nid = node["id"]
            label = _escape_label(str(node["label"]))
            lines.append(f'  {nid}["{label}"]')
        for i in range(len(self.nodes) - 1):
            a = self.nodes[i]["id"]
            b = self.nodes[i + 1]["id"]
            lines.append(f"  {a} --> {b}")
        return "\n".join(lines) + "\n"

    def save(self, path: Path | str) -> None:
        atomic_write_text(Path(path), self.to_mermaid())

    def load(self, path: Path | str) -> None:
        path = Path(path)
        if not path.is_file():
            self.nodes = []
            return
        text = path.read_text(encoding="utf-8")
        loaded: list[dict[str, str | None]] = []
        for line in text.splitlines():
            line = line.strip()
            m = _NODE_RE.match(line)
            if not m:
                continue
            loaded.append(
                {
                    "id": m.group(1),
                    "label": _unescape_label(m.group(2)),
                    "detail": None,
                }
            )
        self.nodes = loaded

    def clear(self) -> None:
        self.nodes = []
