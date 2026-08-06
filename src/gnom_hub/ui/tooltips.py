"""Box 1 tooltip registry – multi-language (en + de).

Shape: { id: { lang: { title, how_to, example } } }
"""

from __future__ import annotations

from typing import TypedDict


class TooltipText(TypedDict):
    title: str
    how_to: str
    example: str


# id → lang → text
TOOLTIPS: dict[str, dict[str, TooltipText]] = {
    "brainstorm": {
        "en": {
            "title": "Brainstorm",
            "how_to": "Free idea partner. Send chats to brainstorm; click card to tune; double-click toggles.",
            "example": "Chat about a logo → ideas appear in Box 2. Press Execute when ready for workers.",
        },
        "de": {
            "title": "Brainstorm",
            "how_to": "Freier Ideenpartner. Chat = Brainstorm; Klick = Tuning; Doppelklick = an/aus.",
            "example": "Über ein Logo chatten → Ideen in Box 2. Execute startet die Worker.",
        },
    },
    "memory": {
        "en": {
            "title": "Memory",
            "how_to": "Always on. Session facts, Mermaid canvas, recall/curate with LLM tokens.",
            "example": "After Execute, durable facts are stored so later chats stay consistent.",
        },
        "de": {
            "title": "Memory",
            "how_to": "Immer an. Session-Fakten, Mermaid-Canvas, LLM-Recall/Curate.",
            "example": "Nach Execute bleiben wichtige Fakten für spätere Chats erhalten.",
        },
    },
    "flex": {
        "en": {
            "title": "Flex",
            "how_to": "Security / Neutral / Researcher preset (header dropdown). Reviews before workers.",
            "example": "Security → lists risks; then Coordinator assigns workers.",
        },
        "de": {
            "title": "Flex",
            "how_to": "Preset Security / Neutral / Researcher (Dropdown oben). Prüft vor den Workern.",
            "example": "Security → listet Risiken; danach verteilt der Coordinator Aufgaben.",
        },
    },
    "coordinator": {
        "en": {
            "title": "Coordinator",
            "how_to": "Distills requirements and assigns 1–2 workers. Runs on Execute.",
            "example": "After brainstorm, Execute → requirements + worker tasks.",
        },
        "de": {
            "title": "Coordinator",
            "how_to": "Destilliert Anforderungen und steuert 1–2 Worker. Läuft bei Execute.",
            "example": "Nach Brainstorm → Execute → Requirements + Worker-Aufgaben.",
        },
    },
    "worker1": {
        "en": {
            "title": "Worker 1",
            "how_to": "First execution slot. Results in Box 3; HTML gets Preview/Source.",
            "example": "Assigned 'draft HTML' → full page appears in Box 3 + Workspace temp.",
        },
        "de": {
            "title": "Worker 1",
            "how_to": "Erster Ausführungs-Slot. Ergebnisse in Box 3; HTML mit Preview/Source.",
            "example": "Aufgabe „HTML entwerfen“ → Seite in Box 3 + Workspace Temp.",
        },
    },
    "worker2": {
        "en": {
            "title": "Worker 2",
            "how_to": "Second execution slot. Parallel task from Coordinator.",
            "example": "Worker 1 drafts page, Worker 2 adds structure or checklist.",
        },
        "de": {
            "title": "Worker 2",
            "how_to": "Zweiter Slot. Parallele Aufgabe vom Coordinator.",
            "example": "Worker 1 baut die Seite, Worker 2 ergänzt Struktur/Checkliste.",
        },
    },
    "worker3": {
        "en": {
            "title": "Worker 3 (later)",
            "how_to": "Reserved slot. v1 uses at most two workers.",
            "example": "Shows as on · later until more workers ship.",
        },
        "de": {
            "title": "Worker 3 (später)",
            "how_to": "Reservierter Slot. v1 nutzt maximal zwei Worker.",
            "example": "Anzeige „on · later“ bis mehr Worker kommen.",
        },
    },
    "worker4": {
        "en": {
            "title": "Worker 4 (later)",
            "how_to": "Reserved slot. v1 uses at most two workers.",
            "example": "Shows as on · later until more workers ship.",
        },
        "de": {
            "title": "Worker 4 (später)",
            "how_to": "Reservierter Slot. v1 nutzt maximal zwei Worker.",
            "example": "Anzeige „on · later“ bis mehr Worker kommen.",
        },
    },
    "box1": {
        "en": {
            "title": "Box 1",
            "how_to": "Mouse over or click agents/controls — explanation shows here.",
            "example": "Hover or click Memory → explanation in Box 1.",
        },
        "de": {
            "title": "Box 1",
            "how_to": "Maus über Agenten/Controls oder Klick — Erklärung hier.",
            "example": "Memory hovern oder klicken → Erklärung in Box 1.",
        },
    },
    "box2": {
        "en": {
            "title": "Box 2",
            "how_to": "Dialogue turns, flex notes, distilled requirements.",
            "example": "You + Brainstorm messages stack here until Execute.",
        },
        "de": {
            "title": "Box 2",
            "how_to": "Dialog-Turns, Flex-Notizen, destillierte Anforderungen.",
            "example": "Du + Brainstorm erscheinen hier bis Execute.",
        },
    },
    "box3": {
        "en": {
            "title": "Box 3",
            "how_to": "Worker 1/2 panels with HTML Preview + Source.",
            "example": "After Execute, landing-page HTML renders in Preview.",
        },
        "de": {
            "title": "Worker-Ergebnisse (Box 3)",
            "how_to": "Worker-1/2-Panels mit HTML Preview + Source.",
            "example": "Nach Execute: Landingpage-HTML im Preview.",
        },
    },
    "chat": {
        "en": {
            "title": "Chat",
            "how_to": "Send = brainstorm turn. Execute = full worker pipeline. Mic = speech-to-text.",
            "example": "Type ideas freely, then press green Execute.",
        },
        "de": {
            "title": "Chat",
            "how_to": "Send = Brainstorm-Turn. Execute = Worker-Pipeline. Mic = Spracheingabe.",
            "example": "Frei brainstormen, dann grünes Execute.",
        },
    },
    "save": {
        "en": {
            "title": "Save",
            "how_to": "Global save: HOT memory, WARM facts, agent toggles/tuning.",
            "example": "Click Save after a good session so work is not lost.",
        },
        "de": {
            "title": "Save",
            "how_to": "Global speichern: HOT, WARM, Agent-Toggles/Tuning.",
            "example": "Nach guter Session speichern, damit nichts verloren geht.",
        },
    },
    "clarify": {
        "en": {
            "title": "Clarify",
            "how_to": "Answer distillation questions: Yes / No / Whatever / Later.",
            "example": "Question: 'MVP or robust?' → Yes / No / …",
        },
        "de": {
            "title": "Clarify",
            "how_to": "Destillationsfragen: Ja / Nein / Egal / Später.",
            "example": "Frage: „MVP oder robust?“ → Yes / No / …",
        },
    },
    "system": {
        "en": {
            "title": "System",
            "how_to": "Keys status, free-only, budget, default model, UI language.",
            "example": "Set UI lang DE, budget $1.00, check DeepSeek connected.",
        },
        "de": {
            "title": "System",
            "how_to": "Key-Status, Free-only, Budget, Default-Modell, UI-Sprache.",
            "example": "UI-Sprache DE, Budget 1 $, DeepSeek prüfen.",
        },
    },
    "workspace": {
        "en": {
            "title": "Workspace",
            "how_to": "Temp = agent outputs after Execute. Promote to permanent. Clear temp anytime.",
            "example": "worker1_done.html in Temp → ↑ perm to keep.",
        },
        "de": {
            "title": "Workspace",
            "how_to": "Temp = Agent-Outputs nach Execute. Promote → permanent. Temp leeren möglich.",
            "example": "worker1_done.html in Temp → ↑ perm zum Behalten.",
        },
    },
    "trace": {
        "en": {
            "title": "Trace",
            "how_to": "Light pipeline log (stages, workers, quality). No heavy spans.",
            "example": "Open Trace after Execute to see stage sequence.",
        },
        "de": {
            "title": "Trace",
            "how_to": "Leichtes Pipeline-Log (Stages, Worker, Quality). Keine Heavy-Spans.",
            "example": "Nach Execute Trace öffnen für Stage-Abfolge.",
        },
    },
}


def get_tooltip(tooltip_id: str, lang: str = "en") -> TooltipText | None:
    """Return tooltip text for id+lang, falling back to en."""
    entry = TOOLTIPS.get(tooltip_id)
    if not entry:
        return None
    return entry.get(lang) or entry.get("en")
