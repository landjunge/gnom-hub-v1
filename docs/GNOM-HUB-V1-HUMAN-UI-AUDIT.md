# Gnom-Hub-V1 Human-UI-Audit

Datum: 2026-09-10. Projektname: **Gnom-Hub-V1**.

## Testumgebung

| Item | Wert |
|------|------|
| OS | macOS 15.7.4 |
| Checkout für Code/UI/Tests | Branch `docs/shared-desk-tokens`, SHA `56fc27b45e17af99617ab926e617a16b64e5da5a` |
| GitHub `origin/main` | `06cfcc592e9c0f2c2ddb760185c10b41cf29bdf4` |
| Lokales `main` | `587a579` — 13 Commits hinter GitHub-main, **nicht** als Basis verwendet |
| Python | `.venv` 3.12.13 (Homebrew). System-`python3` 3.8.0 nicht verwendet. `requires-python >=3.10` |
| Node | v25.9.0, npm 11.12.1 |
| Ruff | 0.16.1 im venv |
| Pytest | 8.3.5 |
| Laufender Hub | `127.0.0.1:8080`, Version `3.10.1`, God-Mode aus, Stage `idle` |
| Chrome CDP `127.0.0.1:9222` | **nicht offen** — headed Live-E2E blockiert |
| Fremde Untracked im Working Tree | 4AllPass-Desk-Assets — **nicht** Teil dieses Audits, nicht gestaged |

PR #56 (Mutation Nightly venv-cache) und PR #49 (sandboxed-environment) wurden nicht vermischt.

Agent-Tabs in den drei Boxen (`buildPanelAgentTabs`) existieren **nur** auf `56fc27b`, nicht auf `origin/main`. Send/Execute/God-Mode/Worker-Code ist auf beiden gleich.

## Geprüfte Commit-SHA

- **UI + Orchestrator gelesen:** `56fc27b`
- **Soll-Basis laut Auftrag (current main):** `06cfcc59`
- **Diese Audit-Branch:** `docs/human-ui-three-box-audit` von `origin/main`

## Tatsächlicher Ablauf (Ist, nicht Doku)

Acht Agenten-Slots: Brainstorm, Memory, Flex, Coordinator, Worker 1–4. Box 1/2/3 sind Flächen, kein Arounder-Agent.

```
Send  → POST /api/chat → Job „brainstorm“
         → ggf. Tool-Drill / Live-Browser / Go-only / Bau-Heuristik / Flex
         → dann execute()  (Worker, Tools, Dateien)
         sonst nur Brainstorm-LLM in Box 2

Execute → POST /api/execute
         → Distill → Clarify? → Flex → Prefetch → Worker 1–n → Box 3
```

Kein WebSocket. Lange Arbeit: Job-ID, Poll auf `/api/jobs/{id}`, Snapshot global. Ein Pipeline-Lock, zweiter Start → 409.

**Send ist im Code nicht gleich „nur Gespräch“.** Tests fordern, dass „Build a simple landing page…“ per Send Worker startet.

Dry-Run ist kein eigenes persistiertes Flag. God-Mode aus bedeutet Dry-Run nur für OS-Maus/Tastatur/Allowlist-Shell. Browser öffnen, `file_write` ins Jail, `web_fetch`, Prefetch/`install_tool` laufen trotzdem.

God-Mode startet aus (außer `GNOM_GOD_MODE_AUTO`). Persistiert nicht über Hub-Neustart. `POST /api/god-mode` hat keine Auth (Default-Bind `127.0.0.1`).

## Boxen

| Soll | Ist |
|------|-----|
| Box 1 Arounder, Hilfe, Rückfragen | Hilfe, Clarify, Flex-Review, Choice-Karten, COLD. **Kein Arounder-Modul.** Name kommt in der ausgelieferten HTML nicht vor. |
| Box 2 Brainstorm und Gespräch | Trifft zu. Chat wird per JS nach Box 2 verschoben. Zusätzlich Flex-/Coordinator-Layer. |
| Box 3 Worker-Ergebnisse | Trifft zu (Result-Stage). Dual-Layer tot. Busy-Banner/Job-Timer im HTML **fehlend**, CSS/JS suchen die IDs. |

