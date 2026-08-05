# Gnom-Hub v3.7.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB · COLD · Vector · Trace · Backup · Jobs · Workspace · Tools · HOT facts · **↻ single-worker re-run** · **card cost** · **Hist↓**.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## HOT vs WARM

| Layer | Lifetime | System | Telegram |
|-------|----------|--------|----------|
| **HOT** | Session (reset clears) | Add / Del / Clear / →W promote | `/hot …` |
| **WARM** | Durable across reset | Add / Del / Clear | `/warm …` |

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=79**

---

## UI (3.7)

| Control | Action |
|---------|--------|
| **↻** (worker panel) | Re-run that worker only |
| **Hist↓** | Export session result history as Markdown |
| **Agent cards** | `tok · $cost` per agent |
| **Re-Exec** | Full re-execute from history brainstorm (2.0+) |

---

## API (new in 3.7)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/workers/{worker1–4}/rerun` | Re-run one worker (`?sync=1` optional) |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 3.4 | Workspace zip + /ws |
| 3.5 | Tools browser + /tools /fetch |
| 3.6 | HOT facts manager + promote to WARM |
| **3.7** | Single-worker re-run, card cost, history export |

---

## Dev

```bash
./scripts/quality_check.sh
```

Docs: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## License

Private use.
