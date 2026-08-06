# Konkrete Agenten-Definition (Gnom-Hub v1)

**Source of truth = Python.** UI-Karten sind Spiegel + Tuning.  
Dateien: `agents/models.py`, `agents/manager.py`, `agents/roles.py`, `agents/roles_ext.py`, `agents/base.py`

---

## 1. Registry (8 feste slots)

| # | id | Name | role | Farbe (CSS/UI) | Enabled default | Toggleable | Preset |
|---|-----|------|------|----------------|-----------------|------------|--------|
| 1 | brainstorm | Brainstorm | brainstorm | red / `#ff0000` | an | ja | — |
| 2 | memory | Memory | memory | blue / `#0066ff` | an | nein (locked on) | — |
| 3 | flex | Flex | flex | yellow / `#ffff00` | an | **nein (locked on, fixed role)** | — (kein Preset) |
| 4 | coordinator | Coordinator | coordinator | green / `#00cc44` | an | ja | — |
| 5 | worker1 | Worker 1 | worker | cyan / `#00d4ff` | an | ja | — |
| 6 | worker2 | Worker 2 | worker | violet / `#7c3aed` | an | ja | — |
| 7 | worker3 | Worker 3 | worker | magenta / `#ff2d95` | an | ja | — |
| 8 | worker4 | Worker 4 | worker | orange / `#ff6600` | an | ja | — |

Gebaut in `AgentManager._build_agents()`.

**Tune-Felder** (`AgentState`): `model`, `api_key`, `system_prompt` (nur Extra-Anhang; **bei Flex ignoriert für Rollen-Logik**),  
`temperature`, `top_p`, `max_tokens`, `frequency_penalty`, `presence_penalty`, `tts`.

**TTS default:** `tts=true` für **brainstorm** und **flex** (von vornherein an). Gedanken/Chat-Beiträge dieser beiden Agenten werden vorgelesen.

---

## 2. Globale Identität (jeder LLM-Call)

Aus `base.py` → vor jedem Role-System-Prompt:

> Du bist ein Agent in Gnom-Hub v1 (Pipeline: chat → brainstorm → distill → flex → coordinator → workers → memory).  
> Kein Notes-App, kein localStorage-Spielzeug. Kein Umdefinieren von Gnom-Hub. Nur User-Task.

User-Extra-Prompt aus der Karte wird **angehängt**, ersetzt die Code-Rolle **nicht**.  
**Ausnahme Flex:** Rolle und System-Prompt sind **nur im Code** fest; UI-Tune ändert die Flex-Rolle nicht.

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
- **TTS:** default an

### Flex (`FlexAgent`) — **FIXED SYSTEM AGENT**

Flex ist **kein** freier Companion-Preset mehr. Er ist **fest verdrahtet**, **nicht togglebar**, **kein Preset-Wechsel**, Rolle **nicht über UI änderbar**.

#### Drei unveränderliche Jobs

1. **Wünsche speichern** – nur was der User schreibt, landet dauerhaft in der DB  
2. **Andere Agenten nachziehen** – wenn Brainstorm/Coordinator/Worker Anweisungen vergessen, schiebt Flex Fakten und offene Aufgaben nach  
3. **Für den User handeln** – im Brainstorm mitschreiben und Execute anstoßen

#### Was Flex speichern darf

| Speichert | Speichert **nicht** |
|-----------|---------------------|
| Explizite User-Wünsche / Regeln | Worker-HTML, Code-Dumps |
| Gestellte Aufgaben + Status (offen/erledigt) | Brainstorm-Geschwätz ohne User-Intent |
| Korrekturen („so und nicht anders“) | Pipeline-Meta, Test-Müll |

- **Speicherort:** WARM/dauerhafte Facts + optional `flex_wishes` (HOT/DB)  
- Nie überschreiben ohne neuen User-Input  
- Nie „vergessen“ bei Clear von HOT  
- Clear/Reset löscht **keine** Flex-Wünsche (außer expliziter User-Befehl „Wünsche löschen“)

