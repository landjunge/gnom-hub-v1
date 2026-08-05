"""HOT memory: session.json + mermaid_canvas.mmd + node_id offload."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gnom_hub.config.paths import project_root
from gnom_hub.memory.atomic import atomic_write_text
from gnom_hub.memory.canvas import MermaidCanvas
from gnom_hub.memory.offload import DEFAULT_THRESHOLD, offload, recall


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _short_label(text: str, max_len: int = 48) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1] + "…"


class HotMemory:
    """Session HOT layer under {root}/data/hot/ (+ offload under data/offload/)."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        offload_threshold: int = DEFAULT_THRESHOLD,
        auto_load: bool = True,
    ) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.offload_threshold = offload_threshold
        self.hot_dir = self.root / "data" / "hot"
        self.offload_dir = self.root / "data" / "offload"
        self.session_path = self.hot_dir / "session.json"
        self.canvas_path = self.hot_dir / "mermaid_canvas.mmd"
        self.session: dict[str, Any] = self._empty_session()
        self.canvas = MermaidCanvas()
        if auto_load:
            self.load()

    @staticmethod
    def _empty_session() -> dict[str, Any]:
        return {
            "messages": [],
            "facts": [],
            "updated_at": _utc_now_iso(),
        }

    def _touch(self) -> None:
        self.session["updated_at"] = _utc_now_iso()

    def _store_text(self, text: str, label_prefix: str) -> str:
        """Store text as-is or offload + canvas node when long."""
        if len(text) <= self.offload_threshold:
            return text
        label = f"{label_prefix}: {_short_label(text)}"
        node_id = self.canvas.add_node(label)
        return offload(text, node_id, self.offload_dir, threshold=self.offload_threshold)

    def add_message(self, role: str, content: str) -> None:
        stored = self._store_text(content, role)
        self.session["messages"].append({"role": role, "content": stored})
        self._touch()

    def add_fact(self, text: str) -> bool:
        t = " ".join(str(text).split()).strip()
        if not t:
            return False
        facts = list(self.session.get("facts") or [])
        # de-dupe exact stored text after short-path store
        stored = self._store_text(t, "fact")
        if stored in facts:
            return False
        facts.append(stored)
        self.session["facts"] = facts
        self._touch()
        return True

    def all_facts(self) -> list[str]:
        out: list[str] = []
        for f in self.session.get("facts") or []:
            if isinstance(f, str) and f.strip():
                out.append(f.strip())
        return out

    def remove_fact(self, text: str) -> bool:
        t = " ".join(str(text).split()).strip()
        if not t:
            return False
        facts = list(self.session.get("facts") or [])
        if t not in facts:
            return False
        self.session["facts"] = [f for f in facts if f != t]
        self._touch()
        return True

    def remove_fact_at(self, index: int) -> str | None:
        """1-based index into all_facts order."""
        facts = list(self.session.get("facts") or [])
        if index < 1 or index > len(facts):
            return None
        removed = facts.pop(index - 1)
        self.session["facts"] = facts
        self._touch()
        return str(removed)

    def clear_facts(self) -> int:
        n = len(self.session.get("facts") or [])
        self.session["facts"] = []
        self._touch()
        return n

    def save(self) -> None:
        self.hot_dir.mkdir(parents=True, exist_ok=True)
        self._touch()
        payload = json.dumps(self.session, ensure_ascii=False, indent=2) + "\n"
        atomic_write_text(self.session_path, payload)
        self.canvas.save(self.canvas_path)

    def load(self) -> None:
        if self.session_path.is_file():
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
            self.session = {
                "messages": list(data.get("messages") or []),
                "facts": list(data.get("facts") or []),
                "updated_at": data.get("updated_at") or _utc_now_iso(),
            }
        else:
            self.session = self._empty_session()
        self.canvas.load(self.canvas_path)

    def recall(self, node_id: str) -> str:
        return recall(node_id, self.offload_dir)

    def clear(self, *, save: bool = True) -> None:
        """Wipe HOT session + canvas (offload files left for safety)."""
        self.session = self._empty_session()
        self.canvas.clear()
        if save:
            self.save()

    def compress_if_needed(
        self,
        *,
        max_facts: int = 24,
        max_messages: int = 40,
    ) -> dict[str, int]:
        """
        Context compression for long sessions (plan §8.4).
        Collapses old facts/messages into one summary fact; keeps recent tail.
        """
        facts = list(self.session.get("facts") or [])
        msgs = list(self.session.get("messages") or [])
        removed_facts = 0
        removed_msgs = 0
        if len(facts) > max_facts:
            old = facts[: -max_facts // 2]
            keep = facts[-max_facts // 2 :]
            summary = "Compressed older facts: " + " | ".join(
                _short_label(str(f), 60) for f in old[:12]
            )
            self.session["facts"] = [summary[:200], *keep]
            removed_facts = len(old)
        if len(msgs) > max_messages:
            old_m = msgs[: -max_messages // 2]
            keep_m = msgs[-max_messages // 2 :]
            roles = [str(m.get("role") or "?") for m in old_m if isinstance(m, dict)]
            summary_msg = {
                "role": "system",
                "content": (f"[compressed {len(old_m)} messages: " + ",".join(roles[-8:]) + "]"),
            }
            self.session["messages"] = [summary_msg, *keep_m]
            removed_msgs = len(old_m)
        if removed_facts or removed_msgs:
            self._touch()
            self.save()
        return {"facts_collapsed": removed_facts, "messages_collapsed": removed_msgs}

    def get_context_summary(self) -> str:
        """Short string for the pipeline (not full session dump)."""
        msgs = self.session.get("messages") or []
        facts = self.session.get("facts") or []
        n_nodes = len(self.canvas.nodes)
        last_roles = [m.get("role", "?") for m in msgs[-3:]]
        parts = [
            f"messages={len(msgs)}",
            f"facts={len(facts)}",
            f"canvas_nodes={n_nodes}",
        ]
        if last_roles:
            parts.append("last=" + ",".join(last_roles))
        if facts:
            preview = facts[-1]
            if isinstance(preview, str):
                parts.append("fact=" + _short_label(preview, 40))
        return "HOT: " + " | ".join(parts)

    def recent_facts(self, limit: int = 8) -> list[str]:
        facts = self.session.get("facts") or []
        out: list[str] = []
        for f in facts[-limit:]:
            if isinstance(f, str) and f.strip():
                out.append(f.strip())
        return out

    def recent_messages(self, limit: int = 4) -> list[dict[str, str]]:
        msgs = self.session.get("messages") or []
        out: list[dict[str, str]] = []
        for m in msgs[-limit:]:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "?")
            content = str(m.get("content") or "")
            if content:
                out.append({"role": role, "content": _short_label(content, 120)})
        return out

    def pipeline_context(
        self,
        *,
        max_chars: int = 900,
        warm_facts: list[str] | None = None,
    ) -> str:
        """
        Compact context for LLM/stub stages (Memory always on).
        Optional warm_facts (durable) first, then HOT facts, messages, canvas.
        """
        chunks: list[str] = []
        if warm_facts:
            chunks.append("WARM facts (durable):")
            for f in warm_facts[:8]:
                chunks.append(f"- {_short_label(f, 100)}")
        facts = self.recent_facts(6)
        if facts:
            chunks.append("HOT facts (session):")
            for f in facts:
                chunks.append(f"- {_short_label(f, 100)}")
        msgs = self.recent_messages(3)
        if msgs:
            chunks.append("Recent:")
            for m in msgs:
                chunks.append(f"- {m['role']}: {m['content']}")
        if self.canvas.nodes:
            labels = [str(n.get("label") or n.get("id") or "") for n in self.canvas.nodes[-5:]]
            labels = [x for x in labels if x]
            if labels:
                chunks.append("Canvas: " + " → ".join(_short_label(x, 40) for x in labels))
        text = "\n".join(chunks).strip()
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text
