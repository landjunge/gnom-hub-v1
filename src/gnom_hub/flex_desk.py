"""Flex Box 1 desk: questions and answers. No execute / god / success authority."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

ALLOWED_COMPONENTS = frozenset(
    {
        "text",
        "yes_no",
        "later",
        "single_select",
        "multi_select",
        "free_text",
        "start_work",
    }
)
ALLOWED_AGENTS = frozenset({"coordinator", "flex", "worker1", "worker2", "worker3", "worker4"})
_START_YES = frozenset(
    {
        "ja",
        "yes",
        "y",
        "ok",
        "start",
        "arbeit starten",
        "ja, arbeit starten",
        "ja arbeit starten",
    }
)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"(?is)<script[^>]*>.*?</script>")
_JS_RE = re.compile(r"(?i)javascript:|onerror\s*=|onload\s*=|onclick\s*=")


def sanitize_box1_text(raw: str, *, limit: int = 400) -> str:
    """Plain German-ready text. Never keep markup or event handlers."""
    s = str(raw or "")
    s = _SCRIPT_RE.sub(" ", s)
    s = _JS_RE.sub(" ", s)
    s = _TAG_RE.sub(" ", s)
    s = s.replace("&lt;", " ").replace("&gt;", " ").replace("&quot;", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@dataclass
class FlexQuestion:
    question_id: str
    job_id: str
    task_id: str
    agent_id: str
    component: str
    text: str
    options: list[str] = field(default_factory=list)
    status: str = "open"
    answer: Any = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


class FlexDesk:
    """Mediator for Box 1. Communication only — no authority."""

    def __init__(self, *, job_id: str = "") -> None:
        self.job_id = (job_id or "").strip()
        self._questions: dict[str, FlexQuestion] = {}

    def bind_job(self, job_id: str, *, reset: bool = False) -> str:
        jid = (job_id or "").strip()
        if not jid:
            return self.job_id
        if reset or not self.job_id:
            if reset and self.job_id and self.job_id != jid:
                for q in self._questions.values():
                    if q.status == "open":
                        q.status = "stale"
            self.job_id = jid
        return self.job_id

    def ask(
        self,
        *,
        agent_id: str,
        text: str,
        job_id: str = "",
        task_id: str = "",
        component: str = "yes_no",
        options: list[str] | None = None,
    ) -> dict[str, Any]:
        aid = str(agent_id or "").strip().lower()
        if aid not in ALLOWED_AGENTS:
            return {"ok": False, "error": "unknown_agent"}
        jid = (job_id or self.job_id or _new_id("job")).strip()
        self.bind_job(jid)
        tid = (task_id or "task").strip() or "task"
        comp = str(component or "text").strip().lower()
        if comp not in ALLOWED_COMPONENTS:
            comp = "text"
        clean = sanitize_box1_text(text)
        if not clean:
            return {"ok": False, "error": "empty_text"}
        opts = [sanitize_box1_text(o, limit=80) for o in (options or []) if str(o).strip()]
        opts = [o for o in opts if o]
        if comp == "start_work" and not opts:
            opts = ["Ja, Arbeit starten", "Später"]
        if comp == "yes_no" and not opts:
            opts = ["Ja", "Nein", "Später"]
        key = (jid, aid, tid, clean.lower())
        for q in self._questions.values():
            if q.status == "open" and (q.job_id, q.agent_id, q.task_id, q.text.lower()) == key:
                return {"ok": True, "merged": True, **q.to_dict()}
        q = FlexQuestion(
            question_id=_new_id("q"),
            job_id=jid,
            task_id=tid,
            agent_id=aid,
            component=comp,
            text=clean,
            options=opts,
        )
        self._questions[q.question_id] = q
        return {"ok": True, "merged": False, **q.to_dict()}

    def offer_start_work(self, *, job_id: str = "", task_id: str = "plan") -> dict[str, Any]:
        return self.ask(
            agent_id="flex",
            job_id=job_id or self.job_id,
            task_id=task_id,
            component="start_work",
            text="Der Plan ist bereit. Möchtest du die Arbeit jetzt starten?",
        )

    def answer(
        self,
        question_id: str,
        value: Any,
        *,
        job_id: str = "",
    ) -> dict[str, Any]:
        q = self._questions.get(str(question_id or "").strip())
        if q is None or q.status != "open":
            return {"ok": False, "error": "stale_question"}
        if job_id and q.job_id != str(job_id).strip():
            return {"ok": False, "error": "job_mismatch"}
        raw = value
        if isinstance(value, list):
            raw = [sanitize_box1_text(str(v), limit=200) for v in value]
        else:
            raw = sanitize_box1_text(str(value), limit=200) if value is not None else ""
        q.status = "answered"
        q.answer = raw
        wants_start = False
        if q.component == "start_work":
            token = raw if isinstance(raw, str) else ""
            wants_start = token.lower().strip(" !.。") in _START_YES
        return {
            "ok": True,
            "question_id": q.question_id,
            "job_id": q.job_id,
            "task_id": q.task_id,
            "agent_id": q.agent_id,
            "component": q.component,
            "value": raw,
            "wants_start_work": wants_start,
        }

    def open_questions(self) -> list[FlexQuestion]:
        return [q for q in self._questions.values() if q.status == "open"]

    def snapshot(self) -> dict[str, Any]:
        open_qs = [q.to_dict() for q in self.open_questions()]
        return {
            "title": "Rückfragen und Entscheidungen",
            "owner": "flex",
            "job_id": self.job_id,
            "questions": open_qs,
        }

    def to_list(self) -> list[dict[str, Any]]:
        return [q.to_dict() for q in self._questions.values()]

    @classmethod
    def from_list(
        cls,
        rows: list[dict[str, Any]] | None,
        *,
        job_id: str = "",
    ) -> FlexDesk:
        desk = cls(job_id=job_id)
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            qid = str(row.get("question_id") or "").strip()
            if not qid:
                continue
            q = FlexQuestion(
                question_id=qid,
                job_id=str(row.get("job_id") or desk.job_id or ""),
                task_id=str(row.get("task_id") or "task"),
                agent_id=str(row.get("agent_id") or "flex"),
                component=(
                    str(row.get("component") or "text")
                    if str(row.get("component") or "text") in ALLOWED_COMPONENTS
                    else "text"
                ),
                text=sanitize_box1_text(str(row.get("text") or "")),
                options=[
                    sanitize_box1_text(str(o), limit=80)
                    for o in (row.get("options") or [])
                    if str(o).strip()
                ],
                status=str(row.get("status") or "open"),
                answer=row.get("answer"),
            )
            if not desk.job_id and q.job_id:
                desk.job_id = q.job_id
            desk._questions[qid] = q
        return desk

    def mark_done(self) -> None:
        raise PermissionError("Flex has no authority to mark a job done")

    def start_execute(self) -> None:
        raise PermissionError("Flex has no authority to start Execute")

    def set_god_mode(self, _enabled: bool = True) -> None:
        raise PermissionError("Flex has no authority to change God-Mode")

    def grant_tools(self) -> None:
        raise PermissionError("Flex has no authority to grant tools")
