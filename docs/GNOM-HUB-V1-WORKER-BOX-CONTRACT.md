# Gnom-Hub-V1 — Worker / Box contract

**Commit:** `06cfcc5` plus audit repairs on `test/human-ui-audit`.  
**Source of truth:** Python + `src/gnom_hub/ui/static/parts/*.js`. Where docs disagree, this file follows the code.

There is **no agent id `arounder`**. Box 1 is the round-trip overlay (clarify, Flex review, agent info).

## Who may write which box

| Box | May write | Must not write |
|-----|-----------|----------------|
| **Box 1** | UI (agent click / help), Coordinator (`pending_question` / Yes·No·Whatever·Later), Brainstorm suggestion cards (text only), Flex review after `stage=done`, COLD browser | Workers (no Box 1 body). Memory (facts go HOT/WARM, Mem badge only) |
| **Box 2** | Brainstorm turns, Flex notes (Execute path), Coordinator distilled requirements, HTML page overlay | Workers (they belong in Box 3) |
| **Box 3** | Workers 1–4 (`worker_outputs`). Tool-drill / browser-nav impersonate `worker1` | Brainstorm, Flex, Coordinator, Memory, user chat |

Every box has 8 **visibility** layers (`#boxN-{agentId}`). Clicking a card shows that layer in all three boxes. That is display, not write permission.

Chat (`#chat-mod`) is **not** a box. Per-agent chat layers live under the three boxes.

## What appears

| Surface | Message types |
|---------|----------------|
| Box 1 clarify | Coordinator question; options Yes / No / Whatever / Later. Later parks; workers do not start |
| Box 1 Flex review | After Execute `done`: Gut so / Mittel / Schlecht / rebuild / wishes |
| Box 2 | User + Brainstorm (+ Flex lines in `brainstorm_turns`, currently painted as “Brainstorm:”) |
| Box 3 | Worker body, DoD checklist, tool chips, Copy / Keep / Temp / Perm |
| Chat | User input, system toasts, job status |

## How job, worker, and result bind

- One hub, one `PipelineState`, one `_pipeline_lock`. HTTP **409** if a second pipeline job starts.
- Job id = 12-hex uuid. UI polls only `currentJobId`.
- Each worker output: `{worker, name, index, task, result, validation}`.
- Snapshot `pipeline.deliverable_ok` is true only if at least one worker body is a real deliverable (not `FEHLER` / stub / &lt;400 chars).
- Snapshot `pipeline.validation` is the worst DoD gate (failed first).
- DOM is **not** keyed by job id. Reload shows current hub state, not a frozen job.

## Send vs Execute

| Action | API | Agents | Workers? |
|--------|-----|--------|----------|
| **Send** | `POST /api/chat` (`full` omitted) | Memory recall, Brainstorm, Flex absorb/chat + Box 1 start_work ask | **No** (except tool-drill / live-browser short-circuits, not Flex) |
| **Execute** | `POST /api/execute` | Distill → [clarify halt] → Flex → Coordinator plan → workers sequential | Yes, after distill (and after clarify unless Later) |
| **Send+Exec** | Send then Execute | Both | Yes |

Allowed short-circuits in `AGENTS.md`: tool drill, live browser nav, go-only (`mach das` / `ja` / `execute` after a prior task).

**Code is broader:** `_wants_auto_execute` also fires on HTML/build language (`baue`, `landing page`, `todo app`, …). Flex `maybe_request_execute` can fire from Send. Desk toast does not claim Send auto-executes.

`POST /api/chat?full=1`, `/api/reexecute`, `/api/workers/{id}/rerun`, `/api/tools/call`, `/api/mcp`, Telegram `/do` bypass the Execute button.

## Abort, error, reload, late result

| Event | Contract |
|-------|----------|
| **Cancel** | Soft flag. Honored between stages/workers, not mid-LLM/tool. Partials stay in Box 3. Memory store skipped. |
| **Error** | `_fail` → `stage=error`. Worker LLM failure → `FEHLER - kein Deliverable` (no fake stub). Pipeline may still `_finish` as `done`. |
| **Reload** | In-memory jobs lost on process restart. Browser loses `currentJobId`; does not resume poll. `GET /api/state` is the live desk. |
| **Late result** | Two pipeline jobs cannot overlap (lock). After `done`, `resyncState` can show the next job. `tools/call` is outside the job lock. |
| **Done** | `_finish` sets `stage=done` and clears `error` even when every worker is FEHLER. UI must use `deliverable_ok`, not stage alone. |

Workers run **sequentially**, not in parallel. `full_page_html` → one worker. `plan_mode=team` → up to 3.

## God-Mode / Dry-Run

Default **off**. Only `POST /api/god-mode` or `GNOM_GOD_MODE_AUTO=1`. Agents cannot enable it via LLM. Computer-use click/type/shell are dry-run until God is on. Inspect/OCR blocked without God. Flag is process-global, not per-job; it does **not** persist across restart.

## Known code/doc contradictions

1. AGENTS.md / CODE_ANALYSIS: no auto-execute on HTML after brainstorm. Code: `_wants_auto_execute` does.
2. CODE_ANALYSIS: Worker 3/4 default off. Code: all four on (`manager.py`, `enable_all`).
3. HUB_ARCHITECTURE: workers call tools with `TOOL_CALL`. Fixed on this branch: Orchestrator no longer zeroes `tools` after `__init__`; assigning `pipe.tools` also updates WorkerAgent. Prefetch remains the auto path.
4. Flex preset dropdown is disabled leftover chrome.
