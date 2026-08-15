# Changelog — 3.10.0 (V4 Skills wave)

## 3.10.0 (2026-08-10)

### Skills (playbooks)
- Local skill loader: `skills/` + `data/skills/user/`
- Seed skills: `html_landing`, `tool_honesty`, `de_desk`
- Soft inject into worker system prompts
- API: GET/POST skills, enable, install (text-only packs)
- UI: Skills badge + modal (reload, enable, install path)
- Catalog: `docs/skills_catalog.json`
- Docs: SKILLS.md · freeze wording updated (playbooks OK)

### Marketplace light
- Local catalog + install from path
- Rejects skill packs containing `.py`

### Neural embeddings (optional)
- Plugin `embeddings_neural` (fastembed / sentence-transformers if installed)
- `pip install gnom-hub[embeddings]` for fastembed extra
- Default remains bow

### Mobile
- Responsive CSS @ max-width 640px (stack boxes, scroll agents, touch targets)

### Version
- `__version__` = 3.10.0

## 3.10.1 finish

- Learned skills S2: learn / learn_from_last + UI **Als Skill speichern**
- Skill inject: Brainstorm + Coordinator + Workers
- Seed `qa_checklist`; Telegram `/skills` `/skill_on` `/skill_off`
- Mobile box tabs ≤640px
- Docs: ORCHESTRATION.md · GITHUB_HOLDER_3.10.md
- F-03 Protect: no stub / no legacy DeepSeek spillover when Tollgate denies; chat shows 🛑 Protect

## Neural install

- `requirements-embeddings.txt` + fastembed wired in API/UI
- Preference restore via `data/hot/vector_embedder.json`

## UI quality polish

- Coherent agent color family (no pure neon clash); CSS tokens ok/warn/err/radius
- Adaptive job poll (faster start, calmer mid-work, slower when tab hidden)
- focus-visible + prefers-reduced-motion
- docs/UI_QUALITY.md

## Memory freshness

- `memory_search` = HOT + WARM lexical + Vector hybrid (layer/indexed flags)
- Promote / warm API / goals / session pack: sync vector index on write
- Write-then-read tests · docs/MEMORY_FRESHNESS.md

## Prefetch why · Clarify Later

- tool_calls carry `reason` (UI + chat + job tool_log)
- Clarify **Later** defers without workers (deferred_clarifies)
- docs/PIPELINE_RELIABILITY.md

## Reliability follow-ups

- Resume deferred clarify (API + Box 1 list)
- Job timeout → FEHLER error (not soft-cancelled only)
- Prefetch why lines in quality_notes

## Desk hardening

- Tools badge title + toast include prefetch **why**
- Session pack / checkpoint persist **deferred_clarifies**
- Job error poll surfaces **FEHLER** clearly

## Box3 honesty · pack tools · poll timeout FEHLER

- Box3 DoD checklist gets `validation` again + FEHLER banner CSS
- Session pack: tool_calls + tool_log round-trip
- Client poll cancel `?as_timeout=1` → server FEHLER finalize
- Toast/chat FEHLER dedupe on job error
