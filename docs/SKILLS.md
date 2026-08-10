# Playbook Skills (V4)

Skills are **markdown playbooks** injected into agent system prompts.
They are **not** plugins (no code) and **not** a workflow engine.

## Layout

| Path | Role |
|------|------|
| `skills/<id>/skill.md` | Bundled seeds (git) |
| `data/skills/user/<id>/skill.md` | User / installed packs |
| `docs/skills_catalog.json` | Local catalog (marketplace light) |

## Frontmatter

```yaml
---
id: html_landing
name: Single-file HTML landing
version: 0.1.0
enabled: true
tags: [html, frontend]
agents: [coordinator, worker1]
triggers: [full_page_html, html_page]
---
Body markdown…
```

## API

| Method | Path |
|--------|------|
| GET | `/api/skills` |
| POST | `/api/skills/reload` |
| POST | `/api/skills/{id}/enable` body `{enabled}` |
| POST | `/api/skills/install` body `{path}` local folder |

## Rules

1. No `.py` inside skill packs (install rejects)
2. Soft match only — Coordinator still owns plan_mode
3. Body size capped on inject (~3.5k total)
