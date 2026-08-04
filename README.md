# Gnom-Hub v1

Local-first multi-agent system.

**Pipeline:** Brainstorm → Distillation → Coordinator → Workers  
**Control:** Toggle agents, budget protection, free models only when you want  
**UI:** Agent cards + 3 boxes + interactive Box 1  
**Portable:** USB-capable, desktop-only

## Status

**Step 0.1 done** – project structure + EventBus

Full plan: [`docs/PRE_PLAN.md`](docs/PRE_PLAN.md)  
V1 scope: [`docs/V1_SCOPE.md`](docs/V1_SCOPE.md)

## Quick start

```bash
# from repo root (with PYTHONPATH=src)
PYTHONPATH=src python -m gnom_hub.main
```

Expected:
```
[EventBus] hello -> {'msg': 'Gnom-Hub v1 ready'}
Gnom-Hub v1 - Step 0.1 OK
```

## Structure

```
src/gnom_hub/
├── core/       EventBus
├── agents/     Brainstorm, Memory, Flex, Coordinator, Workers
├── memory/     HOT / WARM / COLD + Mermaid
├── llm/        LLM-Manager, keys
├── ui/         Desktop UI
├── config/     Config + keys
└── main.py
```

## Next

Step 0.2 – Key.txt → .env + LLM-Manager (DeepSeek)
