# UI state contract — Box 1 Flex desk

Gnom-Hub-V1. Source of truth: `src/gnom_hub/flex_desk.py` + Hub `execute()`.

## Owners

| Surface | Owner | Authority |
|---------|--------|-----------|
| Box 1 Rückfragen | **Flex** (`FlexDesk`) | none — communication only |
| Execute / Arbeit starten | **Hub** `execute()` / `#btn-execute` | starts workers |
| Box 2 | Brainstorm (+ Flex chat lines) | dialogue |
| Box 3 | Workers | deliverables |
| God-Mode / tools | User + API, not Flex | elevation |

## Identifiers

Every Box 1 question and answer binds:

- `job_id` — session/pipeline Flex job (not a per-Send jobs.py id unless Hub binds it)
- `task_id` — worker/coordinator task
- `agent_id` — `coordinator` \| `flex` \| `worker1`–`worker4`
- `question_id` — unique; answered or unknown ids are **stale** and rejected

## Allowed Box 1 components

`text` · `yes_no` · `later` · `single_select` · `multi_select` · `free_text` · `start_work`

Unknown component → stored as `text`. Markup/JS stripped (`sanitize_box1_text`). UI uses `textContent` only.

## Send vs Arbeit starten

- **Send** (`POST /api/chat`) = brainstorm + Flex may **ask** start_work. Never starts workers (except documented tool-drill / live-browser short-circuits in the orchestrator, which are not Flex).
- **Arbeit starten** (`#btn-execute` → `POST /api/execute`) = user confirmation. Central gate.
- Answering start_work with Ja → Hub calls `execute()`, not `FlexDesk.start_execute()` (that method raises).

Start-work copy (fixed):

> Der Plan ist bereit. Möchtest du die Arbeit jetzt starten?

## Coordinator and workers → Flex

- Coordinator clarify is posted to FlexDesk (`agent_id=coordinator`, `single_select`) **and** kept as `pending_question`.
- Workers may return a `FLEX_ASK` block (`FLEX_ASK yes_no task=hero\\nFrage…`). Flex shows it in Box 1; Box 3 does not get the ask body. Pipeline pauses (`flex_wait_agent`).
- Answering injects `User→{agent} ({task}, {question_id}): {value}` only for that agent, plus Flex-Erinnerung of standing wishes. Flex does not guess missing facts.

## Reload

`GET /api/state` → `flex_box1.questions` + `pipeline.flex_questions`. Open questions keep `job_id`. A new FlexDesk can be restored with `FlexDesk.from_list`.

## Forbidden for Flex

No Execute, no tool grant, no God-Mode, no invented answers, no skipping confirmations, no `stage=done`, no raw HTML/JS in Box 1.
