# DoD Linting Rules

Stable **issue codes** and **structure checks** for Definition-of-Done.

Code: `src/gnom_hub/pipeline/dod_lint.py`  
Plan: [DOD_GATE_PLAN.md](DOD_GATE_PLAN.md)

## Layers

| Layer | Function | Purpose |
|-------|----------|---------|
| **Rule catalog** | `DOD_LINT_RULES` | Codes the gate emits (`incomplete_html`, …) |
| **Spec structure** | `lint_dod_spec(spec)` | Spec shape: ids, severity, html/wish coverage |
| **Prompt structure** | `lint_dod_prompt(text)` | Markers `=== DEFINITION OF DONE` / checkboxes |
| **Code hygiene** | `lint_issue_codes(codes)` | No unknown codes in results |
| **Scoring helpers** | `score_from_issues` / `retryable_from_issues` / `hints_for_issues` | Retry + UI |

## Severity

| Level | Meaning | Default retry |
|-------|---------|----------------|
| **must** | Hard fail → `ok=False` | per rule (`retryable`) |
| **should** | Soft fail → `soft_ok` path / nudge | often once |
| **info** | Annotation only | no |

## Catalog (excerpt)

| Code | Severity | Retry | Category |
|------|----------|-------|----------|
| `worker_error` | must | no | honesty |
| `stub` | must | no | honesty |
| `too_short` | must | yes | honesty |
| `truncated_ellipsis` | must | yes | honesty |
| `incomplete_html` | must | yes | html |
| `missing_html_close` | must | yes | html |
| `missing_required_interaction` | must | yes | html |
| `no_interaction` | should | yes | html |
| `css_before_functions` | should | yes | html |
| `wish_missing` | must | yes | wish |
| `prefetch_palette_unused` | should | yes | prefetch |
| `prefetch_scaffold_ignored` | info | no | prefetch |
| `req_unmatched` | should | no | req |
| `multi_html_collision` | should | no | meta |

Full list: `catalog()` or import `DOD_LINT_RULES`.

**Do not rename codes lightly** — UI, Flex nudges, and tests depend on them.

## Spec structure rules

`lint_dod_spec` enforces:

- `items` non-empty list  
- `item.id`: `[a-z][a-z0-9_]{1,47}` **or** `wish_*` / `req_N`  
- unique ids  
- `severity` ∈ must|should|info  
- label ≥ 3 chars (should)  
- `wants_html` ⇒ at least one HTML item  
- `wishes` ⇒ at least one `wish_*` item (should)  
- ≥1 `must` item (should)

## Prompt structure rules

Workers still get a text block. It must:

```text
=== DEFINITION OF DONE (mandatory) ===
  [ ] …        ← MUSS checklist
  [!] …        ← absolute wishes
=== END DoD ===
```

`lint_dod_prompt` checks markers, order, checkboxes, absolute `[!]` when wish language appears, and length (info if >6k chars).

## Usage

```python
from gnom_hub.pipeline.dod_lint import (
    catalog,
    lint_dod_spec,
    lint_dod_prompt,
    lint_issue_codes,
    hints_for_issues,
    retryable_from_issues,
    score_from_issues,
)

# After building a spec (Slice B)
assert not [i for i in lint_dod_spec(spec) if i.severity == "must"]

# After rendering prompt
assert not [i for i in lint_dod_prompt(dod_text) if i.severity == "must"]

# After gate
codes = result.issues
assert not lint_issue_codes(codes)  # all codes known
if retryable_from_issues(codes):
    retry_with(hints_for_issues(codes))
score = score_from_issues(codes)  # 0–100
```

## Adding a rule

1. Append a `DodLintRule` to `DOD_LINT_RULES` (unique `code`).  
2. Document in this file + `DOD_GATE_PLAN.md` issue table.  
3. Map Flex nudge message in `roles.py` when implementing gate.  
4. Add/adjust `tests/test_dod_lint.py`.  
5. Never reuse a retired code for a different meaning.

## Ruff / Python style (module conventions)

Same as hub library code (`pyproject.toml`):

- `line-length = 100`, `target-version = py310`  
- No bare `except` without logging/emit  
- Public helpers typed; catalog frozen dataclasses  
- Tests under `tests/test_dod_*.py`

## Related

- Gate plan: `docs/DOD_GATE_PLAN.md`  
- Prefetch: `docs/WORKER_PREFETCH.md`  
- Worker prompts: `docs/WORKER_PROMPTS.md`  
