# Gnom-Hub

**Lokaler Multi-Agenten-Steuerungs-Hub** — erst brainstormen, ausführen nur wenn du es sagst.

| | |
|--|--|
| **Version** | 3.7.1 |
| **Stack** | Python ≥3.10 · FastAPI · Desktop-SPA |
| **UI** | `http://127.0.0.1:8080/` |
| **LLM** | DeepSeek (`deepseek-v4-flash`, Thinking aus) · optional Ollama |
| **Lizenz** | Private Nutzung |

**English:** [README.md](README.md)  
**Tiefe Code-Analyse (für andere KIs):** [docs/CODE_ANALYSIS_FOR_AI.md](docs/CODE_ANALYSIS_FOR_AI.md)

---

### Screenshots

![Gnom-Hub Desktop-UI](docs/assets/gnom-hub-ui.png)

*Acht Agenten-Karten · drei Arbeitsboxen · Chat — lokal am Desktop*

![Tools · Computer use](docs/assets/gnom-hub-tools.png)

*Tools-Modal: Core-Tools + Computer-Use (Inspect / Click / Type / Shell)*

---

## Warum Gnom?

Viele Agenten-Produkte **starten Tools bei jeder Nachricht** oder verstecken Steuerung in schweren Frameworks. Gnom folgt einer klaren Produktregel:

> **Frei brainstormen. Ausführen nur, wenn du Execute drückst.**

Diese Trennung ist das Kernprodukt: Exploration bleibt günstig und umkehrbar; Worker (Kosten, Dateien, Nebenwirkungen) starten nur bewusst.

### Was besonders gut ist

| Stärke | In der Praxis |
|--------|----------------|
| **Brainstorm → Execute** | Send ist nur Dialog. Worker laufen erst nach **Execute** (oder Send+Exec). |
| **Sichtbarer Multi-Agenten-Tisch** | Acht feste Rollen als Karten + drei Boxen — du siehst wer arbeitet und wo das Ergebnis landet. |
| **Eine HTML-Seite, nicht vier** | Bei Landing/Page: **ein** Worker, **eine** komplette Single-File-HTML. |
| **Lokal & portabel** | Läuft auf deinem Rechner; Keys in `Key.txt`; USB-taugliches `data/`; kein Cloud-Zwang. |
| **Sicherheit by default** | Maus / Tastatur / Shell nur **Dry-Run**, bis **God-Mode** bewusst an ist. |
| **Operator-Ops** | HOT / WARM / COLD-Memory, Workspace, Backups, Session-Packs, Jobs, Soft-Cancel, Light-Trace, Budget-Schutz. |
| **Schlanke Orchestrierung** | Eine feste Pipeline. Team-/Worker-**Presets** + `plan_mode` — keine zweite Workflow-Engine. |
| **Sauberes Memory** | Dauerhafte Fakten nach WARM; Flex-Wünsche (`source=flex`) überleben HOT-Clear / warm_trim-Reserve; HTML/Meta-Müll gefiltert. |
| **Flex als Operator-Proxy** | Gesperrter Agent: speichert nur deine Wünsche, schreibt im Brainstorm mit, kann Execute auslösen, injiziert binding wishes für Worker. |

### Für wen

- Builder mit **Desktop-Steuerfläche** für Multi-Agenten-Arbeit  
- Leute, die **HTML-Ergebnisse** direkt in der Box previewen wollen  
- Operatoren, die **Kosten, Keys, Cancel und Überblick** brauchen — nicht nur Vibe-Chat  

### Nicht für

- Vollautonome Agenten ohne menschliche Freigabe  
- Drop-in-Ersatz für LangGraph / CrewAI-Research-Stacks  
- Stille PC-Steuerung bei jeder Chat-Nachricht  

---

