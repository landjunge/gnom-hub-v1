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

## Post-V2.4 (optional)

| Item | Notes |
|------|--------|
| True embeddings | Replace lexical vector |
| Skill marketplace | Agent tool install |
| Auto-update | Channel + checksum |
| Mobile / remote UI | Explicitly out of V1 |

Heavy optional: real OCR/pyautogui — install extras yourself if needed.
