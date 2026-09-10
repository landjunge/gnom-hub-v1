# UI-Rebuild-Plan — Gnom-Hub-V1

Stand: 2026-09-10. Branch: `feat/rebuild-human-workspace-ui`.

## Ausgangs-SHA

| Ref | SHA | Hinweis |
|-----|-----|---------|
| **origin/main** (Basis) | `06cfcc592e9c0f2c2ddb760185c10b41cf29bdf4` | `Gnom-Hub-V1-Bildmarke und Wortmarke trennen (#54)` |
| Diese Branch | von `origin/main`, nicht von Audit- oder Desk-Token-Branches | |

Nicht gemergt, nicht als Basis verwendet:

| PR | Branch | Rolle |
|----|--------|--------|
| #57 | `test/human-ui-audit` | Befund: Send≠Execute rot, `done` ohne Deliverable, Tollgate-Install |
| #58 | `docs/human-ui-three-box-audit` | Befund: Layer, tote IDs, Auto-Execute-Pfade, Reload ohne Poll |

Live-Checkout `docs/shared-desk-tokens` (Agent-Tabs + Layout-Fix `6d2e596`) bleibt unangetastet.

## Produktziel

Ein Mensch soll Gnom-Hub-V1 benutzen können, ohne die interne Agentenarchitektur zu kennen.

Sichtbare Struktur:

1. Oben: Agentenkarten (bleiben)
2. Links: **Rückfragen und Entscheidungen** (intern weiter Box 1)
3. Mitte: **Gespräch und Auftrag**
4. Rechts: **Arbeit und Ergebnisse** (intern weiter Box 3)

Hauptaktionen: **Nachricht senden**, **Arbeit starten**, **Arbeit abbrechen**. Kein `Send+Exec`. Senden startet niemals Worker oder Werkzeuge.

---

## A. Bestandsaufnahme (origin/main)

### UI-Dateien

| Datei | Zeilen | Rolle |
|-------|--------|--------|
| `src/gnom_hub/ui/static/index.html` | 695 | Markup: Header, 8 Karten, 3 Boxen, Chat, 7 Modale |
| `src/gnom_hub/ui/static/app.css` | 3123 | Layout, Layer, Modale, Mobile |
| `src/gnom_hub/ui/static/tokens.css` | 25 | Farbtokens (grau + Agentenfarben) — **behalten** |
| `src/gnom_hub/ui/static/app.js` | 8351 | Gebündelt aus `parts/` — nicht von Hand editieren |
| `parts/00-preamble.js` | 706 | Karten, Agent-Layer in Box 1/2/3, Chat-Layer |
| `parts/01-api-snapshot-tts.js` | 1140 | `/api/*`, Snapshot, TTS |
| `parts/02-modals-tools-ws.js` | 1810 | Workspace/System/Vector/Docs/Skills/Tools/Usage |
| `parts/03-chat-jobs-ops.js` | 2505 | Send, Execute, Send+Exec, Jobs, History-Handler |
| `parts/04-boxes.js` | 1672 | Box-3-Ergebnisse, Diff, Fullscreen |
| `parts/05-init.js` | 518 | Bindings |
| `src/gnom_hub/ui/tooltips.py` | — | Hilfe-Texte |

Nach JS-Änderung: `python scripts/build_ui_js.py`.

### Layer (entfernen)

Auf **main** existieren bereits unsichtbare Agent-Layer (nicht die extra Tab-Leisten von `docs/shared-desk-tokens`):