Live-HTML auf `:8080` (curl): `#box1`, `#box2`, `#box3`, `#btn-send`, `#btn-execute`, `#btn-send-exec` vorhanden. `arounder`, `pipeline-busy-banner`, `job-timer` nicht vorhanden.

## Matrix der Bedienelemente

Status: **funktioniert** / **teilweise** / **funktioniert nicht** / **nicht erreichbar** / **nur Platzhalter** / **unverständlich**. Ohne headed Browser: Click-Handler aus dem Code, Sichtbarkeit der drei Boxen per curl bestätigt.

### Chat / Pipeline

| Element | Status | Beleg |
|---------|--------|-------|
| Send | funktioniert, verletzt Soll-Regel | `sendChat` → `/api/chat`; Auto-Execute möglich |
| Execute | funktioniert | `/api/execute`; disabled ohne `can_execute` |
| Send+Exec | teilweise | nach Auto-Execute kann ein zweites Execute folgen |
| Cancel | funktioniert kooperativ | kein Kill des laufenden LLM |
| Enter | funktioniert | Send |
| Ctrl/Cmd+Enter | funktioniert | Execute |
| Mic | funktioniert | Browser SpeechRecognition |
| TD | funktioniert | füllt Input, sendet nicht |
| drei `·`-Buttons | nur Platzhalter | `disabled` |
| Busy-Banner / Job-Timer | nicht erreichbar | IDs fehlen in `index.html` |

### Box 1

| Element | Status |
|---------|--------|
| Clarify Yes/No/Whatever/Later | funktioniert |
| Later → Resume | funktioniert |
| Flex-Review-Buttons nach done | funktioniert |
| Choice-Karten | funktioniert |
| COLD Restore/Delete/Close | funktioniert |
| Help-Hover → Box 1 | funktioniert |
| Gnom-Info-Layer | nicht erreichbar | `showInfoLayer("gnom")` wird nicht aufgerufen |
| Arounder | nicht erreichbar | kein Code |

### Box 2 / 3

| Element | Status |
|---------|--------|
| Brainstorm-Text | funktioniert |
| Worker-HTML in Box 3 | funktioniert |
| Copy / Download / Open / Keep / Temp / Perm | funktioniert |
| Worker-Tabs ab 2 Workern | funktioniert |
| `#box3-dual` Crossfade | nicht erreichbar |
| Result-History / Diff / Reexec / Copy-all | nicht erreichbar | JS sucht fehlendes DOM |
| DoD-Checkliste | teilweise | Anzeige, kein Click |

### Header / Karten / Modale

| Element | Status |
|---------|--------|
| Workspace, Tools, System, Skills, Docs, Vector, Usage | funktioniert |
| Reset / Save / Archive / Clear chat | funktioniert |
| God-Badge | funktioniert (Confirm in der UI) |
| Flex-Preset-Select | nur Platzhalter | `disabled`, immer personal |
| Flex-Karte Toggle | teilweise | Toast „fixed“ |
| Agent-Karten + TTS | funktioniert |
| Online-Punkt | teilweise | „Key vorhanden“, nicht „läuft gerade“ |

Mobile: drei Tabs, eine Box sichtbar. Chat nur in Box 2 — auf Mobile muss Tab 2 aktiv sein.

## Testfälle Box 1 / 2 / 3

Code- und API-Lage. Headed Maus/Tastatur **nicht** ausgeführt (kein CDP).

### Box 1

