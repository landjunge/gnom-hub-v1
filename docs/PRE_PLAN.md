# Gnom-Hub v1 – Pre-Plan (Stand: 05.08.2026)

Vollständige Zusammenfassung aus dem gesamten Brainstorming.
Nichts Wichtiges soll verloren gehen.

---

## 1. Grundidee

Ein lokales, portables Multi-Agenten-System mit klarem Ablauf:

**Erst freies Brainstorming → dann automatische Ausführung**

Das System soll vom USB-Stick laufen können und sowohl schlank lokal als auch mit Cloud-LLMs arbeiten.

Schlankheits-Prinzip: **Kein Overengineering. So schlank wie möglich, so viel wie nötig (YAGNI + KISS).**

---

## 2. Architektur

### Feste Agenten (4) – kurze Namen + feste Farben

| Kurzer Name   | Rolle                  | Rahmenfarbe |
|---------------|------------------------|-------------|
| **Brainstorm**| Brainstorm-Moderator   | Rot         |
| **Memory**    | Memory-Agent           | Blau        |
| **Security**  | Security-Guard         | Gelb        |
| **Coordinator**| Coordinator           | Grün        |

### Dynamische Worker (bis zu 4)

| Name     | Rahmenfarbe |
|----------|-------------|
| Worker 1 | Orange      |
| Worker 2 | Lila        |
| Worker 3 | Türkis      |
| Worker 4 | Grau/Rosa   |

- Werden vom Coordinator bei Bedarf erzeugt
- Können als Presets gespeichert und wiederverwendet werden
- Haben Skills und können bei Bedarf Tools/Plugins nachladen

### Besondere Modi
- **God-Mode**: Volle Rechnerrechte (bewusst aktivierbar, inkl. Kernel-Änderungen möglich)
- Normal-Modus mit sinnvollen Grenzen

---

## 3. Gedächtnis

### Kurzzeitgedächtnis (symbolisch)
- **Mermaid Canvas** + Context-Offload mit `node_id`
- Schwere Inhalte (Tool-Logs, Captures etc.) werden ausgelagert
- Agent sieht nur die kompakte Mermaid-Landkarte
- Bei Bedarf: Drill-down über `node_id`

### Langzeitgedächtnis (HOT / WARM / COLD)

| Zone   | Inhalt                              | Persistenz                     |
|--------|-------------------------------------|--------------------------------|
| **HOT**| Aktuelle Session, Mermaid-Canvas, offene Aufgaben | JSON + `.mmd` (schnell)       |
| **WARM**| Fakten, Skills, Zusammenfassungen, Projekte | JSONL / SQLite + Markdown     |
| **COLD**| Alte Sessions, Roh-Logs, Archiv     | Dateien + Index                |

### Persistenz-Struktur
```
memory/
├── hot/
│   ├── session.json
│   ├── mermaid_canvas.mmd
│   └── working_context.md
├── warm/
│   ├── facts.jsonl
│   ├── skills/
│   ├── summaries/
│   └── projects/
└── cold/
    ├── sessions/
    ├── raw_logs/
    └── archive_index.json
```

- Atomic Writes
- Append-only wo sinnvoll
- Alles relative Pfade (USB-fähig)
- Memory-Agent steuert Promotion (HOT → WARM → COLD)

### Optionale Vektor-Schicht (Plugin)
- Standard: `null` (aus)
- Später aktivierbar: LanceDB oder sqlite-vec
- Hybrid-Ranking (Keyword + Vektor) via Reciprocal Rank Fusion (RRF)
- Wird nur geladen, wenn konfiguriert

---

## 4. LLM- und Key-Management

### Prinzipien
- Free-Modelle werden **nur bevorzugt, wenn der User das aktiv will**
- Kein automatisches teures Modell (Budget-Schutz)
- Lokale Modelle werden nicht erzwungen (Wartezeit)
- Jeder Agent kann eigenes Modell + eigenen Key haben
- Keys aus `Key.txt` (Desktop) → private `.env`

### Unterstützte Free-Quellen (Beispiele)
- OpenRouter (`:free`)
- OpenCode Zen
- Groq
- Google AI Studio (Gemini)
- NVIDIA NIM
- Cloudflare Workers AI
- Cerebras
- GitHub Models
- Lokale Modelle (Ollama)

### Capability-Tags
Jedes Modell kennt seine Fähigkeiten: `text`, `vision`, `image-generation`, `free`, `fast`, `reasoning` usw.

### Agent-Tuning-Seite
- Prompt (links, scrollbar)
- Modell-Auswahl + Capability-Tags + Key-Status
- 5 Schieberegler (Temperature, Top-P, Max Tokens, Frequency Penalty, Presence Penalty)
- Live-Erklärung der Regler in Box 1
- Schalter „Free-Modelle bevorzugen“
- **Nur ein globaler Speicher-Button**

---

## 5. Benutzeroberfläche

### Oben
- Header
- 8 Agenten als **Visitenkarten** (horizontal, feste Breite)
  - Tokenverbrauch, aktuelle LLM, Online/Offline
  - TTS-Checkbox
  - 1-Pixel-Rahmen (pulsiert bei Aktivität in Echtzeit)
  - Feste Rahmenfarbe pro Agent

