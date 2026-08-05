# Plan vs Code — ehrlicher Abgleich

Stand: 2026-08-05 · Repo `gnom-hub-v1`

Quellen: `docs/V1_SCOPE.md`, `docs/PRE_PLAN.md` vs. `src/gnom_hub/`.

---

## Legende

| Symbol | Bedeutung |
|--------|-----------|
| ✅ | im Wesentlichen umgesetzt |
| 🟡 | teilweise / dünn / Demo-Qualität |
| ❌ | fehlt oder nur Attrappe |

---

## A) V1_SCOPE (was rein sollte)

| Anforderung | Code | Status | Kommentar |
|-------------|------|--------|-----------|
| Frei brainstormen | `BrainstormAgent` | 🟡 | LLM/Stub vorhanden; Qualität abhängig von Prompt/Key |
| Destillieren | `CoordinatorAgent.distill` | 🟡 | Ja, aber keine eigene „Destill“-Karte (Plan: Stufe, nicht Agent) |
| Coordinator steuert 1–2 Worker | `CoordinatorAgent.plan` + `WorkerAgent` | 🟡 | Ja; Worker nicht dynamisch erzeugt (fix) |
| Desktop-UI steuern | `ui/static/*` | 🟡 | Layout-Maße ok; viel Feature-Chrome, Kern wirkt dünn |
| 4 feste Agenten + 2 Worker | `AgentManager` | ✅ | Worker 3/4 nur UI-Slots (parked) |
| Doppelklick-Toggle außer Memory | `app.js` + `AgentManager.toggle` | ✅ | |
| Flex-Presets Security/Neutral/Researcher | `set_flex_preset` | 🟡 | API + Shift+Dblclick; kein Preset-UI-Dropdown |
| Live-Status EventBus | `agent.status` / `agent.activity` | 🟡 | Events da; UI-Pulse nur stage-basiert |
| LLM-Manager + DeepSeek | `llm/*` | ✅ | |
| Pro Agent Modell+Key | `AgentState.model/api_key` | 🟡 | API ja, **keine UI** zum Setzen |
| Free-only + Budget | `LLMManager` | 🟡 | Env-Flags; **keine UI** |
| Karten 140×100, Gap 5 | CSS | ✅ | |
| Boxen 380×380, Gap 5 | CSS | ✅ | |
| Box 1 Tooltips + Clarify-Buttons | UI | 🟡 | Tooltips ok; Clarify ok |
| Box 2 Brainstorm | UI | 🟡 | Zeigt Notes; „persistent“ nur via HOT |
| Box 3 Worker | UI | 🟡 | Text-Dump, keine echte Live-Preview |
| Chat ~150px | CSS | 🟡 | teils 200px gemacht |
| Global Save | UI + `/api/save` | ✅ | |
| UI Basic English | strings | 🟡 | gemischt DE/EN in Outputs |
| Box-1 mehrsprachig vorbereitet | `tooltips.py` | 🟡 | nur `en`-Struktur |
| HOT session.json + mermaid | `memory/hot.py` | ✅ | |
| Mermaid + node_id Offload | `canvas.py` `offload.py` | ✅ | |
| **Memory-Agent immer an** | `MemoryAgent` | 🟡→fix | war nur I/O (**0 Tokens**); jetzt LLM recall+curate |
| EventBus | `core/event_bus.py` | ✅ | |
| Atomic writes, relative Pfade | memory/* | ✅ | |
| Key.txt → .env | `config/keys.py` | ✅ | |

---

## B) Warum Memory **0 Tokens** hatte (dein Punkt)

Laut Plan:

> Memory hält den roten Faden und speichert Wichtiges.  
> Memory-Agent steuert Promotion.

**Ist-Code bis eben:**

| Methode | Was passierte | LLM? | Tokens |
|---------|---------------|------|--------|
| `MemoryAgent.recall()` | liest `pipeline_context()` von Disk | ❌ | **0** |
| `MemoryAgent.store()` | `emit(pipeline.memory_hint)` → Hub schreibt JSON | ❌ | **0** |

Memory war ein **Dateimanager mit Agenten-Namen**, kein Agent.

**Soll (Plan):**

1. **Recall** vor der Pipeline: aus HOT/WARM nur Relevantes für *diesen* Auftrag (LLM-Filter)  
2. **Store** nach der Pipeline: was ist langlebig? (LLM-Curate → Promotion)

**Fix (dieser Commit):** `recall(user_text)` + `store()` rufen bei vorhandenem Key `self.ask(...)` → Tokens unter Agent-ID **`memory`**.

---

## C) Pre-Plan vs. V1_SCOPE — was wir falsch priorisiert haben

V1_SCOPE sagt explizit **draußen**:

- WARM / COLD  
- Vector  
- Computer-Use  
- Plugin/MCP  
- God-Mode  
- Workspace  

**Trotzdem im Code (viel Fläche, wenig Kern-Qualität):**

| Modul | Pfad | V1_SCOPE |
|-------|------|----------|
| WARM | `memory/warm.py` | ❌ draußen |
| COLD | `memory/cold.py` | ❌ draußen |
| Vector | `memory/vector_store.py` | ❌ draußen |
| Computer-Use | `computer_use/*` | ❌ draußen |
| Plugins/MCP | `plugins/*` | ❌ draußen |
| God-Mode | `security/god_mode.py` | ❌ draußen (Pre-Plan optional) |
| Workspace | `memory/workspace.py` | ❌ draußen |
| Telegram | `telegram/*` | Pre-Plan optional ok |

**Kern laut Plan war unterimplementiert**, Rand-Features überimplementiert.

---

## D) Pre-Plan UI-Details (oft vergessen)

| Plan | Code |
|------|------|
| Karte: Tokenverbrauch | 🟡 tok-Feld, nur wenn LLM-Call auf Agent-ID |
| Karte: aktuelle LLM | 🟡 default model string |
| Karte: Online/Offline | ❌ fehlt |
| Karte: TTS-Checkbox | ❌ fehlt |
| 1px Rahmen pulsiert | 🟡 `is-active` pulse |
| Box-Rahmen Farbe des aktiven Agenten | ❌ fehlt |
| Spracheingabe im Chat | ❌ fehlt |
| System-Button | ❌ fehlt (nur Help) |
| Destillation fragt in Box 1 | ✅ Buttons |
| Chat durchgängiger Faden | 🟡 Log ja; kein Thread-Modell |

---

## E) Pipeline-Regel aus dem Plan

> Coordinator und Worker bekommen nur den sauberen, destillierten Kontext + das Nötige aus dem Memory

| | |
|--|--|
| Soll | Memory filtert → Distill reinigt → Workers nur Req + Memory-Slice |
| Ist früher | alles + Müll-WARM + Flex-Roman in Requirements |
| Ist jetzt | Memory-LLM-Recall; Flex nur 1 Zeile; Workers bekommen Requirements |

Noch nicht perfekt: kein harter Kontext-Contract / Token-Budget pro Stage.

---

## F) Nächste echte Lücken (Priorität)

1. **Memory-Tokens sichtbar** nach Live-Lauf (recall+curate) — Fix im Code  
2. Online/Offline + TTS-Checkbox auf Karten (Plan §6)  
3. Box-Rahmenfarbe = aktiver Agent  
4. Per-Agent Modell/Key in UI  
5. System-Panel (Keys, free_only, budget)  
6. Rand-Features (WARM/COLD/…) hinter Feature-Flags / aus V1-Default raus  

---

*Dieses Dokument ist die SSOT für „was fehlt noch am Plan“.*
