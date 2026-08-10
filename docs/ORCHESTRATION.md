# Agent orchestration (exact)

How the 8 fixed agents run — **no second orchestrator**.

## Pipeline (the only workflow)

```
chat ──► brainstorm_turn* ──► [user clicks Execute]
                                 │
                                 ▼
                    distill → flex → coordinate → work(workers) → quality → done
```

| Stage | Agent(s) | Output |
|-------|----------|--------|
| brainstorm | Brainstorm (+ Flex contribute) | Box 2 notes / dialogue |
| distill | Coordinator | requirements list (+ optional clarify) |
| flex | Flex | wishes / personal notes (protected) |
| coordinate | Coordinator | plan: worker → task lines |
| work | Worker 1–4 | deliverables + TOOL_CALL tools |
| quality | heuristics + Flex nudges | quality_notes / agent_nudges |

**Short-circuits:** `tool_drill` and `browser_nav` skip HTML team plans.

## plan_mode (Coordinator strategy only)

| Mode | Behavior |
|------|----------|
| `default` | Heuristic; `full_page_html` if score ≥ 3 |
| `full_page_html` | One worker, complete single-file page |
| `team` | Multi-worker split allowed |
| `plan_qa` | QA checklist style |
| `diagnosis` | Root-cause style |

Scoring: `_html_page_score` in `plan_fast_path.py`. Soft playbook skills **do not** replace this.

## Skills in the loop (prompt inject)

```
SkillLoader (skills/ + data/skills/user)
        │ match(agent, plan_mode, task_kind, text)
        ▼
skills_prompt_block → appended to system prompts
        │
        ├── Brainstorm
        ├── Coordinator (LLM plan path)
        └── Workers (L1–L5 + skills)
```

Skills never change stage order. Soft triggers only.

## Plugins vs skills vs presets

See [SKILLS.md](SKILLS.md) · [PLUGINS.md](PLUGINS.md) · [WORKFLOWS_AND_PRESETS.md](WORKFLOWS_AND_PRESETS.md).

## Learned skills (S2)

User confirms after Execute:

- UI: Skills modal → **Als Skill speichern**
- API: `POST /api/skills/learn_from_last` or `POST /api/skills/learn`
- Writes markdown under `data/skills/user/learned_*`

No auto-exec, no `.py`.

## Architecture map

Full desk layers: [HUB_ARCHITECTURE.md](HUB_ARCHITECTURE.md) · V4 plan: [V4_PLAN.md](V4_PLAN.md).
