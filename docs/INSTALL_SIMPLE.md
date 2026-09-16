# Installation — Terminal-Schnellinstallation

Kein Ein-Klick. Git und Python 3.10+.

## Desk

```bash
./scripts/install.sh
./scripts/start.sh
```

Browser: `http://127.0.0.1:8080/`. Key in `WS-gnom-hub-v1/User/Key.txt`.
Senden = reden. Arbeit starten = Arbeiter.

---

## Neural search (optional — only if you want better vectors)

**One command:**

```bash
./scripts/install_embeddings.sh
```

**Or one click in the desk:**  
Vector badge → **Install neural** → choose **fastembed** → **Apply + reindex**

**Or with main install:**

```bash
./scripts/install.sh --with-embeddings
```

Without this step everything still works with **bow** (no extra packages).

---

## That’s it

| Goal | Command |
|------|---------|
| Run Gnom | `./scripts/install.sh` then `./scripts/start.sh` |
| Better semantic search | `./scripts/install_embeddings.sh` once |
| God-Mode extras | `pip install -e ".[computer]"` (optional, advanced) |

No Docker. No second app. USB-friendly.
