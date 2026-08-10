# Worker Prefetch Strategy (deep)

How Gnom-Hub **plans and budgets** tool runs before workers execute.

See also: [WORKER_PROMPTS.md](WORKER_PROMPTS.md) (prompt layers that consume this block).

## Why prefetch (not agentic tool loops)

| Goal | Mechanism |
|------|-----------|
| **Deterministic cost** | Hard `max_tool_calls` + category caps |
| **Visible tools** | Every call → `pipeline.tool_call` → Tools UI |
| **Ground truth** | Workers treat injected text as fact |
| **KISS** | No mid-turn ReAct loop in V1 |

```
task blob
   │
   ▼
plan_prefetch()  ── pure, no I/O
   │  ordered PrefetchStep list
   ▼
prefetch_for_workers()
   │  budget checks · registry · execute
   ▼
"[prefetch] used N/M · ran: …"
 + chunks joined by ---
   │
   ▼
Worker user message: Tool prefetch (auto):
```

## Plan → execute

### `plan_prefetch(blob)`

Builds `PrefetchStep{name, category, priority, cost, reason, args, optional}`.

| Priority band | Category | Tools |
|---------------|----------|--------|
| 10+ | **install** | `install_tool` (≤2 packages) |
| 20+ | **design** | `color_palette` → `contrast_check?` → `html_scaffold` → `css_tokens?` |
| 30+ | **workspace** | `workspace_read` for mentioned basenames |
| 40+ | **net** | `web_fetch` (ranked URLs) |
| 50 | **memory** | `memory_search` on wish language |

`optional=True` steps (`contrast_check`, `css_tokens`) yield first under budget pressure.

### `prefetch_for_workers(...)`

| Budget | Default |
|--------|---------|
| `max_tool_calls` | **8** if HTML/UI task else **6** |
| Category soft caps | install 4 · design 4 · net 3 · memory 1 · workspace 2 |
| `max_context_chars` | 12_000 (truncate chunks, never explode prompt) |
| `max_urls` | 3 |

Returns context **string**, or `PrefetchReport` when `return_report=True`.

Header line always when anything planned/ran:

```text
[prefetch] used 4/8 calls · ran: color_palette, contrast_check, html_scaffold · skipped: css_tokens:budget
```

## Heuristics

### Design

- Trigger: html / landing / website / seite / dashboard / css / …
- Seed: ocean/blau · forest/grün · sunset · rose · brand · light · slate · else **dark**
- Scaffold kind: dashboard · form · article · else **landing**
- `contrast_check` uses palette `text` on `surface` after palette succeeds

### URLs

- Dedupe; rank **docs / github / mdn** higher; `utm_` lower
- Cap `max_urls`

### Workspace

- Regex basenames: `*.html`, `*.css`, `*.js`, `*.md`, …
- Read `temp` then fallback `perm`

### Memory

- Trigger on wish/always/dark theme/flex/…
- Query = clause around hint (not full multi-URL blob)

### Install

- Allowlist only (playwright, pillow, …)
- dry_run first; install only if missing
- Counts as 1–2 calls per package

## API surface

```python
from gnom_hub.tools.worker_prefetch import (
    plan_prefetch,
    prefetch_for_workers,
    tool_calls_needed,
    default_max_tool_calls,
    PrefetchReport,
)

plan = plan_prefetch(task_text)
ctx = prefetch_for_workers(task_text, bus=bus, tools=registry, memory=mem)
rep = prefetch_for_workers(task_text, tools=registry, return_report=True)
assert isinstance(rep, PrefetchReport)
```

Orchestrator: `_prefetch_worker_tools` uses `default_max_tool_calls` when cap omitted.

## What we deliberately skip

- Full agentic tool-calling inside the worker LLM turn  
- Unbounded web crawls  
- Non-allowlisted package install  
- Huge HTML dumps (scaffold/html/css truncated)

## Tests

- `tests/test_worker_prefetch.py` — plan order, budgets, design report, workspace, context cap  
- `tests/test_worker_prompts.py` — design detection + registry design tools  

## Related code

- `src/gnom_hub/tools/worker_prefetch.py`  
- `src/gnom_hub/pipeline/orchestrator.py` (`_prefetch_worker_tools`)  
- `plugins/web_design/` · `plugins/install_tool/`  
- `docs/WORKER_PROMPTS.md` L5 tool protocol  
