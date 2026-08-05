# Keys & Models — single source of truth (for agents & humans)

**Do not put real secrets in this file.** Real values live only in local `Key.txt` / `.env` / `data/hot/agents.json` (gitignored).

Last verified: **2026-08-05** against [DeepSeek API Pricing](https://api-docs.deepseek.com/quick_start/pricing/) and [Change Log](https://api-docs.deepseek.com/updates/).

---

## 1. Official DeepSeek API

| Item | Value |
|------|--------|
| Base URL (OpenAI format) | `https://api.deepseek.com` |
| Chat path | `/chat/completions` |
| Auth | `Authorization: Bearer <key>` |
| Anthropic-compatible base | `https://api.deepseek.com/anthropic` |

### Model IDs (use these strings as `model`)

| Model ID | Role | Notes |
|----------|------|--------|
| **`deepseek-v4-flash`** | **Default / recommended** | V4 Flash official; public beta 2026-07-31; fast & cheap |
| `deepseek-v4-pro` | Higher quality | Same endpoint; higher price |
| `deepseek-chat` | Legacy | Older alias; prefer v4-flash |
| `deepseek-reasoner` | Legacy thinking | Prefer thinking mode on v4 models |

**Gnom-Hub code default:** `src/gnom_hub/llm/deepseek.py` → `DEFAULT_MODEL = "deepseek-v4-flash"`.

### Pricing (USD per 1M tokens, regular / cache-miss)

| Model | Input (cache miss) | Input (cache hit) | Output |
|-------|--------------------|-------------------|--------|
| `deepseek-v4-flash` | $0.14 | $0.0028 | $0.28 |
| `deepseek-v4-pro` | $0.435 | $0.003625 | $0.87 |

Context: **1M**. Max output: **384K**.  
Gnom-Hub cost estimate uses cache-miss rates in `_PRICE_PER_M` (`deepseek.py`).

### Thinking mode

V4 Flash/Pro default to **thinking on** in the API, which can:

- spend `max_tokens` on reasoning and leave `message.content` empty/short
- make hub worker HTML outputs look “poor” or blank

**Gnom-Hub default:** send `"thinking": {"type": "disabled"}` for `deepseek-v4*` models.

| Env | Effect |
|-----|--------|
| `DEEPSEEK_THINKING=0` (default) | non-thinking, stable content |
| `DEEPSEEK_THINKING=1` | thinking enabled (slower, may need higher max_tokens) |

If content is still empty, client falls back to `reasoning_content` when present.

---

## 2. Local files (secrets)

| File | Git | Purpose |
|------|-----|---------|
| **`Key.txt`** | ignored | Source of truth for keys + model |
| **`.env`** | ignored | Generated / merged from Key.txt on start |
| **`data/hot/agents.json`** | ignored | Per-agent `api_key` + `model` after hub applies Key.txt |
| **`Key.txt.example`** | tracked | Template only |

### Canonical `Key.txt` shape

```text
# Model (official id)
DEEPSEEK_MODEL=deepseek-v4-flash

# System agents + global default
DEEPSEEK_API_KEY=sk-...
SYSTEM=sk-...

# All workers
WORKER_API_KEY=sk-...
WORKER=sk-...
```

### Key.txt aliases → env names (`config/keys.py`)

| Alias in Key.txt | Canonical env |
|------------------|---------------|
| `deepseek`, `system`, `system_key`, … | `DEEPSEEK_API_KEY` |
| `worker`, `workers`, `worker_key`, … | `WORKER_API_KEY` |
| `model`, `deepseek_model`, `default_model` | `DEEPSEEK_MODEL` |

### How hub applies keys (`Hub._apply_keys_from_keyfile`)

| Source | Agents |
|--------|--------|
| `DEEPSEEK_API_KEY` | brainstorm, memory, flex, coordinator |
| `WORKER_API_KEY` | worker1, worker2, worker3, worker4 |
| `DEEPSEEK_MODEL` | `llm.default_model` + **every** agent `.model` |

Order on start: load `agents.json` → apply Key.txt keys/model → save agents.json.

---

## 3. Ollama (local, optional)

| Item | Value |
|------|--------|
| Default host | `OLLAMA_HOST` or `http://127.0.0.1:11434` |
| Default model env | `OLLAMA_MODEL` (code default often `llama3.2`) |
| Route in Gnom-Hub | model prefix `ollama/` or `ollama:` |

If no DeepSeek key but Ollama is up, manager may auto-route to Ollama.

---

## 4. Env vars (product)

| Variable | Meaning |
|----------|---------|
| `DEEPSEEK_API_KEY` | System / global cloud key |
| `WORKER_API_KEY` | Shared worker key |
| `DEEPSEEK_MODEL` | Default DeepSeek model id |
| `GNOM_FREE_ONLY` | Block paid models if set |
| `GNOM_MAX_BUDGET_USD` | Soft spend cap |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | Local LLM |
| `GNOM_UI_LANG` | `en` / `de` |
| `GNOM_TELEGRAM_POLL` | Auto bot poll |
| `GNOM_WEB_ALLOW_LOCAL` | web_fetch private hosts |

---

## 5. Agent map (8 cards)

| Agent ID | Key bucket | Default model |
|----------|------------|---------------|
| `brainstorm` | system | `DEEPSEEK_MODEL` |
| `memory` | system | same |
| `flex` | system | same |
| `coordinator` | system | same |
| `worker1` … `worker4` | worker | same |

`has_key` / `online` = agent enabled AND (per-agent key OR global DeepSeek OR Ollama).

---

## 6. Smoke checks (no re-research needed)

```bash
# 1) Key.txt parses
python -c "from pathlib import Path; from gnom_hub.config.keys import parse_key_file; print(parse_key_file(Path('Key.txt').read_text()))"

# 2) Live chat with flash (uses system key from Key.txt)
python scripts/smoke_live.py   # or minimal chat/completions POST

# 3) Hub state after start
curl -s http://127.0.0.1:8080/api/state | python -c "import sys,json; d=json.load(sys.stdin); print(d['llm'].get('default_model')); print([(a['id'],a.get('model')) for a in d['agents']])"
```

Expected: `default_model == deepseek-v4-flash` and all agents same model.

---

## 7. Change log (project decisions)

| Date | Decision |
|------|----------|
| 2026-08-05 | Keys: system vs worker split in Key.txt |
| 2026-08-05 | Model: **`deepseek-v4-flash`** (official id; not “deepseek-flash”) |
| 2026-08-05 | Per-agent keys persisted in `data/hot/agents.json` |
| 2026-08-05 | This doc created so agents skip re-research |

---

## 8. Related docs

- [`Key.txt.example`](../Key.txt.example) — template  
- [`BASIC_USER_TEST.md`](BASIC_USER_TEST.md) — keyboard E2E  
- [`AGENTS.md`](../AGENTS.md) — coding rules  
- Code: `src/gnom_hub/config/keys.py`, `llm/deepseek.py`, `llm/manager.py`, `hub.py` (`_apply_keys_from_keyfile`)
