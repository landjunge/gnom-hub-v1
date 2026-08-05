# V1 Implementation Roadmap

| Step | Title | Status |
|------|--------|--------|
| 0.1 | Project structure + EventBus | **done** |
| 0.2 | Key.txt → .env + LLM-Manager (DeepSeek) | **done** |
| 0.3 | Agents: base, manager, toggle, status events | **done** |
| 0.4 | Pipeline: chat → brainstorm → distill → coord → workers | **done** |
| 0.5 | Memory HOT: session.json + mermaid canvas + offload | **done** |
| 0.6 | Desktop UI skeleton (cards, boxes, chat, save) | **done** |
| 0.7 | HTTP API + wire UI ↔ hub | **done** |
| 0.8 | Interactive distillation (Box 1 Yes/No/…) | **done** |
| 0.9 | Flex presets API + per-agent model/key | **done** |
| 1.0 | Polish, start script, README runbook | **done** |
| 1.1 | Hardening: Flex stage, coordinator skip, UI status, install | **done** |
| 1.2 | UX: tokens on cards, toasts, LLM usage in snapshot | **done** |
| 1.3 | Phase 2+: agent state persist, canvas API, live DeepSeek verified | **done** |
| 1.4 | LLM soft-fallback, max_tokens, Help/Reset, session clear | **done** |
| 1.5 | Memory → pipeline context (HOT facts feed all stages) | **done** |
| CI | Install `.[dev]` so httpx is present for TestClient | **done** |
| 1.6 | Quality: smoke_e2e, quality_check.sh, empty hints, CI smoke | **done** |
| 2.0 | WARM lite (durable facts) + dual workspace + optional Telegram | **done** |
| 3.0 | COLD archive, vector lite, God-Mode, Computer-Use kit, plugins/MCP-lite | **done** |
| 3.1 | Vector→pipeline, auto-COLD on reset, UI badges, allowlisted shell | **done** |
| 3.2 | UI God toggle, COLD browser, optional live DeepSeek smoke | **done** |

Heavy optional still (real OCR/pyautogui/embeddings models): install extras yourself if needed.