#### Verhalten im Pipeline-Flow

```
Chat / Brainstorm
  → Flex liest User-Text, extrahiert Wünsche, schreibt in DB
  → Flex darf selbst Chat-Zeilen schreiben (Stellvertreter)

Wenn andere abweichen / vergessen
  → Flex injectet: gespeicherte Wünsche + offene Aufgaben
  → an Coordinator / Workers (nudge), klar und kurz

Execute
  → Flex darf Execute auslösen (oder User sagt „Execute“ = Trigger)
  → nur wenn: klare Aufgabe + User-Wünsche erfüllt werden sollen
  → kein wildes Auto-Execute bei jedem Chat
```

#### Feste Regeln (Code, nicht verhandelbar)

1. Source of truth = geschriebener User-Text, nicht Agent-Fantasie  
2. Flex-Prompt und Rolle **nur im Code**, nicht aus UI-Tune  
3. Clear/Reset löscht nicht Flex-Wünsche (außer explizit)  
4. Execute nur bei klarer Aufgabe + Wünschen  
5. Sprache DE/EN wie der User schreibt  
6. **TTS:** default an

#### Code-API (Ziel)

- `store_wish` / `list_open_tasks` / `nudge_context` (Memory, garbage-filter bleibt)  
- Hooks: nach User-Turn → Flex absorb; vor Worker → Flex nudge; Flex setzt optional `execute` flag  
- UI: Flex-Karte nur Anzeige — kein Toggle, kein Prompt-Edit, kein Preset

#### Legacy (entfernen / wirkungslos)

- Presets `personal` | `security` | `neutral` | `researcher` → **weg**  
- Freier Companion-Essay-Output → ersetzt durch wish/store/nudge/act

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
- Flex-Wünsche bleiben in WARM auch wenn HOT cleared wird

---

## 4. Pipeline-Zuordnung

```
Send    → Brainstorm (+ Flex absorb wishes / optional chat write)
Execute → Coordinator distill → Flex nudge/review → Coordinator plan → Workers → Memory/Flex nudge
Flex    → may request execute when task + wishes are clear
```

Enabled Workers = `enabled_workers()` (bis 4).

---

## 5. UI-Spiegel (nicht die echte Rolle)

`parts/00-preamble.js` · `AGENTS[]` + `DEFAULT_PROMPTS` = Hinweise für Box1/Tune.  
Echte Logik = Python `roles*.py`.

**Flex:** UI darf **nicht** Rolle, Toggle, Preset oder system_prompt der Flex-Rolle ändern.  
TTS-Checkbox für Flex/Brainstorm: default **on** (User kann stummschalten, Rolle bleibt).

---

## 6. Datei-Karte

| Was | Datei |
|-----|--------|
| IDs, Farben, State | `agents/models.py` |
| 8er-Registry, Toggle, Flex **locked** | `agents/manager.py` |
| Brainstorm, Flex (fixed) | `agents/roles.py` |
| Coordinator, Worker, Memory | `agents/roles_ext.py` |
| HUB_IDENTITY, ask(), Tuning-Merge | `agents/base.py` |
| Persist/Tune API | `agent_ops.py` |
| Wishes / open tasks | Memory + ggf. `flex_wishes` |

---

## 7. DoD Flex (fixed)

- [ ] Flex-Toggle/Preset weg bzw. wirkungslos
- [ ] User-Wunsch nach Clear HOT noch da
- [ ] Worker ignoriert Regel → Flex schiebt nach
- [ ] Flex schreibt im Brainstorm mit
- [ ] Flex löst Execute aus (Flag oder „Execute“-Befehl)
- [ ] TTS default on für Flex + Brainstorm

---

*Siehe auch: [LAYERS_FOR_AI.md](./LAYERS_FOR_AI.md)*
