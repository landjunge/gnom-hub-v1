# Builder-Polling für Teilaufgaben

Kleines Polling-Skript, das offene Issues mit Label `teilaufgabe` findet und den Builder genau einmal anstupst. Kein Webhook-Server.

## Start

Token braucht `repo` / Issues-Rechte.

```bash
export GITHUB_TOKEN=ghp_xxx          # oder GNOM_GITHUB_TOKEN
export GNOM_GITHUB_REPO=landjunge/gnom-hub-v1   # optional, Default ist dieses Repo

# einmalig (CI / Test)
python scripts/poll_teilaufgaben.py --once

# Dauerbetrieb, Intervall 30–60 Sekunden (Default 45)
python scripts/poll_teilaufgaben.py --interval 45
```

Nur ansehen, nichts schreiben:

```bash
python scripts/poll_teilaufgaben.py --once --dry-run
```

Optional den echten Builder-Prozess starten, statt nur eine Datei zu legen:

```bash
export GNOM_BUILDER_CMD='your-builder-launcher'
python scripts/poll_teilaufgaben.py
```

Das Kommando bekommt `ISSUE_NUMBER` in der Umgebung und den Prompt aus `agents/builder.md` plus Issue-Hinweis auf stdin.

Ohne `GNOM_BUILDER_CMD` schreibt das Skript den Prompt nach `data/builder-launch/{nummer}.txt` (liegt unter `data/`, wird nicht committed).

## Stop

Prozess beenden (`Ctrl+C` oder `kill <pid>`). Es gibt keinen Dienst und kein Docker.

State-Datei: `data/agent_poll_state.json`. Löschen setzt die Doppelstart-Sperre lokal zurück. Zusätzliche Sperren:

- Label `in-bearbeitung` auf der Issue
- Issue-Kommentar mit Marker `<!-- gnom-builder-poll:started -->`

## Verhalten

1. Fragt offene Issues mit Label `teilaufgabe` ab.
2. Überspringt Issues, die schon gestartet / in Bearbeitung sind.
3. Startet höchstens einen Builder-Lauf pro Issue.
4. Loggt `Timestamp Aktion issue=#N Detail` auf stdout.

Nach dem Merge sollen offene Teilaufgaben wie #106 und #107 ohne manuelles Anstupsen weiterlaufen, sobald dieses Skript läuft.
