# Memory freshness — searchable as soon as written

## Problem

Classic multi-layer bug: fact lands in HOT/WARM, but `memory_search` only hit the
vector store → **“just updated, not searchable”** until some later index path ran.

## Current design (after 3.10 freshness fix)

| Layer | Write | Search |
|-------|--------|--------|
| **HOT** | sync (session) | **sync lexical** via `memory_search` |
| **WARM** | sync (SQLite) | **sync lexical** + promote/API also **vector upsert** |
| **Vector** | **sync** on durable writes (`vectors.add` embeds immediately) | hybrid BM25 + cosine |

There is **no background embedding queue** today. With BOW / hashing embedders that is fine
(milliseconds). Neural (`fastembed`) is still **synchronous on write** — acceptable for
short facts; if it ever blocks UX, add async re-embed later without dropping lexical.

### Freshness flags

Each `memory_search` hit may include:

| Field | Meaning |
|-------|---------|
| `layer` | `hot` · `warm` · `vector` |
| `indexed` | `true` if a stored embedding vector exists |
| `layers` | all layers that matched after dedupe |

### Write paths that index

- Pipeline wiring: requirements, memory agent, flex wishes, goals
- **Promote HOT → WARM** → `index_durable_fact`
- **POST warm fact API** → index
- Flex learn buttons · session pack restore

### Tests

```bash
pytest tests/test_memory_freshness.py -q
```

Write-then-read is mandatory: save fact → immediate search → must hit.

### Jobs / pipeline notes

- **Busy lock:** second Execute while a job runs returns `busy` (no double pipeline).
- **Soft cancel:** cooperative between stages; in-flight LLM call may still complete cost-wise.
