# Gnom-Hub

**Version:** 3.7.1 · **Python:** ≥3.10 · **UI:** `http://127.0.0.1:8080/`  
**Lizenz:** private Nutzung  

**English:** [README.md](README.md)

Lokaler Multi-Agenten-Hub: zuerst **Brainstorm**, dann **Execute** für Worker.

**Nicht:** zweite LangGraph/CrewAI-Engine · keine vollautomatische PC-Steuerung nur über Chat.

---

## Pipeline

```
Send → Brainstorm (Box 2)
Execute → Distill → Flex → Coordinator → Worker → Box 3
```

Landing/HTML: **ein** Worker, **eine** HTML-Seite.

## Agenten (8 fest)

| id | Rolle | Default |
|----|-------|---------|
| brainstorm | Ideen | an |
| memory | Session-Gedächtnis | an (nicht abschaltbar) |
| flex | security / neutral / researcher | an |
| coordinator | destillieren + planen | an |
| worker1…worker4 | Ergebnisse | 1–2 an; 3–4 aus |

## Oberfläche

| Bereich | Inhalt |
|---------|--------|
| Box 1 | Hilfe + Clarify (Yes / No / Whatever / Later) |
| Box 2 | nur Brainstorm-Dialog |
| Box 3 | ein Worker-Ergebnis (bei HTML: Preview / Source / Copy) |
| Chat | Send · Execute · Send+Exec · Mic · Cancel |
| Tools | Tool-Liste + **Computer use** (Inspect / Click / Type / Shell) |
| God-Badge | echte Maus/Tastatur/Shell wenn **an** (sonst dry-run) |

## Installation

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Keys → Key.txt  (siehe Key.txt.example)
./scripts/start.sh
```

Keys & Modell: [`docs/KEYS_AND_MODELS.md`](docs/KEYS_AND_MODELS.md) · Default **`deepseek-v4-flash`**.

Computer-Use-Pakete (optional):

```bash
pip install -e ".[computer]"
# macOS OCR: brew install tesseract
python -m playwright install chromium   # für E2E-Skripte
```

Details: [`docs/TOOLS_PORTFOLIO.md`](docs/TOOLS_PORTFOLIO.md)

## Tests / Qualitäts-Gate

```bash
./scripts/quality_check.sh
# Server auf :8080:
python scripts/basic_tests.py
python scripts/user_landing_e2e.py
```

Regeln für Coding-Agenten (ruff + pytest vor jedem Push): [`AGENTS.md`](AGENTS.md)

## Doku-Index

| Datei | Thema |
|-------|--------|
| [README.md](README.md) | English README |
| [AGENTS.md](AGENTS.md) | Coding / Push-Gate |
| [docs/KEYS_AND_MODELS.md](docs/KEYS_AND_MODELS.md) | API-Keys, Modelle |
| [docs/BASIC_USER_TEST.md](docs/BASIC_USER_TEST.md) | Keyboard Landing-E2E |
| [docs/STABILITY.md](docs/STABILITY.md) | Stabilitäts-Checkliste |
| [docs/TOOLS_PORTFOLIO.md](docs/TOOLS_PORTFOLIO.md) | Computer-Use-Bibliotheken |
| [docs/WORKFLOWS_AND_PRESETS.md](docs/WORKFLOWS_AND_PRESETS.md) | Presets / plan_mode |
| [docs/V1_SCOPE.md](docs/V1_SCOPE.md) | v1-Scope |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Historie / Status |

## Konventionen

- Fertige Arbeit auf **`main`** pushen  
- Nie `Key.txt`, `.env` oder echte Secrets committen  
- UI-Cache: `?v=` an `app.css` / `app.js` in `index.html`

## Lizenz

Private Nutzung.
