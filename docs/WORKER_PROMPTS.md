# Worker-Prompt-Strategien

How Gnom-Hub builds worker LLM prompts so deliverables stay **honest**, **wish-bound**, and **tool-aware**.

## Mental model

Workers **do not call tools mid-turn**. The hub **prefetches** allowlisted tools before `WorkerAgent.run`, injects results into the user message as `Tool prefetch (auto):`, and the system prompt tells the model how to use that block.

```
Execute
  → distill / flex / plan
  → worker_prefetch (install · design · web_fetch · memory)
  → WorkerAgent.run(system L1–L5, user = task + DoD + memory + prefetch)
  → Flex nudge if gaps
```

## Prompt layers

| Layer | Source | Role |
|-------|--------|------|
| **L0 Identity** | `HUB_IDENTITY` in `base.py` | Kill product-hallucination loops |
| **L1 Role** | `worker_system_prompt` | Concrete deliverable; FEHLER if impossible |
| **L2 Priority** | same | Structure → interaction → empty states → CSS last |
| **L3 Domain (HTML)** | only if `task_wants_html` | One complete file + design-tool rules |
| **L4 Flex wishes** | same | Absolute orders from `User:` / Flex |
| **L5 Tools** | same | Prefetch is ground truth |
| **User body** | `WorkerAgent.run` | Aufgabe · Original · Anforderungen · Memory · Prefetch |
| **Extra tuning** | `AgentState.system_prompt` | Appended by `BaseAgent.ask` (never replaces L1–L5) |

### L1–L5 assembly

```python
# gnom_hub.agents.roles_workers.worker_system_prompt
worker_system_prompt(wants_html=True|False)
```

HTML detection: keywords like `html`, `landing`, `website`, `seite`, `dashboard`, `frontend`, …

## Prefetch strategy (tools)

| Trigger | Tools | Purpose |
|---------|-------|---------|
| Package keywords (playwright, pillow, …) | `install_tool` dry → real | Self-heal deps |
| HTML / page / UI keywords | `color_palette` → `contrast_check` → `html_scaffold` | Design ground truth |
| `https://…` in task | `web_fetch` | Real page text |
| Wish / memory hints | `memory_search` | Standing context |

Budget: default `max_tool_calls=6`. Each call emits `pipeline.tool_call` for the Tools UI.

### Design seed heuristics

| Task language | Palette seed |
|---------------|--------------|
| (default) / dark | `dark` |
| ocean / blau / blue | `ocean` |
| forest / grün | `forest` |
| sunset / orange | `sunset` |
| brand / violet | `brand` |
| light / hell | `light` |

Scaffold kind: `dashboard` · `form` · `article` · else `landing`.

## Honesty strategy

| Condition | Output |
|-----------|--------|
| No usable LLM / placeholder key | `FEHLER - kein Deliverable` + reason |
| Auth 401/403 | same, via `user_message_for_failure` |
| Gate `_validate_worker_draft` sees FEHLER | Flex / quality path treats as `worker_error` |

Never invent green stubs. UI surfaces FEHLER banners and red chat lines (see `docs/UI_ERROR_LAYER.md`).

## DoD strategy (Coordinator → Worker)

Coordinator distill prefers **testable** lines (observable behavior or complete deliverable, e.g. full HTML with `</html>`).  
HTML full-page plan: **one** worker owns the page (`_html_full_page_plan`) — no parallel competing HTML.

Flex agent restates binding wishes into worker-facing hints; nudge after workers if gaps.

## What good worker prompts do

1. **Absolute wishes first** — Flex beats decoration  
2. **Finish the file** — never sacrifice `</html>` for CSS  
3. **Reuse design prefetch** — no second palette  
4. **Cite tool truth** — no hallucinated fetch content  
5. **Fail loudly** — FEHLER, not empty success  

## What they deliberately do *not* do

- Full agentic tool-calling loops inside one worker turn (budget + KISS)  
- Replace L1–L5 with user card tuning (tuning only **appends**)  
- Store HTML/code as durable memory facts  

## Related

- Prefetch: `src/gnom_hub/tools/worker_prefetch.py`  
- Worker agent: `src/gnom_hub/agents/roles_workers.py`  
- Orchestrator inject: `pipeline/orchestrator.py` (`Tool prefetch (auto):`)  
- Design plugin: `plugins/web_design/`  
- Error UI: `docs/UI_ERROR_LAYER.md`  
- Auth honesty: `tests/test_worker_honesty.py`  
