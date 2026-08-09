"""Flex result-review panel: dynamic feedback buttons after Execute (learn / retry)."""

from __future__ import annotations

from typing import Any


class FlexOpsMixin:
    """Mixin: expects Hub pipeline, warm, flex agent, snapshot."""

    def flex_review_panel(self) -> dict[str, Any]:
        """
        Content for the right Platzhalter next to chat.

        Active after stage=done with worker output — Flex asks quality + next steps.
        """
        st = self.pipeline.state
        stage = st.stage.value if st.stage else "idle"
        outs = list(st.worker_outputs or [])
        chars = sum(len(str(o.get("result") or "")) for o in outs)
        active = stage == "done" and (chars > 80 or bool(st.worker_results))

        if not active:
            return {
                "active": False,
                "title": "Flex",
                "question": "Nach einem Ergebnis fragt Flex hier nach Feedback.",
                "buttons": [],
                "hint": "Platzhalter rechts = Flex lernt & steuert",
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
                "action": "execute",
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
                    "action": "execute",
                    "learn": "User: HTML war unvollständig — nächstes Mal vollständiges Dokument",
                },
            )
        if "interaction" in low_q or "onclick" in low_q:
            buttons.insert(
                3,
                {
                    "id": "add_js",
                    "label": "Mehr Interaktion bauen",
                    "action": "execute",
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
            "hint": "Klick = lernen und/oder nächster Schritt",
            "stats": {"workers": len(outs), "chars": chars},
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
          execute — re-run workers from current brainstorm notes
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

        job: dict[str, Any] | None = None
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

        if action == "execute":
            # Optional learn before rebuild
            if not (self.pipeline.state.brainstorm_notes or "").strip():
                raise ValueError("nichts zum erneuten Bauen — erst brainstormen")
            job = self.execute_async()
            return {
                "ok": True,
                "action": "execute",
                "learned": learned,
                "learn_text": learn if learned else "",
                "message": f"Flex: baue nochmal — {message}",
                "job": job,
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
