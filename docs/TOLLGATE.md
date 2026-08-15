# Stack: ThreadDesk · Gnom · Tollgate

Drei Rollen, **kein zweiter Provider-Stack** in Gnom.

| Schicht | Rolle | Ruft Cloud-Provider? |
|---------|--------|----------------------|
| **ThreadDesk** | Kontext vorbereiten (`td gnom`, TD-Knopf) | nein |
| **Gnom-Hub v1** | Desk, Brainstorm, Execute, Worker | nein — nur Client |
| **Tollgate** | Keys, Budget, Route, Chat, Search, TTS | **ja, allein** |

Lokal darf Gnom **Ollama** direkt sprechen. DeepSeek/OpenRouter/Zen nur über Tollgate (`GNOM_TOLLGATE_LLM=1`, Default).

`GET /api/health` und Snapshot tragen `stack.providers_owner`. Default: `tollgate`.
Nach einem Chat liegt die von Tollgate gewählte Route in `llm.last_route` (provider/model). Gnom wählt nicht selbst.

Legacy (nicht der Desk-Pfad):

```bash
export GNOM_TOLLGATE_LLM=0   # direkter DeepSeek-Client — nur Opt-out
```

# Gnom + Tollgate

Gnom is a **client**. Tollgate owns keys, budgets, and routing.

## Default (in-process)

With `tollgate` installed in the same venv:

```bash
export GNOM_WS=$HOME/WS-gnom-hub-v1
export TOLLGATE_HOME=$GNOM_WS   # same User/Key.txt
export GNOM_TOLLGATE_LLM=1      # default: all cloud LLM via Tollgate
# gnom-hub
```

Brave search and ElevenLabs budget already go through the gateway.

## HTTP mode (separate Tollgate process — like n8n)

```bash
# terminal 1
export TOLLGATE_HOME=$HOME/WS-gnom-hub-v1
cd ~/tollgate && ./scripts/desk-up.sh

# terminal 2 — Gnom
export TOLLGATE_URL=http://127.0.0.1:8787
export TOLLGATE_CONSUMER=gnom   # or gnom:<secret> if auth on
export GNOM_WS=$HOME/WS-gnom-hub-v1
# start gnom-hub
```

## n8n

| Field | Value |
|-------|--------|
| OpenAI Base URL | `http://127.0.0.1:8787/v1` |
| API Key | `n8n` or `n8n:<secret>` |
| Model | `tollgate/free` |

## Tools via Tollgate

| Tool | Path |
|------|------|
| `web_search` | Brave → gateway admit + ledger |
| `elevenlabs_budget` | EL floor via Tollgate |
| LLM chat | `GNOM_TOLLGATE_LLM=1` (default) |

## Opt out

```bash
export GNOM_TOLLGATE_LLM=0   # legacy direct DeepSeek client only
```

## Desk check

```bash
# Tollgate repo
./scripts/desk-check.sh
```
