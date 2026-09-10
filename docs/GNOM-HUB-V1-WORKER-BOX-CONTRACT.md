# Gnom-Hub-V1 Worker-Box-Vertrag

Stand: 2026-09-10. Gilt für den gelesenen Code auf `docs/shared-desk-tokens` (`56fc27b`) und denselben Orchestrator auf `origin/main` (`06cfcc59`). Die Agent-Tabs in den Boxen existieren nur auf `56fc27b`.

„Arounder“ ist ein Dokumentname. Im Code gibt es keinen Agent `arounder`.

## Wer darf Box 1 schreiben

| Quelle | Darf schreiben | Inhalt |
|--------|----------------|--------|
| User | ja | Clarify-Klicks (Yes / No / Whatever / Later), Choice-Karten, Flex-Feedback, Flex-Notiz |
| Coordinator | ja | `pending_question` → Clarify-Karte |
| Flex | ja | Feedback-Leiste nach `stage=done`; Choice-Karten-Fallback aus `flex_notes` |
| Brainstorm | ja | Choice-Karten aus Notizen / letztem Assistant-Turn |
| Memory | nur bei Kartenklick | Agent-Info, keine Memory-Dumps im Snapshot-Pfad |
| Worker 1–4 | nein | nur Karten-Highlight |
| System / UI | ja | Hilfe, Tooltips, COLD-Browser, Tune-Tipps, Chat-Spiegel nicht-User-Zeilen |
| Arounder-Modul | existiert nicht | — |

Box 1 bleibt leer (Platzhalter), wenn keine Rückfrage, kein Hover-Help und kein Flex-Review ansteht.

## Wer darf Box 2 schreiben

| Quelle | Darf schreiben | Inhalt |
|--------|----------------|--------|
| User | ja | Chat nach `mountChatInBox2()`; Eingabe nur `#chat-input` |
| Brainstorm | ja | Layer `#box2-content` / `setBox2()` |
| Flex | ja | Layer `flex` aus `flex_notes` |
| Coordinator | ja | destillierte Requirements |
| Worker | teilweise | zweites HTML-Ergebnis kann `#box2-page-stage` füllen |
| Memory | nein im Snapshot-Pfad | Layer bleibt Empty-Hint |

Send landet als Dialog in Box 2. Das ist der vorgesehene Brainstorm-Ort.

## Wer darf Box 3 schreiben

| Quelle | Darf schreiben | Inhalt |
|--------|----------------|--------|
| Worker 1–4 | ja | `#box3-result-stage` und Layer `#box3-workerN` |
| User | Dateiaktionen | Keep / Temp / Perm / Copy / Open / Download — kein LLM-Text |
| Tune-UI | ja | Agent-Regler, nicht Worker-Deliverable |
| Dual-Layer `#box3-dual` | tot | `hidden`, wird nicht eingeblendet |

Box 3 gilt als Ergebnisfläche. „Fertig“ in der UI folgt dem Snapshot, nicht einem eigenen Abschluss-Event pro Worker.

## Nachrichten, die dort erscheinen dürfen

- **Box 1:** Hilfe, Clarify, Flex-Review, Auswahlkarten, COLD, Agent-Erklärung bei Kartenklick. Kein Worker-HTML.
- **Box 2:** Brainstorm-Turns, User-Chat, Flex-Notizen, destillierte Requirements, optional eine geöffnete Worker-HTML-Seite.
- **Box 3:** Worker-Bodies (Preview / Source / Copy), DoD-Checkliste, Tool-Chips, FEHLER-Banner im Worker-Text.

Chat-Systemzeilen („Stage: distill“) können zusätzlich im Box-1-Pane des *aktuell aktiven* Chat-Agenten landen. Das ist nicht der produzierende Agent.

## Auftrag, Worker, Ergebnis verbinden

Es gibt **keine** getrennte Auftrags-ID in der UI.

| Begriff | Wert |
|---------|------|
| Job-ID | 12 Hex-Zeichen, `jobs.py` UUID |
| Worker-ID | `worker1` … `worker4` im Output-Dict |
| Ergebnis | `pipeline.worker_outputs[]` mit `worker`, `index`, `task`, `result` |
| Datei nach Erfolg | `data/workspace/temp/{wid}_{stage}.html` / `.txt` nur bei Job-Status `done` |

Ein Hub hält **einen** Pipeline-Job. Ein zweiter Send/Execute liefert HTTP 409. Worker laufen **nacheinander** im selben Thread, nicht parallel.

## Abbruch

`POST /api/jobs/{id}/cancel` setzt nur `cancel=True`. Kein Kill des LLM-HTTP und kein Kill von `subprocess`.

- Der laufende `worker.run` (inkl. `file_write`, `install_tool`, Screenshot) läuft zu Ende.
- Danach stoppt die Schleife. `_finish` / Memory entfällt.
- Workspace-Capture nach Cancel **nicht**.
- Playwright-Session bleibt global stehen.

Ein Auftrag ist nach Cancel **nicht** „keine Dateiänderung mehr“, solange der aktuelle Worker noch läuft.

## Fehler

Worker-LLM-Fehler schreiben einen FEHLER-Text ins Worker-Feld. Die Pipeline kann trotzdem `_finish` und `done` erreichen. Leere Bodies: `done` plus Warning `empty_worker_results`. Job-Timeout (Default 600s): Status `error`, Text `FEHLER — job timeout`.

## Browser-Neuladen

Solange der Hub-Prozess lebt, füllt `GET /api/state` Box 2/3. Der Job-Poll wird **nicht** automatisch fortgesetzt. Live-Pulse und Tool-Log im Chat fehlen nach Reload, der Server arbeitet weiter. Hub-Neustart löscht Jobs (nur RAM). Checkpoint speichert God-Mode nicht.

## Verspätete Antwort

Nach Cancel kann der aktuelle Worker noch in `worker_outputs` schreiben. Die UI kann Partials in Box 3 zeigen. Events nach Job-Ende werden abgemeldet (`_active_job_id` geleert). Ein späteres Ergebnis eines *anderen* Jobs kann denselben Snapshot nicht überschreiben, solange die Job-ID bindet — der Snapshot selbst ist aber **global**.

## Wann ein Auftrag wirklich beendet ist

Ein Auftrag gilt erst als beendet, wenn **alle** gelten:

1. `job.finished == True`
2. `job.status ∈ {done, error, cancelled, clarify}`
3. Kein aktiver Pipeline-Lock / Busy-Job

Zusätzlich:

- `clarify` ist Job-Ende **ohne** Worker-Finish. Worker starten erst nach `/api/clarify`.
- `done` kommt nur nach `_finish`.
- Die UI-Anzeige „fertig“ darf nicht allein aus einem Worker-HTML in Box 3 abgeleitet werden, solange `job.finished` falsch ist.

## Send gegen Execute

Send **darf** im aktuellen Code Worker starten (Tool-Drill, Live-Browser, Go-only, Bau-Heuristik, Flex-Flag, `?full=1`). Das widerspricht der Soll-Regel „Send ist nicht Execute“ und ist testgesichert. Der Vertrag dokumentiert das Ist-Verhalten; er ändert es nicht.
