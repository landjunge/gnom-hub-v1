# UI-Zustandsvertrag — Gnom-Hub-V1

Gilt für Branch `feat/rebuild-human-workspace-ui`, Basis `06cfcc59`.
Sichtbar immer Deutsch. Interne IDs dürfen englisch bleiben.

## Identifiers

| ID | Wer vergibt | Lebensdauer |
|----|-------------|-------------|
| `job_id` | Hub, 12 Hex | ein Pipeline-Lauf |
| `task_id` | Hub, stabil über Brainstorm-Turns bis Reset | der menschliche Auftrag |
| `question_id` | Hub, pro Rückfrage | nur solange `status=open` |
| `agent_id` | fest: `brainstorm` `memory` `flex` `coordinator` `worker1`–`worker4` | — |
| `attempt` | Hub, zählt Execute/Rerun | Version der Ausführung |
| `result_id` | Hub, pro Worker-Output | gebunden an `job_id` + `attempt` |

Eine Antwort oder ein Worker-Ergebnis ohne passende IDs wird verworfen.

## Gespräch (`conversation`)

| Status intern | Sichtbar | Bedeutung |
|---------------|----------|-----------|
| `idle` | Bereit | keine Nachricht |
| `brainstorm` | Im Gespräch | Send hat nur Dialog geführt |
| `blocked` | Wartet | Chat gesperrt, solange ein Job noch wirksam ist (Busy/Cancel) |

Send ändert nur Gespräch + Auftragstext + ggf. offene Rückfrage. Send ändert niemals Worker, Dateien, Tools.

## Auftrag (`task`)

Der Auftrag ist die destillierte Absicht des Menschen, unabhängig vom Job.

| Status | Sichtbar |
|--------|----------|
| `empty` | „Beschreibe hier, was du machen möchtest.“ |
| `draft` | erkannt, noch kein Plan |
| `planned` | Plan sichtbar, noch keine Arbeit |
| `running` | Arbeit läuft |
| `done` | Fertig — nur mit bestätigtem Ergebnis |
| `error` | Fehler |
| `cancelled` | Abgebrochen |

Übergänge:

```
empty → draft          (Send mit Inhalt)
draft → planned        (Distill ohne Execute; oder Plan nach Send)
planned → running      (nur „Arbeit starten“ oder gültige Box-1-Ausführungsbestätigung)
running → done         (deliverable_ok)
running → error        (alle Worker fehlgeschlagen oder kein Ergebnis)
running → cancelled    (Abbruch)
cancelled|error|done → draft   (neue Nachricht, neuer task_id-Abschnitt)
```

Kein Sprung `draft → running` über Send.

## Job (`job`)

Ein Job ist ein Server-Lauf hinter einem Auftrag.

| Status intern | Sichtbar |
|---------------|----------|
| `queued` / `running` | Arbeit läuft |
| `clarify` | Wartet auf deine Antwort |
| `done` | intern fertig — UI sagt **Fertig** nur bei `deliverable_ok` |
| `error` | Fehler |
| `cancelled` | Abgebrochen |

Genau ein Pipeline-Job gleichzeitig (bestehende Lock-Regel). Zweiter Start → sichtbar „Bitte warten, eine Arbeit läuft noch.“

Nach Abbruch: Status `cancelled`, nie `done`. Verspätete Events mit alter `job_id` werden ignoriert oder unter „alter Auftrag“ abgelegt.

## Rückfrage (`question`) — Box 1

Strukturierte Daten, kein Agenten-HTML.

Erlaubte `type`:

| type | UI |
|------|-----|
| `info` | nur Text |
| `yes_no` | Ja / Nein |
| `later` | zusätzlich Später |
| `free_text` | eigenes Feld + Senden |
| `single_choice` | eine Option |
| `multi_choice` | mehrere Optionen |
| `confirm_plan` | Plan zeigen, Bestätigen / Ändern |
| `confirm_execute` | Freigabe der Arbeit (einziger Weg, außer Button „Arbeit starten“) |
| `confirm_action` | Freigabe einer klar beschriebenen Aktion |
| `fix_input` | Korrektur |
| `abort_or_continue` | Abbruch / Weiterarbeiten |

Pflichtfelder: `question_id`, `job_id`, `task_id`, `agent_id`, `type`, `title`, `created_at`, `status`.

`status`: `open` | `answered` | `expired` | `superseded`.

Antwort-POST muss dieselben IDs tragen. Weicht `job_id`/`question_id` ab oder `status≠open` → HTTP 409, UI „Diese Frage gilt nicht mehr.“

„ja“ / „mach das“ / „los“ im Chat startet Arbeit **nur**, wenn genau eine `confirm_execute` mit `status=open` existiert und die Nachricht als Antwort auf diese `question_id` gebunden wird.

## Worker

Ist-Architektur: **sequentiell** im selben Job, keine parallelen Pipeline-Jobs.

| Status | Sichtbar auf der Karte |
|--------|------------------------|
| `idle` | wartet |
| `thinking` | denkt |
| `needs_input` | braucht eine Antwort |
| `working` | arbeitet |
| `error` | Fehler |
| `done` | fertig (dieser Worker, nicht der Auftrag) |

Karten klicken öffnet den Detailbereich im Hauptfenster, schaltet keine Box-Layer.

## Ergebnis (`result`) — Box 3

Felder: `result_id`, `job_id`, `task_id`, `worker_id`, `attempt`, `kind` (`html`|`text`|`file`|`error`), `body` oder `path`, `deliverable_ok`.

`deliverable_ok` ist wahr nur wenn:

- erwartete Datei existiert und lesbar ist, **oder**
- ein nicht-leerer Worker-Body den Auftrag erfüllt (kein `FEHLER`-Banner, DoD nicht 0),
- und `job_id` der aktuelle Job ist.

UI **Fertig** nur wenn der Auftrag `done` und mindestens ein `deliverable_ok`.
Alle Worker fehlgeschlagen → Auftrag `error`, kein grüner Toast.

Verspätetes Ergebnis: `job_id ≠ current_job_id` → nicht in die aktuelle Box 3 schreiben.

## Sichtbare Hauptaktionen

| Button | Intern | Darf |
|--------|--------|------|
| Nachricht senden | `POST /api/chat` ohne `full` | Gespräch, Plan, Rückfrage vorbereiten |
| Arbeit starten | `POST /api/execute` | Worker und Werkzeuge |
| Arbeit abbrechen | `POST /api/jobs/{id}/cancel` | Job beenden; danach nicht Fertig |

Enter = nur senden. Strg/Cmd+Enter = Arbeit starten, nur wenn der Button dazu sichtbar aktiv ist. Escape bricht Arbeit nicht ohne Bestätigung im Hauptfenster ab.

## Erlaubte Übergänge (Kurz)

```
Send:     conversation brainstorm | task draft|planned | niemals job running
Execute:  task planned → running → (done|error|cancelled)
Clarify:  nur question.status=open und question.job_id == current job
Cancel:   running → cancelled; ignore late results
Reload:   restore job + questions + results from GET /api/state and /api/jobs/busy; resume poll
```
