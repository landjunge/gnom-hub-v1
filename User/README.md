# User/ — personal unit (sync yourself, never git-push secrets)

| File | Purpose |
|------|---------|
| `Key.txt` | API keys (source of truth). Copy from `Key.txt.example`. |
| `user.db` | Personal SQLite: WARM facts, HOT session, Flex memory. |

Gnom-Hub loads keys from `User/Key.txt` (fallback: root `Key.txt`) and stores memory in `User/user.db`.

Override path: `GNOM_USER_DB=/path/to/user.db`

Do not commit `Key.txt` or `user.db`.
