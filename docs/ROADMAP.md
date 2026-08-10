# Roadmap

## V1.0.0 — COMPLETE

| Step | Title | Status |
|------|--------|--------|
| 0.x–1.6 | Core, UI, API, quality/CI | **done** |
| 2.0 | WARM + workspace + Telegram | **done** |
| 3.x | COLD, vector lite, God-Mode, plugins, async jobs | **done** |
| 4.x | Brainstorm→Execute, tuning, TTS/STT, trace, quality, checkpoint | **done** |
| 5.x | Workers 3/4, clean, backup, presets, compress, docs 1.0 | **done** |

## V1.1.0

| Item | Status |
|------|--------|
| Ollama local provider | **done** |
| web_fetch tool (SSRF-safe) | **done** |

## V1.2.0

| Item | Status |
|------|--------|
| Ollama model list in System UI | **done** |
| Auto web_fetch when tasks contain URLs | **done** |
| Export last results (Markdown download) | **done** |

## V1.3.0

| Item | Status |
|------|--------|
| Soft job cancel | **done** |
| Chat log sessionStorage | **done** |
| Worker presets apply/delete in System | **done** |
| Backups list API + System UI | **done** |

## V1.4.0

| Item | Status |
|------|--------|
| Backup zip download endpoint | **done** |
| Keyboard: Enter send, Ctrl+Enter execute, Esc cancel | **done** |
| Clear chat button | **done** |
| Live version badge in header | **done** |

## V1.5.0

| Item | Status |
|------|--------|
| Send+Execute one-shot button | **done** |
| Copy worker output | **done** |
| Auto-save after Execute | **done** |
| Delete backup (API + UI) | **done** |
| Help shows keyboard shortcuts | **done** |

## V1.6.0

| Item | Status |
|------|--------|
| Worker result download (HTML/txt) | **done** |
| Fullscreen HTML/source preview | **done** |
| Ctrl/⌘+S save shortcut | **done** |
| Focus + flash Box 3 after Execute | **done** |

## V1.7.0

| Item | Status |
|------|--------|
| Open HTML result in new browser tab | **done** |
| Save worker result to temp workspace (WS) | **done** |
| Chat log timestamps + structured persist | **done** |

## V1.8.0

| Item | Status |
|------|--------|
| Copy all worker results (Box 3 toolbar) | **done** |
| Diff first two workers (line LCS overlay) | **done** |
| Job duration timer in Box 3 header | **done** |
| Save worker result to permanent workspace (↑) | **done** |

## V1.8.1 (bugfix)

| Item | Status |
|------|--------|
| Clear sticky `pipeline.error` on re-execute | **done** |
| Job status by stage (not sticky error) | **done** |
| `web_fetch` re-validate redirect hops (SSRF) | **done** |
| Chat: log pipeline error only once / stage=error | **done** |
| UI: handle job.status cancelled | **done** |

## V1.9.0

| Item | Status |
|------|--------|
| Live cost badge (spend / budget warn) | **done** |
| Result history (session, restore Box 3) | **done** |
| Compact density mode | **done** |
| clarify_async under pipeline lock | **done** |
| install.sh shows real version | **done** |

## V2.0.0

| Item | Status |
|------|--------|
| Portable session pack (JSON export/import) | **done** |
| History Re-Exec (re-run workers from prior brainstorm) | **done** |
| Version badge / docs 2.0 | **done** |

## V2.1.0

| Item | Status |
|------|--------|
| Persist packs under data/packs/ | **done** |
| List / Load / Delete packs in System | **done** |
| Auto-pack after Execute (toggle + env) | **done** |
| Version / docs 2.1 | **done** |

## V2.2.0

| Item | Status |
|------|--------|
| Download named pack from list (↓) | **done** |
| Import file stores under data/packs/ | **done** |
| pack_max prune (env GNOM_PACK_MAX / System) | **done** |
| Version / docs 2.2 | **done** |

## V2.3.0

| Item | Status |
|------|--------|
| Rename pack label (PATCH + Ren) | **done** |
| mtime / exported_at in pack list | **done** |
| Optional label prompt on Pack ↓ | **done** |
| Version / docs 2.3 | **done** |

## V2.4.0

| Item | Status |
|------|--------|
| Pack ui_chat_log + ui_result_history | **done** |
| POST /api/session/pack/export with UI state | **done** |
| Import restores chat + History in UI | **done** |
| Version / docs 2.4 | **done** |

## V2.5.0

| Item | Status |
|------|--------|
| Pack workspace temp/perm (size-capped) | **done** |
| include_workspace on export | **done** |
| Pack list filter (label/name) | **done** |
| Version / docs 2.5 | **done** |

## V2.6.0

