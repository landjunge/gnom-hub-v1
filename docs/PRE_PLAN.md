# Gnom-Hub v1 – Pre-Plan (Stand: 05.08.2026)

Vollständige Zusammenfassung aus dem gesamten Brainstorming.
Nichts Wichtiges soll verloren gehen.

---

## 1. Grundidee

Ein lokales, portables Multi-Agenten-System mit klarem Ablauf:

**Erst freies Brainstorming → dann automatische Ausführung**

Das System soll vom USB-Stick laufen können und sowohl schlank lokal als auch mit Cloud-LLMs arbeiten.

Schlankheits-Prinzip: **Kein Overengineering. So schlank wie möglich, so viel wie nötig (YAGNI + KISS).**

Desktop/Laptop only – keine Mobile-Responsive-Anforderungen.

---

## 2. Kern-Pipeline (fester Ablauf)

```
User-Chat / Auftrag
        │
        ▼
   Brainstorm (frei, ungestört, optional abschaltbar)
        │
        ▼
   Destillation (was wirklich gewollt ist)
        │  ggf. Rückfragen
        ▼
   Coordinator
        │
        ├── Worker 1
        ├── Worker 2
        └── …
        │
        ▼
   Ergebnis → Box 3 + Memory
```

### Regeln der Pipeline

- Der Chat ist der durchgängige Faden von der ersten Idee bis zum Ergebnis
- Brainstorm darf frei und chaotisch sein
- Danach wird klar destilliert
- Coordinator und Worker bekommen nur den sauberen, destillierten Kontext + das Nötige aus dem Memory
- Memory hält den roten Faden und speichert Wichtiges
- Nichts Wichtiges geht verloren, kein ungefiltertes Chaos wird weitergereicht

### Interactive Distillation (Rückfragen)

Wenn bei der Destillation etwas unklar ist (z. B. „Dark Mode?“):

| Kanal | Wie wird gefragt? |
|-------|-------------------|
| **Desktop-UI** | In **Box 1** mit Buttons: Ja / Nein / Egal / Später |
| **Telegram** | Als klarer Text + erwartete Antwort (Ja / Nein / Egal) |

- Box 1 nur, wenn die Desktop-UI aktiv ist
- Über Telegram (und andere Kanäle ohne UI) immer als Text
- Nach der Antwort wird die Anforderung ergänzt und die Pipeline läuft weiter
- Chat bleibt frei und wird nicht mit Rückfragen zugespamt

Beispiel „Bau eine Webseite“:
1. User schreibt Auftrag im Chat
2. Brainstorm sammelt Ideen (Stil, Abschnitte, Farben …)
3. Destillation erzeugt klare Anforderungen
4. Bei Unklarheiten → kurze Rückfrage in Box 1 (oder Telegram)
5. Coordinator verteilt Teilaufgaben an aktive Worker
6. Ergebnisse erscheinen in Box 3 und können weiterverfeinert werden

---

## 3. Architektur

### Feste Agenten (4) – kurze Namen + feste Farben

| Kurzer Name    | Rolle                  | Rahmenfarbe | Abschaltbar |
|----------------|------------------------|-------------|-------------|
| **Brainstorm** | Brainstorm-Moderator   | Rot         | Ja          |
| **Memory**     | Memory-Agent           | Blau        | **Nein**    |
| **Flex**       | Flexibler System-Slot  | Gelb        | Ja          |
| **Coordinator**| Coordinator            | Grün        | Ja          |

**Flex** (früher Security):
- Standard-Preset: Security
- Weitere Presets möglich: Researcher, Reviewer, Neutral, Planner usw.
- Kann per Preset die Rolle wechseln

### Dynamische Worker (bis zu 4)

| Name     | Rahmenfarbe | Abschaltbar |
|----------|-------------|-------------|
| Worker 1 | Orange      | Ja          |
| Worker 2 | Lila        | Ja          |
| Worker 3 | Türkis      | Ja          |
| Worker 4 | Grau/Rosa   | Ja          |

- Werden vom Coordinator bei Bedarf erzeugt
- Presets speicherbar
- Coordinator startet nie mehr Worker als aktuell aktiv sind

### Doppelklick-Toggle
- Doppelklick auf Agentenkarte → Agent ein-/ausschalten
- Memory ist **nicht** abschaltbar
- Ausgeschaltete Agenten: ausgegraut, keine Tokens, werden übersprungen

### Besondere Modi
- **God-Mode**: Volle Rechnerrechte (bewusst aktivierbar)
- Normal-Modus mit sinnvollen Grenzen

---

## 4. Gedächtnis

### Kurzzeitgedächtnis (symbolisch)
- **Mermaid Canvas** + Context-Offload mit `node_id`

### Langzeitgedächtnis (HOT / WARM / COLD)

