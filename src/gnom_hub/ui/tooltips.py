"""Box 1 tooltip registry – multi-language ready (en first).

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
            "how_to": "Free idea agent. Double-click the card to enable or disable. Ideas land in Box 2.",
            "example": "You chat about a logo → Brainstorm lists colors, styles, and slogans in Box 2.",
        }
    },
    "memory": {
        "en": {
            "title": "Memory",
            "how_to": "Always on. Keeps session facts and the Mermaid canvas. Cannot be toggled off.",
            "example": "After a task, Memory stores key decisions so later chats stay consistent.",
        }
    },
    "flex": {
        "en": {
            "title": "Flex",
            "how_to": "Role-switch agent (Security, Neutral, Researcher, …). Double-click to toggle.",
            "example": "Set Flex to Security → it reviews plans for risks before workers run.",
        }
    },
    "coordinator": {
        "en": {
            "title": "Coordinator",
            "how_to": "Plans work and drives 1–2 workers. Double-click to toggle.",
            "example": "After distillation, Coordinator splits tasks and fills Box 3 via workers.",
        }
    },
    "worker1": {
        "en": {
            "title": "Worker 1",
            "how_to": "First execution slot. Double-click to toggle. Results show in Box 3.",
            "example": "Coordinator assigns 'draft outline' → Worker 1 writes it into Box 3.",
        }
    },
    "worker2": {
        "en": {
            "title": "Worker 2",
            "how_to": "Second execution slot. Double-click to toggle. Results show in Box 3.",
            "example": "Parallel research task runs on Worker 2 while Worker 1 drafts.",
        }
    },
    "worker3": {
        "en": {
            "title": "Worker 3 (parked)",
            "how_to": "Slot reserved for later. v1 uses at most two workers. Double-click still toggles local state.",
            "example": "Shows as off/parked until more workers are enabled in a later release.",
        }
    },
    "worker4": {
        "en": {
            "title": "Worker 4 (parked)",
            "how_to": "Slot reserved for later. v1 uses at most two workers. Double-click still toggles local state.",
            "example": "Shows as off/parked until more workers are enabled in a later release.",
        }
    },
    "box1": {
        "en": {
            "title": "Arounder (Box 1)",
            "how_to": "Hover cards and controls to see title, how-to, and example here. Clarify Yes/No/Whatever/Later when asked.",
            "example": "Hover Memory → this panel explains what Memory does.",
        }
    },
    "box2": {
        "en": {
            "title": "Brainstorm (Box 2)",
            "how_to": "Shows free thoughts and distilled summary from the Brainstorm agent.",
            "example": "Ideas stream here while you chat; distillation may ask questions in Box 1.",
        }
    },
    "box3": {
        "en": {
            "title": "Worker results (Box 3)",
            "how_to": "Live output from active workers driven by the Coordinator.",
            "example": "Drafts, research notes, and task results appear here.",
        }
    },
    "chat": {
        "en": {
            "title": "Chat",
            "how_to": "Type a message and press Send. Starts the brainstorm pipeline.",
            "example": "Type: 'Help me plan a weekend trip' → Send.",
        }
    },
    "save": {
        "en": {
            "title": "Save",
            "how_to": "One global Save. Persists session / memory state (wired later via API).",
            "example": "Click Save after a good brainstorm so work is not lost.",
        }
    },
    "clarify": {
        "en": {
            "title": "Clarify",
            "how_to": "Answer distillation questions with Yes, No, Whatever, or Later.",
            "example": "Question: 'Use dark theme?' → Yes / No / Whatever / Later.",
        }
    },
}


def get_tooltip(tooltip_id: str, lang: str = "en") -> TooltipText | None:
    """Return tooltip text for id+lang, falling back to en."""
    entry = TOOLTIPS.get(tooltip_id)
    if not entry:
        return None
    return entry.get(lang) or entry.get("en")
