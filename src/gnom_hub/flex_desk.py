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
ALLOWED_ENTRY_TYPES = frozenset(
    {
        "entscheidung",
        "freigabe",
        "information",
        "nachbesserung",
        "blockiert",
        "fehler",
    }
)
_START_ID_RE = re.compile(r"START-([A-Z]\d+)", re.IGNORECASE)
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
# Line start, optional markdown fence (` ``` ` / ` ```text `), then FLEX_ASK.
_FLEX_ASK_LINE = re.compile(
    r"^(?:`{3,}\w*[ \t]*)?FLEX_ASK\b(.*)$",
    re.IGNORECASE,
)


_GERMAN_TERMS = (
    (re.compile(r"\bhero\b", re.IGNORECASE), "Kopfbereich"),
    (re.compile(r"\bcta\b", re.IGNORECASE), "Button zum Handeln"),
    (re.compile(r"\bfooter\b", re.IGNORECASE), "Fußzeile"),
    (re.compile(r"\bnavigation\b", re.IGNORECASE), "Menü"),
    (re.compile(r"\bnav\b", re.IGNORECASE), "Menü"),
    (re.compile(r"\bpayload\b", re.IGNORECASE), "Inhalt"),
    (re.compile(r"\bexecute\b", re.IGNORECASE), "Arbeit starten"),
    (re.compile(r"\bdark\s*mode\b", re.IGNORECASE), "dunkles Erscheinungsbild"),
)


def plain_german(raw: str) -> str:
    """Map a few technical tokens to simple German. Never invent an answer."""
    s = sanitize_box1_text(raw)
    for pat, de in _GERMAN_TERMS:
        s = pat.sub(de, s)
    return s.strip()


def parse_flex_ask(raw: str) -> dict[str, str] | None:
    """Parse the first FLEX_ASK block in worker text. None if not an ask."""
    lines = str(raw or "").splitlines()
    start: int | None = None
    head = ""
    for i, line in enumerate(lines):
        m = _FLEX_ASK_LINE.match(line.strip())
        if m:
            start = i
            head = m.group(1).strip()
            break
    if start is None:
        return None
    body_lines: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip().startswith("```"):
            break
        body_lines.append(line)
    component = "yes_no"
    task_id = "task"
    leftover: list[str] = []
    for tok in head.split():
        low = tok.lower()
        if low.startswith("task="):
            task_id = tok.split("=", 1)[1].strip() or "task"
        elif low in ALLOWED_COMPONENTS:
            component = low
        else:
            leftover.append(tok)
    body = "\n".join(body_lines).strip()
    text = plain_german(body or " ".join(leftover))
    if not text:
        return None
    return {"component": component, "task_id": task_id, "text": text}


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
    assignment_id: str = ""
    entry_type: str = "entscheidung"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


class FlexDesk:
    """Mediator for Box 1. Communication only — no authority."""

    def __init__(self, *, job_id: str = "") -> None:
        self.job_id = (job_id or "").strip()
        self._questions: dict[str, FlexQuestion] = {}
        self._assignment_seq = 0

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
        assignment_id: str = "",
        entry_type: str = "entscheidung",
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
        clean = plain_german(text)
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
        et = str(entry_type or "entscheidung").strip().lower()
        if et not in ALLOWED_ENTRY_TYPES:
            et = "entscheidung"
        q = FlexQuestion(
            question_id=_new_id("q"),
            job_id=jid,
            task_id=tid,
            agent_id=aid,
            component=comp,
            text=clean,
            options=opts,
            assignment_id=str(assignment_id or "").strip(),
            entry_type=et if comp != "start_work" else "freigabe",
        )
        self._questions[q.question_id] = q
        return {"ok": True, "merged": False, **q.to_dict()}

    def next_assignment_id(self, prefix: str = "C") -> str:
        self._assignment_seq += 1
        return f"{prefix}{self._assignment_seq}"

    def offer_start_work(
        self,
        *,
        job_id: str = "",
        task_id: str = "plan",
        workers: str = "",
        effect: str = "Code und Tests ändern",
    ) -> dict[str, Any]:
        aid = self.next_assignment_id("C")
        who = (workers or "laut Plan").strip()
        text = (
            f"START-{aid} — Auftrag {aid} ist ausführbar. "
            f"Vorgesehen: {who}. "
            f"Wirkung: {effect}. "
            f"Soll genau dieser Auftrag jetzt starten?"
        )
        return self.ask(
            agent_id="flex",
            job_id=job_id or self.job_id,
            task_id=task_id,
            component="start_work",
            text=text,
            options=[f"Ja, START-{aid} starten", "Später"],
            assignment_id=aid,
            entry_type="freigabe",
        )

    def answer(
        self,
        question_id: str,
        value: Any,
        *,
        job_id: str = "",
        assignment_id: str = "",
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
        token = raw if isinstance(raw, str) else ""
        low = token.lower().strip(" !.。")
        extracted = ""
        m = _START_ID_RE.search(token)
        if m:
            extracted = m.group(1).upper()
        want_id = str(assignment_id or extracted or "").strip().upper()
        open_n = len(self.open_questions())
        bare_yes = low in _START_YES
        if q.component == "start_work" and bare_yes and (open_n > 1 or q.assignment_id):
            return {"ok": False, "error": "unbound_yes"}
        if (
            q.component == "start_work"
            and want_id
            and q.assignment_id
            and want_id != q.assignment_id.upper()
        ):
            return {"ok": False, "error": "assignment_mismatch"}
        q.status = "answered"
        q.answer = raw
        wants_start = False
        if q.component == "start_work":
            if extracted:
                wants_start = extracted == (q.assignment_id or "").upper()
            else:
                wants_start = bare_yes and open_n <= 1
        return {
            "ok": True,
            "question_id": q.question_id,
            "job_id": q.job_id,
            "task_id": q.task_id,
            "agent_id": q.agent_id,
            "component": q.component,
            "assignment_id": q.assignment_id,
            "entry_type": q.entry_type,
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
                assignment_id=str(row.get("assignment_id") or ""),
                entry_type=str(row.get("entry_type") or "entscheidung"),
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
