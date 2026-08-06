# User/ — portable personal unit (sync & update this folder)

Lives **next to the hub code** in the workspace — on SSD **or USB stick**.
If you install/run Gnom on a USB volume, `User/` is created **on that USB**.

| File | Who updates | Purpose |
|------|-------------|---------|
| `Key.txt` | you | API keys (source of truth) |
| `user.db` | hub (always) | WARM / HOT / Flex memory |

## Rules

1. **Live store = only this folder.** Not `~/.local/share/…`.
2. **Sync unit = whole `User/`** (Key + DB) together with the workspace/USB.
3. **Never git-push** `Key.txt` or `user.db`.
4. Fresh install → creates empty/seeded `User/` here. Old home DB is copied **once** only if `user.db` is missing.

```text
/Volumes/MyUSB/gnom-hub-v1/     ← or any local path
  User/
    Key.txt
    user.db                     ← hub keeps this updated
  src/ …
```
