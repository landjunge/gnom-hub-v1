# DoD-Gate — Implementierungsplan

Ziel: **Definition of Done** als **strukturiertes, prüfbares Gate** — nicht nur Prompt-Text + lose Heuristiken.

Status heute: **teilweise vorhanden** (Inject + `_validate_worker_draft` + Retry + Flex-Nudge).  
Lücke: Gate kennt **Prefetch/Design/Wishes** nicht, API ist flach (`ok` + `issues[]`), Modul sitzt im Orchestrator-Monolith.

---

## 0. Ist-Zustand (Code)

| Baustein | Ort | Rolle |
|----------|-----|--------|
| DoD-Text inject | `_definition_of_done` → an `task_full` | Prompt-Pflichtkatalog |
| Draft-Gate | `_validate_worker_draft` | HTML complete, interaction, stub, FEHLER, length |
| Retry loop | Execute `while retries < 2` | incomplete_html / missing_interaction / gate_fail |
| Aggregate | `_quality_check` | score/7 + notes string |
| Flex | `nudge_gaps` / `_heuristic_nudges` | Issues → Worker-Messages |
| UI | snapshot `validation`, `quality_notes` | Box 3 / Tools history partial |

### Was das Gate **heute** prüft

- `too_short`, `worker_error`, `stub`
- HTML: `incomplete_html`, `missing_html_close`, `no_interaction`, `missing_required_interaction`, `css_before_functions`
- `truncated_ellipsis`

### Was es **nicht** prüft

- Prefetch-Design genutzt? (CSS-Variablen aus `color_palette`)
- Absolute Wishes (`User:` / `Flex-wish:`) im Deliverable?
- DoD-Checkboxen aus Requirements (nur Keyword-Hit in quality score)
- Multi-worker: ein HTML-Owner vs. alle
- Strukturelles `DoDResult` (severity, checklist, retryable, code)

---

## 1. Zielbild

```
DoDSpec  ──build──►  from requirements + user_text + prefetch report
   │
   ▼
DoDGate.check(body, spec)  →  DoDResult
   │
   ├─ ok / fail / soft_fail
   ├─ checklist: [{id, label, pass, severity}]
   ├─ issues: machine codes (stable)
   ├─ retryable: bool
   └─ hints: short strings for retry prompt / Flex nudge
   │
   ├─► Worker retry (if retryable)
   ├─► quality_notes (human)
   ├─► agent_nudges
   └─► snapshot.validation (UI FEHLER / badges)
```

**Prinzipien**

1. **Deterministisch first** — Regex/Struktur vor LLM-Judge  
2. **Stable issue codes** — UI + Nudge + Tests hängen daran  
3. **Prefetch-aware** — Design-Ground-Truth ist Teil der Spec  
4. **KISS** — kein zweites LLM im Gate (optional später)  
5. **Ehrlichkeit** — `worker_error` = hard fail, kein Retry-Spam  

---

## 2. Datenmodell (neu)

Datei-Vorschlag: `src/gnom_hub/pipeline/dod_gate.py`

```python
@dataclass
class DoDItem:
    id: str                 # e.g. "html_complete", "wish:dark_theme"
    label: str
    severity: str           # "must" | "should" | "info"
    kind: str               # "html" | "wish" | "req" | "prefetch" | "honesty"

@dataclass
class DoDSpec:
    items: list[DoDItem]
    wants_html: bool
    wishes: list[str]       # absolute lines
    req_keywords: list[str]
    prefetch_css_vars: list[str]   # e.g. ["--color-primary"]
    prefetch_used_tools: list[str]

@dataclass
class CheckResult:
    id: str
    pass_: bool             # field name: passed
    detail: str = ""

@dataclass
class DoDResult:
    ok: bool
    soft_ok: bool           # should-fails only
    issues: list[str]       # stable codes
    checklist: list[dict]
    retryable: bool
    hints: list[str]
    score: int              # 0–100
    chars: int
    html_complete: bool | None
    has_interaction: bool | None
```

**Issue-Code-Katalog (stabil)**

| Code | Severity | Retry? |
|------|----------|--------|
| `worker_error` | must | no |
| `stub` | must | no* |
| `too_short` | must | yes |
| `incomplete_html` | must (if wants_html) | yes |
| `missing_html_close` | must | yes |
| `missing_required_interaction` | must | yes |
| `no_interaction` | should | yes |
| `css_before_functions` | should | yes |
| `truncated_ellipsis` | must | yes |
| `wish_missing` | must | yes |
| `prefetch_palette_unused` | should | yes |
| `req_unmatched` | should | soft |
| `multi_html_collision` | should | no (coord issue) |

\* stub: only if LLM available; else treated like worker_error

---

## 3. Spec bauen (`build_dod_spec`)

Eingaben:

- `user_text`, `requirements`, optional `PrefetchReport` / tool_calls list, `plan_mode`

Schritte:

1. Filter meta-requirements (`_is_flex_meta_requirement`)  
2. Dedupe requirements (`dedupe_texts` strategy=requirement)  
3. Extract absolute wishes (`User:`, `Wish:`, `Flex-wish:`)  
4. `wants_html` via existing `_wants_one_html_page` / `task_wants_html`  
5. From prefetch/tool_calls: collect CSS var names if `color_palette` ok  
6. Emit `DoDItem`s:

| Item id | When |
|---------|------|
| `honesty` | always |
| `html_complete` + `html_interaction` | wants_html |
| `wish:{hash}` | each absolute wish (keyword extract) |
| `req:{i}` | top 4–6 requirements as should/must |
| `prefetch_palette` | if color_palette ran ok |

`_definition_of_done` text stays for **prompt inject**, but is **generated from the same `DoDSpec`** so prompt and gate never diverge.

---

## 4. Check-Pipeline (`DoDGate.check`)