| Zone    | Inhalt                           | Persistenz                |
|---------|----------------------------------|---------------------------|
| **HOT** | Aktuelle Session, Mermaid-Canvas | JSON + `.mmd`             |
| **WARM**| Fakten, Skills, Summaries, Projekte | JSONL / SQLite + Markdown |
| **COLD**| Alte Sessions, Roh-Logs, Archiv  | Dateien + Index           |

- Atomic Writes, relative Pfade (USB-fähig)
- Memory-Agent steuert Promotion

### Optionale Vektor-Schicht (Plugin)
- Standard: `null`
- Später: LanceDB oder sqlite-vec + Hybrid Ranking (RRF)

---

## 5. LLM- und Key-Management

- Free-Modelle nur bevorzugt, wenn der User das aktiv will
- Budget-Schutz gegen teure Modelle
- Jeder Agent kann eigenes Modell + eigenen Key haben
- Keys aus `Key.txt` (Desktop) → private `.env`
- Erster Test-Modell: **DeepSeek**
- Capability-Tags pro Modell
- Nur **ein globaler Speicher-Button**

---

## 6. Benutzeroberfläche (Desktop-only, 13″ optimiert)

### Agenten-Karten (oben)
- 8 Karten horizontal
- Größe: **140 × 100 px**
- Abstand: **5 px**
- Inhalt: Tokenverbrauch, aktuelle LLM, Online/Offline, TTS-Checkbox
- 1-Pixel-Rahmen (pulsiert bei Aktivität)
- Feste Rahmenfarbe pro Agent
- Doppelklick = Toggle (außer Memory)

### Drei Boxen
- Größe: **380 × 380 px** (fest)
- Abstand: **5 px**
- 1-Pixel-Rahmen (Farbe des aktiven Agenten)

**Box 1 – Arounder (zentrale Erklärungs- und Entscheidungsfläche)**
- Mouse-over auf alles → reiche Erklärung (Titel + How-to + Beispiel)
- Bei Destillations-Rückfragen: Ja / Nein / Egal / Später-Buttons
- UI selbst bleibt Basic English
- Box-1-Inhalte sind mehrsprachig
- Jedes neue Element muss einen Tooltip-Eintrag haben

**Box 2 – Brainstorm**
- Destillierte Gedanken + Zusammenfassung (persistent)

**Box 3 – Worker-Ergebnisse**
- Live-Preview

### Chatfenster
- ca. 150 px hoch, volle Breite
- Spracheingabe

### Globale Buttons
- System, Hilfe, **ein globaler Speicher-Button**

---

## 7. Zugriff von außen

### LAN-Zugriff (v1-fähig)
- UI läuft als lokale Web-App
- Im selben WLAN vom Handy/Browser erreichbar (z. B. `http://192.168.x.x:8080`)
- Kein optimiertes Mobile-Layout – nur grundlegende Nutzbarkeit

### Telegram-Bot (optionalals Modul)
- Basis-Befehle: `/status`, `/disable`, `/do`, `/last`, `/reset temp` usw.
- Rückfragen der Destillation als Text (Ja / Nein / Egal)
- Bot sendet Events an den EventBus
- Nicht Teil des Kerns – optional aktivierbar

---

## 8. Workspace-Konzept

Zwei Workspaces (temporär + permanent) mit Preview-Kästchen und Übertragen-Funktion.

---

## 9. Computer-Use / UI-Automation

Modulares Paket (Capture, Vision+Teaching, OCR, Action, Workflow) – Phase 5.

---

## 10. Installation & Betrieb

Einfache Installation, USB-Erkennung, Key.txt → .env, Update + Backup.

---

## 11. Weitere Features

- TTS, Spracheingabe, MCP, Plugin-System, Skills, God-Mode
- Ein-Klick „Sauberer Zustand“
- Mehrsprachigkeit nur für Box-1-Inhalte (UI = English)
- Accessibility-Fokus

---

## 12. Technische Prinzipien

- YAGNI + KISS
- EventBus + Facade + schmale Interfaces
- Atomic Writes
- Checkpointing / Resume
- Light Tracing

---

## 13. Modul-Struktur

Core/EventBus, AgentManager, MemoryModule, BrainstormModule, WorkerModule, UI Module, TTS, Reset, Plugin/MCP, Workspace, Computer-Use, Install/Update/Backup, LLM-Manager, TooltipService, TelegramBot (optional)

---

## 14. Umsetzungs-Reihenfolge

**Phase 0** – Fundament  
**Phase 1** – Kern-UI (Karten 140×100, Boxen 380×380, 5 px Abstände)  
**Phase 2** – Agenten + Toggle + Flex-Presets + LLM-Manager + Pipeline + Interactive Distillation  
**Phase 3** – Memory (HOT + Mermaid) + Workspace  
**Phase 4** – Dynamik + Qualität  
**Phase 5** – Erweiterungen (Plugins, Computer-Use, Vector, Telegram …)

---

**Ende des Pre-Plans**  
Stand: 05.08.2026 – Interactive Distillation (Box 1 Buttons / Telegram Text) ergänzt.
