# DoD Gate (automated)

Deterministic Definition-of-Done checks run **after every worker draft** (and on Flex fix re-validation).

| Piece | Module |
|-------|--------|
| Lint codes | `pipeline/dod_lint.py` · [DOD_LINT.md](DOD_LINT.md) |
| Gate engine | `pipeline/dod_gate.py` |
| Orchestrator | thin wrappers + retry loop |
| Events | `pipeline.dod_gate`, `pipeline.quality_retry` |

## Flow

```
worker.run → validate_worker_draft (auto)
                │
                ├ worker_error / stub → stop (no retry)
                ├ should_retry? → format_retry_hint → worker.run (≤2)
                └ final gate → validation on worker_outputs
                     + bus: pipeline.dod_gate
```

## What is checked

1. **Honesty** — FEHLER/Deliverable, stub, too short, ellipsis  
2. **HTML** (when task wants a page) — complete doc, `</html>`, interaction, CSS-before-JS  
3. **Absolute wishes** — `User:` / `Wish:` / `Flex-wish:` reflected in body  
4. **Prefetch palette** — if `color_palette` ran ok, primary hex or `--color-*` must appear  

## Result shape (`validation`)

```json
{
  "ok": true,
  "issues": ["no_interaction"],
  "chars": 1200,
  "html_complete": true,
  "has_interaction": false,
  "score": 75,
  "retryable": true,
  "hints": ["no_interaction: Prefer a small working control…"],
  "soft_issues": ["no_interaction"],
  "checklist": [{"id": "…", "pass": false, "severity": "should"}]
}
```

Legacy fields (`ok`, `issues`, `chars`, `html_complete`, `has_interaction`) stay stable.

## Retry policy

| Situation | Retry |
|-----------|-------|
| `worker_error`, `stub` | no |
| `incomplete_html`, interaction must, `wish_missing` | yes ≤2 |
| `prefetch_palette_unused` | yes **once** |
| soft-only (`no_interaction`) | no auto-retry |

Hints come from the lint catalog (`hints_for_issues`).

## API usage

```python
from gnom_hub.pipeline.dod_gate import run_dod_check, should_retry, format_retry_hint

gate = run_dod_check(body, user_text=…, task=…, requirements=…, tool_calls=…, bus=bus)
if should_retry(gate, user_text=…)[0]:
    hint = format_retry_hint(gate, attempt=1)
```

## Related

- Plan: [DOD_GATE_PLAN.md](DOD_GATE_PLAN.md)  
- Lint: [DOD_LINT.md](DOD_LINT.md)  
- Prefetch: [WORKER_PREFETCH.md](WORKER_PREFETCH.md)  
