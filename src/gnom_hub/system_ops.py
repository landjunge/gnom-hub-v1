"""System settings, usage, help, canvas, god-mode (extracted from Hub)."""

from __future__ import annotations

from typing import Any

from gnom_hub import __version__
from gnom_hub.ui.tooltips import TOOLTIPS


class SystemOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def set_god_mode(
        self, enabled: bool, reason: str = "user", assignment_id: str = ""
    ) -> dict[str, Any]:
        if enabled:
            self.god_mode.enable("user", assignment_id=assignment_id)
        else:
            self.god_mode.disable(reason or "user")
        self.computer.set_god_mode(self.god_mode.enabled)
        return self.god_mode.snapshot()

    # ── commands ────────────────────────────────────────────────────

    def usage_dict(self) -> dict[str, Any]:
        snap = self.llm.usage_snapshot()
        return {
            "spent_usd": snap.get("spent_usd", 0.0),
            "prompt_tokens": snap.get("prompt_tokens", 0),
            "completion_tokens": snap.get("completion_tokens", 0),
            "by_agent": snap.get("by_agent") or {},
            "free_only": self.llm.free_only,
            "max_budget_usd": self.llm.max_budget_usd,
        }

    def reset_usage(self) -> dict[str, Any]:
        data = self.llm.reset_usage()
        self._append_trace("usage.reset", {"ok": True})
        return {"ok": True, **data, **self.usage_dict()}

    def set_system(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Global free_only / budget / UI lang (system panel)."""
        if "free_only" in fields and fields["free_only"] is not None:
            self.llm.free_only = bool(fields["free_only"])
        if "max_budget_usd" in fields:
            raw = fields["max_budget_usd"]
            if raw is None or raw == "":
                self.llm.max_budget_usd = None
            else:
                self.llm.max_budget_usd = float(raw)
        if fields.get("default_model"):
            self.llm.default_model = str(fields["default_model"]).strip()
        if fields.get("ui_lang"):
            lang = str(fields["ui_lang"]).strip().lower()
            if lang in ("en", "de"):
                self.ui_lang = lang
        if "auto_pack_after_execute" in fields and fields["auto_pack_after_execute"] is not None:
            self.auto_pack_after_execute = bool(fields["auto_pack_after_execute"])
        if "pack_max" in fields and fields["pack_max"] is not None:
            try:
                self.pack_max = max(5, min(100, int(fields["pack_max"])))
            except (TypeError, ValueError):
                pass
        return self.system_dict()

    def system_dict(self) -> dict[str, Any]:
        usage = self.llm.usage_snapshot()
        return {
            "deepseek": self.llm.has_provider("deepseek"),
            "ollama": self.llm.has_provider("ollama"),
            "free_only": self.llm.free_only,
            "max_budget_usd": self.llm.max_budget_usd,
            "spent_usd": usage["spent_usd"],
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "default_model": self.llm.default_model,
            "god_mode": self.god_mode.enabled,
            "ui_lang": self.ui_lang,
            "checkpoint_exists": self._checkpoint_path.is_file(),
            "version": __version__,
            "providers": self.llm.providers_snapshot(),
            "backups": self.list_backups()[:8],
            "packs": self.list_session_packs()[:12],
            "auto_pack_after_execute": self.auto_pack_after_execute,
            "pack_max": self.pack_max,
            "setup": self._setup_dict(),
        }

    def _setup_dict(self) -> dict[str, Any]:
        from gnom_hub.config.user_workspace import inspect_user_workspace
        from gnom_hub.stack import via_tollgate

        st = inspect_user_workspace(getattr(self, "root", None))
        tg_ok = True
        tg_note = ""
        if via_tollgate():
            try:
                import tollgate  # noqa: F401
            except ImportError:
                tg_ok = False
                tg_note = "TollGate fehlt — DeepSeek-Key wird direkt genutzt."
        return {
            "key_ok": bool(st.key_has_deepseek),
            "personal_ws": st.personal_ws,
            "tollgate_ok": tg_ok,
            "tollgate_note": tg_note,
        }

    def help_text(self) -> dict[str, Any]:
        topics = [
            {
                "id": "senden",
                "label": "Senden",
                "wozu": "Du redest mit einem Agenten. Sonst passiert nichts.",
                "steps": [
                    "Oben das Flag wählen: Brain, Coord, Flex oder A1–A4. Gelb = Empfänger.",
                    "Text in die Zeile unten schreiben. Mikrofon füllt dieselbe Zeile.",
                    "Senden oder Enter drücken.",
                    "Die Antwort steht in Box 2 beim gewählten Agenten und im Chat darunter.",
                ],
                "points": [
                    "Senden und Enter bedeuten nur reden.",
                    "Der Empfänger ist das Flag, nicht die angeklickte Karte.",
                    "Kartenklick öffnet Infos. Das Sendeziel bleibt, wo das Flag steht.",
                    "Brain redet frei. Coord plant. Flex fragt nach. A1–A4 sind Arbeiter.",
                    "Läuft schon eine Antwort, bleibt sie dem Agenten zugeordnet, der sie begonnen hat.",
                ],
                "nicht": "Senden startet keine Arbeiter, keine Werkzeuge und keine Dateiänderung.",
            },
            {
                "id": "arbeit",
                "label": "Arbeit",
                "wozu": "Die Arbeiter sollen etwas bauen, prüfen oder liefern.",
                "steps": [
                    "Auftrag in die Zeile schreiben oder nach dem Gespräch stehen lassen.",
                    "Arbeit starten oder Ctrl/⌘+Enter.",
                    "Fragen in Box 1 beantworten. Ja gilt nur für die sichtbare Frage.",
                    "In Box 3 die Reiter A1–A4 öffnen. Sicht = Seite, Code = Text.",
                    "Laufenden Job mit Esc oder Abbrechen stoppen.",
                ],
                "points": [
                    "Arbeit starten startet Distill und danach die Arbeiter.",
                    "Ohne diesen Knopf (oder Ctrl/⌘+Enter) bleibt es ein Gespräch.",
                    "Offene Entscheidungen stehen in Box 1, nicht im Chat versteckt.",
                    "Ergebnisse gehören nach Box 3, nicht als JSON in Box 2.",
                    "Ein zweites Arbeit starten wartet, bis der laufende Job frei ist, oder du brichst ab.",
                ],
                "nicht": "Senden und Enter starten keine Arbeit.",
            },
            {
                "id": "boxen",
                "label": "Boxen",
                "wozu": "Drei Orte, drei Aufgaben. Nichts soll sich verstecken.",
                "steps": [
                    "Box 1 links: wenn Gnom fragt, hier klicken oder eine Karte wählen.",
                    "Box 2 Mitte: Reiter Brain, Flex, Coord, Mem, A1–A4 — eine Antwort lesen.",
                    "Box 3 rechts: Ergebnis. Sicht = echte Seite, Code = der Text dahinter.",
                    "Unter den Reitern: Weg, Neu, Behalten.",
                ],
                "points": [
                    "Box 1 ist Rückfrage und Entscheidung, kein Chat-Verlauf.",
                    "Box 2 ist die Antwort des gewählten Agenten.",
                    "Box 3 ist die Lieferung nach Arbeit starten.",
                    "Kurze weiße Namen auf den Reitern. Voller Name steht im Hover.",
                    "Scrollen geht, der Balken bleibt unsichtbar.",
                ],
                "nicht": "Eine Box ist keine Textwand und kein rohes JSON.",
            },
            {
                "id": "god",
                "label": "God",
                "wozu": "Echter Desktop nur, wenn du das ausdrücklich einschaltest.",
                "steps": [
                    "Den roten Badge oben rechts anklicken.",
                    "God an: nach einer sichtbaren Nachfrage dürfen Maus, Tastatur, Shell wirklich greifen.",
                    "Badge nochmal: God aus, wieder Trockenlauf.",
                    "Im System-Fenster nachsehen: dort gibt es keinen God-Schalter.",
                ],
                "points": [
                    "God geht ausschließlich über den roten Nutzer-Badge.",
                    "God aus = Trockenlauf. Klicks und Shell tun so, als würden sie laufen.",
                    "God an = echte Aktionen auf diesem Mac, nicht still im Hintergrund.",
                    "Werkzeuge ohne God bleiben Trockenlauf, auch wenn das Werkzeug-Fenster offen ist.",
                    "God schaltet sich nicht durch Senden, Arbeit oder Kartenklick ein.",
                ],
                "nicht": "Im System-Fenster gibt es keinen God-Schalter.",
            },
            {
                "id": "dateien",
                "label": "Dateien",
                "wozu": "Ergebnisse behalten, ohne sie ins Git zu schieben.",
                "steps": [
                    "In Box 3 den Reiter wählen, dessen Datei du willst.",
                    "Behalten klicken. Erfolg kommt erst nach bestätigtem Rücklesen.",
                    "Workspace öffnen: drei Spalten Temp, Dauerhaft, Behalten.",
                    "HTML zuerst als Sicht ansehen, daneben Code, wenn du den Text brauchst.",
                ],
                "points": [
                    "Behalten meldet Erfolg erst, wenn die Datei wirklich geschrieben wurde.",
                    "Weg legt ab, Zurück holt die letzte Weg-Datei.",
                    "Neu leert die aktuelle Lieferung, ohne den Desk zu zerstören.",
                    "Persönlicher Ordner ist WS-gnom-hub-v1, nicht das Git-Repo.",
                    "Löschen fragt nach. Zip gibt es erst, wenn die Datei erzeugt ist.",
                ],
                "nicht": "Persönliche Dateien liegen nicht im Git und nicht im Repo.",
            },
            {
                "id": "tastatur",
                "label": "Tastatur",
                "wozu": "Die wichtigsten Taten ohne Menü suchen.",
                "steps": [
                    "Enter: senden, also nur reden.",
                    "Ctrl/⌘+Enter: Arbeit starten.",
                    "Ctrl/⌘+S: speichern. Esc: Overlay zu oder laufenden Job abbrechen.",
                    "Mikrofon: Zeile füllen. Nochmal klicken schaltet es aus.",
                ],
                "points": [
                    "Enter und Senden sind dieselbe Tat: reden.",
                    "Ctrl/⌘+Enter und Arbeit starten sind dieselbe Tat: liefern.",
                    "Das Mikrofon bleibt an, bis du es ausklickst. Es sendet nicht von allein.",
                    "Sprache (Vorlesen) spricht Antworten, startet aber keine Arbeit.",
                    "Kleine Fenster: dieselben Tasten, dieselben drei Boxen.",
                ],
                "nicht": "Mikrofon und Sprache senden nicht von allein.",
            },
            {
                "id": "update",
                "label": "Update",
                "wozu": "Neue Version suchen. Einspielen nur, wenn du klickst.",
                "steps": [
                    "System öffnen.",
                    "Suchen drücken. Danach Details lesen.",
                    "Vor einem Wechsel Backup anlegen. Die Liste steht im selben Fenster.",
                    "Aktualisieren nur klicken, wenn ein von Daniel freigegebenes Release da ist.",
                    "Wiederherstellen spielt ein vorhandenes Backup, kein stilles main.",
                ],
                "points": [
                    "Suche darf GitHub prüfen.",
                    "Installation nie von allein und nie von main.",
                    "Laufende Arbeit blockiert das Einspielen.",
                    "Ohne Nutzer-Release gibt es nichts zum Installieren.",
                    "Notfallweg: Backup in der Liste mit Laden zurückspielen.",
                ],
                "nicht": "Kein stilles Update, kein Einspielen während Arbeit, kein main für normale Nutzer.",
            },
        ]
        return {
            "title": "Hilfe",
            "topics": topics,
            "how_to": topics[0]["points"][0],
            "example": "Senden = reden. Arbeit starten = Arbeiter. God nur Badge.",
            "pipeline": "Brainstorm → Arbeit starten → Distill → Flex → Arbeiter (1–4) → Quality → Memory",
            "keys": "Enter senden · Ctrl/⌘+Enter Arbeit · Ctrl/⌘+S speichern · Esc zu",
        }

    def canvas(self) -> dict[str, Any]:
        return {
            "mermaid": self.hot.canvas.to_mermaid(),
            "nodes": list(self.hot.canvas.nodes),
            "path": str(self.hot.canvas_path),
        }

    def tooltips(self, lang: str = "en") -> dict[str, Any]:
        out: dict[str, Any] = {}
        for tip_id, langs in TOOLTIPS.items():
            block = langs.get(lang) or langs.get("en")
            if block:
                out[tip_id] = dict(block)
        return out
