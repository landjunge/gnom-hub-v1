# Error-handling strategies (Gnom-Hub)

How failures are classified, retried, and shown — without lying and without leaking secrets.

Code: [`src/gnom_hub/core/errors.py`](../src/gnom_hub/core/errors.py) · [`config/auth.py`](../src/gnom_hub/config/auth.py) · [`plugins/retry.py`](../src/gnom_hub/plugins/retry.py)

---

## Layers

| Layer | Responsibility | Primary types |
|-------|----------------|---------------|
| **Auth / LLM** | Keys, 401, rate limit, network | `KeyStatus`, `LlmFailureKind`, `user_message_for_failure` |
| **Tool** | Registry, plugins, retries | `ToolRetry`, `ToolFailed`, `error_envelope` |
| **Pipeline** | Stages, cancel, worker FEHLER | `PipelineCancelled`, quality gates |
| **API** | HTTP mapping | `HTTPException` + structured `detail` |
| **IO** | Backups, workspace files | `FileNotFoundError`, `ValueError` |

---

## Rules (non-negotiable)

1. **No fake success** — missing/placeholder keys → worker text with **FEHLER**, never “(Stub) ready”.
2. **No secret echo** — `sanitize_message` strips long `sk-…` tokens; snapshots use fingerprints only.
3. **Retry only when safe** — `ToolRetry` / rate-limit / network; never retry auth after 401 (session blocklist).
4. **Structured when crossing process/UI** — envelope fields below.
5. **User text is actionable** — “what to fix”, not stack traces in the chat.

---

## Envelope shape

```json
{
  "ok": false,
  "layer": "tool",
  "code": "tool_failed",
  "message": "human-readable, sanitized",
  "retryable": false,
  "detail": null
}
```

| Field | Meaning |
|-------|---------|
| `layer` | `llm` · `tool` · `pipeline` · `api` · `validation` · `io` · `auth` · `internal` |
| `code` | stable machine id (`ErrorCode`) |
| `message` | UI / toast |
| `retryable` | agent or client may try again |
| `detail` | optional short structured data |

`POST /api/tools/call` puts this object in HTTP `detail` on failure (status from code).

---

## Tool path

```text
handler
  ├─ return ok dict          → 200 { ok: true, result }
  ├─ return { ok:false }     → 200 { ok: false, result, error: envelope }
  ├─ raise ToolRetry         → registry retries (budget) → else ToolFailed
  ├─ raise ToolFailed        → 422 + envelope (or mapped status)
  ├─ TypeError/ValueError    → ToolFailed code=validation
  └─ other Exception         → ToolFailed code=internal
```

Plugin helpers: `from gnom_hub.plugins.sdk import ok, fail, retry`.

| Exception | Retry? | Terminal? |
|-----------|--------|-----------|
| `ToolRetry` | yes (budget) | after exhausted |
| `ToolFailed` | only if `retryable=True` (rare) | default yes |
| `KeyError` unknown tool | no | 404 |

---

## LLM / auth path

| Kind | Worker behavior | Nudge re-run? |
|------|-----------------|---------------|
| missing / placeholder key | FEHLER text | no |
| AUTH (401) | FEHLER + blocklist fingerprint | no |
| RATE_LIMIT | FEHLER / message | maybe later |
| NETWORK | FEHLER | soft yes |
| OTHER | FEHLER truncated | quality-dependent |

See `classify_api_key` · `classify_llm_failure` · `keys_auth_snapshot`.

---

## HTTP status map (tools / generic)

| Code | HTTP |
|------|------|
| `not_found` / `tool_unknown` / `not_found_file` | 404 |
| `validation` / `tool_failed` / `tool_retry_exhausted` | 422 |
| `bad_request` | 400 |
| `auth` / `missing_key` | 401 |
| `rate_limit` | 429 |
| `network` | 502 |
| `cancelled` | 409 |
| `internal` / `unknown` | 500 |

---

## UI

- Toast uses `detail.message` (+ `[code]`) when `detail` is an object.
- Tools history marks `ok:false` rows red; badge `Tools: N·F!` on fails.
- Pipeline errors stay on `snapshot.pipeline.error` / `last_error`.

---

## Checklist for new code

1. Pick layer + code; prefer envelope over bare strings at API boundary.  
2. Decide **retryable** explicitly.  
3. Never put raw keys in `message`.  
4. Workers: on auth/missing → FEHLER, not stub HTML.  
5. Add a unit test for the new failure mode.

---

## Related

- [PYTHON_CACHE.md](PYTHON_CACHE.md) — CI failures vs app errors  
- [PLUGIN_SECURITY.md](PLUGIN_SECURITY.md) — plugin trust  
- [AGENTS_DEFINITION.md](AGENTS_DEFINITION.md) — Flex / worker contracts  
