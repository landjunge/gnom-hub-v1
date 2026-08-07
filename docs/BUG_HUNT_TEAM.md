# Team Bug-Hunt Report (static)

**Date:** 2026-08-07  
**Method:** 4 parallel explore agents (orchestrator · jobs/locks · SQLite/memory · telegram/tools)  
**Also done same session:** Plugin loader harden (`73adc83`) — log failures, `/api/plugins.errors`, `PLUGIN_SECURITY.md`

Code wins over this doc if fixed later.

---

## Executive summary

| Area | Top theme |
|------|-----------|
| Orchestrator | Soft-cancel incomplete / turns into error; empty Flex notes crash |
| Jobs | Cancel vs finalize race; UI busy clears before thread exits |
| SQLite | HOT `save()` clear+rebuild not one transaction; WAL file copy |
| Telegram/Tools | **No chat allowlist**; open local API = God-Mode risk on LAN |

No classic `eval` / bare `except:` / SQL f-string injection in core scan.

---

## Priority backlog (team consensus)

### Critical

| ID | Finding | Where |
|----|---------|--------|
| C1 | Telegram: any `chat_id` can run `/do`, `/exec`, backup, warm clear, tools | `telegram/bot.py` ~108–124 |
| C2 | HOT `save()`: clear then re-insert without single transaction; crash → empty/partial HOT preferred over JSON | `memory/hot.py` + `sqlite_store` |
| C3 | `start()` treats `PipelineCancelled` as hard `_fail` | `orchestrator.py` ~146 |

### High

| ID | Finding | Where |
|----|---------|--------|
| H1 | Soft-cancel leaves mid-stage → `can_execute` stuck false | `orchestrator` + `snapshot_ops` |
| H2 | `answer_clarify` consumes question before work finishes | `orchestrator` |
| H3 | Flex notes whitespace → `IndexError` on `splitlines()[0]` | `orchestrator` ~481–489 |
| H4 | Worker outputs only assigned after full loop (cancel loses partial) | `orchestrator` |
| H5 | Job cancel TOCTOU: finalize can overwrite `cancelled` with `done` | `jobs.py` |
| H6 | `restore_for_reexecute` / checkpoint / pack without pipeline lock | `pipeline_api`, `session_*` |
| H7 | Cancel before `_finish` still can run memory/done | `orchestrator` |
| H8 | Unauth God-Mode + computer-use on open bind | `api/app.py` (127.0.0.1 default mitigates) |
| H9 | Inspect/OCR not gated by God-Mode | `computer_use/workflow.py` |
| H10 | `web_fetch` SSRF edge (IPv4-mapped / DNS rebind) | `tools/web_fetch.py` |
| H11 | Backup zip misses live `user.db`; `shutil.copy2` under WAL | `backup_ops`, `user_workspace` |

### Medium

| ID | Finding | Where |
|----|---------|--------|
| M1 | `rerun_worker` / `brainstorm_turn` / early `start` little or no cancel | orchestrator |
| M2 | UI `chatBusy` clears on status=cancelled while thread still holds lock | jobs + UI |
| M3 | `get_job` live snapshot for non-owner jobs | jobs.py |
| M4 | Telegram sync handlers block poll loop | bot.py |
| M5 | Plugin tools can overwrite core tool names | registry |
| M6 | God-Mode shell `cat`/`head` no path jail | action.py |
| M7 | `allow_path` prefix before `..` check (latent) | god_mode.py |
| M8 | Empty workers can still `_finish` success | orchestrator |
| M9 | WARM clear reports full wipe while Flex kept | warm.py API |
| M10 | DB `close()` leaves dead entry in `_instances` | sqlite_store |
| M11 | HTML gate can false-pass truncated docs with `</html>` | orchestrator |

---

## Suggested fix waves

1. **Safety:** C1 Telegram allowlist · H8/H9 God-Mode + inspect gate · H10 SSRF harden  
2. **Cancel correctness:** C3 · H1 · H5 · H7 · M1–M2  
3. **Data integrity:** C2 · H11 · M10 · transactions on multi-step DB ops  
4. **UX edge:** H2 · H3 · H4 · M8  

### Wave 1 status (2026-08-07)

| ID | Status | Notes |
|----|--------|-------|
| C1 | **Fixed** | `TELEGRAM_ALLOWED_CHAT_IDS`; empty allowlist denies real `chat_id`, allows test hook |
| H9 | **Fixed** | `inspect_screen` / OCR require God-Mode |
| H10 | **Fixed** | IPv4-mapped, link-local/metadata, `.local`, redirect+final re-check |
| H8 | Partial | Default bind 127.0.0.1 still primary; God-Mode explicit; Inspect gated |

---

## Not a full dynamic audit

This was **static**. No load tests, no live Telegram fuzz, no adversarial plugin pack run.

---

*Produced by parallel subagents; orchestrator/jobs/sqlite/telegram-tools.*