## Schnellstart

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Keys → Key.txt  (siehe docs/KEYS_AND_MODELS.md)
./scripts/start.sh
# öffnen: http://127.0.0.1:8080/
```

`Key.txt.example` → `Key.txt` und mindestens setzen:

- `DEEPSEEK_API_KEY` — System-Agenten (Brainstorm, Memory, Flex, Coordinator)  
- `WORKER_API_KEY` — Worker (kann derselbe Key sein)  
- `DEEPSEEK_MODEL=deepseek-v4-flash`  

Nie `Key.txt` oder `.env` committen.

Ohne API-Keys läuft die Pipeline mit **Stubs** (Tests / Smoke).

---

## Desk bedienen

### Chat-Steuerung

| Steuerung | Aktion |
|-----------|--------|
| **Send** | Ein Brainstorm-Turn → Box 2 |
| **Execute** | Distill → Flex → Coordinator-Plan → Worker → Box 3 + Memory |
| **Send+Exec** | Beides nacheinander |
| **Mic** | Browser Speech-to-Text |
| **Cancel** | Laufenden Job soft abbrechen |

### Boxen

| Box | Rolle |
|-----|--------|
| **1 · Arounder** | Hilfe / Tooltips · Clarify (Yes / No / Whatever / Later) |
| **2 · Brainstorm** | Mehrturn-Dialog |
| **3 · Workers** | Ergebnis — HTML-**Preview** / Source / Copy |

### Agenten (festes Roster)

| Agent | Rolle | Default |
|-------|------|---------|
| Brainstorm | Freier Mehrturn-Partner | an |
| Memory | Recall + dauerhafte Fakten | an (gesperrt) |
| Flex | **Fest** persönlicher Companion: Wünsche → WARM, Mitreden, Execute-Trigger, Worker-Nudge | an (**gesperrt**) |
| Coordinator | Requirements destillieren · Worker planen | an |
| Worker 1–2 | Lieferobjekte erzeugen | an |
| Worker 3–4 | Extra-Kapazität | an (toggelbar) |

### Computer-Use

**Tools → Computer use** — Inspect · Click · Type · Shell.

| Modus | Verhalten |
|-------|-----------|
| God **aus** | nur Dry-Run (sicherer Default) |
| God **an** | echte Maus / Tastatur / Allowlist-Shell |

```bash
pip install -e ".[computer]"   # optionale Extras
```

Details: [docs/TOOLS_PORTFOLIO.md](docs/TOOLS_PORTFOLIO.md).

---

## Architektur

```
Browser-SPA (app.js ← parts/* via build_ui_js.py)
       │  REST + Job-Polling
       ▼
FastAPI  ──►  Hub (~180 LOC Composition Root + Mixins)
                 ├── EventBus (sync)
                 ├── Orchestrator (Stages)
                 ├── 8 Rollen-Agenten
                 ├── LLM-Manager (DeepSeek / Ollama)
                 ├── Memory (HOT / WARM / COLD / Vector)
                 ├── Workspace · Packs · Backups · Jobs
                 └── Computer-Use-Kit (+ God-Mode)
```

Öffentliche Hub-Methoden liegen in fokussierten Mixins (`pipeline_api`, `jobs`, `session_pack`, `presets`, …). API bleibt dünn.

### Pipeline-Stages

```
memory → brainstorm → distill → [clarify] → flex → coordinate → work → done
```

- **Brainstorm** (Send): nur Dialog; Flex speichert Wünsche + schreibt mit; kann bei klarem Intent auto-Execute.  
- **Execute**: Distill → optional Clarify → Flex-Briefing + Wish-Inject → Plan → Worker → Flex-Nudge.  
- One-Shot-Pfad für Tests / Telegram (`/do`).  

### Memory-Schichten

| Schicht | Lebensdauer | Zweck |
|---------|-------------|--------|
| **HOT** | Session | Messages, Session-Fakten, Mermaid-Canvas |
| **WARM** | Dauerhaft | Langzeit-Fakten (überleben HOT-Clear / Clean) |
| **COLD** | Archiv | Gespeicherte Sessions |
| **Vector** | Dauerhaft | Hybrid BM25 + Cosine (Short-Facts; Flex-Boost) |
| **Workspace** | Artefakte | Temp / permanent nach Execute |

Clean / Reset leert HOT + Temp-Workspace + Pipeline; **WARM bleibt**, außer explizit geleert.

### Plan-Modi (Presets)

Über Team-Presets — keine zweite Orchestrierungs-Runtime:

| Modus | Verhalten |
|-------|-----------|
| `default` | Auto HTML-Full-Page wenn Task wie eine Seite wirkt; sonst LLM/Stub-Split |
| `full_page_html` | Genau **ein** Worker baut eine komplette HTML-Seite |
| `plan_qa` | Deterministische QA-Task-Templates |
| `diagnosis` | Deterministische Diagnose-Templates |

Siehe [docs/WORKFLOWS_AND_PRESETS.md](docs/WORKFLOWS_AND_PRESETS.md).

---

## Qualität & Mitarbeit

```bash
ruff check .
ruff format .
ruff format --check .
pytest tests/ -q --tb=short

# Mutationstests (Tests der Tests)
python scripts/mutation_check.py              # schnelle Helper — alle Mutanten killen
# optional tief: ./scripts/run_mutmut.sh      # siehe docs/MUTMUT.md

./scripts/quality_check.sh
python scripts/basic_tests.py          # braucht Server :8080
python scripts/user_landing_e2e.py     # Playwright + Live-Key
python -m gnom_hub.main --smoke        # Brainstorm → Execute ohne UI
```

Coding-Agenten: [AGENTS.md](AGENTS.md) — ruff + pytest grün vor jedem Push; nach jedem fertigen Schritt committen und pushen; keine Secrets committen.

Flex-Vertrag: [docs/AGENTS_DEFINITION.md](docs/AGENTS_DEFINITION.md). Tests: [docs/TESTING.md](docs/TESTING.md).

---

## Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [README.md](README.md) | English README |
| [AGENTS.md](AGENTS.md) | Coding-Regeln / Push-Gate |
| [docs/CODE_ANALYSIS_FOR_AI.md](docs/CODE_ANALYSIS_FOR_AI.md) | Volle Architektur für externe KIs |
| [docs/KEYS_AND_MODELS.md](docs/KEYS_AND_MODELS.md) | Keys & Modell-IDs |
| [docs/BASIC_USER_TEST.md](docs/BASIC_USER_TEST.md) | Canonical User-E2E |
| [docs/STABILITY.md](docs/STABILITY.md) | Stabilitäts-Checkliste |
| [docs/TOOLS_PORTFOLIO.md](docs/TOOLS_PORTFOLIO.md) | Computer-Use-Bibliotheken |
| [docs/AGENTS_DEFINITION.md](docs/AGENTS_DEFINITION.md) | Agenten-Roster · **Flex fixed** |
| [docs/WORKFLOWS_AND_PRESETS.md](docs/WORKFLOWS_AND_PRESETS.md) | Presets & plan_mode |
| [docs/TESTING.md](docs/TESTING.md) | pytest + Mutation-Überblick |
| [docs/MUTMUT.md](docs/MUTMUT.md) | mutmut-Config · Profile · Hooks |
| [docs/V1_SCOPE.md](docs/V1_SCOPE.md) | Produkt-Scope |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Release-Historie |

---

## Lizenz

Private Nutzung.
