# Builder-Polling für Teilaufgaben

Kleines Polling-Skript, das offene Issues mit Label `teilaufgabe` findet und den Builder genau einmal anstupst. Kein Webhook-Server.

## Pflicht-Umgebung

Ohne `GNOM_BUILDER_CMD` startet nichts. Das Skript loggt `error missing-cmd` und speichert die Issue nicht als gestartet. Es legt auch keine Queue-Datei mehr.

```bash
export GITHUB_TOKEN=ghp_xxx          # oder GNOM_GITHUB_TOKEN
export GNOM_GITHUB_REPO=landjunge/gnom-hub-v1   # optional, Default ist dieses Repo
# konkretes ausführbares Kommando — wird mit shlex.split zerlegt, shell=False
export GNOM_BUILDER_CMD="/usr/bin/python3 /pfad/zum/builder-launcher.py"
```

Das Kind bekommt `ISSUE_NUMBER` in der Umgebung und den Prompt aus `agents/builder.md` plus Issue-Hinweis auf stdin.

## Start

```bash
# einmalig (CI / Test)
python scripts/poll_teilaufgaben.py --once

# Dauerbetrieb, Intervall 30–60 Sekunden (Default 45)
python scripts/poll_teilaufgaben.py --interval 45
```

Nur ansehen, nichts schreiben (kein Claim, kein Start):

```bash
python scripts/poll_teilaufgaben.py --once --dry-run
```

## Stop

Prozess beenden (`Ctrl+C` oder `kill <pid>`). Es gibt keinen Dienst und kein Docker.

State-Datei: `data/agent_poll_state.json`. Löschen setzt die lokale Doppelstart-Sperre zurück. Zusätzliche Sperren:

- Label `in-bearbeitung` auf der Issue
- Issue-Kommentar mit Marker `<!-- gnom-builder-poll:started -->` (ohne Prompt-Dump)

## Verhalten

1. Fragt offene Issues mit Label `teilaufgabe` ab.
2. Überspringt Issues, die schon gestartet / in Bearbeitung sind.
3. Pro Tick höchstens *eine* noch freie Teilaufgabe.
4. Claim zuerst (Marker-Kommentar + Label), danach Start.
5. Ohne `GNOM_BUILDER_CMD`: klare Fehlermeldung, kein Claim, kein State-Eintrag.
6. Loggt `Timestamp Aktion issue=#N Detail` auf stdout.

Nach dem Merge sollen offene Teilaufgaben wie #106 und #107 ohne manuelles Anstupsen weiterlaufen, sobald dieses Skript mit Token und `GNOM_BUILDER_CMD` läuft.
