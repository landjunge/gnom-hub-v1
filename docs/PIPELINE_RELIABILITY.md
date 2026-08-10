# Pipeline reliability — prefetch why · clarify Later · busy/cancel

## Prefetch transparency

Each auto tool call now carries:

| Field | Meaning |
|-------|---------|
| `reason` | Why prefetch fired (e.g. `URL in task`, `wish/preference language`) |
| `mode` | Usually `prefetch` |
| `tool` / `name` | Tool id (job log listens to both) |

Surfaces: Tools modal (`why:`), Box-3 strip title, live chat `Tool: … why:`.

## Clarify → Later

| Option | Behavior |
|--------|----------|
| Yes / concrete choice | Workers run as before |
| **Later** / Später / Später entscheiden | **No workers**, stage → brainstorm, question cleared |
| | Stored in `deferred_clarifies` + HOT note |

No zombie clarify box; user can Send again when ready.

## Busy / cancel

- Second Execute while busy → `busy` response (lock)
- Soft cancel: cooperative; in-flight LLM may still complete cost-wise
- See `tests/test_jobs_cancel.py`

## Tests

```bash
pytest tests/test_prefetch_why_clarify_later.py tests/test_jobs_cancel.py -q
```
