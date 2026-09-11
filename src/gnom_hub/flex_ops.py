"""Flex result-review panel: dynamic feedback buttons after Execute (learn / retry)."""

from __future__ import annotations

from typing import Any

from gnom_hub.snapshot_ops import _deliverable_ok


class FlexOpsMixin:
    """Mixin: expects Hub pipeline, warm, flex agent, snapshot."""

    def flex_review_panel(self) -> dict[str, Any]:
        """
        Content for Flex feedback panel in Box 1.

        Active after stage=done with worker output — Flex asks quality + next steps.
        """
        st = self.pipeline.state
        stage = st.stage.value if st.stage else "idle"
        outs = list(st.worker_outputs or [])
        chars = sum(len(str(o.get("result") or "")) for o in outs)
        active = stage == "done" and (chars > 80 or bool(st.worker_results))
        ok_deliv = _deliverable_ok(st)

        if not active:
            return {
                "active": False,
                "title": "Flex",
                "question": "Nach einem Ergebnis fragt Flex hier nach Feedback.",
                "buttons": [],
                "hint": "Box 1 = Flex lernt & steuert",
                "deliverable_ok": False,
            }

        if not ok_deliv:
            return {
                "active": True,
                "title": "Flex · kein Deliverable",
                "question": (
                    "Kein gültiges Ergebnis. Worker hat FEHLER gemeldet — "
                    "nicht bewerten. Key, Tollgate oder Budget prüfen, dann neu bauen."
                ),
                "buttons": [
                    {
                        "id": "rebrainstorm",
                        "label": "Nochmal Brainstorm",
                        "action": "brainstorm",
                        "prompt": (
                            "Bitte nochmal brainstormen: wie wird das Ergebnis besser? "
                            "Kurz, max 6 Zeilen. Danach frage, ob ich neu bauen soll."
                        ),
                    },
                    {
                        "id": "rebuild",
                        "label": "Nochmal bauen",
                        "action": "start_work",
                    },
                ],
                "hint": "Erst Ursache (Key/Tollgate/Budget), dann Box 1 Ja",
                "stats": {"workers": len(outs), "chars": chars},
                "deliverable_ok": False,
            }

        qnotes = (st.quality_notes or "").strip()
        quality_hint = ""
        if qnotes:
            quality_hint = qnotes.splitlines()[0][:120]

        buttons = [
            {
                "id": "good",
                "label": "Gut so",
                "action": "learn",
                "learn": "User: letztes Ergebnis war gut — so weiter",
            },
            {
                "id": "mid",
                "label": "Mittel",
                "action": "learn",
                "learn": "User: letztes Ergebnis war mittel — noch verbessern",
            },
            {
                "id": "bad",
                "label": "Schlecht",
                "action": "learn",
                "learn": "User: letztes Ergebnis war schlecht — bitte anders angehen",
            },
            {
                "id": "rebrainstorm",
                "label": "Nochmal Brainstorm",
                "action": "brainstorm",
                "prompt": (
                    "Bitte nochmal brainstormen: wie wird das Ergebnis besser? "
                    "Kurz, max 6 Zeilen. Danach frage, ob ich neu bauen soll."
                ),
            },
            {
                "id": "rebuild",
                "label": "Nochmal bauen",
                "action": "start_work",
            },
            {
                "id": "more_dark",
                "label": "Merken: dunkler",
                "action": "learn",
                "learn": "User: bevorzugt dunkleres Theme und starker Kontrast",
            },
            {
                "id": "more_interact",
                "label": "Merken: mehr Klicks",
                "action": "learn",
                "learn": "User: will mehr Interaktion (Buttons, onclick, JS)",
            },
            {
                "id": "shorter",
                "label": "Merken: knapper",
                "action": "learn",
                "learn": "User: will knappe Brainstorm-Antworten und schlanke UI",
            },
        ]

        # Dynamic extra from quality notes (thin heuristic, no LLM required)
        low_q = qnotes.lower()
        if "html" in low_q or "incomplete" in low_q:
            buttons.insert(
                3,
                {
                    "id": "fix_html",
                    "label": "HTML reparieren",
                    "action": "start_work",
                    "learn": "User: HTML war unvollständig — nächstes Mal vollständiges Dokument",
                },
            )
        if "interaction" in low_q or "onclick" in low_q:
            buttons.insert(
                3,
                {
                    "id": "add_js",
                    "label": "Mehr Interaktion bauen",
                    "action": "start_work",
                    "learn": "User: Interaktion fehlte — nächstes Mal klickbare UI",
                },
            )

        question = "Wie war das Ergebnis?"
        if quality_hint:
            question = f"Ergebnis da. Flex fragt: Wie war's?\n({quality_hint})"

        return {
            "active": True,
            "title": "Flex · Feedback",
            "question": question,
            "buttons": buttons[:10],
            "hint": "Klick = lernen · Bauen fragt in Box 1",
            "stats": {"workers": len(outs), "chars": chars},
            "deliverable_ok": True,
        }

    def apply_flex_feedback(
        self,
        button_id: str,
        *,
        label: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        """
        Handle a Flex panel button.

        Actions:
          learn — store Flex wish in WARM
          brainstorm — start short improve brainstorm turn
          start_work — ask Box 1 to confirm Execute (Flex has no execute authority)
        """
        panel = self.flex_review_panel()
        btn = None
        for b in panel.get("buttons") or []:
            if str(b.get("id")) == str(button_id):
                btn = b
                break
        if btn is None and not label and not note and str(button_id) != "custom_note":
            raise ValueError("unknown flex feedback button")

        action = str((btn or {}).get("action") or "learn")
        learn = str((btn or {}).get("learn") or "").strip()
        if note.strip():
            # Free-text flag/note is always a standing wish fragment
            learn = (learn + " · " if learn else "") + f"User: {note.strip()[:200]}"
        elif str(button_id) == "custom_note":
            raise ValueError("Notiz leer")
        if not learn and label:
            learn = f"User feedback: {label.strip()[:160]}"

        learned = False
        if learn:
            learned = bool(self.warm.add_fact_flex(learn))
            if learned and hasattr(self, "index_durable_fact"):
                self.index_durable_fact(
                    learn if learn.lower().startswith(("user:", "wish:")) else "User: " + learn,
                    source="flex_wish",
                )

        message = (btn or {}).get("label") or label or button_id

        if action == "brainstorm":
            prompt = str((btn or {}).get("prompt") or "").strip() or (
                "Bitte kurzes Brainstorm: wie verbessern wir das letzte Ergebnis?"
            )
            # Sync short turn so UI gets notes immediately; user can Execute after
            snap = self.chat(prompt, full=False)
            return {
                "ok": True,
                "action": "brainstorm",
                "learned": learned,
                "learn_text": learn if learned else "",
                "message": f"Flex: Brainstorm neu — {message}",
                "snapshot": snap,
            }

        if action in ("execute", "start_work"):
            # Flex has no execute authority — Box 1 start_work / #btn-execute
            if not (self.pipeline.state.brainstorm_notes or "").strip():
                raise ValueError("nichts zum erneuten Bauen — erst brainstormen")
            desk = getattr(self.pipeline, "flex_desk", None)
            if desk is None:
                raise TypeError("flex desk missing")
            ensure = getattr(self.pipeline, "_ensure_flex_job", None)
            if callable(ensure):
                ensure()
            asked = desk.offer_start_work(task_id="plan")
            sync = getattr(self.pipeline, "_sync_flex_state", None)
            if callable(sync):
                sync()
            return {
                "ok": True,
                "action": "start_work",
                "learned": learned,
                "learn_text": learn if learned else "",
                "message": f"Flex fragt in Box 1: Arbeit starten? — {message}",
                "flex_ask": asked,
                "snapshot": self.snapshot(),
            }

        # default learn only
        return {
            "ok": True,
            "action": "learn",
            "learned": learned,
            "learn_text": learn if learned else "",
            "message": f"Flex hat gelernt: {message}",
            "snapshot": self.snapshot(),
            "flex_review": self.flex_review_panel(),
        }