- `#box1-layers`, `#box2-layers`, `#box3-layers` — 8 Layer pro Box (`00-preamble.js`)
- `.chat-agent-layer` — Chat-Log pro Agent
- `#box1-layer-live` / `tune` / `gnom` — Info-Schichten; `gnom` nie eingeblendet (PR #58)
- `#box3-dual` — tot, `hidden`
- Klick auf Agentenkarte: Layer + Rahmenfarbe + ggf. Tune in Box 3

Karten sollen künftig einen **eingebetteten Detailbereich** öffnen, keine Layer in allen Boxen.

### Modale (ersetzen durch Hauptfenster-Panel)

| ID | Auslöser | Echte Funktion |
|----|----------|----------------|
| `#workspace-modal` | Workspace | ja — Dateilisten, Preview, zip |
| `#system-modal` | System | ja — Budget, Checkpoint, HOT/WARM, Teams |
| `#vector-modal` | Vec-Badge | ja |
| `#docs-modal` | Docs | ja |
| `#skills-modal` | Skills | ja |
| `#tools-modal` | Tools | ja — Tool-Call, Computer-Use |
| `#usage-modal` | $-Badge | ja — Jobs, Usage |

Zusätzlich schwebend: Tune-Layer in Box 3, COLD-Browser in Box 1, Diff-Overlay, Fullscreen-Overlay, Toasts. God-Mode-`confirm` bleibt vorerst als einzige kleine Sicherheitsabfrage.

### Chat / Boxen — echte vs tot

**Echt:** Send, Execute, Cancel, Mic, TD, Clarify Yes/No/Whatever/Later, Flex-Review nach `done`, Box-3 Copy/Download/Open/Keep/Temp/Perm, Agentenkarten, Badges.

**Entfernen oder ersetzen:**

| Element | Status auf main |
|---------|-----------------|
| `#btn-send-exec` | echt, widerspricht neuem Vertrag |
| `#flex-preset-select` | Platzhalter, `disabled` |
| drei `·`-Buttons unter Box 1 | Platzhalter |
| `#box1-layer-gnom` | tot |
| `#box3-dual` | tot |
| `#btn-copy-all`, `#btn-diff`, `#result-history`, `#btn-reexec`, `#btn-hist-export` | JS ohne HTML (PR #58 hat HTML nur auf der Audit-Branch) |
| `#pipeline-busy-banner`, `#job-timer` | JS ohne HTML auf main |
| Per-Box-Agent-Tabs | nicht auf main; auf `docs/shared-desk-tokens` — nicht übernehmen |

### Send- und Execute-Wege (vollständig)

| Weg | Startet Worker? | Verbleib |
|-----|-----------------|----------|
| UI Send → `POST /api/chat` → `brainstorm_turn` | ja, bei Heuristik | Send darf nur Gespräch |
| UI Execute → `POST /api/execute` | ja | umbenennen zu „Arbeit starten“ |
| UI Send+Exec | ja | **entfernen** |
| `_wants_auto_execute` (`baue`, `landing`, `website`, …) | ja | **entfernen** für Send |
| Tool-Drill auf Send | ja, Tools | **entfernen** für Send |
| Live-Browser auf Send | ja | **entfernen** für Send |
| Go-only (`ja`, `mach das`) | ja | nur wenn an gültige Box-1-Ausführungsfrage gebunden |
| Flex `maybe_request_execute` | ja | **entfernen** für Send |
| `POST /api/chat?full=1` | ja | Test/Telegram-Bypass — vom Desk-Send trennen, nicht als normalen Chat belassen |
| `pipeline_do` Tool | ja | nicht über Send |
| Telegram `/do`, `/exec` | ja | außerhalb Desk; nicht in dieser UI-Fläche |
| `POST /api/workers/{id}/rerun` | ja | nur nach bewusster Box-3-Aktion |
| `POST /api/clarify` | startet Worker nach Antwort | an `question_id` + `job_id` binden |
| `POST /api/reexecute` | ja | nur mit gültiger History-Bindung |
| `POST /api/tools/call` | sofort | nur eingebettete Werkzeuge, nicht Send |

Backend-Pipeline (Distill → Clarify → Flex → Coordinator → Worker 1–n sequentiell) **bleibt**. Geändert wird, **wer sie auslöst**.

### Tests, die Auto-Execute oder Send+Exec verlangen

Diese Tests werden nicht abgeschwächt, sondern an den neuen Vertrag angepasst (Rot nachweisen, dann ersetzen):

- `tests/test_api.py::test_chat_brainstorm_then_execute` — erwartet Worker nach Send mit Build-Text
- `tests/test_flex_pipeline.py::test_wants_auto_execute_go_word_after_two_users`
- `tests/test_api.py` Pfade mit `full=1` (`test_chat_full_pipeline_compat`)
- E2E-Szenarien, die Send als Execute nutzen (`user_scenarios_e2e.py` S1)

Neue Tests zuerst (Rot):

- Send mit „Build a landing page“ bleibt `brainstorm`, 0 Worker, keine Tools
- `btn-send-exec` fehlt im HTML
- sichtbare deutsche Box-Titel
- Box-1-Frage trägt `question_id` + `job_id`; alte Antwort → Ablehnung
- `done` ohne lesbare Datei ist nicht „Fertig“

PR #57 hat bereits `tests/test_deliverable_ok.py` und ehrliches `deliverable_ok` — **Ideen übernehmen, Dateien nicht mergen**. Neu implementieren auf dieser Branch.

### Befunde aus PR #57 / #58, die den Umbau treiben

1. Send startet Worker (Build-Sprache, Go-only, Flex, `full=1`).
2. `stage=done` + Toast „Umgesetzt“, obwohl Box 3 FEHLER / keine Datei (PR #57).
3. Nach Reload kein Job-Poll (PR #58).
4. Clarify nicht an Job-ID gebunden; alte Freigabe wiederverwendbar.
5. Sieben schwebende Modale; Esc schließt nicht alle.
6. Layer und tote Dual-/History-IDs.
7. Oberfläche englisch/technisch (`idle`, Send, Execute).
8. Desk für Menschen ohne Agentenwissen unbrauchbar (Karten + Layer + drei Kästen).

---

## B–F. Phasen (kurz)

### B — Verträge

`docs/UI-STATE-CONTRACT.md`: Gespräch, Auftrag, Job, Rückfrage, Worker, Ergebnis; erlaubte Übergänge; deutsche Labels. **Vor** dem Markup.

### C — Grundgerüst

Neues `index.html`-Gerüst: Karten oben, drei benannte Bereiche, eingebettetes `#workspace-panel` statt `.modal`. CSS: bestehende graue Tokens. Mobile: eine Spalte, Bereichs-Tabs auf Deutsch.

### D — Verhalten

1. Rot: Send startet keine Worker (`test_send_never_starts_workers`).
2. `_wants_auto_execute` und Flex-Auto-Execute aus dem Chat-Pfad entfernen.
3. Box-1-Komponenten aus JSON-Schema (Whitelist).
4. Box 3: Job/Worker/Versuch/Version.
5. Reload: `GET /api/jobs/busy` + Poll fortsetzen.
6. Fertig nur bei `deliverable_ok`.

### E — Alten UI-Code entfernen

Erst nach grünen Ersatztests: Layer-Builder, Send+Exec, Dual-Layer, tote History-Handler, Modal-Chrome, ungenutztes CSS.

### F — Menschentests

Frische Umgebung, headed Browser, Pflichtszenarien aus dem Auftrag. Screenshots nach `docs/assets/ui-rebuild/`.

---

## Was erhalten bleibt

- 8 Agentenkarten, Farben, `tokens.css`
- FastAPI, Jobs, Orchestrator, Memory, Tools, Plugins, God-Mode (Prozess)
- Sequenzielle Worker (keine Parallel-Jobs — Ist-Architektur)
- Workspace-Dateien, Checkpoint, Skills-Katalog — nur die **Darstellung** wechselt ins Hauptfenster

## Was nicht in diesen Umbau gehört

- PR #56 Mutation Nightly
- God-Mode-Auth für LAN (`0.0.0.0`)
- Plugin-Sandbox
- Zweites Orchestrator / Tollgate-Rewrite
- Merge von #57/#58

## Reihenfolge der ersten Commits

1. dieser Plan
2. `docs/UI-STATE-CONTRACT.md`
3. Roter Test: Send startet keine Worker
4. HTML-Gerüst mit deutschen Bereichstiteln (sichtbar, noch ohne volles Verhalten)
5. Send-Pfad hart trennen
6. Box-1-Schema + Renderer
7. Box 3 + ehrliches Fertig
8. Modale → Panel
9. Layer-Entfernung
10. Menschentests + `docs/UI-HUMAN-ACCEPTANCE-TEST.md`
