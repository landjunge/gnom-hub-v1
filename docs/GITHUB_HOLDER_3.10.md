# GitHub holder summary — Gnom-Hub 3.10.x

**Audience:** release notes / PR epic summary for maintainers.

## Headline

**3.10.0 V4 desk wave:** playbook skills, local skill catalog, optional neural embeddings plugin, mobile responsive UI — without breaking freeze (no workflow engine, no second orchestrator).

## PR timeline (this wave + closeout)

| PR | Topic |
|----|--------|
| #13–#21 | Coordinator scoring, export/cancel hygiene, v3.9.1, toasts |
| #22–#25 | Embeddings lite + plugin disk + docs + mermaid |
| #26 | V4 design plan |
| #27–#28 | Skills / marketplace light / neural plugin / mobile → 3.10.0 |
| #29 (this) | Learned skills, orchestration docs, mobile tabs, qa skill, telegram |

## What changed for users

1. **Skills badge** — enable/disable playbooks; install folder; **Als Skill speichern** after Execute  
2. **Better HTML plans** — scoring + `html_landing` skill inject  
3. **Vector embedder** switch in Vector modal (bow / char_ngram / hashing)  
4. **Mobile** — ≤640px stack + box tabs  
5. **Telegram** — `/skills`, `/skill_on`, `/skill_off`

## What changed for agents

| Agent | Skills |
|-------|--------|
| Brainstorm | soft inject (e.g. de_desk) |
| Coordinator | soft inject on LLM plan path |
| Workers | soft inject on HTML/tool tasks |
| Flex / Memory | unchanged roles; Flex wishes still protected |

## Architecture (one paragraph)

Fixed 8-agent hub: Brainstorm→Execute pipeline only. Coordinator chooses plan_mode (incl. full_page_html fast path). Workers deliver via layered prompts + tools. **Skills** = markdown playbooks injected into system prompts. **Plugins** = executable tools. Memory HOT/WARM/COLD/Vector; vector default bow with optional neural plugin.

## Files to know

| Path | Role |
|------|------|
| `src/gnom_hub/skills/` | loader, inject, match, learned save |
| `skills/*/skill.md` | bundled seeds |
| `docs/ORCHESTRATION.md` | stage map |
| `docs/SKILLS.md` | skill authoring |
| `docs/HUB_ARCHITECTURE.md` | layers |
| `docs/V4_PLAN.md` | design |

## Install / verify

```bash
git pull
source .venv/bin/activate
PYTHONPATH=src pytest tests/ -q
# optional neural:
# pip install 'gnom-hub[embeddings]'
```

## Explicit non-goals (still)

- Remote auto-install marketplace executing code  
- Workflow graph / second orchestrator  
- Neural embeddings as default CI path  
- Native mobile app  
