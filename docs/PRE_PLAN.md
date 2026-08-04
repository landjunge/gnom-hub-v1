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

## 2. Architektur

### Feste Agenten (4) – kurze Namen + feste Farben

| Kurzer Name   | Rolle                  | Rahmenfarbe | Abschaltbar |
|---------------|------------------------|-------------|-------------|
| **Brainstorm**| Brainstorm-Moderator   | Rot         | Ja          |
| **Memory**    | Memory-Agent           | Blau        | **Nein**    |
| **Flex**      | Flexibler System-Slot  | Gelb        | Ja          |
| **Coordinator**| Coordinator           | Grün        | Ja          |

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
- Können als Presets gespeichert und wiederverwendet werden
- Status (active/disabled) wird live über EventBus bekannt gegeben
- Coordinator startet nie mehr Worker als aktuell aktiv sind

### Doppelklick-Toggle
- Doppelklick auf Agentenkarte → Agent ein-/ausschalten
- Memory ist **nicht** abschaltbar
- Ausgeschaltete Agenten: ausgegraut, keine Tokens, werden übersprungen

### Besondere Modi
- **God-Mode**: Volle Rechnerrechte (bewusst aktivierbar)
- Normal-Modus mit sinnvollen Grenzen

---

## 3. Gedächtnis

### Kurzzeitgedächtnis (symbolisch)
- **Mermaid Canvas** + Context-Offload mit `node_id`
- Schwere Inhalte werden ausgelagert
- Agent sieht nur die kompakte Mermaid-Landkarte

### Langzeitgedächtnis (HOT / WARM / COLD)

| Zone   | Inhalt                              | Persistenz                     |
|--------|-------------------------------------|--------------------------------|
| **HOT**| Aktuelle Session, Mermaid-Canvas    | JSON + `.mmd`                  |
| **WARM**| Fakten, Skills, Summaries, Projekte | JSONL / SQLite + Markdown      |
| **COLD**| Alte Sessions, Roh-Logs, Archiv     | Dateien + Index                |

- Atomic Writes, relative Pfade (USB-fähig)
- Memory-Agent steuert Promotion

### Optionale Vektor-Schicht (Plugin)
- Standard: `null`
- Später: LanceDB oder sqlite-vec + Hybrid Ranking (RRF)

---

## 4. LLM- und Key-Management

- Free-Modelle nur bevorzugt, wenn der User das aktiv will
- Budget-Schutz gegen teure Modelle
- Jeder Agent kann eigenes Modell + eigenen Key haben
- Keys aus `Key.txt` (Desktop) → private `.env`
- Erster Test-Modell: **DeepSeek**
- Capability-Tags pro Modell

---

## 5. Benutzeroberfläche (Desktop-only, 13″ optimiert)

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

**Box 1 – Arounder (zentrale Erklärungsfläche)**
- Mouse-over auf alles (Agent, Button, Modul, Regler, Workflow) → reiche Erklärung
- Aufbau: Titel + Kurzbeschreibung + How-to-use + Beispiel
- Wechselt Sprache (DE/EN/…), UI selbst bleibt Basic English
- Jedes neue Element **muss** einen Tooltip-Eintrag haben

**Box 2 – Brainstorm**
- Destillierte Gedanken + Zusammenfassung (persistent)

**Box 3 – Worker-Ergebnisse**
- Live-Preview

### Chatfenster
- ca. 150 px hoch, volle Breite
- Spracheingabe

### Globale Buttons
- System, Hilfe, **ein globaler Speicher-Button**

### Layout-Prinzip
- Feste Pixelmaße (kein Mobile-Responsive)
- Optimiert für 13-Zoll und größer
- Gesamtbreite Agentenkarten ≈ Gesamtbreite Boxen (≈ 1150–1155 px)

---

## 6. Workspace-Konzept

Zwei Workspaces (temporär + permanent) mit Preview-Kästchen und Übertragen-Funktion.

---

## 7. Computer-Use / UI-Automation

Modulares Paket (Capture, Vision+Teaching, OCR, Action, Workflow) – Phase 5.

---

## 8. Installation & Betrieb

Einfache Installation, USB-Erkennung, Key.txt → .env, Update + Backup.

---

## 9. Weitere Features

- TTS, Spracheingabe, MCP, Plugin-System, Skills, God-Mode
- Ein-Klick „Sauberer Zustand“
- Mehrsprachigkeit nur für Box-1-Inhalte (UI = English)
- Accessibility-Fokus

---

## 10. Technische Prinzipien

- YAGNI + KISS
- EventBus + Facade + schmale Interfaces
- Atomic Writes
- Checkpointing / Resume
- Light Tracing

---

## 11. Modul-Struktur

Core/EventBus, AgentManager, MemoryModule, BrainstormModule, WorkerModule, UI Module, TTS, Reset, Plugin/MCP, Workspace, Computer-Use, Install/Update/Backup, LLM-Manager, TooltipService

---

## 12. Umsetzungs-Reihenfolge

**Phase 0** – Fundament  
**Phase 1** – Kern-UI (Karten 140×100, Boxen 380×380, 5 px Abstände)  
**Phase 2** – Agenten + Toggle + Flex-Presets + LLM-Manager  
**Phase 3** – Memory (HOT + Mermaid) + Workspace  
**Phase 4** – Dynamik + Qualität  
**Phase 5** – Erweiterungen (Plugins, Computer-Use, Vector …)

---

**Ende des Pre-Plans**  
Stand: 05.08.2026
