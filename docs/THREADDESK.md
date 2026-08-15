# Gnom-Hub v1 ← ThreadDesk

Gnom liest das letzte lokale ThreadDesk-Paket. Es wird **nicht** gesendet und **nicht** ausgeführt.

```bash
# in ThreadDesk
td gnom                 # schreibt ~/.threaddesk/gnom-chat.json
```

Im Desk: Knopf **TD** — füllt die Chat-Zeile. Du drückst weiterhin **Send** oder **Execute**.

```http
GET /api/threaddesk
```

Liest nur:

- `~/.threaddesk/gnom-chat.json` (`{"text": "…"}`)
- sonst `gnom.json`
- sonst `handoff.json`

Override für Tests: `THREADDESK_ROOT`. Keine fremden Pfade. Kein POST an `/api/chat`.

ThreadDesk kennt keine Provider. Cloud-Calls laufen erst, wenn du in Gnom **Send/Execute** drückst — und dann über **Tollgate**. Siehe [TOLLGATE.md](TOLLGATE.md).