Reihenfolge (fail-fast where useful, still collect all musts):

```
1. Honesty: FEHLER+Deliverable → worker_error (stop retries)
2. Length / stub / ellipsis
3. If wants_html:
     html_complete, close tag, interaction, css_heavy
4. Wishes: each wish → token match in body (normalized)
5. Prefetch: if --color-primary (or listed vars) in palette result
     → body should contain at least one --color-* or primary hex
6. Requirements: soft keyword coverage
7. Score + retryable = any failed must with retryable code
```

**Wish matching (KISS v1)**

- Normalize: lower, strip `user:` prefix  
- Tokens: words length > 3, minus stopwords  
- Pass if ≥50% tokens hit OR full phrase substring  
- Special: `dark` + (`theme`|`mode`|`dunkel`) → look for dark bg / `prefers-color-scheme` / `#0`/`#1` surfaces  

**Prefetch palette (v1)**

- If tool_calls contain ok `color_palette` with `primary`:  
  - pass if `primary` hex in body OR `--color-primary` in body  
  - else `prefetch_palette_unused` (should → retryable once)

---

## 5. Orchestrator-Integration (Slice)

### Slice A — Extract + parity (no behavior change)

1. Move `_validate_worker_draft`, `_html_complete`, `_has_interaction`, `_css_heavy_*`, `_definition_of_done` → `dod_gate.py`  
2. Thin wrappers in orchestrator for imports/tests  
3. `DoDResult` serializes to **same dict shape** as today (`ok`, `issues`, `chars`, …) + extra fields  
4. All existing tests green  

### Slice B — Spec-driven DoD text

1. `build_dod_spec` + `render_dod_prompt(spec)` replaces hand-built string  
2. Same markers `=== DEFINITION OF DONE` for tests  
3. Checklist items mirror gate ids  

### Slice C — Prefetch + wish checks

1. Pass `tool_calls` / `PrefetchReport` into gate  
2. New issues + Flex nudge messages  
3. Retry hint includes failing checklist labels  

### Slice D — UI

1. Snapshot: `validation.checklist`, `validation.score`  
2. Box 3: small checklist under FEHLER / weak  
3. Tools modal: optional link “DoD fail reasons”  
4. Chat: retry only when `retryable`  

### Slice E — Optional LLM judge (later)

- Only if `soft_ok is False` and musts passed — “does this match user intent?”  
- Budget 1 call, never overrides `worker_error`  

---

## 6. Retry-Policy (klar)

| Condition | Action |
|-----------|--------|
| `worker_error` / auth | **no** auto-retry |
| `incomplete_html`, interaction, palette_unused, wish_missing | retry ≤2 with **structured hints** from `DoDResult.hints` |
| only `should` fails | no retry; Flex nudge only |
| after max retries still must-fail | keep result + `validation.ok=False` + quality fail |

Retry prompt template (replace free-form strings):

```
RETRY (DoD Gate):
Failed MUST:
- {id}: {label} — {detail}
Do this next:
- {hint}
Do NOT: re-litigate wishes; invent new palette if prefetch provided one.
```

---

## 7. Tests

| Test | Assert |
|------|--------|
| `test_dod_spec_from_html_task` | wants_html items present |
| `test_dod_gate_incomplete_html` | issues include incomplete_html, retryable |
| `test_dod_gate_worker_error_not_retryable` | FEHLER path |
| `test_dod_wish_absolute` | missing dark theme → wish_missing |
| `test_dod_prefetch_palette` | palette hex unused → prefetch_palette_unused |
| `test_dod_prompt_parity` | render contains same req lines as spec |
| `test_orchestrator_wrapper_compat` | old `_validate_worker_draft` API |

Keep: `test_worker_honesty`, flex wish DoD tests, pipeline quality tests.

---

## 8. Dateien / Diff-Schätzung

| File | Change |
|------|--------|
| `src/gnom_hub/pipeline/dod_gate.py` | **new** core |
| `src/gnom_hub/pipeline/orchestrator.py` | import + pass tool_calls; thinner |
| `src/gnom_hub/agents/roles.py` | nudge map new issue codes |
| `src/gnom_hub/snapshot_ops.py` | optional checklist pass-through |
| `tests/test_dod_gate.py` | **new** |
| `docs/DOD_GATE.md` | user-facing after implement |
| UI parts (later) | checklist render |

Effort: Slice A–B ~0.5–1d · C ~0.5d · D ~0.5d · E optional.

---

## 9. Nicht-Ziele (V1)

- LLM-as-judge as primary gate  
- Pixel/visual regression  
- Cross-worker merge gate beyond single-HTML plan  
- Blocking Execute permanently (user can always re-exec)  

---

## 10. Empfohlene Reihenfolge

1. **Slice A** extract + parity (safe)  
2. **Slice C** prefetch palette + wishes (highest product value after V3.7.7 prefetch)  
3. **Slice B** unified prompt from spec  
4. **Slice D** UI checklist  
5. **Slice E** only if soft fails stay noisy  

---

## 11. Acceptance

- [ ] Existing honesty + HTML gate tests still pass  
- [ ] New `test_dod_gate.py` covers codes + retryable  
- [ ] HTML run with design prefetch: unused palette → should-fail + one retry hint  
- [ ] Absolute wish missing → must-fail + Flex nudge  
- [ ] `worker_error` never burns 2 LLM retries  
- [ ] Docs: `DOD_GATE.md` + ROADMAP V3.8.x  

---

## 12. Open questions (for product)

1. Wish fail = **must** or **should**? (Plan default: **must**)  
2. Palette unused = **should** (retry once) or **must**? (Plan default: **should**)  
3. Should gate results block stage `done` or only annotate? (Plan: **annotate + nudge**, never hang pipeline)  
