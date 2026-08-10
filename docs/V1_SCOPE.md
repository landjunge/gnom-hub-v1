# Gnom-Hub – V1 Scope (final, 1.0.0)

Stand: 05.08.2026

V1 ist **fertig** als lauffähiger Multi-Agent-Hub.  
Alles darüber hinaus → `PRE_PLAN.md` / Roadmap, nicht blockierend.

---

## Ziel von v1.0

1. Frei brainstormen (mehrere Chat-Turns)
2. Explizit **Execute** → Destillation + Worker
3. 1–4 Worker steuern (3/4 default aus)
4. Desktop-UI: Karten, 3 Boxen, Chat, System, Workspace

---

## In v1.0 **drin**

### Agenten
- Brainstorm, Memory, Flex, Coordinator
- Worker 1–4 (EventBus, Toggle, Tuning, TTS)
- Flex-Presets: security / neutral / researcher

### Pipeline
- `brainstorm_turn` + `execute` (+ `full` one-shot)
- Clarify in Box 1
- Quality-Heuristik + Light Trace + Checkpoint

### LLM
- DeepSeek, pro Agent Model/Key, free-only, Budget

### UI
- Viewport-füllend, Agent-Zeile = Box-Breite
- Box-Rahmenfarbe = aktiver Agent
- HTML Preview in Box 3
- System: lang DE/EN, backup, clean, checkpoint
- Mic STT

### Memory & Workspace
- HOT / WARM / COLD, Mermaid + Offload, Kompression
- Temp + Permanent Workspace + Auto-Capture nach Execute

### Technik
- EventBus, Atomic Writes, relative Pfade, Key.txt → .env
- Install mit OS/USB-Hinweis, pinned dev-tools für CI

---

## Parked (nicht v1-Blocker)

- Skill-Marketplace / auto tool load
- Web-Surfing-Agent
- Echte Kernel-Rechte
- Auto-Update-Kanal
- True embeddings → **partial** (pluggable bow/char_ngram/hashing + embeddings_lite; neural optional)
- Self-explaining videos
- Mobile UI

---

**Ende V1 Scope — v1.0.0 complete**

## Runtime constraint

**No Docker.** Gnom-Hub V1 is a local Python process (venv + FastAPI + static SPA). Do not add Dockerfile/compose for the default path.
