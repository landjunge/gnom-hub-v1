# Plan vs Code — Abgleich (komplett)

Stand: 2026-08-05 · Repo `gnom-hub-v1` · nach „komplett abarbeiten“

Quellen: Pre-Plan (04.08.), `V1_SCOPE.md` vs. Code.

---

## Legende

| Symbol | Bedeutung |
|--------|-----------|
| ✅ | umgesetzt |
| 🟡 | dünn / heuristisch / Demo |
| ❌ | bewusst nicht / später |

---

## Pre-Plan Kern

| Thema | Status |
|-------|--------|
| Brainstorm zuerst, dann Execute | ✅ |
| 4 feste Agenten + bis 4 Worker | ✅ (W3/W4 default off) |
| Flex-Presets | ✅ Dropdown |
| Memory HOT/WARM/COLD + Mermaid/Offload | ✅ / 🟡 |
| Kontext-Kompression | ✅ `HotMemory.compress_if_needed` |
| Dual Workspace temp/perm | ✅ UI + API |
| Agent-Tuning 5 Slider + Prompt | ✅ |
| TTS / STT | ✅ Browser Web Speech |
| Online/Offline Karten | ✅ |
| Box-Rahmen = aktiver Agent | ✅ |
| System-Panel (Keys, budget, lang) | ✅ |
| Light Trace | ✅ |
| Worker Quality Check | ✅ Heuristik |
| Checkpoint Resume | ✅ |
| Clean State | ✅ `/api/clean` |
| Backup | ✅ zip unter `data/backups/` |
| Worker-Presets speichern | ✅ |
| DE/EN Tooltips | ✅ |
| EventBus + Atomic + Key.txt | ✅ |
| Job-Listener-Leak fix + Pipeline-Lock | ✅ |
| Viewport-Layout | ✅ |

---

## Bewusst dünn / nicht voll Pre-Plan

| Thema | Status | Kommentar |
|-------|--------|-----------|
| Dynamische Worker-Erzeugung | 🟡 | 4 feste Slots, an/aus — kein Spawn neuer Klassen |
| Skills / Tool-Nachladen | 🟡 | Plugin/MCP Gerüst |
| Internet-Surfen | ❌ | nicht gebaut |
| Echte Kernel/God-Mode | 🟡 | Allowlist-Shell, dry-run |
| Self-Explaining Videos | ❌ | |
| Install-Wizard USB/LLM-Erkennung | 🟡 | scripts/install.sh only |
| Update-System | ❌ | Backup zip manuell |
| Echtes Embedding-Vector | 🟡 | lexikalisch |
| LLM Quality Review | 🟡 | nur Heuristik |

---

## API (Auszug neu)

- `POST /api/execute`, `POST /api/chat` (brainstorm) / `?full=1`
- `POST /api/agents/{id}/tune`, `POST /api/agents/enable-all`
- `GET/POST /api/system`, `GET /api/trace`
- `POST /api/checkpoint/save|load`
- `POST /api/clean`, `POST /api/backup`
- `GET/POST /api/worker-presets`, `POST …/apply`
- Workspace: write, promote, file, clear-temp, delete

---

## Bedienung (Kurz)

1. **Send** = Brainstorm-Dialog  
2. **Execute** = Distill → Flex → Worker 1–4 (enabled) → Quality → Memory  
3. **Worker 3/4** = Doppelklick zum Einschalten  
4. **Workspace** = Temp → Promote  
5. **System** = Lang DE/EN, Checkpoint, Backup, Clean  

---

*SSOT für „was der Plan noch will vs. was da ist“.*
