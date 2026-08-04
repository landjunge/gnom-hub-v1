# Gnom-Hub v1

Local-first multi-agent system.

**Pipeline:** Brainstorm → Distillation → Coordinator → Workers  
**Control:** Toggle agents, budget protection, free models only when you want  
**UI:** Agent cards + 3 boxes + interactive Box 1  
**Portable:** USB-capable, desktop-only

## Status

**Step 0.1 done** – project structure + EventBus  
**Step 0.2 done** – Key.txt → `.env` + LLM-Manager (DeepSeek)

Full plan: [`docs/PRE_PLAN.md`](docs/PRE_PLAN.md)  
V1 scope: [`docs/V1_SCOPE.md`](docs/V1_SCOPE.md)

## Quick start

```bash
# 1) Keys (optional for smoke; required for live LLM)
cp Key.txt.example Key.txt
# edit Key.txt → set DEEPSEEK_API_KEY=...

# 2) Smoke
PYTHONPATH=src python -m gnom_hub.main
```

Expected:
```
[EventBus] hello -> {'msg': 'Gnom-Hub v1 ready'}
[Keys] ...
[LLM] DeepSeek key=yes|no ...
Gnom-Hub v1 - Step 0.2 OK
```

### Keys

| File | Role |
|------|------|
| `Key.txt` | Your secrets (gitignored). Source of truth on first setup. |
| `.env` | Private env written/merged from `Key.txt` (gitignored). |
| `Key.txt.example` / `.env.example` | Templates only |

Optional policy env vars:

- `GNOM_FREE_ONLY=1` — block non-free models
- `GNOM_MAX_BUDGET_USD=1.0` — session spend guard (estimate)

### Live DeepSeek call (manual)

```python
from gnom_hub.config import ensure_env_from_key_txt, load_keys
from gnom_hub.llm import LLMManager, LLMMessage

ensure_env_from_key_txt()
llm = LLMManager(keys=load_keys())
print(llm.chat([LLMMessage(role="user", content="Say hi in one word.")]).content)
```

## Structure

```
src/gnom_hub/
├── core/       EventBus
├── agents/     Brainstorm, Memory, Flex, Coordinator, Workers
├── memory/     HOT / WARM / COLD + Mermaid
├── llm/        LLM-Manager, DeepSeek
├── ui/         Desktop UI
├── config/     paths, Key.txt → .env
└── main.py
```

## Dev

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest tests/ -v
```

## Next

Step 0.3 – (TBD) Agent shells / UI skeleton per V1_SCOPE
