# Konkrete Agenten-Definition (Gnom-Hub v1)

**Source of truth = Python.** UI-Karten sind Spiegel + Tuning.  
Dateien: `agents/models.py`, `agents/manager.py`, `agents/roles.py`, `agents/roles_ext.py`, `agents/base.py`

---

## 1. Registry (8 feste Slots)

| # | id | Name | role | Farbe (CSS/UI) | Enabled default | Toggleable | Preset |
|---|-----|------|------|----------------|-----------------|------------|--------|
| 1 | brainstorm | Brainstorm | brainstorm | red / `#ff0000` | an | ja | — |
| 2 | memory | Memory | memory | blue / `#0066ff` | an | nein (locked on) | — |
| 3 | flex | Flex | flex | yellow / `#ffff00` | an | ja | personal |
| 4 | coordinator | Coordinator | coordinator | green / `#00cc44` | an | ja | — |
| 5 | worker1 | Worker 1 | worker | cyan / `#00d4ff` | an | ja | — |
| 6 | worker2 | Worker 2 | worker | violet / `#7c3aed` | an | ja | — |
| 7 | worker3 | Worker 3 | worker | magenta / `#ff2d95` | an | ja | — |
| 8 | worker4 | Worker 4 | worker | orange / `#ff6600` | an | ja | — |

Gebaut in `AgentManager._build_agents()`.

**Tune-Felder** (`AgentState`): `model`, `api_key`, `system_prompt` (nur Extra-Anhang),  
`temperature`, `top_p`, `max_tokens`, `frequency_penalty`, `presence_penalty`, `tts`.

---

## 2. Globale Identität (jeder LLM-Call)

Aus `base.py` → vor jedem Role-System-Prompt:

> Du bist ein Agent in Gnom-Hub v1 (Pipeline: chat → brainstorm → distill → flex → coordinator → workers → memory).  
> Kein Notes-App, kein localStorage-Spielzeug. Kein Umdefinieren von Gnom-Hub. Nur User-Task.

User-Extra-Prompt aus der Karte wird **angehängt**, ersetzt die Code-Rolle **nicht**.

---

## 3. Rollen-Prompts (Code-Default)

### Brainstorm (`BrainstormAgent.run`)

- Scharfer Denkpartner, kein „5–8 Bullets“-Bot
- Workers erst nach klarem Bau-Auftrag / ja-ok
- Sprache DE/EN, History nutzen, Thread vorantreiben
- Kreativ: 3–6 Winkel mit WHY, kein fertiger Code
- Diagnose Hub: echte Failure-Modes, keine Fake-Todo-Apps
- Bau-Angebot genau eine Zeile: „Soll ich das jetzt umsetzen?“
- Defaults: temp **0.9** (Diagnose **0.35**), max_tokens **700** / **900**

### Flex (`FlexAgent`)

- Personal Companion: Fakten aus User-Zeilen → WARM
- Presets: `personal` | `security` | `neutral` | `researcher`
- `nudge_gaps`: fehlende/falsche Worker-Ergebnisse → Korrekturzeilen an worker/coordinator
- Heuristik + LLM (temp ~0.15)

### Coordinator (`CoordinatorAgent`)

- **distill:** 4–7 Requirement-Zeilen, DoD, testbar; temp **0.3**, max_tokens **400**
- **plan:** Tasks für enabled Workers (`full_page_html`, `plan_qa`, `diagnosis`, default)
- ggf. Clarify-Frage (MVP vs gründlich)

### Worker 1–4 (`WorkerAgent` — gleiche Klasse, andere id/name)

- Konkretes Ergebnis: Plan, Checkliste, Draft oder volles HTML
- Priorität: Struktur → Interaktion → Empty/Error → CSS zuletzt (~30 %)
- HTML: ein File `<!DOCTYPE` … `</html>`, mind. eine echte Interaction
- max_tokens **3200** HTML / **1800** sonst, temp **0.45**

### Memory (`MemoryAgent`)

- Immer an, nicht togglbar
- `recall` / Kontext aus HOT+WARM, Garbage-Filter
- LLM kuratiert Fakten für Pipeline-Context; kein HTML-Müll in WARM

---

## 4. Pipeline-Zuordnung

```
Send    → Brainstorm (+ Flex absorb facts)
Execute → Coordinator distill → Flex → Coordinator plan → Workers → Memory/Flex nudge
```

Enabled Workers = `enabled_workers()` (bis 4).

---

## 5. UI-Spiegel (nicht die echte Rolle)

`parts/00-preamble.js` · `AGENTS[]` + `DEFAULT_PROMPTS` = Hinweise für Box1/Tune.  
Echte Logik = Python `roles*.py`.

---

## 6. Datei-Karte

| Was | Datei |
|-----|--------|
| IDs, Farben, State | `agents/models.py` |
| 8er-Registry, Toggle, Flex-Preset | `agents/manager.py` |
| Brainstorm, Flex | `agents/roles.py` |
| Coordinator, Worker, Memory | `agents/roles_ext.py` |
| HUB_IDENTITY, ask(), Tuning-Merge | `agents/base.py` |
| Persist/Tune API | `agent_ops.py` |

---

*Siehe auch: [LAYERS_FOR_AI.md](./LAYERS_FOR_AI.md)*