| Fall | Erwartung Soll | Ist laut Code |
|------|----------------|---------------|
| unklare Aufgabe Send | Arounder-Rückfrage in Box 1 | oft nur Brainstorm in Box 2; Clarify erst auf Execute |
| Yes/No/Whatever/Later | landet im richtigen Auftrag | Clarify ist an `pending_question` gebunden, nicht an Job-ID |
| Worker-Rückfrage ohne Weiterarbeiten | Worker stoppt | Clarify hält die Pipeline; `/api/clarify` startet danach Worker |
| keine Rückfrage | Box 1 leer | Platzhalter + ggf. Chat-Spiegel |

### Box 2

| Fall | Erwartung Soll | Ist laut Code |
|------|----------------|---------------|
| mehrere Brainstorm-Nachrichten | nur Box 2, keine Worker | nur wenn Heuristik nicht greift |
| leere Eingabe / Sonderzeichen | kein Crash | leerer Send: Server `_fail("Empty user text")` |
| Doppel-Send | ein Job | `chatBusy` vor `await`; 409 bei zweitem Job |
| Reload während Brainstorm | Verlauf passt | Chat in sessionStorage; Pipeline vom Hub-RAM |

### Box 3

| Fall | Erwartung Soll | Ist laut Code |
|------|----------------|---------------|
| Execute startet Worker | ja | ja, und Send kann dasselbe |
| parallele Worker | sichtbar getrennt | **keine** parallelen Worker-Jobs, nur sequentiell |
| Abbruch | sofort tot | kooperativ; aktueller Worker läuft durch |
| Reload während Arbeit | kein altes Ergebnis überschreibt neu | globaler Snapshot; Poll nach Reload fehlt |
| „fertig“ vor echtem Ende | darf nicht | UI kann Partials zeigen; `finished` ist die Wahrheit |

## Bestätigte Fehler / Befunde

1. **Send startet Worker.** Bau-Heuristik, Tool-Drill, Live-Browser, Go-only, Flex-Flag, `POST /api/chat?full=1`. Tests verlangen das. Widerspricht der Audit-Soll-Regel und `docs/CODE_ANALYSIS_FOR_AI.md` („No auto-execute“). `AGENTS.md` erlaubt drei Short-Circuits; die Heuristik ist breiter (`baue`, `landing`, `website`).
2. **Kein Arounder.** Box 1 ist Hilfe/Clarify/Flex, nicht das benannte Modul.
3. **Busy-Banner und Job-Timer tot.** CSS+JS vorhanden, HTML-IDs fehlten. **Repariert** in dieser Branch: Test `test_ui_hosts_pipeline_busy_banner_and_job_timer` war rot, IDs in `index.html`, Test grün. Der laufende Hub auf `:8080` serviert noch den alten Stand, bis er neu geladen wird.
4. **History/Diff/Reexec/Copy-all tot.** Handler ohne DOM. **Repariert** in dieser Branch: Test `test_ui_hosts_box3_history_diff_reexec` war rot, IDs in der Box-3-Leiste, Test grün.
5. **`_action_to_dict` verlor `dry_run`.** Dry-Run-Shell wurde als live gelabelt (`tools_ops.py`). **Repariert** in dieser Branch: Test `tests/test_action_to_dict.py` war rot, dann `dry_run`/`detail`/`blocked` kopiert, Test grün.
6. **`POST /api/god-mode` ohne Auth.** Lokal by design; Agent-TOOL_CALL kann God nicht setzen, Plugin und localhost-HTTP können.
7. **Dry-Run deckt Browser/Dateien/Prefetch nicht.** `browser_open` auf macOS ohne God.
8. **Alte Freigabe wiederverwendbar.** Go-only, standing wish, Reexecute ohne Nonce, Worker-Rerun der letzten Task.
9. **Plugin = Hub-User.** `exec` von `plugins/*/main.py`, kein Sandbox. Kann God setzen.
10. **`file_read` liest das Repo-Root** (inkl. Key-Dateien). Write bleibt auf `data/` + `gnom_workspace/`.
11. **Playwright-Screenshot ohne Path-Jail.**
12. **Nach Reload kein Job-Poll.** Server arbeitet, UI zeigt keinen Live-Fortschritt.
13. **Doku intern widersprüchlich** (Send vs auto-Execute, Flex locked vs Presets, Worker-3/4 Default, Version 3.10.1 vs 3.9.1 in älteren Docs). Bei Widerspruch gilt der Code (`AGENTS_DEFINITION.md`).

