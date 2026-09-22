"""Send/chat turns — never starts Execute."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from gnom_hub.pipeline.choices import (
    conversation_history,
    last_offered_choice,
    parse_offered_choices,
)
from gnom_hub.pipeline.constants import ALLOWED_SEND_TARGETS, PipelineCancelled
from gnom_hub.pipeline.helpers import (
    _format_turns,
    _is_go_only,
    _is_topic_switch,
    _pick_execute_task,
)
from gnom_hub.pipeline.models import PipelineStage, PipelineState


class BrainstormMixin:
    def _comm_now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _record_user(self, text: str, agent: str) -> dict[str, Any]:
        rec = {
            "message_id": f"m-{uuid.uuid4().hex[:12]}",
            "conversation_id": f"conv-{agent}",
            "target_agent_id": agent,
            "role": "user",
            "user_text": text,
            "visible_text": text,
            "status": "sent",
            "source": "user",
            "accepted_at": self._comm_now(),
            "created_at": self._comm_now(),
        }
        self._state.messages.append(rec)
        return rec

    def _record_reply(
        self,
        *,
        agent: str,
        text: str,
        in_reply_to: str,
        source: str = "live",
    ) -> dict[str, Any]:
        rid = f"r-{uuid.uuid4().hex[:12]}"
        status = "replied"
        if source in ("template", "fallback"):
            status = source
        rec = {
            "reply_id": rid,
            "message_id": rid,
            "conversation_id": f"conv-{agent}",
            "target_agent_id": agent,
            "reply_agent_id": agent,
            "role": "agent",
            "in_reply_to": in_reply_to,
            "visible_text": text,
            "status": status,
            "source": source,
            "created_at": self._comm_now(),
        }
        self._state.messages.append(rec)
        return rec

    def _reply_source(self, text: str) -> str:
        low = (text or "").lower()
        if "ziel in einem satz" in low or "mvp mit 3 kernfunktionen" in low:
            return "template"
        if (text or "").startswith("(Brainstorm agent is off"):
            return "fallback"
        return "live"

    def chat_turn(self, user_text: str, *, target: str = "brainstorm") -> PipelineState:
        """Send to an explicit target. Never starts Execute."""
        t = str(target or "brainstorm").strip().lower()
        if t not in ALLOWED_SEND_TARGETS:
            raise ValueError(f"invalid send target: {t}")
        self._state.send_target = t
        if t == "coordinator":
            return self.coordinator_intake(user_text)
        if t == "flex":
            return self.flex_intake(user_text)
        if t.startswith("worker"):
            return self.worker_intake(user_text, worker_id=t)
        return self.brainstorm_turn(user_text)

    def brainstorm_turn(self, user_text: str) -> PipelineState:
        text = user_text.strip()
        self._state.send_target = getattr(self._state, "send_target", "") or "brainstorm"
        try:
            if not text:
                self._fail("Empty user text")
                return self._state

            # Tool drill first (S7 etc. may mention kleinanzeigen without pure-nav intent)
            from gnom_hub.tools.agent_bridge import is_live_browser_task
            from gnom_hub.tools.tool_scenarios import is_tool_drill_task

            if is_tool_drill_task(text) and self.tools is not None:
                self._state.user_text = text
                self._state.send_target = getattr(self._state, "send_target", "") or "brainstorm"
                user = self._record_user(text, "brainstorm")
                self._record_reply(
                    agent="brainstorm",
                    text="Erkannt. Arbeit starten liefert das Ergebnis in Box 3.",
                    in_reply_to=user["message_id"],
                    source="live",
                )
                self._set_stage(PipelineStage.brainstorm)
                return self._state

            # Live browser: Send still does not run tools — Box 1 START-ID only.
            if is_live_browser_task(text) and self.tools is not None:
                self._state.user_text = text
                notes = "Live-Browser erkannt — Start nur nach Freigabe in Box 1."
                self._state.brainstorm_turns = [
                    {"role": "user", "text": text},
                    {"role": "brainstorm", "text": notes},
                ]
                self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)
                user = self._record_user(text, "brainstorm")
                self._record_reply(
                    agent="brainstorm",
                    text=f"{notes} Arbeit starten liefert in Box 3.",
                    in_reply_to=user["message_id"],
                    source="live",
                )
                self._set_stage(PipelineStage.brainstorm)
                return self._state

            continuing = (
                self._state.mode == "brainstorm"
                and self._state.stage == PipelineStage.brainstorm
                and bool(self._state.brainstorm_turns or self._state.messages)
                and not _is_topic_switch(self._state.brainstorm_turns, text)
            )
            # "mach das" / "jetzt ausführen" / "was ich gesagt habe" = go-only, keep prior task
            _exec_only = _is_go_only(text)
            if not continuing:
                prev_turns = list(self._state.brainstorm_turns or [])
                prev_notes = self._state.brainstorm_notes or ""
                prev_task = (self._state.user_text or "").strip()
                prev_flex_job = self._state.flex_job_id
                prev_target = getattr(self._state, "send_target", "") or "brainstorm"
                prev_messages = list(getattr(self._state, "messages", None) or [])
                prev_workers = list(self._state.worker_results or [])
                prev_outputs = list(self._state.worker_outputs or [])
                prev_offered = list(getattr(self._state, "offered_choices", None) or [])
                prev_confirmed = list(getattr(self._state, "confirmed_choices", None) or [])
                self._state = PipelineState(user_text=text, mode="brainstorm")
                self._state.flex_job_id = prev_flex_job
                self._state.send_target = prev_target
                self._state.messages = prev_messages
                self._state.worker_results = prev_workers
                self._state.worker_outputs = prev_outputs
                self._state.offered_choices = prev_offered
                self._state.confirmed_choices = prev_confirmed
                self._sync_flex_state()
                if _exec_only and prev_turns:
                    # Resolve last real task (browser/HTML/long), not the go-phrase
                    resolved = _pick_execute_task(prev_turns, fallback=prev_task)
                    self._state.brainstorm_turns = prev_turns
                    self._state.brainstorm_notes = prev_notes
                    self._state.user_text = resolved or prev_task or text
                    self._state.mode = "brainstorm"
            else:
                self._state.mode = "brainstorm"
                self._state.error = None
                self._state.pending_question = None
                if not _exec_only:
                    self._state.user_text = text

            self._clarified_once = False

            if _exec_only:
                choice = last_offered_choice(self._state)
                if choice:
                    return self.confirm_choice(str(choice.get("id") or ""), choice)

            # Go-only with a real prior task → remind to press Arbeit starten
            if _exec_only and (self._state.brainstorm_notes or "").strip():
                task = _pick_execute_task(
                    list(self._state.brainstorm_turns or []),
                    fallback=(self._state.user_text or "").strip(),
                )
                if task and not _is_go_only(task):
                    self._state.user_text = task
                    self._state.brainstorm_turns.append({"role": "user", "text": text})
                    self._state.brainstorm_turns.append(
                        {
                            "role": "brainstorm",
                            "text": f"Plan liegt vor: {task[:200]}",
                        }
                    )
                    self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)
                    user = self._record_user(text, "brainstorm")
                    self._record_reply(
                        agent="brainstorm",
                        text="Plan liegt vor. Arbeit starten liefert in Box 3.",
                        in_reply_to=user["message_id"],
                        source="live",
                    )
                    self._set_stage(PipelineStage.brainstorm)
                    self.bus.emit(
                        "pipeline.brainstorm_ready",
                        {
                            "can_execute": True,
                            "turns": len(self._state.brainstorm_turns),
                        },
                    )
                    return self._state

            self._check_cancel()
            self.bus.emit("pipeline.stage", {"stage": "memory"})
            topic = self._state.user_text or text
            mem = self.memory.recall(topic)
            self._state.memory_context = mem
            if mem:
                self.bus.emit("pipeline.memory_context", {"context": mem})

            history = conversation_history(self._state)
            self._state.brainstorm_turns.append({"role": "user", "text": text})
            # Send must not call tools. Prefetch belongs to Execute, not chat_turn.

            self._check_cancel()
            if not self.brainstorm.enabled:
                notes = "(Brainstorm agent is off — enable it to collect ideas.)"
            else:
                self._set_stage(PipelineStage.brainstorm)
                notes = self.brainstorm.run(text, mem, history=history)

            self._state.brainstorm_turns.append({"role": "brainstorm", "text": notes})
            self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)
            self._state.offered_choices = parse_offered_choices(str(notes or ""))
            user = self._record_user(text, "brainstorm")
            self._record_reply(
                agent="brainstorm",
                text=str(notes or ""),
                in_reply_to=user["message_id"],
                source=self._reply_source(str(notes or "")),
            )
            if not _exec_only:
                self._state.user_text = text

            self._set_stage(PipelineStage.brainstorm)
            self.bus.emit(
                "pipeline.brainstorm",
                {
                    "notes": notes,
                    "turns": list(self._state.brainstorm_turns),
                    "mode": "brainstorm",
                },
            )
            self.bus.emit(
                "pipeline.brainstorm_ready",
                {
                    "can_execute": bool(self._state.brainstorm_notes.strip()),
                    "turns": len(self._state.brainstorm_turns),
                },
            )
            # Arbeit starten is the button. No START-C1 after Send.
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            try:
                from gnom_hub.agents.roles_helpers import (
                    format_protect_user_message,
                    is_protect_error,
                )

                if is_protect_error(exc):
                    self._fail(format_protect_user_message(exc))
                else:
                    self._fail(str(exc))
            except Exception:  # noqa: BLE001
                self._fail(str(exc))
        return self._state

    def confirm_choice(self, choice_id: str = "", choice: dict | None = None) -> PipelineState:
        """Store a V4 card click as a real selection. Never starts Execute."""
        offered = list(getattr(self._state, "offered_choices", None) or [])
        picked: dict | None = None
        cid = str(choice_id or "").strip()
        if isinstance(choice, dict) and (choice.get("title") or choice.get("value")):
            picked = {
                "id": str(choice.get("id") or cid or f"choice-{len(offered) + 1}"),
                "title": str(choice.get("title") or choice.get("value") or "").strip(),
                "effect": str(choice.get("effect") or choice.get("value") or "").strip(),
                "value": str(choice.get("value") or choice.get("title") or "").strip(),
            }
        if picked is None:
            for row in offered:
                if isinstance(row, dict) and str(row.get("id") or "") == cid:
                    picked = dict(row)
                    break
        if picked is None and offered:
            picked = dict(offered[0])
        if picked is None or not str(picked.get("value") or picked.get("title") or "").strip():
            self._fail("Keine Auswahl zum Übernehmen")
            return self._state
        confirmed = list(getattr(self._state, "confirmed_choices", None) or [])
        if not any(str(c.get("id") or "") == str(picked.get("id") or "") for c in confirmed):
            confirmed.append(picked)
        self._state.confirmed_choices = confirmed
        self._state.pending_question = None
        title = str(picked.get("title") or picked.get("value") or "Auswahl")
        effect = str(picked.get("effect") or picked.get("value") or title)
        user_line = f"Ich wähle: {title}."
        reply = (
            f"Verstanden. Richtung: {title}. {effect} "
            "Nicht nochmal dieselbe Frage. Arbeit starten, wenn du bereit bist."
        )
        if effect and effect not in (self._state.user_text or ""):
            base = (self._state.user_text or "").strip()
            self._state.user_text = (base + " — " + effect).strip(" —") if base else effect
        self._state.brainstorm_turns.append({"role": "user", "text": user_line})
        self._state.brainstorm_turns.append({"role": "brainstorm", "text": reply})
        self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)
        rec = self._record_user(user_line, "brainstorm")
        self._record_reply(
            agent="brainstorm",
            text=reply,
            in_reply_to=rec["message_id"],
            source="live",
        )
        self._set_stage(PipelineStage.brainstorm)
        self.bus.emit(
            "pipeline.choice_confirmed",
            {"id": picked.get("id"), "title": title, "value": picked.get("value")},
        )
        self.bus.emit(
            "pipeline.brainstorm_ready",
            {"can_execute": True, "turns": len(self._state.brainstorm_turns)},
        )
        return self._state
