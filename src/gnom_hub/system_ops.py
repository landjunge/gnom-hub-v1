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
        }

    def help_text(self) -> dict[str, Any]:
        topics = [
            {
                "id": "senden",
                "label": "Senden",
                "points": [
                    "Senden und Enter bedeuten nur reden.",
                    "Die Nachricht geht an den Empfänger mit dem Flag (Brain, Coord, Flex, A1…).",
                    "Die Antwort erscheint in Box 2, im Chat des Empfängers.",
                    "Kartenklick ändert das Sendeziel nicht.",
                ],
                "nicht": "Senden startet keine Worker, keine Werkzeuge und keine Dateiänderung.",
            },
            {
                "id": "arbeit",
                "label": "Arbeit",
                "points": [
                    "Arbeit starten oder Ctrl/⌘+Enter startet Distill und die Worker.",
                    "Offene Fragen stehen in Box 1. Ja gilt nur für die sichtbare Frage.",
                    "Ergebnisse landen in Box 3.",
                    "Abbrechen: Esc oder Abbrechen, solange ein Job läuft.",
                ],
                "nicht": "Send und Enter starten keine Arbeit.",
            },
            {
                "id": "boxen",
                "label": "Boxen",
                "points": [
                    "Box 1 links: Rückfragen, Entscheidungen, Flex-Karten.",
                    "Box 2 Mitte: Antworten. Reiter Brain, Flex, Coord, Mem, A1–A4.",
                    "Box 3 rechts: Worker-Seiten. Sicht = Seite, Code = Text.",
                    "Weg, Neu, Behalten stehen in Box 3 unter den Reitern.",
                ],
                "nicht": "Eine Box ist keine Textwand und kein JSON.",
            },
            {
                "id": "god",
                "label": "God",
                "points": [
                    "God geht nur über den roten Badge oben rechts.",
                    "God aus: Trockenlauf. Maus, Tastatur, Shell greifen nicht wirklich.",
                    "God an: echte Desktop-Aktionen, nach einer Nachfrage.",
                    "Werkzeuge ohne God bleiben Trockenlauf.",
                ],
                "nicht": "Im System-Fenster gibt es keinen God-Schalter.",
            },
            {
                "id": "dateien",
                "label": "Dateien",
                "points": [
                    "Behalten in Box 3 schreibt erst nach bestätigtem Rücklesen.",
                    "Workspace zeigt drei Spalten: Temp, Dauerhaft, Behalten.",
                    "HTML zuerst als Sicht, daneben Code.",
                    "Löschen fragt nach. Zip erst, wenn die Datei erzeugt ist.",
                ],
                "nicht": "Persönliche Dateien liegen nicht im Git und nicht im Repo.",
            },
            {
                "id": "tastatur",
                "label": "Tastatur",
                "points": [
                    "Enter = senden (reden).",
                    "Ctrl/⌘+Enter = Arbeit starten.",
                    "Ctrl/⌘+S = speichern. Esc = Overlay zu oder Job abbrechen.",
                    "Mikrofon füllt die Eingabe und bleibt an, bis du es ausklickst.",
                ],
                "nicht": "Mikrofon und Sprache senden nicht von allein.",
            },
        ]
        return {
            "title": "Hilfe",
            "topics": topics,
            "how_to": topics[0]["points"][0],
            "example": "Senden = reden. Arbeit starten = Worker. God nur Badge.",
            "pipeline": "Brainstorm → Execute → Distill → Flex → Workers (1–4) → Quality → Memory",
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
