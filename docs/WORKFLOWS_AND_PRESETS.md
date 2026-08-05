# Presets & plan_mode (frozen design)

**Decision (2026-08-05):** No workflow engine. No skill files. No graph.
Config snapshots + one plan strategy flag. Pipeline stays fixed.

## Mental model (3 things only)

| # | Name | Question | Where |
|---|------|----------|--------|
| 1 | **Agent setup** | Who is on? How does each think? | Toggles, Flex preset, Worker presets, Team snapshot |
| 2 | **plan_mode** | How does Coordinator assign work? | `hub.plan_mode` → Coordinator.plan |
| 3 | **Pipeline** | What stages run? | Orchestrator (code) — **not configurable** |

**Session pack** = save/load a run. Not a recipe. Do not mix with presets.

## What we ship

### Worker preset
One worker’s tuning (prompt, temp, max_tokens, model).  
API: `/api/worker-presets*` · System UI.

### Team preset
Named snapshot: `enabled` + `flex` + `plan_mode` + optional worker `tunes`.  
API: `/api/team-presets*` · System UI Save / Apply / Delete.  
File: `data/hot/team_presets.json`.

### plan_mode (whitelist)

| Value | Effect |
|-------|--------|
| `default` | Normal assign; auto full-page HTML if user text looks like a page |
| `full_page_html` | Always full single-file page plan (no section split) |
| `plan_qa` | Checklist / QA-style tasks |
| `diagnosis` | Root-cause / evidence-style tasks (Coordinator only; not Brainstorm) |

API: `POST /api/plan-mode` · System dropdown. Also stored inside team presets.

## Explicitly out of scope (do not build)

- Workflow JSON/YAML recipes with seed prompts  
- SKILL.md / Agent Skills marketplace  
- Second orchestrator (LangGraph, CrewAI Flows, …)  
- Visual workflow editor  
- Peer handoffs between workers  
- Dynamic agent spawn beyond the fixed 8  

If a future need appears: extend **plan_mode** enum + one code branch, or a thicker Team snapshot — not a new subsystem.

## Why this freeze

- Anthropic / production practice: simplest path first; fixed workflows beat free multi-agent graphs when the path is known.  
- Gnom-Hub’s pipeline **is** the workflow. Extra “workflow” layers only rename config.  
- Multi-agent over-split hurts quality (`full_page_html` already fixes the real bug).  
- YAGNI: Team + plan_mode cover Save/Apply and plan discipline.

## Maintainer rule

Before adding preset/workflow features: does it fix a real user pain after live E2E?  
If not → leave frozen.
