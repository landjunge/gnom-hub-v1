# Workflows & Presets (Gnom-Hub)

Stand: 2026-08-05 · Design from multi-agent research + current codebase.

## Layers (do not merge)

| Layer | Question | Storage | Status |
|-------|----------|---------|--------|
| **Agent preset** | How does one agent think? | Flex enum; `worker_presets.json` | **done** |
| **Team preset** | Who is on + which agent presets? | `team_presets.json` | **P0** |
| **Workflow** | What recipe (plan_mode, seed, team)? | `config/workflows/` or hot JSON | **P1** |
| **Session pack** | Snapshot of one run | packs/ | **done** (not a recipe) |
| **Pipeline** | Fixed stages BS→…→Workers | code | **done** — never replace with a second engine |

**Rule:** Workflow *parameterizes* the existing Orchestrator; it does not become LangGraph/CrewAI.

## Plan modes (whitelist)

| `plan_mode` | Coordinator behavior |
|-------------|----------------------|
| `default` | Normal assign / HTML auto if user text asks for a page |
| `full_page_html` | Deterministic full single-file page plan (no section split) |
| `plan_qa` | Checklist / review tasks, not HTML fragments |
| `diagnosis` | Prefer diagnosis-style distill (existing brainstorm modes stay separate) |

No free-form graphs. Extend only via new enum values + code paths.

## Team preset schema

```json
{
  "name": "landing-team",
  "flex": "security",
  "plan_mode": "full_page_html",
  "enabled": {
    "brainstorm": true,
    "memory": true,
    "flex": true,
    "coordinator": true,
    "worker1": true,
    "worker2": true,
    "worker3": false,
    "worker4": false
  },
  "tunes": {
    "worker1": {
      "system_prompt": "",
      "model": null,
      "temperature": 0.45,
      "max_tokens": 3200
    }
  }
}
```

- Memory stays enabled even if listed false (locked agent).
- `tunes` optional; missing slots leave current tuning.
- Keys/model system defaults from Key.txt are not wiped by empty tune fields.

## Workflow schema (P1, not required for Team)

```yaml
---
name: landing-page
description: Single-file HTML landing with previews
team: landing-team
plan_mode: full_page_html
seed: "Build a modern landing page … full HTML with inline CSS."
---
1. Brainstorm
2. Execute
3. Check Box 3 + export
```

Aligned with Agent Skills progressive disclosure: short description in UI; body optional.

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/team-presets` | list |
| POST | `/api/team-presets` | save current team as name |
| POST | `/api/team-presets/apply` | apply by name |
| POST | `/api/team-presets/delete` | delete by name |

Worker presets stay at `/api/worker-presets*`.

## UI

- System panel: Team presets (select / Apply / Save current / Delete)
- After apply: refresh agent cards + toast; chat system line with name + plan_mode

## Status

| Item | Status |
|------|--------|
| Team preset CRUD + apply | **done** (`/api/team-presets*`, System UI) |
| `plan_mode` on hub + coordinator | **done** |
| Workflow files + seed prompt | later (P1) — only if needed |
| SKILL.md export | later — not required |

Keep it thin: no second orchestrator, no graph engine.

## What we refuse

- Second orchestration runtime  
- Visual n8n-style editor in v1.x  
- Peer handoffs between workers  
- Unlimited dynamic agent spawn  

## Research anchors (why)

- Supervisor/orchestrator-worker fits fixed 8 agents; P2P/swarm do not.  
- Multi-agent hurts sequential reasoning when tasks are over-split → full_page_html.  
- CrewAI: team + YAML config.  
- Agent Skills / Cursor: recipe ≠ always-on rules; load procedure on demand.
