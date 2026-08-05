"""WARM lite: durable facts (JSONL) that survive HOT session reset."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from gnom_hub.config.paths import project_root
from gnom_hub.memory.atomic import atomic_write_text


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class WarmMemory:
    """
    Long-lived facts under {root}/data/warm/facts.jsonl.

    KISS: append-only JSONL, last N facts for context, de-dupe exact lines.
    """

    def __init__(self, root: Path | None = None, *, max_facts: int = 200) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.warm_dir = self.root / "data" / "warm"
        self.facts_path = self.warm_dir / "facts.jsonl"
        self.max_facts = max_facts
        self._facts: list[str] = []
        self.load()

    def load(self) -> None:
        self._facts = []
        if not self.facts_path.is_file():
            return
        for line in self.facts_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # plain text line fallback
                self._facts.append(line)
                continue
            if isinstance(obj, dict) and obj.get("text"):
                self._facts.append(str(obj["text"]).strip())
            elif isinstance(obj, str):
                self._facts.append(obj.strip())
        self._facts = [f for f in self._facts if f]

    def save(self) -> None:
        self.warm_dir.mkdir(parents=True, exist_ok=True)
        # rewrite trimmed file (keeps last max_facts)
        lines = self._facts[-self.max_facts :]
        body = ""
        for text in lines:
            body += json.dumps({"text": text, "ts": _utc_now_iso()}, ensure_ascii=False) + "\n"
        atomic_write_text(self.facts_path, body)

    def add_fact(self, text: str) -> bool:
        t = " ".join(text.split()).strip()
        if not t:
            return False
        if t in self._facts:
            return False
        self._facts.append(t)
        if len(self._facts) > self.max_facts:
            self._facts = self._facts[-self.max_facts :]
        self.save()
        return True

    def recent_facts(self, limit: int = 12) -> list[str]:
        return list(self._facts[-limit:])

    def all_facts(self) -> list[str]:
        return list(self._facts)

    def clear(self) -> None:
        self._facts = []
        self.save()

    def pipeline_context(self, *, max_chars: int = 500) -> str:
        facts = self.recent_facts(8)
        if not facts:
            return ""
        lines = ["WARM facts (durable):"]
        for f in facts:
            lines.append(f"- {f[:120]}")
        text = "\n".join(lines)
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text
