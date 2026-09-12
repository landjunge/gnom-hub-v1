# UI-State-Vertrag — Box 1 Flex-Desk

Gnom-Hub-V1. Quelle: `src/gnom_hub/flex_desk.py`, Hub `execute()`, `flex_answer()`.

## Owners

| Fläche | Owner | Autorität |
|--------|--------|-----------|
| Box 1 Rückfragen | **Flex** (`FlexDesk`) | keine — nur Kommunikation |
| Execute / Arbeit starten | **Hub** `execute()` / `#btn-execute` | startet Worker |
| Box 2 | Brainstorm (+ Flex-Chatzeilen) | Dialog |
| Box 3 | Workers | Deliverables |
| God-Mode / Tools | User + API, nicht Flex | Elevation |

## IDs

Jede Box-1-Frage und -Antwort bindet:

- `job_id` — Flex-Job der Sitzung/Pipeline
- `task_id` — Worker-/Coordinator-Task
- `agent_id` — `coordinator` \| `flex` \| `worker1`–`worker4`
- `question_id` — eindeutig; beantwortet oder unbekannt = **stale**, abgelehnt

## Erlaubte Box-1-Komponenten

`text` · `yes_no` · `later` · `single_select` · `multi_select` · `free_text` · `start_work`

Unbekannt → `text`. Markup/JS weg (`sanitize_box1_text`). UI nur `textContent`.

## Send vs Arbeit starten

- **Send** (`POST /api/chat` + `target`) geht an Brainstorm (default), Coordinator, Flex oder einen Worker. **Keine Route startet Worker.** Tool-Drill / Live-Browser / Go-only werden sichtbare START-IDs, kein Short-Circuit.
- Farbe/Flag = Orientierung für das Ziel, keine Rechte.
- **Arbeit starten** (`#btn-execute` → `POST /api/execute`) oder Ja auf die **sichtbare START-ID** = Nutzerbestätigung.
- `execute()` setzt offene Box-1-`start_work`-Fragen auf `stale`. Ein späteres Ja darf Execute nicht erneut feuern (`stale_question`).
- Nacktes Ja bei mehreren offenen Fragen → `unbound_yes`. Falsche START-ID → `assignment_mismatch`.
- Ja auf `start_work` → Hub `execute()`, nicht `FlexDesk.start_execute()` (wirft).
- UI pollt den `start_work`-Job wie Execute (`pollJob`). Die Envelope `{job_id}` ohne `flex_box1` darf Box 1 nicht leeren.
- Box 3 `result_status` ist GELIEFERT/FEHLER/UNGEPRÜFT — nie von allein ABGENOMMEN.

Start-work-Text (mit Auftrag-ID):

> START-C1 — Auftrag C1 ist ausführbar. Vorgesehen: laut Plan. Wirkung: Code und Tests ändern. Soll genau dieser Auftrag jetzt starten?

## Flex-Review nach `done`

Rebuild / HTML reparieren / mehr Interaktion: `action=start_work`. `apply_flex_feedback` ruft `offer_start_work`, **nicht** `execute()`. Gate bleibt `#btn-execute` oder Box-1-Ja.

## Coordinator und Worker → Flex

- Coordinator-Clarify landet in FlexDesk (`agent_id=coordinator`, `task_id=clarify`, `single_select`) **und** intern als `pending_question`.
- Snapshot (`pipeline.pending_question`): `null`, wenn Flex Box 1 die Coordinator-Clarify schon offen zeigt. Pipeline-State behält die Frage für `/api/clarify`. Worker-Ask allein blendet sie nicht aus.
- Worker dürfen `FLEX_ASK` zurückgeben. `parse_flex_ask` nimmt den **ersten** Block, auch nach Preamble, Markdown-Fence oder `TOOL_CALL` (case-insensitive). Box 1 zeigt die Frage; Box 3 bekommt den Ask-Body nicht. Pipeline pausiert (`flex_wait_agent`, Stage `clarify`, nicht `done`).
- Worker-Prompt: fehlende User-Entscheidung / `FLEX_ASK` **vor** Always-Finish. Finish-the-file nur, wenn die Task spezifiziert genug ist. Nicht raten.
- Pause speichert den **fragenden Worker plus Original-Plan-Task vorne** in `flex_wait_remaining`, Rest dahinter.
- `Hub.flex_answer` nach Worker-Ask: `continue_after_flex_ask` — Asker mit Plan-Task, dann Rest. Kein `rerun_worker` und kein `_finish` vor dem Rest. Neue `FLEX_ASK` pausiert erneut (Stage bleibt `clarify`).
- Antwort injiziert nur `User→{agent} ({task}, {question_id}): {value}` plus Flex-Erinnerung stehender Wünsche. Flex erfindet keine Fakten.
- Vergessene Requirements → Box-1-`nachbesserung` Ja/Nein. Ja darf den einen Worker neu laufen; Flex Execute nicht den ganzen Job.
- Checkpoint-Load und Session-Pack tragen `flex_job_id`, `flex_questions`, `flex_wait_*` und rufen `restore_flex_from_state()`.

## Reload

`GET /api/state` → `flex_box1.questions` + `pipeline.flex_questions`. Offene Fragen behalten `job_id`. Restore: `FlexDesk.from_list`.
Hub-Boot (`Hub.__init__` → `_load_checkpoint_on_boot`) lädt `checkpoint.json` wie `POST /api/checkpoint/load` und stellt Box-1-Fragen wieder her.

## Verboten für Flex

Kein Execute, kein Tool-Grant, kein God-Mode, keine erfundenen Antworten, keine übersprungenen Bestätigungen, kein `stage=done`, kein Roh-HTML/JS in Box 1.
