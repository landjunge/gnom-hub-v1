# UI layer — error logic

How the SPA surfaces failures from API, jobs, tools, and worker drafts.

Source of truth for **server** envelopes: [ERROR_HANDLING.md](ERROR_HANDLING.md).  
UI code: `src/gnom_hub/ui/static/parts/` → built into `app.js`.

---

## Flow

```text
fetch /api/*
    |
    |- network fail     -> toast error · throw
    |- HTTP !ok         -> parse detail envelope -> toast [code] message · throw (err.detail)
    |- HTTP 200
         |- data.ok === false (tools) -> soft-fail toast · history row fail
         |- success path

Jobs (chat / execute / re-run)
    |
    |- job.status=error -> formatApiError · chat line · toast once · set lastReportedPipelineError
    |- applySnapshot

applySnapshot (poll + after job)
    |
    |- llm.auth badge   -> auth-warn / auth-bad classes
    |- pipeline.tool_calls -> Tools badge + history
    |- last_error + stage=error -> toast **once** (dedupe via lastReportedPipelineError)
    |- warnings -> toast **once** (lastWarningsKey)
    |- p.error -> chat system line once
    |- worker_outputs -> Box 3; FEHLER -> banner + .box3-fehler
```

---

## Rules

| Rule | Implementation |
|------|----------------|
| No toast spam on poll | `lastReportedPipelineError`, `lastWarningsKey`, `lastToolsKey`, `lastNudgeKey` |
| Structured API errors | `api()` reads `detail.message` / `code` / `retryable` |
| Job errors same format | `formatApiError(job.error)` |
| Tools soft-fail (HTTP 200, ok:false) | not "Tool ok"; red history; error toast |
| Worker honesty | `FEHLER` prefix -> banner, no treated as success HTML |
| Auth visibility | LLM badge `auth-warn` / `auth-bad` from `snap.llm.auth` |

---

## Known surfaces

| UI element | Error signal |
|------------|--------------|
| Toast host | Transient messages |
| Chat system lines | Persistent error text |
| LLM badge | Key/placeholder/blocked |
| Tools badge | `Tools: N·F!` on fails |
| Tools history | green/red rows · click -> JSON |
| Box 3 | `.fehler-banner` on FEHLER drafts |

---

## Checklist when changing UI error paths

1. Dedupe any toast that can fire from `applySnapshot` polls.  
2. Prefer `formatApiError` for job/API objects.  
3. Tools: handle both HTTP error **and** `ok: false` body.  
4. Rebuild: `python scripts/build_ui_js.py`.  
5. Worker FEHLER must stay visually distinct from success HTML.
