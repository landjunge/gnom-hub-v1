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