### Drei Boxen (ca. 300–400 × 300–400 px)
- 1-Pixel-Rahmen
- Rahmenfarbe wechselt zur Farbe des Agenten, der die Box gerade benutzt
- Pre-Rendering

**Box 1 – Arounder** (interaktive Kontext-Box)
- Hover-Erklärungen
- Agenten-Vorschläge
- Live-Auswirkungen von Reglern
- Mehrsprachig (DE/EN, erweiterbar)

**Box 2 – Brainstorm**
- Destillierte Gedanken + Zusammenfassung
- Persistent

**Box 3 – Worker-Ergebnisse**
- Live-Preview

### Darunter
- **Chatfenster** (ca. 150 px hoch)
  - Spracheingabe (API oder Mac-System-Fallback)
  - Eigenes Modul

### Globale Buttons
- System
- Hilfe
- **Ein globaler Speicher-Button** (speichert alles)

---

## 6. Workspace-Konzept

**Zwei Workspaces:**

1. **Temporärer Workspace**
   - Sammelplatz für alles, was Agenten erzeugen
   - Preview als Kästchen (Seiten + Code)
   - Checkbox + Übertragen → permanent
   - Button „Temporären Workspace löschen“

2. **Permanenter Workspace**
   - Nur bewusst übernommene Ergebnisse

---

## 7. Computer-Use / UI-Automation (modulares Paket)

Kombinierbare Module:
- Capture (Screen, Fenster, Element, Scrolling, Seite, Video, Audio)
- Vision + Teaching (individuelle Konzepte lernen, nachfragen)
- OCR
- Action (Maus + Tastatur)
- Workflow / Recording → speicherbare Skills

Ziel: Agenten lernen Programme und Formulare zu bedienen und speichern die Abläufe.

---

## 8. Installation & Betrieb

- Wirklich einfache Installation
- Erkennt OS + USB-Stick
- Vorschläge für lokales LLM (Schlank / Größer / Empfohlen)
- Update- + Backup-System
- Keys: `Key.txt` auf Desktop → private `.env`

---

## 9. Weitere wichtige Features

- TTS von Anfang an
- Spracheingabe
- MCP-Unterstützung
- Plugin-System (saubere Interfaces)
- Skills + Tool-Nachladen
- Internet-Surfen
- God-Mode (volle Kontrolle)
- Ein-Klick „Sauberer Zustand“
- Mehrsprachigkeit (DE/EN, erweiterbar)
- Accessibility-Fokus (unterschiedliche menschliche Fähigkeiten)

---

## 10. Technische Verbesserungen

1. Starkes Checkpointing / Resume
2. Light Tracing (Nachvollziehbarkeit)
3. Automatische Qualitätsprüfung der Worker-Ergebnisse
4. Kontext-Kompression
5. Ein-Klick „Sauberer Zustand“
6. Hybrid-Ranking (Keyword + optional Vektor via RRF)
7. Design Patterns: Facade, EventBus/Pub-Sub, Composition over Inheritance

---

## 11. Modul-Struktur

- Core / EventBus
- AgentManager
- MemoryModule (HOT/WARM/COLD + Mermaid + optionale Vektor-Plugins)
- BrainstormModule
- WorkerModule
- UI Module (Karten + Boxen + Chat + Tuning)
- TTS Module
- ResetModule
- Plugin / MCP Module
- Workspace Module
- Computer-Use Module (Capture / Vision / OCR / Action / Workflow)
- Install / Update / Backup Module

Kommunikation über EventBus + schmale Interfaces.

---

## 12. Umsetzungs-Reihenfolge

**Phase 0 – Fundament**
- Modulare Projektstruktur
- EventBus + Schnittstellen
- Einfache Installation + USB-Erkennung
- Key.txt → .env

**Phase 1 – Kern-UI**
- Header + Agenten-Visitenkarten (Farben + kurze Namen)
- 3 Boxen + Pre-Rendering + farbige Rahmen
- Chatfenster
- Globaler Speicher-Button

**Phase 2 – Agenten-Grundgerüst**
- 4 feste Agenten
- Agent-Tuning-Seite + 5 Regler + LLM-Kontrolle
- TTS + Checkboxen
- God-Mode

**Phase 3 – Memory & Workspace**
- Mermaid Canvas + HOT/WARM/COLD Persistenz
- Temporärer + permanenter Workspace
- Kontext-Kompression
- Sauberer Zustand

**Phase 4 – Dynamik & Qualität**
- Dynamische Worker + Presets
- Checkpointing / Resume
- Light Tracing
- Qualitätsprüfung

**Phase 5 – Erweiterungen**
- Plugin-System + MCP
- Skills + Tool-Nachladen
- Computer-Use Module
- Optionale Vektor-Schicht + Hybrid-Ranking
- Update + Backup
- Mehrsprachigkeit

---

## 13. Offene Punkte (später)

- Konkrete lokale LLM-Empfehlungen für 4-Kern-Systeme
- Genaues Hover-Verhalten des Arounders bei komplexen Situationen
- Aggressivität der automatischen Qualitätsprüfung
- Genaue Accessibility-Profile

---

**Ende des Pre-Plans**  
Stand: 05.08.2026 – aktualisiert mit allen bisherigen Brainstorming-Entscheidungen.
