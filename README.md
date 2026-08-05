# Gnom-Hub v3.7.1

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB · COLD · Vector · Trace · Backup · Jobs · Workspace · Tools · HOT facts · **↻ re-run** · **card cost** · **Hist↓** · **Execute re-enable fix**.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=80**

---

## Basic user test (keyboard → landing page)

Real browser + real keyboard (Playwright), live LLM:

```bash
python scripts/user_landing_e2e.py
# optional: GNOM_E2E_HEADED=1 python scripts/user_landing_e2e.py
```

Doc: [`docs/BASIC_USER_TEST.md`](docs/BASIC_USER_TEST.md)

---

## UI (3.7.x)

| Control | Action |
|---------|--------|
| **Send / Enter** | Brainstorm |
| **Execute** | Workers (must enable after brainstorm — fixed in 3.7.1) |
| **↻** | Re-run one worker |
| **Hist↓** | Export result history |
| **Cards** | `tok · $cost` |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 3.6 | HOT facts + promote to WARM |
| 3.7 | Single-worker re-run, card cost, Hist↓ |
| **3.7.1** | Execute re-enable after brainstorm; basic user E2E |

---

## Dev

```bash
./scripts/quality_check.sh
python scripts/user_landing_e2e.py   # needs server + key + playwright
```

Docs: [`docs/ROADMAP.md`](docs/ROADMAP.md) · [`docs/BASIC_USER_TEST.md`](docs/BASIC_USER_TEST.md) · [`docs/KEYS_AND_MODELS.md`](docs/KEYS_AND_MODELS.md)

## License

Private use.
