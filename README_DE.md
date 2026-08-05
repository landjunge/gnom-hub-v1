# Gnom-Hub

**Lokaler Multi-Agenten-Steuerungs-Hub** — erst denken, dann handeln.

| | |
|--|--|
| **Version** | 3.7.1 |
| **Stack** | Python ≥3.10 · FastAPI · Desktop-UI |
| **Standard** | `http://127.0.0.1:8080/` |
| **LLM** | DeepSeek (`deepseek-v4-flash`) · optional Ollama |
| **Lizenz** | Private Nutzung |

**English:** [README.md](README.md)

---

## Warum Gnom?

Viele Agenten-Tools **starten sofort** (Chat → Tools → Chaos) oder stecken in schweren Frameworks. Gnom folgt einer klaren Produktregel:

> **Frei brainstormen. Ausführen nur, wenn du Execute drückst.**

Diese Trennung ist das Kernprodukt.

### Was besonders gut ist

| Stärke | In der Praxis |
|--------|----------------|
| **Brainstorm → Execute** | Chat bleibt explorativ. Worker (Kosten, Dateien, Nebenwirkungen) starten erst mit **Execute**. |
| **Sichtbarer Multi-Agenten-Tisch** | Acht feste Rollen als Karten + drei Arbeitsboxen — du siehst immer *wer* arbeitet und *wo* das Ergebnis landet. |
| **Eine Seite, nicht vier** | Bei Landing/HTML: **ein** Worker, **eine** komplette HTML-Datei — kein Fragment-Salat. |
| **Lokal & portabel** | Läuft auf deinem Rechner; Keys in `Key.txt`; USB-tauglich; kein Cloud-Zwang. |
| **Sicherheit by default** | Maus/Tastatur/Shell nur **dry-run**, bis **God-Mode** bewusst an ist. |
| **Operator-tauglich** | HOT/WARM/COLD-Memory, Workspace, Backups, Packs, Jobs, Light-Trace, Budget-Schutz — für echte Sessions. |
| **Schlanke Architektur** | Ein fester Orchestrator. Presets konfigurieren das Team — sie erfinden **keine** zweite Agenten-Runtime. |

### Für wen

- Builder mit **Desktop-Steuerfläche** für Multi-Agenten-Arbeit  
- Leute, die **HTML/Seiten-Ergebnisse** direkt in der Box previewen wollen  
- Operatoren, die **Kosten, Keys, Cancel und Überblick** brauchen — nicht nur „Vibe-Chat“  

### Nicht für

- Vollautonome Agenten ohne menschliche Freigabe  
- Drop-in-Ersatz für LangGraph/CrewAI-Research-Stacks  
- Stille PC-Steuerung bei jeder Chat-Nachricht  

---

## Schnellstart

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Keys in Key.txt  →  docs/KEYS_AND_MODELS.md
./scripts/start.sh
# öffnen: http://127.0.0.1:8080/
```

### Chat

| Steuerung | Aktion |
|-----------|--------|
| **Send** | Brainstorm-Turn → Box 2 |
| **Execute** | Distill → Flex → Coordinator → Worker → Box 3 |
| **Send+Exec** | beides nacheinander |
| **Mic** | Sprache → Text |
| **Cancel** | laufenden Job abbrechen |

### Boxen

| Box | Rolle |
|-----|--------|
| **1 · Arounder** | Hilfe + Clarify (Yes / No / Whatever / Later) |
| **2 · Brainstorm** | Mehrturn-Dialog |
| **3 · Workers** | Ergebnis (HTML-Preview oder Text) |

### Computer-Use

Desktop-Steuerung unter **Tools → Computer use** (Inspect · Click · Type · Shell).

| Modus | Verhalten |
|-------|-----------|
| God **aus** | nur Dry-Run (sicher) |
| God **an** | echte Maus / Tastatur / Allowlist-Shell |

Optional: `pip install -e ".[computer]"` — siehe [`docs/TOOLS_PORTFOLIO.md`](docs/TOOLS_PORTFOLIO.md).

---

## Architektur (kurz)

```
UI  ──►  Hub (FastAPI)  ──►  Orchestrator
                │                 │
                ├─ Agenten (8)    ├─ Brainstorm
                ├─ LLM-Manager    ├─ Distill / Flex
                ├─ Memory HOT/WARM/COLD
                ├─ Workspace
                └─ Computer-Use (+ God-Mode)
```

**Agenten:** brainstorm · memory · flex · coordinator · worker1–4  

**Stages:** memory → brainstorm → distill → [clarify] → flex → coordinate → work → done  

---

## Qualität & Mitarbeit

```bash
./scripts/quality_check.sh
python scripts/basic_tests.py
python scripts/user_landing_e2e.py
```

Coding-Agenten: [`AGENTS.md`](AGENTS.md) — ruff + pytest grün vor jedem Push; keine Secrets committen.

---

## Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [README.md](README.md) | English README |
| [AGENTS.md](AGENTS.md) | Coding-Regeln / Push-Gate |
| [docs/KEYS_AND_MODELS.md](docs/KEYS_AND_MODELS.md) | Keys & Modell-IDs |
| [docs/BASIC_USER_TEST.md](docs/BASIC_USER_TEST.md) | Canonical User-E2E |
| [docs/STABILITY.md](docs/STABILITY.md) | Stabilitäts-Checkliste |
| [docs/TOOLS_PORTFOLIO.md](docs/TOOLS_PORTFOLIO.md) | Computer-Use-Bibliotheken |
| [docs/WORKFLOWS_AND_PRESETS.md](docs/WORKFLOWS_AND_PRESETS.md) | Team-Presets & plan_mode |
| [docs/V1_SCOPE.md](docs/V1_SCOPE.md) | Produkt-Scope |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Release-Historie |

---

## Lizenz

Private Nutzung.
