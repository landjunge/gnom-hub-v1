# Gnom-Hub – Pre-Plan (Stand: 05.08.2026)

Vollständige Zusammenfassung aus dem gesamten Brainstorming.
Nichts Wichtiges soll verloren gehen.

---

## 1. Grundidee

Ein lokales, portables Multi-Agenten-System mit klarem Ablauf:

**Erst freies Brainstorming → dann automatische Ausführung**

- Läuft vom USB-Stick
- Schlank lokal + Cloud-LLMs möglich
- **Desktop/Laptop only** (kein Mobile-Responsive nötig)
- Prinzip: So schlank wie möglich, so viel wie nötig (YAGNI + KISS)

---

## 2. Architektur

### Feste Agenten (4) – kurze Namen + feste Farben

| Kurzer Name     | Rolle                         | Rahmenfarbe |
|-----------------|-------------------------------|-------------|
| **Brainstorm**  | Brainstorm-Moderator          | Rot         |
| **Memory**      | Memory-Agent (immer aktiv)    | Blau        |
| **Flex**        | Flexibler System-Slot         | Gelb        |
| **Coordinator** | Coordinator                   | Grün        |

**Flex-Slot:**
- Standard-Preset: Security
- Weitere Presets möglich: Neutral, Researcher, Reviewer, Planner …
- Kann bei Bedarf umfunktioniert werden (kein fester Flaschenhals)

### Dynamische Worker (bis zu 4)

| Name     | Rahmenfarbe |
|----------|-------------|
| Worker 1 | Orange      |
| Worker 2 | Lila        |
| Worker 3 | Türkis      |
| Worker 4 | Grau/Rosa   |

- Werden vom Coordinator bei Bedarf erzeugt
- Presets speicherbar und wiederverwendbar

### Agenten ein-/ausschalten (Doppelklick)

| Agent        | Abschaltbar? | Begründung                    |
|--------------|--------------|-------------------------------|
| Brainstorm   | Ja           | Optional                      |
| Memory       | **Nein**     | Wird immer gebraucht          |
| Flex         | Ja           | Kann deaktiviert/umfunktioniert werden |
| Coordinator  | Ja           | Optional                      |
| Worker 1–4   | Ja           | Dynamisch                     |

- Doppelklick auf Karte → an/aus
- Aus = abgedunkelt + Status „DEAKTIVIERT“, keine Tokens, keine Events
- Coordinator erkennt live, welche Agenten/Worker aktiv sind und startet nie mehr, als verfügbar sind

---

## 3. Gedächtnis

### Kurzzeitgedächtnis
- Mermaid Canvas + Context-Offload mit `node_id`

### Langzeitgedächtnis (HOT / WARM / COLD)
- HOT: aktuelle Session + Mermaid
- WARM: Fakten, Skills, Summaries, Projekte
- COLD: Archiv

### Persistenz
```
memory/
├── hot/     session.json, mermaid_canvas.mmd, working_context.md
├── warm/    facts.jsonl, skills/, summaries/, projects/
└── cold/    sessions/, raw_logs/, archive_index.json
```

- Atomic Writes, relative Pfade (USB-fähig)
- Optional später: Vector-Plugin + Hybrid-Ranking (RRF)

---

## 4. LLM- und Key-Management

- Free-Modelle nur bevorzugen, wenn User es aktiv will
- Budget-Schutz (kein versehentliches teures Modell)
- Lokale Modelle nicht erzwungen
- Jeder Agent kann eigenes Modell + eigenen Key haben
- Keys: `Key.txt` (Desktop) → private `.env`
- Nur **ein globaler Speicher-Button**
- DeepSeek als erstes Test-Modell

---

## 5. Benutzeroberfläche (Desktop, 13″ optimiert)

### Feste Maße

| Element              | Größe        | Abstand |
|----------------------|--------------|---------|
| Agenten-Karten (8×)  | 140 × 100 px | 5 px    |
| Boxen (3×)           | 380 × 380 px | 5 px    |
| Chatfenster          | volle Breite × ca. 150 px | – |

Gesamtbreite Karten/Boxen ≈ 1150–1155 px → passt auf 13″ (1280 px).

### Agenten-Visitenkarten
- Tokenverbrauch, aktuelle LLM, Online/Offline
- TTS-Checkbox
- 1-Pixel-Rahmen in fester Agentenfarbe (pulsiert bei Aktivität)
- Doppelklick = ein-/ausschalten (außer Memory)

### Drei Boxen
- 1-Pixel-Rahmen, Farbe wechselt zum aktiven Agenten
- Pre-Rendering

**Box 1 – Arounder (zentrale Hilfe)**
- Bei Hover über alles (Agent, Button, Modul, Regler, Workflow):
  - Titel
  - Kurze Erklärung
  - Wie benutzen
  - Beispiel
- Zeigt dynamisch das aktuelle Preset des Agenten
- UI-Sprache bleibt **Basic English**
- Inhalte von Box 1 sind mehrsprachig (DE/EN/…)

**Box 2 – Brainstorm**  
Destillierte Gedanken + Zusammenfassung (persistent)

**Box 3 – Worker-Ergebnisse**  
Live-Preview

### Weitere UI
- Header: System · Help · **ein globaler Save-Button**
- Agent-Tuning-Seite (Klick auf Agent): Prompt, Modell, 5 Regler, Live-Erklärung in Box 1

---

## 6. Workspace

- Temporärer Workspace (Sammelplatz + Preview + Übertragen)
- Permanenter Workspace (nur bewusst übernommene Ergebnisse)

---

## 7. Computer-Use (später)

Capture · Vision+Teaching · OCR · Action · Workflow-Recording → Skills

---

## 8. Installation & Betrieb

- Einfache Installation, USB-Erkennung
- Key.txt → .env
- Update + Backup (später)

---

## 9. Weitere Features (Zielbild)

- TTS, Spracheingabe, MCP, Plugins, Skills
- God-Mode, Sauberer Zustand, Accessibility
- Self-Explaining Videos, Workflows im Memory

---

## 10. Technische Prinzipien

- EventBus / Pub-Sub
- Facade, Composition over Inheritance
- Checkpointing, Light Tracing, Qualitätsprüfung
- Kontext-Kompression

---

## 11. Modul-Struktur

Core/EventBus · AgentManager · MemoryModule · BrainstormModule · WorkerModule · UI · TTS · TooltipService · LLM-Manager · Workspace · Plugin/MCP · Computer-Use · Install/Update/Backup

---

## 12. Phasen

**Phase 0** – Fundament (Struktur, EventBus, Keys, USB)  
**Phase 1** – Kern-UI (Karten 140×100, Boxen 380×380, Chat, Doppelklick, Box-1-Tooltips)  
**Phase 2** – Agenten-Grundgerüst (4 feste + Flex-Presets, LLM-Manager, TTS)  
**Phase 3** – Memory HOT + einfaches Mermaid + Workspace-Basis  
**Phase 4** – Dynamische Worker + Qualität  
**Phase 5** – Erweiterungen (Computer-Use, Vector, Plugins, …)

---

## 13. Offene Punkte

- Konkrete lokale LLM-Empfehlungen für 4-Kern
- Aggressivität der Qualitätsprüfung
- Spätere Remote-Zugriff-Idee (Handy/iPad) – aktuell kein Ziel

---

**Ende Pre-Plan**  
Stand: 05.08.2026
