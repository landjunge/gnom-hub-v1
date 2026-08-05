# Gnom-Hub v3.7.1

Local multi-agent hub: **brainstorm first**, then **Execute** workers.

---

## English

### Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
# http://127.0.0.1:8080/
./scripts/quality_check.sh
```

**Keys:** [`docs/KEYS_AND_MODELS.md`](docs/KEYS_AND_MODE.md) — `Key.txt` + model `deepseek-v4-flash`.

### Chat buttons

| Button | Meaning |
|--------|---------|
| **Send** | Brainstorm only (Box 2) |
| **Execute** | Distill → workers → Box 3 |
| **Send+Exec** | Both in one go |
| **Mic** | Speech-to-text |
| **Cancel** | Stop running job (when visible) |

### Boxes

| Box | Content |
|-----|---------|
| **1 Arounder** | Help tooltips + Clarify (Yes/No/…) |
| **2 Brainstorm** | Dialogue / notes (no HOT strip) |
| **3 Workers** | One worker result (HTML preview or text) + Preview/Source/Copy |

### Computer use (mouse / keyboard / screen)

Backend + **Tools** modal (not automatic from chat):

1. Open **Tools**
2. Section **Computer use**: Inspect / Click / Type / Shell  
3. **God** badge **ON** for real control (else dry-run)  
4. Optional stack: `pip install -e ".[computer]"` — see [`docs/TOOLS_PORTFOLIO.md`](docs/TOOLS_PORTFOLIO.md)

### Tests

```bash
./scripts/quality_check.sh
python scripts/basic_tests.py          # B1–B3, server on :8080
python scripts/user_landing_e2e.py     # keyboard E2E + live LLM
```

### Docs

| Doc | Topic |
|-----|--------|
| [`docs/BASIC_USER_TEST.md`](docs/BASIC_USER_TEST.md) | Landing-page E2E |
| [`docs/KEYS_AND_MODELS.md`](docs/KEYS_AND_MODELS.md) | Keys / model |
| [`docs/STABILITY.md`](docs/STABILITY.md) | Stability checklist |
| [`docs/TOOLS_PORTFOLIO.md`](docs/TOOLS_PORTFOLIO.md) | Computer-use libs |
| [`docs/WORKFLOWS_AND_PRESETS.md`](docs/WORKFLOWS_AND_PRESETS.md) | Team presets / plan_mode freeze |
| [`AGENTS.md`](AGENTS.md) | Agent coding rules (gate before push) |

### License

Private use.

---

## Deutsch

### Install & Start

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
# http://127.0.0.1:8080/
./scripts/quality_check.sh
```

**Keys:** [`docs/KEYS_AND_MODELS.md`](docs/KEYS_AND_MODELS.md) — `Key.txt`, Modell `deepseek-v4-flash`.

### Chat-Buttons

| Button | Bedeutung |
|--------|-----------|
| **Send** | nur Brainstorm (Box 2) |
| **Execute** | Distill → Worker → Box 3 |
| **Send+Exec** | beides hintereinander |
| **Mic** | Sprache → Text |
| **Cancel** | laufenden Job abbrechen |

### Boxen

| Box | Inhalt |
|-----|--------|
| **1 Arounder** | Hilfe + Clarify (Yes/No/…) |
| **2 Brainstorm** | Dialog / Notizen (kein HOT-Streifen) |
| **3 Workers** | ein Worker-Ergebnis (HTML-Preview oder Text) |

### Computer-Use (Maus / Tastatur / Screen)

Im Backend + im **Tools**-Modal (nicht automatisch aus dem Chat):

1. **Tools** öffnen  
2. **Computer use**: Inspect / Click / Type / Shell  
3. **God**-Badge **an** für echte Steuerung (sonst nur dry-run)  
4. Optional: `pip install -e ".[computer]"` — Details: [`docs/TOOLS_PORTFOLIO.md`](docs/TOOLS_PORTFOLIO.md)

### Tests

```bash
./scripts/quality_check.sh
python scripts/basic_tests.py
python scripts/user_landing_e2e.py
```

### Lizenz

Private Nutzung.