Nicht als Produktfehler dieses Audits: Mutation Nightly auf `main` (PR #56, Infra). Mermaid-Inventory-Drift in GitHub-CI auf `main`; lokaler `mermaid_check` auf `56fc27b` war grün (Syntax, nicht Inventory).

## Nicht bestätigte Vermutungen

- Playwright klickt den God-Toggle in der eigenen UI.
- Zwei Browser-Tabs: letzter Poll gewinnt visuell.
- Cross-Origin-POST auf `/api/*` scheitert typischerweise am fehlenden CORS — nicht mit curl/localhost verwechselt.
- Pytest-Hänger (siehe Testergebnisse) durch Netz/LLM-Timeout.

## Screenshots

Keine. Chrome Remote-Debugging (`9222`) war zu. Laut `AGENTS.md` darf kein zufälliger neuer Browser geöffnet werden. Die laufende Seite auf `http://127.0.0.1:8080` wurde per HTTP gelesen, nicht per Maus bedient.

## Sicherheitsbefunde

Lokal, Default `127.0.0.1`. Keine fremden Systeme angegriffen. Keine Schlüssel zitiert.

- API ohne Token: Chat, Execute, Tools, MCP, God-Mode, Workspace-Write, Agent-Keys setzen.
- God-Mode-API umgeht den UI-Confirm.
- Plugins umgehen Tool-Freigabe und God-Mode.
- Worker können Repo-Dateien lesen.
- Tool-Ergebnisse können `file_read`-Inhalt ins Chat-Log schreiben (bis 4000 Zeichen).
- `api_key` liegt unmaskiert in `data/hot/agents.json`. Snapshot maskiert.
- Bind `0.0.0.0` würde die ungeschützte API ins LAN legen.

## Verbleibende Risiken

- Produktregel „Send ≠ Execute“ und ausgelieferter Code + Tests widersprechen sich. Eine stille Code-Änderung würde bestehende Tests rot machen.
- Soft-Cancel während pip/Playwright.
- Globale Playwright-Session über Jobgrenzen.
- Keine Job-Persistenz über Hub-Crash.
- Live-UI-Pfad (Maus, Doppelklick, Mobile, Reload während Worker) ist in dieser Sitzung **nicht** menschlich verifiziert.
- Pytest auf `56fc27b`: 7 rot, 539 grün. Mehrere API-Tests bleiben in `clarify` statt `done`. `test_missing_key` hebt nicht an, vermutlich weil ein echter Key in der Umgebung liegt.

## Ehrliches Gesamturteil

Die drei Boxen **existieren** und werden im Snapshot grob richtig befüllt: Gespräch in Box 2, Ergebnisse in Box 3, Rückfragen/Hilfe in Box 1. Die Agenten-Slots stimmen (8 Karten). Execute startet Worker. God-Mode ist nach Start aus.

Gnom-Hub-V1 ist **kein** System, in dem Send nur redet. Worker und Werkzeuge können ohne Execute-Klick laufen. Dry-Run ist kein allgemeines „nichts passiert“. Busy-Banner, Job-Timer und Box-3-History/Diff/Reexec sind in dieser Branch wieder im HTML. Flex-Preset bleibt Platzhalter. Arounder gibt es nicht.

**Nicht bereit** für eine Verbindung mit dem Agent Authority Lab, solange Send/Execute, Abbruch und God-Mode nicht vertraglich und im Code dieselbe Regel haben und die Live-UI nicht headed geprüft ist.
