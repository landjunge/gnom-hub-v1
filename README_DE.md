# Gnom-Hub-V1 — Deutsch

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/design/icons/dark/Gnom-Hub-V1-dark-128.png">
  <img src="assets/design/icons/light/Gnom-Hub-V1-light-128.png" alt="Gnom-Hub-V1" width="96" height="96">
</picture>

Gnom-Hub-V1 ist ein eigenständiger lokaler Multi-Agenten-Arbeitsplatz.
Im normalen Ablauf bedeutet **Senden** Gespräch; **Arbeit starten** startet
ausdrücklich die bestehende Koordinator-/Worker-Pipeline. Direkte Aufträge
KiraBridge → Codex benötigen Gnom nicht.
[English](README_EN.md) · [Vollständige Übersicht](README.md).

## Installieren und starten

Git und Python 3.10 oder neuer sind erforderlich. Der bestehende Terminalweg
für macOS und Linux ist:

```sh
curl -fsSL https://raw.githubusercontent.com/landjunge/gnom-hub-v1/main/scripts/get.sh | sh
```

Bei vorhandenem Checkout: `./scripts/install.sh`, danach
`./scripts/start.sh`. Oberfläche: `http://127.0.0.1:8080/` oder `/v4`.
Persönliche Daten liegen im benachbarten `WS-gnom-hub-v1` oder einem ausdrücklich
gesetzten `GNOM_WS`. Zugangsdaten und persönliche Datenbanken gehören nicht in Git.
Eine neue native App oder Abnahme auf einem fremden Gerät ist damit nicht belegt.

## Anbieter und Betriebsprofile

Standard ist der eigenständige `standalone`-Betrieb. Cloud-Aufrufe verwenden
bei `GNOM_TOLLGATE_LLM=1` TollGate; fehlt es oder verweigert es den Aufruf,
folgt kein direkter bezahlter Ersatzaufruf. Ausdrückliche `ollama/*`-Auswahl
bleibt lokal. Anbieterzugänge werden über den vorhandenen Key-/Systemweg
eingerichtet, niemals durch Chattexte.

Der Betreiber kann den bestehenden Legacy-Ausweg ausdrücklich mit
`GNOM_TOLLGATE_LLM=0` wählen. Dieser Weg garantiert kein dauerhaftes
Gesamtauftragsbudget und keinen durchgängigen Stopp. Das Profil
`GNOM_EXECUTION_PROFILE=controlled` sperrt Modellstarts, solange verifizierte
Auftragsbindung, technisch begrenzter Provideradapter und geschützter Zugang
fehlen. Ein importierter Text oder Request-Schalter ersetzt diese Voraussetzungen nicht.

## Übergaben, Rückgaben und Stopps

Der lokale Adapter speichert begrenzte Zuordnungsdaten im bestehenden SQLite-Store.
Import startet keinen Auftrag. Für den aktiven Einsatz sind die feste
Betreiberzuordnung, die tatsächlichen ausgestellten Aufträge und beobachtete
eigene Jobquittungen erforderlich. Ungeklärte Läufe bleiben unbekannt und
starten nach Wiederverbindung nicht automatisch neu.

Vorbereitete Rückgaben bleiben ungeprüft und ungesendet. ThreadDesk-Import und
ausdrückliche Bewertung sind weitere Schritte; Keep/Peek ist davon getrennt.
Ein Stopp unterscheidet TollGates dauerhafte Sperre, Gnom-Abbruchanfrage und
tatsächlich beobachtetes Ende. Bereits ausgelöste externe Wirkungen werden
dadurch nicht rückgängig gemacht. Geschützte Konten-/Browserarbeit ist über den
vorhandenen globalen Browser-/Debugweg nicht freigegeben.

## Updates und Grenzen

Quellversion: 3.10.1. Der vorhandene Updater prüft Metadaten; `updates.apply()`
meldet weiterhin `not_published`. Ein Tag ist keine neu installierte Version.
Vor einem tatsächlichen Versionswechsel sichern und den vorhandenen
Backup-/Wiederherstellungsweg verwenden.

Legacy und `/v4` sind getrennte Oberflächen; vollständige englische
UI-Abdeckung ist nicht behauptet. Der
[Arbeitsstände-Vertrag](docs/WORKER_STANDS.md) beschreibt ausdrücklich
konfigurierte Host-Endpunkte, getrennte Worker-Artefakte und beobachtete
Ausgangs-/Ergebnis-/Prüfcommits. Er führt keinen Merge aus und belegt keinen
installierten kontrollierten Team-/Providerweg.
[Integrationsnachweise und Voraussetzungen](docs/SEVEN-TOOLS-GNOM-20261018.md).
Es gilt die vorhandene [Lizenz](LICENSE).
