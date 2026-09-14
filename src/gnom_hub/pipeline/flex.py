"""Flex questions, answers, nudges."""

from __future__ import annotations

import uuid

from gnom_hub.flex_desk import FlexDesk, parse_flex_ask
from gnom_hub.pipeline.helpers import _definition_of_done, _quality_check, _validate_worker_draft
from gnom_hub.pipeline.models import PipelineStage, PipelineState


class FlexMixin:
    def _ensure_flex_job(self) -> str:
        jid = (self._state.flex_job_id or self.flex_desk.job_id or "").strip()
        if not jid:
            jid = uuid.uuid4().hex[:12]
        self.flex_desk.bind_job(jid)
        self._state.flex_job_id = jid
        return jid

    def _sync_flex_state(self) -> None:
        self._state.flex_job_id = self.flex_desk.job_id
        self._state.flex_questions = self.flex_desk.to_list()

    def restore_flex_from_state(self) -> None:
        """Rebuild FlexDesk after checkpoint / snapshot reload."""
        self.flex_desk = FlexDesk.from_list(
            list(getattr(self._state, "flex_questions", None) or []),
            job_id=str(getattr(self._state, "flex_job_id", "") or ""),
        )

    def flex_intake(self, user_text: str) -> PipelineState:
        text = (user_text or "").strip()
        if not text:
            self._fail("Empty user text")
            return self._state
        self._state.send_target = "flex"
        self._state.user_text = text
        user = self._record_user(text, "flex")
        if getattr(self.flex, "enabled", False):
            try:
                self.flex.absorb(text, self._state.memory_context or "")
            except Exception:  # noqa: BLE001
                pass
        self._ensure_flex_job()
        self.flex_desk.ask(
            agent_id="flex",
            text=text[:400],
            component="free_text",
            entry_type="entscheidung",
        )
        self._sync_flex_state()
        self._record_reply(
            agent="flex",
            text="Flex: Nachricht in Box 1. Flex startet keine Arbeit.",
            in_reply_to=user["message_id"],
            source="live",
        )
        self._set_stage(PipelineStage.brainstorm)
        return self._state

    def apply_flex_answer(self, payload: dict) -> None:
        """Inject a Box 1 answer only for the asking agent. Flex does not Execute."""
        agent = str(payload.get("agent_id") or "").strip()
        tid = str(payload.get("task_id") or "task")
        qid = str(payload.get("question_id") or "")
        value = payload.get("value")
        line = f"User→{agent} ({tid}, {qid}): {value}"
        reqs = list(self._state.distilled_requirements)
        if line not in reqs:
            reqs.append(line)
        if self.flex.enabled:
            wishes = []
            try:
                wishes = list(self.flex.binding_wishes(self._state.memory_context or "") or [])
            except Exception:  # noqa: BLE001
                wishes = []
            for w in wishes[:4]:
                rem = f"Flex-Erinnerung für {agent}: {w}"
                if rem not in reqs:
                    reqs.append(rem)
        self._state.distilled_requirements = reqs
        self._sync_flex_state()

    def _pause_worker_flex_ask(
        self,
        wid: str,
        plan_task: str,
        asked: dict[str, str],
        remaining: list[dict],
    ) -> None:
        """Pause execute: keep asking worker + original plan task in flex_wait_*."""
        self._ensure_flex_job()
        self.flex_desk.ask(
            agent_id=wid,
            job_id=self.flex_desk.job_id,
            task_id=asked["task_id"],
            text=asked["text"],
            component=asked["component"],
        )
        queued = [d for d in remaining if isinstance(d, dict)]
        if not queued or str(queued[0].get("worker") or "") != wid:
            queued = [{"worker": wid, "task": plan_task}, *queued]
        else:
            queued[0] = {**queued[0], "worker": wid, "task": plan_task}
        self._state.flex_wait_agent = wid
        self._state.flex_wait_task = plan_task
        self._state.flex_wait_remaining = queued
        self._sync_flex_state()
        self._set_stage(PipelineStage.clarify)

    def _open_worker_askers(self) -> set[str]:
        return {
            str(q.agent_id)
            for q in self.flex_desk.open_questions()
            if str(q.agent_id).startswith("worker")
        }

    def continue_after_flex_ask(self) -> PipelineState:
        """Run workers queued after a Box 1 pause, then quality + finish."""
        remaining = list(getattr(self._state, "flex_wait_remaining", None) or [])
        self._state.flex_wait_remaining = []
        text = (self._state.user_text or "").strip()
        mem = self._state.memory_context or ""
        dod = _definition_of_done(text, self._state.distilled_requirements)
        outputs = list(self._state.worker_outputs or [])
        results = list(self._state.worker_results or [])
        open_askers = self._open_worker_askers()
        self._set_stage(PipelineStage.work)
        for idx, item in enumerate(remaining):
            if not isinstance(item, dict):
                continue
            wid = str(item.get("worker") or "").strip()
            task = str(item.get("task") or "")
            worker = self._workers.get(wid)
            if worker is None or not worker.enabled:
                continue
            if wid in open_askers:
                # Unanswered Box 1 ask — leave this worker; run later queue.
                continue
            task_full = f"{task}\n\n{dod}".strip()
            result = worker.run(
                task_full,
                text,
                self._state.distilled_requirements,
                mem,
            )
            asked = parse_flex_ask(result)
            if asked:
                self._pause_worker_flex_ask(wid, task, asked, remaining[idx:])
                return self._state
            gate = _validate_worker_draft(
                result,
                user_text=text,
                task=task,
                requirements=self._state.distilled_requirements,
                tool_calls=self._state.tool_calls,
            )
            results.append(result)
            outputs.append(
                {
                    "worker": wid,
                    "name": worker.state.name,
                    "index": len(outputs) + 1,
                    "task": task_full,
                    "result": result,
                    "validation": gate,
                }
            )
            self._state.worker_results = list(results)
            self._state.worker_outputs = list(outputs)
        self._state.quality_notes = _quality_check(
            self._state.user_text,
            self._state.distilled_requirements,
            outputs,
        )
        self._append_prefetch_why_notes()
        self._flex_nudge_and_fix(text, mem, dod)
        self._offer_nudge_questions()
        self._finish()
        return self._state

    def _offer_nudge_questions(self) -> None:
        """Forgotten requirements → Box 1 Nachbesserung ask. Flex does not Execute."""
        nudges = list(getattr(self._state, "agent_nudges", None) or [])
        if not nudges:
            return
        self._ensure_flex_job()
        for n in nudges[:3]:
            if not isinstance(n, dict):
                continue
            aid = str(n.get("agent") or "flex").strip().lower()
            msg = str(n.get("message") or "").strip()
            if not msg:
                continue
            self.flex_desk.ask(
                agent_id=aid if aid in ("worker1", "worker2", "worker3", "worker4") else "flex",
                job_id=self.flex_desk.job_id,
                task_id="nachbesserung",
                text=f"Etwas fehlt: {msg}. Soll ich nachbessern lassen?",
                component="yes_no",
            )
        self._sync_flex_state()

    def _flex_nudge_and_fix(self, text: str, mem: str, dod: str) -> None:
        if not self.flex.enabled:
            self._state.agent_nudges = []
            return
        outputs = list(self._state.worker_outputs or [])
        try:
            nudges = self.flex.nudge_gaps(
                text,
                list(self._state.distilled_requirements),
                outputs,
                self._state.quality_notes or "",
                mem,
            )
        except Exception as exc:  # noqa: BLE001
            self.bus.emit(
                "pipeline.warning",
                {"stage": "flex_nudge", "error": str(exc)},
            )
            nudges = []
        self._state.agent_nudges = list(nudges or [])
        if not nudges:
            return
        lines = [
            self._state.quality_notes or "",
            "",
            "Flex → Agenten (bevor du es wiederholen musst):",
        ]
        for n in nudges:
            aid = str(n.get("agent") or "")
            msg = str(n.get("message") or "").strip()
            if not aid or not msg:
                continue
            lines.append(f"• {aid}: {msg}")
            self.bus.emit(
                "pipeline.agent_nudge",
                {"agent": aid, "message": msg, "reason": n.get("reason")},
            )
            worker = self._workers.get(aid)
            if worker is None or not worker.enabled:
                continue
            task = text
            prev_body = ""
            prev_issues: list[str] = []
            for o in outputs:
                if str(o.get("worker") or "") == aid:
                    task = str(o.get("task") or text)
                    prev_body = str(o.get("result") or "")
                    gate_prev = o.get("validation") if isinstance(o.get("validation"), dict) else {}
                    prev_issues = list(gate_prev.get("issues") or [])
                    break
            # Auth / missing-key failures cannot be fixed by re-calling the same dead provider
            if "worker_error" in prev_issues or (
                "FEHLER" in prev_body and "Deliverable" in prev_body
            ):
                self.bus.emit(
                    "pipeline.agent_nudge",
                    {
                        "agent": aid,
                        "message": msg,
                        "reason": "auth_or_missing_key",
                        "rerun": False,
                    },
                )
                continue
            self._check_cancel()
            self.bus.emit("pipeline.stage", {"stage": aid})
            fixed = worker.run(
                f"{task}\n\n{dod}\n\n"
                f"=== FLEX CORRECTION (mandatory — user should not have to repeat this) ===\n"
                f"{msg}\n"
                f"=== END CORRECTION ===",
                text,
                list(self._state.distilled_requirements),
                mem,
            )
            for o in outputs:
                if str(o.get("worker") or "") == aid:
                    o["result"] = fixed
                    o["validation"] = _validate_worker_draft(
                        fixed,
                        user_text=text,
                        task=task,
                        requirements=self._state.distilled_requirements,
                        tool_calls=self._state.tool_calls,
                    )
                    o["flex_nudge"] = msg
                    break
            self.bus.emit(
                "pipeline.worker",
                {
                    "worker": aid,
                    "result": fixed,
                    "task": task,
                    "flex_nudge": msg,
                    "rerun": True,
                },
            )
        self._state.worker_outputs = outputs
        self._state.worker_results = [str(o.get("result") or "") for o in outputs]
        self._state.quality_notes = "\n".join(lines).strip()
        self._state.quality_notes = (
            _quality_check(
                self._state.user_text,
                self._state.distilled_requirements,
                outputs,
            )
            + "\n\n"
            + "\n".join(lines[2:])
        ).strip()
        self.bus.emit(
            "pipeline.quality",
            {
                "notes": self._state.quality_notes,
                "workers": len(outputs),
                "nudges": list(self._state.agent_nudges),
            },
        )