| Item | Status |
|------|--------|
| ui_prefs in pack (compact + ui_lang) | **done** |
| Pack notes field (export / list / Ren) | **done** |
| Import restores compact + lang | **done** |
| Version / docs 2.6 | **done** |

## V2.7.0

| Item | Status |
|------|--------|
| Telegram plain text → brainstorm turn | **done** |
| /bs + /exec (+ aliases) | **done** |
| /pack list \| save \| load | **done** |
| /do remains full one-shot | **done** |
| Version / docs 2.7 | **done** |

## V2.8.0

| Item | Status |
|------|--------|
| WARM remove_fact / remove_at / API delete+clear | **done** |
| System UI WARM list add/del/clear | **done** |
| Telegram /warm list\|add\|del\|clear | **done** |
| Telegram /cancel soft job cancel | **done** |
| /last includes quality + user | **done** |
| Version / docs 2.8 | **done** |

## V2.9.0

| Item | Status |
|------|--------|
| restore_cold / delete_cold | **done** |
| API POST …/restore + DELETE /api/cold/{id} | **done** |
| COLD browser Restore / Delete buttons | **done** |
| Telegram /cold list\|load\|del | **done** |
| Version / docs 2.9 | **done** |

## V3.0.0

| Item | Status |
|------|--------|
| Vector list/get/delete in store | **done** |
| GET /api/vector · DELETE · clear | **done** |
| Vec badge modal (search/add/list/del) | **done** |
| Telegram /vec search\|add\|list\|del\|clear | **done** |
| Version / docs 3.0 | **done** |

## V3.1.0

| Item | Status |
|------|--------|
| Trace export JSON/MD | **done** |
| Trace clear API + UI | **done** |
| Telegram /trace [n] \| clear | **done** |
| Version / docs 3.1 | **done** |

## V3.2.0

| Item | Status |
|------|--------|
| restore_backup (HOT/WARM/agents + optional checkpoint) | **done** |
| POST /api/backups/{name}/restore | **done** |
| System list Rest button | **done** |
| Telegram /backup list\|save\|load\|del | **done** |
| Version / docs 3.2 | **done** |

## V3.3.0

| Item | Status |
|------|--------|
| list_jobs + GET /api/jobs | **done** |
| usage_dict / reset + API | **done** |
| Cost badge → Usage & Jobs modal | **done** |
| Telegram /jobs /usage | **done** |
| Version / docs 3.3 | **done** |

## V3.4.0

| Item | Status |
|------|--------|
| Workspace export_zip (temp/perm/all) | **done** |
| POST export + GET download | **done** |
| UI ↓ zip buttons | **done** |
| Telegram /ws list\|cat\|promote\|del\|clear\|write | **done** |
| Version / docs 3.4 | **done** |

## V3.5.0

| Item | Status |
|------|--------|
| Tools modal (list/run/fetch) | **done** |
| Telegram /tools /tool /fetch | **done** |
| Plain-text arg convenience | **done** |
| Version / docs 3.5 | **done** |

## V3.6.0

| Item | Status |
|------|--------|
| HOT fact add/remove/clear/promote | **done** |
| API /api/memory/hot* | **done** |
| System HOT list UI | **done** |
| Telegram /hot list\|add\|del\|clear\|promote | **done** |
| Version / docs 3.6 | **done** |

## V3.7.0

| Item | Status |
|------|--------|
| Re-run single worker (API + ↻ button) | **done** |
| Cost USD on agent cards | **done** |
| Export result history (Hist↓ Markdown) | **done** |
| Version / docs 3.7 | **done** |

## V3.7.1

| Item | Status |
|------|--------|
| Fix Execute disabled after brainstorm (`lastCanExecute`) | **done** |
| Basic user E2E script (keyboard → landing page) | **done** |
| docs/BASIC_USER_TEST.md + AGENTS.md memory | **done** |

## V3.7.2

| Item | Status |
|------|--------|
| Tools modal: this-run tool_call history | **done** |
| Tools badge click → history | **done** |
| Snapshot test for tool_calls UI contract | **done** |
| Tool history: click JSON · copy · manual session log · fail badge | **done** |

## Post-V3.7 (optional)

| Item | Notes |
|------|--------|
| True embeddings | Replace lexical vector |
| Skill marketplace | Agent tool install |
| Auto-update | Channel + checksum |
| Mobile / remote UI | Explicitly out of V1 |

Heavy optional: real OCR/pyautogui — install extras yourself if needed.

## V3.7.6 (Worker prompt strategies)

| Item | Status |
|------|--------|
| Layered worker system prompt L1–L5 | **done** |
| Design prefetch: color_palette + scaffold + contrast | **done** |
| docs/WORKER_PROMPTS.md | **done** |
| tests/test_worker_prompts.py | **done** |
