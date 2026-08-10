# Changelog — 3.9.x

## 3.9.1 (2026-08-10)

### Coordinator plan quality
- Weighted `_html_page_score` (≥3) for `full_page_html` fast path
- Sharper single-worker HTML prompt (never-truncate, Binding DoD)
- LLM multi-worker HTML only when `plan_mode=team`
- Expanded DE/EN page phrases (`onepager`, `webseite bauen`, `mach eine seite`, …)

### Observability
- `html_score` / `resolved_plan_mode` in snapshot, export, session pack, Box 3 label
- Toast on Execute done: `Plan: full_page_html · score=N`

### Stability
- Export pin + session pack deep-copy (race hardening)
- Tool-loop cancel isolation (no sticky hub cancel)
- Reset/clean clear `cancel_check`

### Plugins
- `scan_disk()` drop-in inventory; Tools modal shows disk + errors
- Version single source: `gnom_hub.__version__`

### API
- `GET /api/plugins` → `disk` field
- `GET /api/ollama/models` force-probes availability
